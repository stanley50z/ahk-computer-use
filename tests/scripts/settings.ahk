; Prints the settings the prelude is responsible for, one per line, for tests/test_prelude.py.
dpiContext := DllCall("GetThreadDpiAwarenessContext", "ptr")
perMonitorV2 := DllCall("AreDpiAwarenessContextsEqual", "ptr", dpiContext, "ptr", -4)
FileAppend "mouse=" A_CoordModeMouse "`n", "*"
FileAppend "pixel=" A_CoordModePixel "`n", "*"
FileAppend "mousedelay=" A_MouseDelay "`n", "*"
FileAppend "mousespeed=" A_DefaultMouseSpeed "`n", "*"
FileAppend "dpi=" (perMonitorV2 ? "per-monitor-v2" : "other") "`n", "*"
FileAppend "trayicon=" (A_IconHidden ? "hidden" : "shown") "`n", "*"
