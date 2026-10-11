; Cancel only recognized new task dialogs in the bound Illustrator process; never save or discard a document.
hwnd := Integer(A_Args[1])
pid := Integer(A_Args[2])
target := "ahk_id " hwnd
if !WinExist(target) || WinGetPID(target) != pid || WinGetProcessName(target) != "Illustrator.exe"
    throw Error("Illustrator identity changed")
protected := FileRead(A_Args[3], "UTF-8")
allowed := Map("Save As", true, "Illustrator Options", true, "PNG Options", true, "Export", true, "Open", true,
               "Locate script file to execute", true, "Eyedropper Options", true)
loop {
    candidates := []
    for candidate in WinGetList("ahk_class #32770 ahk_pid " pid)
        if DllCall("IsWindowEnabled", "ptr", candidate) && DllCall("GetAncestor", "ptr", candidate, "uint", 3, "ptr") = hwnd
            candidates.Push(candidate)
    if candidates.Length = 0 {
        if !DllCall("IsWindowEnabled", "ptr", hwnd)
            throw Error("Unknown Illustrator modal state; refusing cancellation")
        break
    }
    if candidates.Length != 1
        throw Error("Ambiguous Illustrator task dialogs; refusing cancellation")
    dialog := candidates[1]
    title := WinGetTitle("ahk_id " dialog)
    if RegExMatch(protected, "m)^(?:window|hiddenwindow)=" dialog " pid=") || !allowed.Has(title)
        throw Error("Pre-existing or unrecognized Illustrator dialog; refusing cancellation: " title)
    root := UIA.ElementFromHandle(dialog)
    errors := root.FindElements({Type:"Text", AutomationId:"ContentText"})
    if errors.Length = 1 && InStr(errors[1].Name, "The file name is not valid.") {
        FileAppend "file_dialog_error=" errors[1].Name "`n", "*"
        root.FindElement({Type:"Button", Name:"OK", AutomationId:"CommandButton_1"})
        WinActivate "ahk_id " dialog
        if !WinWaitActive("ahk_id " dialog, , 2)
            throw Error("Task file error did not activate")
        SetKeyDelay 30, 30
        SendEvent "{Enter}"
    } else
        root.FindElement({Type:"Button", Name:"Cancel"}).Invoke()
    if !WinWaitClose("ahk_id " dialog, , 3)
        throw Error("Task dialog did not close: " title)
    FileAppend "cancelled=" dialog " " title "`n", "*"
    if !AcuWaitUntil(() => (DllCall("IsWindowEnabled", "ptr", hwnd) && !WinGetList("ahk_class #32770 ahk_pid " pid).Length) || EnabledTaskDialog(pid, hwnd), 3000)
        throw Error("Illustrator did not return from its task dialog")
}

; A nested file error can leave its parent disabled briefly after disappearing.
EnabledTaskDialog(pid, owner) {
    for candidate in WinGetList("ahk_class #32770 ahk_pid " pid)
        if DllCall("IsWindowEnabled", "ptr", candidate) && DllCall("GetAncestor", "ptr", candidate, "uint", 3, "ptr") = owner
            return true
    return false
}
