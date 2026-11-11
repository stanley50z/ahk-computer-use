; The input guard's pop-up (tests/input_guard.py): asks the user to leave the keyboard and mouse alone while a desktop
; test waits to start. It never takes focus, stays on top, and needs no click. The guard ends this process; if the
; pytest process that started it ends first, without unwinding, the notice exits by itself so it never stays on screen.
; Usage: AutoHotkey64.exe input_guard_notice.ahk <window title> <pytest process id>
#Requires AutoHotkey v2.0
#NoTrayIcon
#SingleInstance Off

notice := Gui("+AlwaysOnTop -Caption +ToolWindow +Border +E0x08000000", A_Args[1])  ; WS_EX_NOACTIVATE
notice.BackColor := "FFF4CE"
notice.SetFont("s12", "Segoe UI")
notice.AddText("w420", "A desktop test is waiting to start.`nPlease stop using the keyboard and mouse; it begins after 5 seconds without input.")
notice.Show("NoActivate xCenter y40")
ProcessWaitClose Integer(A_Args[2])  ; Waits without blocking the window.
ExitApp
