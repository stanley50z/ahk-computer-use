; Close the application only when the bench started it and its native cleanup proved there are no documents.
hwnd := Integer(A_Args[1])
target := "ahk_id " hwnd
expectedPid := Integer(A_Args[2])
if !WinExist(target) {
    if !AcuWaitUntil(() => !ProcessExist(expectedPid), 10000)
        throw Error("Task-started Illustrator has no main window but its process remains")
    FileAppend "already_closed=" hwnd "`nprocess_exited=" expectedPid "`n", "*"
    ExitApp
}
if WinGetPID(target) != expectedPid || WinGetProcessName(target) != "Illustrator.exe"
    throw Error("Illustrator identity changed; refusing close")
WinClose target
if !WinWaitClose(target, , 10)
    throw Error("Task-started Illustrator did not close")
if !AcuWaitUntil(() => !ProcessExist(expectedPid), 10000)
    throw Error("Task-started Illustrator window closed but its process remains")
FileAppend "closed=" hwnd "`nprocess_exited=" expectedPid "`n", "*"
