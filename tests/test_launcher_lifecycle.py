"""Launcher lifecycle through the process adapter, without starting AutoHotkey."""

import json
import signal
from contextlib import contextmanager

import pytest

from acu import run as launcher, tool
from acu.tool import RunOptions, run_operation


@pytest.fixture
def process_run(tmp_path, process_adapter):
    """Use real run orchestration with isolated installation paths and a fake process adapter."""
    script = tmp_path / "action.ahk"
    script.write_text("ExitApp\n", encoding="utf-8")
    adapter = process_adapter
    adapter.output = "script output\n"

    def execute(timeout=1, lease=False):
        return run_operation(str(script), timeout, options=RunOptions(lease=lease), process_adapter=adapter)

    return adapter, execute


@pytest.mark.parametrize("phase", ["validation", "execution"])
def test_creation_interrupt_is_deferred_until_cleanup_is_registered(process_run, phase):
    adapter, execute = process_run
    adapter.interrupt_creation = phase
    adapter.script.finish = False
    previous = signal.getsignal(signal.SIGINT)
    result = execute().run

    assert result.exit_code == 130
    assert signal.getsignal(signal.SIGINT) == previous
    assert adapter.events.index("validator.wait") < adapter.events.index("validator.close")
    if phase == "execution":
        assert adapter.script.closed and not adapter.script.alive
        assert result.output == "script output\n"
    else:
        assert "validator.kill" in adapter.events and "script.start" not in adapter.events
        assert "validation" in result.trailer


@pytest.mark.parametrize("ignore_close, ending", [(False, "closed on request"), (True, "killed")])
def test_timeout_requests_close_before_kill_and_verifies_exit(process_run, ignore_close, ending):
    adapter, execute = process_run
    adapter.script.finish = False
    adapter.script.ignore_close = ignore_close
    result = execute().run

    assert result.exit_code == 124 and result.outcome == "timeout"
    assert result.trailer == f"[acu] timeout 1s: {ending}"
    assert adapter.script.closed and not adapter.script.alive
    assert 1.0 in adapter.script.budgets, "close grace period was not offered"
    assert ("script.kill" in adapter.events) == ignore_close
    if ignore_close:
        assert adapter.events.index("script.request_close") < adapter.events.index("script.kill")
    assert adapter.events[-2:] == ["script.exited", "script.close_handle"]


def test_failed_shutdown_retains_ownership_until_exit_is_verified(process_run, acu_home, monkeypatch):
    adapter, execute = process_run
    adapter.script.finish = False
    adapter.script.ignore_close = True
    adapter.script.kill_failure = True

    @contextmanager
    def lease():
        adapter.events.append("lease.acquired")
        try:
            yield
        finally:
            assert adapter.script.closed and not adapter.script.alive
            adapter.events.append("lease.released")

    monkeypatch.setattr(tool, "desktop_lease", lease)
    with pytest.raises(OSError, match="termination denied"):
        execute(lease=True)

    assert adapter.script.checks_after_failure >= 3
    assert adapter.script.closed and not adapter.script.alive
    reports = list((acu_home / "crashes").glob("*.json"))
    assert len(reports) == 1
    output = json.loads(reports[0].read_text(encoding="utf-8"))["output"]
    assert "retaining ownership" in output and "Traceback" in output
    assert adapter.events[-2:] == ["script.close_handle", "lease.released"]


def test_validation_timeout_uses_the_run_budget_and_persists_output(process_run):
    adapter, execute = process_run
    adapter.validator.timeout = True
    adapter.validator.output = b"validator output\n"
    completed = execute(0.25)

    assert 0 < adapter.validator.budgets[0] <= 0.25
    assert completed.run.exit_code == 124
    assert completed.run.trailer == "[acu] timeout 0.25s: validation"
    assert "script.start" not in adapter.events
    assert adapter.events == ["validator.start", "validator.kill", "validator.wait", "validator.close"]
    report = json.loads(completed.crash_report.read_text(encoding="utf-8"))
    assert report["outcome"] == "timeout"
    assert report["output"] == completed.run.output == "validator output\n"


@pytest.mark.parametrize("validation_seconds", [0.4, 1.0])
def test_validation_and_execution_share_one_timeout_budget(process_run, monkeypatch, validation_seconds):
    adapter, execute = process_run
    now = 0

    def finish_validation():
        nonlocal now
        now = validation_seconds

    adapter.validator.on_communicate = finish_validation
    monkeypatch.setattr(launcher.time, "monotonic", lambda: now)
    result = execute().run
    assert adapter.validator.budgets == [1]
    if validation_seconds == 0.4:
        assert adapter.script.budgets[0] == pytest.approx(0.6)
        assert result.exit_code == 0
    else:
        assert "script.start" not in adapter.events
        assert result.exit_code == 124 and result.trailer == "[acu] timeout 1s: validation"


def test_second_interrupt_during_shutdown_does_not_abandon_script(process_run):
    adapter, execute = process_run
    adapter.script.finish = False
    adapter.script.interrupt_wait = True
    adapter.script.interrupt_close = True
    result = execute().run
    assert result.exit_code == 130
    assert adapter.events.index("script.request_close") < adapter.events.index("script.kill")
    assert adapter.script.closed and not adapter.script.alive
