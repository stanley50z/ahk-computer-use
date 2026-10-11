"""English input is selected before native keyboard sends, including a target activated after startup."""

import ctypes
import os

import pytest

from conftest import foreground, run_cli, user32, wait_until

pytestmark = pytest.mark.desktop


@pytest.fixture
def chinese_layout():
    count = user32.GetKeyboardLayoutList(0, None)
    layouts = (ctypes.c_void_p * count)()
    user32.GetKeyboardLayoutList(count, layouts)
    chinese = next((layout for layout in layouts if layout & 0xFFFF == 0x0804), None)
    assert chinese is not None, "these approved checks require the machine's installed Chinese IME"
    assert any(layout & 0x3FF == 9 for layout in layouts), "these approved checks require an installed English keyboard"
    return chinese


# Creates a disposable edit and selects the real Chinese input layout for its thread, after the prelude has run.
def input_script(chinese_layout):
    return (
        'win := Gui(, "ACU input probe")\n'
        'field := win.AddEdit("w200")\n'
        'win.Show("x100 y100")\n'
        'if !WinWaitActive(win.Hwnd, , 2)\n throw Error("input probe did not activate")\n'
        'field.Focus()\n'
        f'DllCall("ActivateKeyboardLayout", "ptr", {chinese_layout}, "uint", 0, "ptr")\n'
        'FileAppend "before_lang=" (DllCall("GetKeyboardLayout", "uint", 0, "uptr") & 0xFFFF) "`n", "*"\n'
    )


@pytest.mark.parametrize("send", ["Send", "SendInput", "SendEvent", "SendText", "ControlSend", "ControlSendText", "AcuKeys"])
def test_keyboard_send_switches_the_active_target_to_english(tmp_path, chinese_layout, send):
    script = tmp_path / "input.ahk"
    expected = "你好+^{}" if send.endswith("Text") else "O"
    keys = expected if send.endswith("Text") else "+o"
    target = ', field.Hwnd' if send.startswith("Control") else ""
    statement = f'AcuKeys(win.Hwnd, "{keys}")' if send == 'AcuKeys' else f'{send} "{keys}"{target}'
    script.write_text(
        input_script(chinese_layout)
        + statement + '\n'
        + f'AcuWaitUntil(() => field.Value = "{expected}", 1000)\n'
        + 'FileAppend "after_primary=" (DllCall("GetKeyboardLayout", "uint", 0, "uptr") & 0x3FF) " text=" field.Value "`n", "*"\nExitApp\n',
        encoding="utf-8",
    )

    result = run_cli(script)

    assert result["exit_code"] == 0, result
    assert "before_lang=2052" in result["output"], result
    assert f"after_primary=9 text={expected}" in result["output"], result["output"]


def test_control_send_preserves_an_omitted_control_argument(tmp_path, chinese_layout):
    script = tmp_path / "window-send.ahk"
    script.write_text(
        input_script(chinese_layout)
        + 'ControlSend "{F24}", , "ahk_id " win.Hwnd\n'
        + 'FileAppend "after_primary=" (DllCall("GetKeyboardLayout", "uint", 0, "uptr") & 0x3FF) " after_send=1`n", "*"\nExitApp\n',
        encoding="utf-8",
    )

    result = run_cli(script)

    assert result["exit_code"] == 0, result["output"]
    assert "after_primary=9 after_send=1" in result["output"], result["output"]


