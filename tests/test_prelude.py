"""Prelude behavior as observed by scripts that run under it."""

import ctypes

import pytest

from conftest import reported, run_acu

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


@pytest.mark.parametrize("monitor", [1, 2])
def test_click_by_screen_coordinate_lands_on_own_button(monitor, monkeypatch):
    if monitor > monitor_count():
        pytest.skip(f"monitor {monitor} is not attached")
    monkeypatch.setenv("ACU_TEST_MONITOR", str(monitor))

    result = run_acu("click_own_button.ahk", "--timeout", "10")

    assert result.returncode == 0, result.stdout + result.stderr
    assert reported(result.stdout, "hits") == "1"
    assert reported(result.stdout, "cursor") == reported(result.stdout, "target")
