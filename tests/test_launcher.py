"""The launcher command line: python acu/run.py SCRIPT [--timeout SECONDS]."""

import ctypes
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from conftest import REPO, SCRIPTS, cursor, run_acu, run_cli, set_cursor, wait_until

pytestmark = pytest.mark.desktop


def log_lines(acu_home):
    return [json.loads(line) for line in (acu_home / "logs" / "runs.jsonl").read_text(encoding="utf-8").splitlines()]


def test_prints_script_output_and_exits_zero():
    result = run_acu("hello.ahk")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "hello from ahk 你好" in result.stdout


def test_scripts_run_with_ui_access_so_elevated_windows_are_reachable():
    result = run_acu("uiaccess.ahk")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "uiaccess=1" in result.stdout.splitlines()


def test_forwards_arguments_after_double_dash_to_the_script():
    result = run_acu("echo_args.ahk", "--timeout", "5", "--", "alpha", "beta gamma", "--max", "0")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "args=alpha|beta gamma|--max|0" in result.stdout.splitlines()


def test_returns_when_the_script_exits_even_if_a_program_it_launched_is_still_running():
    started = time.monotonic()
    result = run_acu("spawn_child.ahk", "--timeout", "10")
    elapsed = time.monotonic() - started

    assert result.returncode == 0, result.stdout + result.stderr
    assert "spawned" in result.stdout
    assert elapsed < 2, f"launcher took {elapsed:.1f}s, so it waited for the launched program instead of the script"


def test_runtime_error_is_printed_with_location_and_exits_nonzero():
    started = time.monotonic()
    result = run_acu("runtime_error.ahk", "--timeout", "3")
    elapsed = time.monotonic() - started

    assert result.returncode == 1, result.stdout + result.stderr
    assert "before" in result.stdout
    assert "after" not in result.stdout
    assert "Target window not found" in result.stdout
    assert "runtime_error.ahk:3" in result.stdout
    assert elapsed < 2.5, f"took {elapsed:.1f}s, which means a dialog blocked until the watchdog fired"


def test_call_to_missing_function_is_printed_and_exits_nonzero():
    started = time.monotonic()
    result = run_acu("undefined_function.ahk", "--timeout", "3")
    elapsed = time.monotonic() - started

    assert result.returncode == 1, result.stdout + result.stderr
    assert "NoSuchFunctionACU" in result.stdout
    assert "after" not in result.stdout
    assert elapsed < 2.5, f"took {elapsed:.1f}s, which means a dialog blocked until the watchdog fired"


def test_globals_named_like_prelude_locals_produce_no_warning():
    result = run_acu("globals_named_like_prelude_locals.ahk", "--timeout", "3")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "sum=6" in result.stdout.splitlines()
    assert "Warning" not in result.stdout, result.stdout


def test_syntax_error_is_printed_and_exits_nonzero():
    result = run_acu("syntax_error.ahk", "--timeout", "3")

    assert result.returncode not in (0, 124), result.stdout + result.stderr
    assert "syntax_error.ahk" in result.stdout
    assert "(2)" in result.stdout


def test_timeout_asks_script_to_exit_then_reports_124(acu_home):
    set_cursor(50, 50)
    started = time.monotonic()
    result = run_acu("hang.ahk", "--timeout", "1")
    elapsed = time.monotonic() - started
    landed = cursor()

    assert result.returncode == 124, result.stdout + result.stderr
    assert "hang: exit handler ran" in result.stdout
    assert landed == (300, 300), "timeout must leave the cursor where the script moved it"
    assert "hang: finished sleeping" not in result.stdout
    assert "[acu] timeout" in result.stdout
    assert elapsed < 5, f"launcher took {elapsed:.1f}s to enforce a 1s timeout"
    assert log_lines(acu_home)[0]["outcome"] == "timeout"
    assert len(list((acu_home / "crashes").glob("*.json"))) == 1


def test_every_run_appends_one_json_log_line(acu_home):
    run_acu("hello.ahk")
    run_acu("hello.ahk")

    lines = log_lines(acu_home)
    assert len(lines) == 2
    entry = lines[0]
    assert entry["outcome"] == "ok"
    assert entry["exit_code"] == 0
    assert entry["script"] == str(SCRIPTS / "hello.ahk")
    assert len(entry["sha256"]) == 64
    assert isinstance(entry["duration_ms"], int)
    assert "hello from ahk" not in json.dumps(entry), "script text must not be logged"


