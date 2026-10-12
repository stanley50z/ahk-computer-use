; Observe only the claimed new Calculator window. Never press buttons or change its state.
windowHandle := Integer(A_Args[1])
if !WinExist("ahk_id " windowHandle)
    throw Error("Owned Calculator window no longer exists")
processName := WinGetProcessName("ahk_id " windowHandle)
if (processName != "CalculatorApp.exe" && processName != "ApplicationFrameHost.exe" && processName != "Calculator.exe")
    throw Error("Claimed window is not Calculator")
root := UIA.ElementFromHandle(windowHandle)
FileAppend "hwnd=" windowHandle "`npid=" WinGetPID("ahk_id " windowHandle) "`nprocess=" processName "`n", "*"
FileAppend "result=" root.FindElement({AutomationId:"CalculatorResults"}).Name "`n", "*"
FileAppend "expression=" root.FindElement({AutomationId:"CalculatorExpression"}).Name "`n", "*"
