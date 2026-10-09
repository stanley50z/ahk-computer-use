"""End-of-script restore: the prelude puts the user's foreground window and cursor back, unless it should not."""

import os
import time

import pytest

from conftest import cursor, foreground, run_acu, set_cursor, wait_until

pytestmark = pytest.mark.desktop

ENTRY_CURSOR = (50, 50)


def arrange(open_window, mode):
    """Open a bystander window, then the user's window on top, park the cursor, and run the probe in the given mode."""
    bystander = open_window(f"ACU bystander {os.getpid()}", 100, 400)
    user_window = open_window(f"ACU user window {os.getpid()}", 100, 100)
    wait_until(lambda: foreground() == user_window, 2, "precondition: the user's window must be in the foreground")
    set_cursor(*ENTRY_CURSOR)
    assert cursor() == ENTRY_CURSOR, "precondition: the cursor must be parked"
    result = run_acu("restore_probe.ahk", "--timeout", "10", "--", mode, str(bystander))
    return user_window, bystander, result


def test_restores_foreground_and_cursor_after_a_click(open_window):
    user_window, _, result = arrange(open_window, "click_own")
    landed = cursor()
    time.sleep(0.2)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "hits=1" in result.stdout
    assert foreground() == user_window
    assert landed == ENTRY_CURSOR


def test_restores_foreground_after_clicking_another_process(open_window):
    user_window, _, result = arrange(open_window, "click_other")
    landed = cursor()
    time.sleep(0.2)

    assert result.returncode == 0, result.stdout + result.stderr
    assert foreground() == user_window
    assert landed == ENTRY_CURSOR
    assert "[acu] foreground left on" not in result.stdout


def test_keep_foreground_leaves_the_clicked_window_in_front_and_still_restores_the_cursor(open_window):
    _, bystander, result = arrange(open_window, "keep_other")
    landed = cursor()
    time.sleep(0.2)

    assert result.returncode == 0, result.stdout + result.stderr
    assert foreground() == bystander
    assert landed == ENTRY_CURSOR
    assert "[acu]" not in result.stdout.replace("[acu] ok", ""), "an opt-out the script asked for needs no note"


def test_leaves_cursor_alone_when_someone_else_moved_it(open_window):
    _, _, result = arrange(open_window, "move_cursor")
    landed = cursor()

    assert result.returncode == 0, result.stdout + result.stderr
    moved = tuple(int(v) for v in result.stdout.split("moved=")[1].splitlines()[0].split(","))
    assert landed == moved
    assert "[acu] restore skipped: cursor moved" in result.stdout


def test_leaves_foreground_on_a_window_it_never_clicked(open_window):
    _, bystander, result = arrange(open_window, "activate_other")
    landed = cursor()
    time.sleep(0.2)

    assert result.returncode == 0, result.stdout + result.stderr
    assert foreground() == bystander
    assert landed == ENTRY_CURSOR
    assert "[acu] foreground left on" in result.stdout
