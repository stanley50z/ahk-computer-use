; A stand-in for one of the user's application windows. Not run through the launcher.
; Shows a window titled ACU_TEST_TITLE at ACU_TEST_X/ACU_TEST_Y, with background ACU_TEST_BACKCOLOR when set,
; and stays alive until closed or killed. ACU_TEST_MONITOR makes X and Y relative to that monitor's corner, in the
; window's own coordinate space. Per-monitor DPI aware unless ACU_TEST_DPI_AWARENESS is "system", which stands in
; for an older application that Windows scales on a monitor whose DPI differs from the system's.
#NoTrayIcon
#SingleInstance Off
DllCall("SetThreadDpiAwarenessContext", "ptr", EnvGet("ACU_TEST_DPI_AWARENESS") = "system" ? -2 : -4, "ptr")
title := EnvGet("ACU_TEST_TITLE")
win := Gui("", title)
if (EnvGet("ACU_TEST_BACKCOLOR") != "")
    win.BackColor := EnvGet("ACU_TEST_BACKCOLOR")
win.AddText("w200 h80", title)
win.OnEvent("Close", (*) => ExitApp())
left := 0, top := 0
if (EnvGet("ACU_TEST_MONITOR") != "")
    MonitorGet Integer(EnvGet("ACU_TEST_MONITOR")), &left, &top
win.Show("x" left + Integer(EnvGet("ACU_TEST_X")) " y" top + Integer(EnvGet("ACU_TEST_Y")))
WinActivate win.Hwnd
