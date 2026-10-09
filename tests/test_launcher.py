"""The launcher command line: python acu/run.py SCRIPT [--timeout SECONDS]."""

import json
import time

from conftest import SCRIPTS, cursor, run_acu, set_cursor


def log_lines(acu_home):
    return [json.loads(line) for line in (acu_home / "logs" / "runs.jsonl").read_text(encoding="utf-8").splitlines()]


def test_prints_script_output_and_exits_zero():
    result = run_acu("hello.ahk")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "hello from ahk 你好" in result.stdout


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
    assert landed == (50, 50), "the prelude's exit handler should have put the cursor back"
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


def test_timeout_kills_script_that_ignores_close_request():
    started = time.monotonic()
    result = run_acu("hang_hard.ahk", "--timeout", "1")
    elapsed = time.monotonic() - started

    assert result.returncode == 124, result.stdout + result.stderr
    assert "hang_hard: finished sleeping" not in result.stdout
    assert "[acu] timeout" in result.stdout and "killed" in result.stdout
    assert elapsed < 5, f"launcher took {elapsed:.1f}s to kill after a 1s timeout"
