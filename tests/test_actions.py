"""Target-bound input safety through the public CLI; only disposable task-owned GUI windows."""

import pytest

from conftest import run_cli, user32

pytestmark = pytest.mark.desktop


def test_paced_pointer_refuses_a_different_window_even_in_the_same_process(tmp_path):
    script = tmp_path / 'foreign-coordinate.ahk'
    script.write_text(
        'targetWin := Gui(, "ACU intended input")\n'
        'targetWin.Show("x100 y100 w200 h100")\n'
        'otherWin := Gui(, "ACU foreign input")\n'
        'otherWin.Show("x1000 y100 w200 h100")\n'
        'WinGetPos &x,&y,&w,&h, "ahk_id " otherWin.Hwnd\n'
        'refused := false\n'
        'try AcuClick(targetWin.Hwnd, x+w//2, y+h//2)\n'
        'catch Error as failure {\n'
        '    if !InStr(failure.Message, "pointer target")\n        throw failure\n'
        '    refused := true\n}\n'
        'if !refused\n    throw Error("Foreign pointer coordinate was accepted")\n'
        'targetWin.Destroy()\notherWin.Destroy()\n', encoding='utf-8')
    result = run_cli(script)
    assert result['exit_code'] == 0, result['output']


def test_paced_drag_releases_its_button_when_the_script_exits_mid_gesture(tmp_path):
    script = tmp_path / 'exit-drag.ahk'
    script.write_text(
        'win := Gui(, "ACU exit input")\nwin.Show("x100 y100 w400 h200")\n'
        'AcuActivate(win.Hwnd)\n'
        'WinGetPos &x,&y,&w,&h, "ahk_id " win.Hwnd\n'
        'SetTimer (() => ExitApp()), -150\n'
        'AcuDrag(win.Hwnd, x+100, y+100, x+200, y+100, 800)\n'
        'throw Error("Exit timer did not interrupt the gesture")\n', encoding='utf-8')
    try:
        result = run_cli(script)
        assert result['exit_code'] == 0, result['output']
        assert not user32.GetAsyncKeyState(1) & 0x8000, 'Gesture left its owned left button held'
    finally:
        # A failing RED must release only the button that this test intentionally held.
        user32.mouse_event(0x0004, 0, 0, 0, 0)


# A task-created competing GUI reproduces focus loss during contact without touching another application.
def test_paced_drag_aborts_and_releases_on_activation_loss(tmp_path):
    script = tmp_path / 'lost-activation.ahk'
    script.write_text(
        'win := Gui(, "ACU drag target")\nwin.Show("x100 y100 w400 h200")\n'
        'other := Gui(, "ACU activation change")\nother.Show("x1200 y100 w200 h100")\n'
        'AcuActivate(win.Hwnd)\nWinGetPos &x,&y,&w,&h, "ahk_id " win.Hwnd\n'
        'SetTimer (() => WinActivate("ahk_id " other.Hwnd)), -150\n'
        'refused := false\ntry AcuDrag(win.Hwnd, x+100, y+100, x+200, y+100, 800)\n'
        'catch Error as failure {\n'
        '    if !InStr(failure.Message, "lost activation")\n        throw failure\n'
        '    refused := true\n}\n'
        'if !refused || GetKeyState("LButton")\n    throw Error("Drag did not stop and release")\n'
        'win.Destroy()\nother.Destroy()\n', encoding='utf-8')
    result = run_cli(script)
    assert result['exit_code'] == 0, result['output']