@pytest.mark.parametrize("reject", [False, True])
def test_input_guard_checks_a_foreign_window_and_stops_if_it_rejects_english(open_window, tmp_path, chinese_layout, reject):
    target = open_window(
        f"ACU foreign input {os.getpid()}", 100, 100, script="input_window.ahk",
        ACU_TEST_LAYOUT=str(chinese_layout), ACU_TEST_REJECT_LANGUAGE="1" if reject else "0",
    )
    script = tmp_path / "foreign-input.ahk"
    script.write_text(
        f'WinActivate "ahk_id {target}"\n'
        f'if !WinWaitActive("ahk_id {target}", , 2)\n throw Error("target did not activate")\n'
        f'field := ControlGetHwnd("Edit1", "ahk_id {target}")\nControlFocus field\n'
        f'SendMessage 0x8001, 0, 0, , "ahk_id {target}"\n'
        f'inputThread := DllCall("GetWindowThreadProcessId", "ptr", {target}, "ptr", 0, "uint")\n'
        'FileAppend "before_lang=" (DllCall("GetKeyboardLayout", "uint", inputThread, "uptr") & 0xFFFF) "`n", "*"\n'
        'Send "+o"\n'
        'AcuWaitUntil(() => ControlGetText(field) = "O", 1000)\n'
        'FileAppend "after_send=" ControlGetText(field) "`n", "*"\n',
        encoding="utf-8",
    )

    result = run_cli(script)

    assert "before_lang=2052" in result["output"], result["output"]
    if reject:
        assert result["exit_code"] == 1, result["output"]
        assert "did not switch to English" in result["output"] and "no keys were sent" in result["output"], result["output"]
        assert "after_send=" not in result["output"], result["output"]
    else:
        assert result["exit_code"] == 0, result["output"]
        assert "after_send=O" in result["output"], result["output"]


def test_read_only_script_warns_if_startup_english_switch_is_rejected(open_window, tmp_path, chinese_layout):
    target = open_window(
        f"ACU read-only input {os.getpid()}", 100, 100, script="input_window.ahk",
        ACU_TEST_LAYOUT=str(chinese_layout), ACU_TEST_REJECT_LANGUAGE="1",
    )
    wait_until(lambda: foreground() == target, 2, "input fixture did not become foreground")
    user32.SendMessageW(ctypes.c_void_p(target), 0x8001, 0, 0)
    script = tmp_path / "read-only.ahk"
    script.write_text('FileAppend "read_only=1`n", "*"\n', encoding="utf-8")

    result = run_cli(script)

    assert result["exit_code"] == 0, result["output"]
    assert "warning:" in result["output"] and "did not switch to English" in result["output"], result["output"]
    assert "read_only=1" in result["output"], result["output"]


def test_send_does_not_change_the_scripts_last_found_window(tmp_path, chinese_layout):
    script = tmp_path / "last-found.ahk"
    script.write_text(
        'anchor := Gui(, "ACU last-found anchor")\nanchor.Show("x500 y100")\n'
        + input_script(chinese_layout)
        + 'WinExist "ahk_id " anchor.Hwnd\n'
        + 'SendText "O"\n'
        + 'FileAppend "preserved=" (WinGetID() = anchor.Hwnd) "`n", "*"\nExitApp\n',
        encoding="utf-8",
    )

    result = run_cli(script)

    assert result["exit_code"] == 0, result["output"]
    assert "preserved=1" in result["output"], result["output"]


def test_missing_english_keyboard_warns_and_stops_before_sending(tmp_path, chinese_layout):
    script = tmp_path / "no-english.ahk"
    # Mock only the Windows layout enumeration boundary; do not remove any of the user's installed layouts.
    script.write_text(
        input_script(chinese_layout)
        + 'nativeCall := GetMethod(DllCall, "Call")\n'
        + 'DllCall.DefineProp("Call", {Call: WithoutEnglish.Bind(nativeCall)})\n'
        + 'SendText "must not be typed"\n'
        + 'FileAppend "after_send=1", "*"\nExitApp\n'
        + 'WithoutEnglish(nativeCall, fn, name, args*) {\n'
        + ' if name = "GetKeyboardLayoutList" {\n'
        + '  if args[2] != 0\n   NumPut "uptr", 0x08040804, args[4], 0\n'
        + '  return 1\n }\n return nativeCall(fn, name, args*)\n}\n',
        encoding="utf-8",
    )

    result = run_cli(script)

    assert result["exit_code"] == 1, result
    assert "warning:" in result["output"] and "no English keyboard" in result["output"], result
    assert "after_send=1" not in result["output"], result
