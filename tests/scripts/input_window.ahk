; An ordinary application edit used to check input-language preparation across process boundaries.
#Requires AutoHotkey v2.0
#NoTrayIcon
#Include "%A_LineFile%\..\english_keyboard.ahk"
#SingleInstance Off
win := Gui(, EnvGet("ACU_TEST_TITLE"))
win.AddEdit("w300 h80")
win.OnEvent("Close", (*) => ExitApp())
OnMessage(0x8001, (*) => DllCall("ActivateKeyboardLayout", "uptr", Integer(EnvGet("ACU_TEST_LAYOUT")), "uint", 0, "ptr"))
; The default Windows handler accepts posted language requests; this mode explicitly refuses one.
if EnvGet("ACU_TEST_REJECT_LANGUAGE") = "1"
    OnMessage(0x50, (*) => 0)
win.Show("x100 y100")
