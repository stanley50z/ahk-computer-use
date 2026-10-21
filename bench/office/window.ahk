; Maintainer action on the trial-owned Office window, outside actor timing. Usage: window.ahk <activate|escape> <hwnd> <pid>
; escape sends two Escapes so COM can save after an actor left a dialog or cell edit open.
mode := A_Args[1], hwnd := Integer(A_Args[2]), pid := Integer(A_Args[3])
target := "ahk_id " hwnd
if !WinExist(target) || WinGetPID(target) != pid
    throw Error("Office window identity changed")
WinActivate target
if !WinWaitActive(target, , 3) && mode = "activate"
    throw Error("Office window did not activate")
if mode = "escape"
    Send "{Esc}{Esc}"
FileAppend "mode=" mode "`nforeground=" WinExist("A") "`n", "*"