def test_failed_run_writes_a_crash_report_with_the_error(acu_home):
    run_acu("runtime_error.ahk", "--timeout", "3")

    reports = list((acu_home / "crashes").glob("*.json"))
    assert len(reports) == 1
    report = json.loads(reports[0].read_text(encoding="utf-8"))
    assert report["outcome"] == "error"
    assert report["exit_code"] == 1
    assert "Target window not found" in report["output"]
    assert "runtime_error.ahk:3" in report["output"]
    assert 'FileAppend "after' not in report["output"], "a line that never ran can only appear if the source was dumped"
    assert log_lines(acu_home)[0]["crash_report"] == str(reports[0])


def test_validation_warning_dialog_times_out_without_running_script(tmp_path):
    marker = tmp_path / "must-not-run.txt"
    script = tmp_path / "blocked-validation.ahk"
    script.write_text(
        '#Warn All, MsgBox\nNoSuchFunctionACU()\n'
        f'FileAppend "ran", "{marker}"\n', encoding="utf-8",
    )
    started = time.monotonic()
    result = run_cli(script, timeout=0.5)

    assert result["exit_code"] == 124, result
    assert result["outcome"] == "timeout"
    assert "validation" in result["trailer"]
    assert not marker.exists()
    assert time.monotonic() - started < 3


@pytest.mark.parametrize("ignore_close", [False, True], ids=["graceful", "forced"])
def test_interrupted_cli_stops_its_script_and_logs_before_releasing_the_lease(tmp_path, acu_home, ignore_close):
    ready = tmp_path / "script.pid"
    exited = tmp_path / "exited.txt"
    script = tmp_path / "interrupted.ahk"
    script.write_text(
        ('OnMessage(0x10, (*) => 0)\n' if ignore_close else '')
        + f'OnExit ((*) => FileAppend("exited", "{exited}"))\n'
        + f'FileAppend DllCall("GetCurrentProcessId"), "{ready}"\nSleep 30000\n', encoding="utf-8",
    )
    process = subprocess.Popen(
        [sys.executable, "-m", "acu", "run", str(script), "--timeout", "30"], cwd=REPO,
        env={**os.environ, "PYTHONPATH": str(REPO)}, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
    )
    script_handle = None
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = [ctypes.c_uint, ctypes.c_bool, ctypes.c_uint]
    kernel32.OpenProcess.restype = ctypes.c_void_p
    kernel32.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint]
    kernel32.TerminateProcess.argtypes = [ctypes.c_void_p, ctypes.c_uint]
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    try:
        wait_until(ready.exists, 5, "owned script did not start")
        script_handle = kernel32.OpenProcess(0x100001, False, int(ready.read_text(encoding="utf-8")))
        assert script_handle, ctypes.WinError(ctypes.get_last_error())
        process.send_signal(signal.CTRL_BREAK_EVENT)
        stdout, stderr = process.communicate(timeout=5)
        assert kernel32.WaitForSingleObject(script_handle, 0) == 0, "script outlived its launcher"
        assert process.returncode == 130, stdout + stderr
        result = json.loads(stdout)
        assert result["outcome"] == "error" and result["exit_code"] == 130
        assert "interrupted" in result["trailer"]
        assert exited.exists() == (not ignore_close)
        report = json.loads(Path(result["artifacts"]["crash_report"]).read_text(encoding="utf-8"))
        assert report["exit_code"] == 130
        assert run_cli(SCRIPTS / "hello.ahk")["exit_code"] == 0, "the next run must acquire the released lease"
    finally:
        # Reap only the processes this test started, including on a regression failure.
        if script_handle:
            if kernel32.WaitForSingleObject(script_handle, 0) != 0:
                kernel32.TerminateProcess(script_handle, 1)
                assert kernel32.WaitForSingleObject(script_handle, 5000) == 0
            kernel32.CloseHandle(script_handle)
        if process.poll() is None:
            process.kill()
        process.communicate(timeout=5)


def test_timeout_kills_script_that_ignores_close_request():
    started = time.monotonic()
    result = run_acu("hang_hard.ahk", "--timeout", "1")
    elapsed = time.monotonic() - started

    assert result.returncode == 124, result.stdout + result.stderr
    assert "hang_hard: finished sleeping" not in result.stdout
    assert "[acu] timeout" in result.stdout and "killed" in result.stdout
    assert elapsed < 5, f"launcher took {elapsed:.1f}s to kill after a 1s timeout"
