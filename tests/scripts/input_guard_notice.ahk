; The input guard's pop-up (tests/input_guard.py): asks the user to leave the keyboard and mouse alone while a desktop
; test waits to start. It never takes focus, stays on top, and needs no click; the guard ends this process.
; Usage: AutoHotkey64.exe input_guard_notice.ahk <window title>
#Requires AutoHotkey v2.0
#NoTrayIcon
#SingleInstance Off

notice := Gui("+AlwaysOnTop -Caption +ToolWindow +Border +E0x08000000", A_Args[1])  ; WS_EX_NOACTIVATE
notice.BackColor := "FFF4CE"
notice.SetFont("s12", "Segoe UI")
notice.AddText("w420", "A desktop test is waiting to start.`nPlease stop using the keyboard and mouse; it begins after 5 seconds without input.")
notice.Show("NoActivate xCenter y40")
