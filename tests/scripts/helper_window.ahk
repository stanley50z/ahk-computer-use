; A stand-in for one of the user's application windows. Not run through the launcher.
; Shows a window titled ACU_TEST_TITLE at ACU_TEST_X/ACU_TEST_Y and stays alive until closed or killed.
#NoTrayIcon
#SingleInstance Off
DllCall("SetThreadDpiAwarenessContext", "ptr", -4, "ptr")
title := EnvGet("ACU_TEST_TITLE")
win := Gui("", title)
win.AddText("w200 h80", title)
win.OnEvent("Close", (*) => ExitApp())
win.Show("x" EnvGet("ACU_TEST_X") " y" EnvGet("ACU_TEST_Y"))
WinActivate win.Hwnd
