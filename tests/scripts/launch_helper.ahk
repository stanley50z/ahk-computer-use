; Exercises AcuLaunch: starts the stand-in window through the plain AutoHotkey build and prints what came back.
; Arguments: <plain AutoHotkey exe> <helper_window.ahk> <title>. The helper reads its title and position from the
; environment, which the program a script starts inherits from the script.
exe := A_Args[1], helper := A_Args[2], title := A_Args[3]
EnvSet "ACU_TEST_TITLE", title
EnvSet "ACU_TEST_X", "300"
EnvSet "ACU_TEST_Y", "300"
window := AcuLaunch('"' exe '" "' helper '"', title)
FileAppend "hwnd=" window.hwnd "`npid=" window.pid "`ntitle=" window.title "`nclass=" window.class "`nprocess=" window.process "`n", "*"
FileAppend "exists=" (WinExist("ahk_id " window.hwnd) ? 1 : 0) "`nelements=" window.elements "`n", "*"
; The tree was already settled when AcuLaunch returned, so a dump now sees the same controls it counted.
FileAppend "dumped=" (StrSplit(AcuTree("ahk_id " window.hwnd), "`n").Length - 3) "`n", "*"
WinClose "ahk_id " window.hwnd
; A command that opens no window must be reported as such, not returned as a guess.
try {
    AcuLaunch(A_ComSpec " /c exit", "ACU window that never opens", 300)
    FileAppend "nowindow=returned`n", "*"
} catch Error as failure {
    FileAppend "nowindow=" failure.Message "`n", "*"
}
