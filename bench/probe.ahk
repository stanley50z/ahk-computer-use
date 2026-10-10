; Read-only observer of Calculator windows and desktop entry state, outside agent timing.
MouseGetPos &pointerX, &pointerY
FileAppend "foreground=" WinExist("A") "`ncursor=" pointerX "," pointerY "`n", "*"
; Visible windows are the user's and are protected from cleanup. Hidden ones are listed separately: the frame host
; keeps hidden shells that a newly launched store app can reuse, so a hidden pre-existing handle is not the user's window.
for windowHandle in WinGetList()
    FileAppend "window=" windowHandle " pid=" WinGetPID("ahk_id " windowHandle) "`n", "*"
DetectHiddenWindows true
for windowHandle in WinGetList()
    if !(WinGetStyle("ahk_id " windowHandle) & 0x10000000)  ; WS_VISIBLE
        FileAppend "hiddenwindow=" windowHandle " pid=" WinGetPID("ahk_id " windowHandle) "`n", "*"
DetectHiddenWindows false
for windowHandle in WinGetList("ahk_exe Calculator.exe")
    FileAppend "calculator=" windowHandle "`npid=" WinGetPID("ahk_id " windowHandle) "`n", "*"
for windowHandle in WinGetList("ahk_exe CalculatorApp.exe")
    FileAppend "calculator=" windowHandle "`npid=" WinGetPID(windowHandle) "`n", "*"
for windowHandle in WinGetList("Calculator ahk_class ApplicationFrameWindow")
    FileAppend "calculator=" windowHandle "`npid=" WinGetPID(windowHandle) "`n", "*"
