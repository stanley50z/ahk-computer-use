"""Target-bound input safety through the public CLI; only disposable task-owned GUI windows."""

import subprocess

import pytest

from conftest import plain_ahk_exe, run_cli, user32

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


# Toolkits such as wxWidgets focus a control when it is set or clicked; during a UI Automation Value or Invoke call that
# focus brings the window to the front. AcuBackground must deliver both to a window behind the user's without that
# window ever leaving the foreground. As on a shared desktop, the user's window, the target and the script are three
# processes, and the target focuses its controls from their handlers, as those toolkits do.
def test_background_actions_reach_a_window_behind_the_users_without_activating_it(tmp_path):
    marker = tmp_path / 'applied.txt'
    target = tmp_path / 'target.ahk'
    target.write_text(
        '#Requires AutoHotkey v2.0\n'
        'app := Gui(, "ACU background target")\n'
        'claim := (control, *) => DllCall("SetFocus", "ptr", control.Hwnd)\n'
        'app.Add("Edit", "w200 vField").OnEvent("Change", claim)\n'
        f'app.Add("Button", , "Apply").OnEvent("Click", (control, *) => (claim(control), FileAppend(app["Field"].Value, "{marker}")))\n'
        'app.Show("x100 y100 w300 h120 NoActivate")\n', encoding='utf-8')
    user = tmp_path / 'user.ahk'
    user.write_text(
        '#Requires AutoHotkey v2.0\n'
        'win := Gui(, "ACU user window")\nwin.Show("x150 y150 w300 h120")\nWinActivate "ahk_id " win.Hwnd\n',
        encoding='utf-8')
    script = tmp_path / 'background.ahk'
    script.write_text(
        'user := WinWait("ACU user window", , 5)\nWinActivate "ahk_id " user\n'
        'if !WinWaitActive("ahk_id " user, , 2)\n    throw Error("user window did not activate")\n'
        'hwnd := WinWait("ACU background target", , 5)\nroot := UIA.ElementFromHandle(hwnd)\n'
        'lost := false\nWatch() {\n    global lost\n    if !WinActive("ahk_id " user)\n        lost := true\n}\nSetTimer Watch, 5\n'
        'AcuBackground(hwnd, () => root.FindElement({Type:"Edit"}).Value := "typed")\n'
        'AcuBackground(hwnd, () => root.FindElement({Type:"Button", Name:"Apply"}).Invoke())\n'
        f'applied := AcuWaitUntil(() => FileExist("{marker}"), 3000)\n'
        'Sleep 300\nSetTimer Watch, 0\nWatch()\n'
        'if !applied\n    throw Error("the click never reached the target")\n'
        'if lost\n    throw Error("the target took the foreground")\n', encoding='utf-8')
    apps = [subprocess.Popen([str(plain_ahk_exe()), str(path)]) for path in (target, user)]
    try:
        result = run_cli(script, timeout=15)
    finally:
        for app in apps:
            app.kill()
    assert result['exit_code'] == 0, result['output']
    assert marker.read_text(encoding='utf-8') == 'typed'
