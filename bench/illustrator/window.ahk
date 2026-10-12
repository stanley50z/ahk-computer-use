; Normalize the initial application window only; never run this observer during an actor's attempt.
hwnd := Integer(A_Args[1])
pid := Integer(A_Args[2])
target := "ahk_id " hwnd
if !WinExist(target) || WinGetPID(target) != pid || WinGetProcessName(target) != "Illustrator.exe"
    throw Error("Illustrator window/process identity changed")
if !DllCall("IsWindowEnabled", "ptr", hwnd)
    throw Error("Illustrator has a modal dialog; refusing window setup")
monitor := MonitorGetPrimary()
MonitorGetWorkArea monitor, &left, &top, &right, &bottom
AcuActivate(target)
WinRestore target
WinMove left, top, right-left, bottom-top, target
WinMaximize target
if !AcuWaitUntil(() => WinGetMinMax(target) = 1, 3000)
    throw Error("Illustrator did not maximize")
if !AcuWaitUntil(() => CoversWorkArea(target, left, top, right, bottom), 3000)
    throw Error("Illustrator does not cover the primary monitor work area")
WinGetPos &x, &y, &width, &height, target
result := '{"maximized":true,"monitor":' monitor ',"bounds":[' x ',' y ',' width ',' height '],"work_area":[' left ',' top ',' right ',' bottom ']}'
FileAppend result, A_Args[3], "UTF-8-RAW"
FileAppend result "`n", "*"

; Maximized frames may include off-screen borders; their bounds must contain the work area.
CoversWorkArea(target, left, top, right, bottom) {
    WinGetPos &x, &y, &width, &height, target
    return x <= left && y <= top && x+width >= right && y+height >= bottom
}
