"""Scripts leave cursor position and foreground at their last action, including errors and timeouts."""

import os

import pytest

from conftest import cursor, foreground, run_cli, set_cursor, visible_frame, wait_until

pytestmark = pytest.mark.desktop


@pytest.mark.parametrize("ending", ["normal", "error", "timeout"])
def test_script_exit_leaves_cursor_and_foreground_on_target(open_window, tmp_path, ending):
    target = open_window(f"ACU state target {os.getpid()}", 100, 400)
    entry = open_window(f"ACU state entry {os.getpid()}", 100, 100)
    setup = tmp_path / "entry.ahk"
    setup.write_text(
        f'WinActivate "ahk_id {entry}"\n'
        f'if !WinWaitActive("ahk_id {entry}", , 2)\n throw Error("entry did not activate")\n',
        encoding="utf-8",
    )
    prepared = run_cli(setup)
    assert prepared["exit_code"] == 0, prepared["output"]
    wait_until(lambda: foreground() == entry, 2, "entry window did not become foreground")
    set_cursor(50, 50)
    x, y, w, h = visible_frame(target)
    point = (x + w // 2, y + h // 2)
    last_step = {"normal": "ExitApp", "error": 'throw Error("expected state probe failure")', "timeout": "Sleep 20000"}[ending]
    script = tmp_path / "state.ahk"
    script.write_text(
        f'WinActivate "ahk_id {target}"\n'
        f'if !WinWaitActive("ahk_id {target}", , 2)\n throw Error("target did not activate")\n'
        f'Click {point[0]}, {point[1]}\n{last_step}\n',
        encoding="utf-8",
    )

    result = run_cli(script, timeout=1 if ending == "timeout" else 5)

    assert result["exit_code"] == {"normal": 0, "error": 1, "timeout": 124}[ending], result
    assert cursor() == point, "script exit must not move the cursor back to the entry position"
    assert foreground() == target, "script exit must not reactivate the entry window"
