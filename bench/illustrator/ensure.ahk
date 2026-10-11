; Start or bind one Illustrator main window; report whether this task owns the application window.
windows := WinGetList("ahk_class illustrator ahk_exe Illustrator.exe")
started := false
if windows.Length = 0 {
    window := AcuLaunch('"' A_Args[1] '"', "ahk_class illustrator ahk_exe Illustrator.exe", 45000)
    hwnd := window.hwnd
    started := true
} else if windows.Length = 1 {
    hwnd := windows[1]
} else
    throw Error("Multiple Illustrator main windows; refusing to guess")
target := "ahk_id " hwnd
FileAppend '{"hwnd":' hwnd ',"pid":' WinGetPID(target) ',"started":' Integer(started) '}', A_Args[2], "UTF-8-RAW"
WinActivate target
if !WinWaitActive(target, , 3)
    throw Error("Illustrator did not activate")
if !DllCall("IsWindowEnabled", "ptr", hwnd)
    throw Error("Illustrator has a modal dialog; refusing to dismiss it")
FileAppend "illustrator=" hwnd "`npid=" WinGetPID(target) "`nstarted=" Integer(started) "`n", "*"
