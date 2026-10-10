"""Prelude behavior as observed by scripts that run under it."""

import ctypes
import os

import pytest

from acu.run import plain_ahk_exe
from conftest import SCRIPTS, reported, run_acu, user32

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
    assert reported(result.stdout, "nowindow").startswith("no new window matching")


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
