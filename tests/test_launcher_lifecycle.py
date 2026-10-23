"""Launcher failure paths through the CLI, without starting AutoHotkey."""

import ctypes
import json
import signal
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from acu import run as launcher
from acu.cli import main


@pytest.fixture
def native_process(tmp_path, monkeypatch):
    """Model process creation/exit at the Win32 boundary without starting a program."""
    script = tmp_path / "action.ahk"
    script.write_text("ExitApp\n", encoding="utf-8")
    for name in ("AutoHotkey64_UIA.exe", "AutoHotkey64.exe"):
        (tmp_path / name).touch()
    monkeypatch.setenv("ACU_AHK", str(tmp_path / "AutoHotkey64_UIA.exe"))
    validator = Mock(stdout=Mock(), returncode=0)
    validator.communicate.return_value = (b"", None)
    validator.poll.return_value = 0
    validator.wait.return_value = 0
    monkeypatch.setattr(subprocess, "Popen", Mock(return_value=validator))
    state = SimpleNamespace(alive=False, closed=False, closed_while_alive=False, interrupt_launch=False)

    def start(info_pointer):
        ctypes.cast(info_pointer, ctypes.POINTER(launcher.ShellExecuteInfo)).contents.hProcess = 12345
        state.alive = True
        if state.interrupt_launch:
            signal.raise_signal(signal.SIGINT)
        return 1

    def terminate(*_):
        state.alive = False
        return 1

    def exit_code(_, pointer):
        ctypes.cast(pointer, ctypes.POINTER(ctypes.c_ulong)).contents.value = 0
        return 1

    def close(_):
        state.closed_while_alive = state.alive
        state.closed = True
        return 1

    kernel = SimpleNamespace(
        WaitForSingleObject=Mock(side_effect=lambda *_: 258 if state.alive else 0),
        GetProcessId=Mock(return_value=424242), TerminateProcess=Mock(side_effect=terminate),
        GetExitCodeProcess=Mock(side_effect=exit_code), CloseHandle=Mock(side_effect=close),
    )
    shell = SimpleNamespace(ShellExecuteExW=Mock(side_effect=start))
    monkeypatch.setattr(ctypes, "WinDLL", lambda name, **_: shell if name == "shell32" else kernel)
    monkeypatch.setattr(ctypes.windll.user32, "EnumWindows", Mock(return_value=1))
    monkeypatch.setattr(launcher, "CLOSE_GRACE_SECONDS", 0)
    return script, state, kernel


def test_interrupt_during_process_creation_is_deferred_until_cleanup_is_registered(native_process):
    script, state, _ = native_process
    state.interrupt_launch = True
    previous = signal.getsignal(signal.SIGINT)
    try:
        result = launcher.run_script(script, 1)
    except KeyboardInterrupt:
        result = None

    assert not state.alive, "an interrupt during ShellExecute orphaned the process"
    assert state.closed and not state.closed_while_alive
    assert result is not None and result.exit_code == 130
    assert signal.getsignal(signal.SIGINT) == previous


def test_failed_shutdown_retains_ownership_until_exit_is_verified(native_process, acu_home):
    script, state, kernel = native_process
    failed_termination = False
    checks_after_failure = 0

    def refuse_termination(*_):
        nonlocal failed_termination
        failed_termination = True
        ctypes.set_last_error(5)
        return 0

    def observe_exit(*_):
        nonlocal checks_after_failure
        if failed_termination:
            checks_after_failure += 1
            if checks_after_failure >= 3:
                state.alive = False
        return 258 if state.alive else 0

    kernel.TerminateProcess.side_effect = refuse_termination
    kernel.WaitForSingleObject.side_effect = observe_exit
    with pytest.raises(OSError):
        launcher.run_script(script, 0.01)

    assert failed_termination
    assert not state.closed_while_alive, "failed shutdown released ownership of a live script"
    assert not state.alive and state.closed
    reports = list((acu_home / "crashes").glob("*.json"))
    assert reports
    assert any("retaining" in json.loads(report.read_text(encoding="utf-8"))["output"] for report in reports)


def test_validator_creation_interrupt_reaps_it_before_returning(tmp_path, monkeypatch, capsys):
    script = tmp_path / "action.ahk"
    script.write_text("ExitApp\n", encoding="utf-8")
    for name in ("AutoHotkey64_UIA.exe", "AutoHotkey64.exe"):
        (tmp_path / name).touch()
    monkeypatch.setenv("ACU_AHK", str(tmp_path / "AutoHotkey64_UIA.exe"))
    state = SimpleNamespace(alive=False, reaped=False)

    def kill():
        state.alive = False

    def wait():
        state.reaped = True
        return -9

    validator = Mock(stdout=Mock(), returncode=-9)
    validator.poll.side_effect = lambda: None if state.alive else -9
    validator.kill.side_effect = kill
    validator.wait.side_effect = wait

    def create(*_, **__):
        state.alive = True
        signal.raise_signal(signal.SIGINT)
        return validator

    monkeypatch.setattr(subprocess, "Popen", create)
    exit_code = main(["run", str(script), "--timeout", "1"])
    response = json.loads(capsys.readouterr().out)

    assert not state.alive and state.reaped, "interrupted validation left its process alive"
    assert exit_code == 130 and response["exit_code"] == 130
    assert "validation" in response["trailer"]


def test_validation_timeout_uses_the_run_budget_and_persists_output(tmp_path, monkeypatch, capsys):
    """A stalled validator must finish as a logged timeout, not a tool crash."""
    script = tmp_path / "action.ahk"
    script.write_text("ExitApp\n", encoding="utf-8")
    for name in ("AutoHotkey64_UIA.exe", "AutoHotkey64.exe"):
        (tmp_path / name).touch()
    monkeypatch.setenv("ACU_AHK", str(tmp_path / "AutoHotkey64_UIA.exe"))
    budgets = []

    def stalled_communication(**options):
        if "timeout" not in options:
            return b"validator output\n", None
        budgets.append(options["timeout"])
        raise subprocess.TimeoutExpired([], options["timeout"], output=b"validator output\n")

    validator = Mock(stdout=Mock(), returncode=-9)
    validator.communicate.side_effect = stalled_communication
    validator.poll.return_value = None
    validator.wait.return_value = -9
    monkeypatch.setattr(subprocess, "Popen", Mock(return_value=validator))
    exit_code = main(["run", str(script), "--timeout", "0.25"])
    response = json.loads(capsys.readouterr().out)

    assert budgets and budgets[0] is not None and 0 < budgets[0] <= 0.25
    assert exit_code == 124, response
    assert response["outcome"] == "timeout"
    assert "validation" in response["trailer"]
    assert "validator output" in response["output"]
    report = json.loads(Path(response["artifacts"]["crash_report"]).read_text(encoding="utf-8"))
    assert report["outcome"] == "timeout"
    assert report["output"] == response["output"]
