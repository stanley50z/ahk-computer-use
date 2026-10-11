"""Prelude behavior as observed by scripts that run under it."""

import ctypes
import os
import subprocess
import uuid

import pytest

from acu.run import plain_ahk_exe
from conftest import SCRIPTS, reported, run_acu, run_cli, user32

pytestmark = pytest.mark.desktop

SM_CMONITORS = 80


def monitor_count():
    return ctypes.windll.user32.GetSystemMetrics(SM_CMONITORS)


def test_prelude_sets():
    result = run_acu("settings.ahk")

    assert result.returncode == 0, result.stdout + result.stderr
    expected = {
        "mouse=Screen", "pixel=Screen", "mousedelay=-1",
        "mousespeed=0", "dpi=per-monitor-v2", "trayicon=hidden",
    }
    assert expected <= set(result.stdout.splitlines()), result.stdout


def test_acu_launch_returns_the_one_new_window_and_refuses_to_guess():
    title = f"ACU launch window {os.getpid()}"
    try:
        result = run_acu("launch_helper.ahk", "--timeout", "20", "--", str(plain_ahk_exe()), str(SCRIPTS / "helper_window.ahk"), title)
    finally:
        if leftover := user32.FindWindowW(None, title):
            user32.PostMessageW(ctypes.c_void_p(leftover), 0x0010, None, None)

    assert result.returncode == 0, result.stdout + result.stderr
    assert reported(result.stdout, "title") == title
    assert reported(result.stdout, "class") == "AutoHotkeyGUI"
    assert reported(result.stdout, "process").lower() == plain_ahk_exe().name.lower()
    assert int(reported(result.stdout, "hwnd")) > 0 and int(reported(result.stdout, "pid")) > 0
    assert reported(result.stdout, "exists") == "1"
    assert int(reported(result.stdout, "elements")) >= 1, "AcuLaunch waits for the window's tree before returning"
    assert int(reported(result.stdout, "dumped")) >= 1
    assert reported(result.stdout, "nowindow").startswith("no new window matching")


@pytest.mark.parametrize("mode", ["transient", "slow-transient", "persistent", "revealed-existing"])
def test_acu_launch_settles_transient_windows_and_describes_persistent_ambiguity(tmp_path, mode):
    prefix = f"ACU launch-settle {uuid.uuid4().hex}"
    pid_file = tmp_path / "child.pid"
    script = tmp_path / "launch.ahk"
    command = f'"{plain_ahk_exe()}" "{SCRIPTS / "launch_windows.ahk"}" "{prefix}" {mode} "{pid_file}"'
    match = prefix + " pre-existing" if mode == "revealed-existing" else prefix
    setup = (
        f'prior := Gui(, "{match}")\nprior.AddText("w200", "existing")\nprior.Show("Hide")\n'
        'SetTimer (() => prior.Show("x800 y100")), -200\n'
    ) if mode == "revealed-existing" else ""
    script.write_text(
        setup + f"window := AcuLaunch('{command}', '{match}', 2000)\n"
        'FileAppend "returned=" window.title "`n", "*"\nExitApp\n', encoding="utf-8",
    )
    try:
        result = run_cli(script)
    finally:
        if pid_file.exists():
            # This PID was written by the unique fixture process started above, never selected by runtime name.
            subprocess.run(["taskkill", "/PID", pid_file.read_text(encoding="utf-8"), "/T", "/F"], capture_output=True, timeout=5)
    if mode == "revealed-existing":
        assert result["exit_code"] == 1, result["output"]
        assert "no new window matching" in result["output"], result["output"]
    elif mode != "persistent":
        assert result["exit_code"] == 0, result["output"]
        assert f"returned={prefix} main" in result["output"]
    else:
        assert result["exit_code"] == 1, result
        for evidence in ("2 new windows match", prefix + " main", prefix + " splash", "hwnd=", "class=AutoHotkeyGUI", "pid="):
            assert evidence in result["output"], result


def test_acu_wait_until_returns_the_observed_value_or_zero_after_the_timeout():
    result = run_acu("wait_until.ahk")

    assert result.returncode == 0, result.stdout + result.stderr
    assert reported(result.stdout, "value") == "seen"
    assert reported(result.stdout, "late") == "0"
    assert 250 <= int(reported(result.stdout, "elapsed")) < 1500


@pytest.mark.parametrize("monitor", [1, 2])
def test_click_by_screen_coordinate_lands_on_own_button(monitor):
    if monitor > monitor_count():
        pytest.skip(f"monitor {monitor} is not attached")

    result = run_acu("click_own_button.ahk", "--timeout", "10", "--", str(monitor))

    assert result.returncode == 0, result.stdout + result.stderr
    assert reported(result.stdout, "hits") == "1"
    assert reported(result.stdout, "cursor") == reported(result.stdout, "target")
