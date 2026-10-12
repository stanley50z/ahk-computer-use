; Close only a claimed new Calculator window; never terminate the shared frame host.
windowHandle := Integer(A_Args[1])
target := "ahk_id " windowHandle
if !WinExist(target) {
    FileAppend "already_closed=" windowHandle "`n", "*"
    ExitApp
}
expectedPid := Integer(A_Args[2])
if (WinGetPID(target) != expectedPid)
    throw Error("Refusing to close a window whose process identity changed")
processName := WinGetProcessName(target)
if (processName != "CalculatorApp.exe" && processName != "ApplicationFrameHost.exe" && processName != "Calculator.exe")
    throw Error("Refusing to close a non-Calculator window")
if (processName = "ApplicationFrameHost.exe" && !InStr(WinGetTitle(target), "Calculator"))
    throw Error("Refusing to close an unrelated frame-host window")
WinClose target
if !WinWaitClose(target, , 3)
    throw Error("Owned Calculator did not close")
FileAppend "closed=" windowHandle "`n", "*"
