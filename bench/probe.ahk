; Read-only observer of Calculator windows and desktop entry state, outside agent timing.
MouseGetPos &pointerX, &pointerY
FileAppend "foreground=" WinExist("A") "`ncursor=" pointerX "," pointerY "`n", "*"
DetectHiddenWindows true
for windowHandle in WinGetList()
    FileAppend "window=" windowHandle " pid=" WinGetPID("ahk_id " windowHandle) "`n", "*"
DetectHiddenWindows false
for windowHandle in WinGetList("ahk_exe Calculator.exe")
    FileAppend "calculator=" windowHandle "`npid=" WinGetPID("ahk_id " windowHandle) "`n", "*"
for windowHandle in WinGetList("ahk_exe CalculatorApp.exe")
    FileAppend "calculator=" windowHandle "`npid=" WinGetPID(windowHandle) "`n", "*"
for windowHandle in WinGetList("Calculator ahk_class ApplicationFrameWindow")
    FileAppend "calculator=" windowHandle "`npid=" WinGetPID(windowHandle) "`n", "*"
