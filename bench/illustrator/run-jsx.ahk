; Run one maintainer-only script through Illustrator's Other Script UI, bound to the prepared HWND and PID.
hwnd := Integer(A_Args[3])
target := "ahk_id " hwnd
if !WinExist(target) || WinGetPID(target) != Integer(A_Args[4]) || WinGetProcessName(target) != "Illustrator.exe"
    throw Error("Illustrator window/process identity changed")
if !DllCall("IsWindowEnabled", "ptr", hwnd)
    throw Error("Illustrator has a modal dialog; refusing script execution")
WinActivate target
if !WinWaitActive(target, , 3)
    throw Error("Illustrator did not activate")
SetKeyDelay 30, 30
SendEvent "^{F12}"
dialog := AcuWaitUntil(() => WinExist("Locate script file to execute ahk_exe Illustrator.exe"), 5000)
if !dialog || WinGetPID("ahk_id " dialog) != Integer(A_Args[4])
    throw Error("Other Script dialog did not appear in the prepared Illustrator process")
root := UIA.ElementFromHandle(dialog)
field := root.FindElement({Type:"Edit", Name:"File name:"})
field.Value := A_Args[1]
root.FindElement({Type:"Button", Name:"Open", AutomationId:"1"}).Invoke()
if !AcuWaitUntil(() => FileExist(A_Args[2]), 30000)
    throw Error("Illustrator script produced no result: " A_Args[2])
FileAppend FileRead(A_Args[2], "UTF-8") "`n", "*"
