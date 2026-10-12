; Cancel only recognized new task dialogs in the bound Illustrator process; never save or discard a document.
hwnd := Integer(A_Args[1])
pid := Integer(A_Args[2])
target := "ahk_id " hwnd
if !WinExist(target) || WinGetPID(target) != pid || WinGetProcessName(target) != "Illustrator.exe"
    throw Error("Illustrator identity changed")
protected := FileRead(A_Args[3], "UTF-8")
allowed := Map("Save As", true, "Illustrator Options", true, "PNG Options", true, "Export", true, "Open", true,
               "Locate script file to execute", true, "Eyedropper Options", true, "Color Picker", true)
loop {
    candidates := TaskDialogs(pid, hwnd)
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
    if title = "Color Picker" {
        if DllCall("GetWindow", "ptr", dialog, "uint", 4, "ptr") != 0
            throw Error("Unrecognized Color Picker owner; refusing cancellation")
        ; The observed ownerless picker has these distinct controls; title/PID alone is insufficient.
        for name in ["OK", "Cancel", "Color Swatches"]
            if root.FindElements({Type:"Button", Name:name}).Length != 1
                throw Error("Unrecognized Illustrator Color Picker; refusing cancellation")
    }
    if !WinExist("ahk_id " dialog) || WinGetPID("ahk_id " dialog) != pid || WinGetTitle("ahk_id " dialog) != title
        throw Error("Illustrator dialog identity changed before cancellation")
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
    if !AcuWaitUntil(() => DllCall("IsWindowEnabled", "ptr", hwnd) || TaskDialogs(pid, hwnd).Length, 3000)
        throw Error("Illustrator did not return from its task dialog")
}

; Include the known ownerless Color Picker even when Illustrator leaves its main frame enabled.
; Baseline protection, ambiguity refusal and UIA identity validation happen before any action above.
TaskDialogs(pid, owner) {
    candidates := []
    for candidate in WinGetList("ahk_class #32770 ahk_pid " pid) {
        if !DllCall("IsWindowEnabled", "ptr", candidate)
            continue
        owned := DllCall("GetAncestor", "ptr", candidate, "uint", 3, "ptr") = owner
        picker := WinGetTitle("ahk_id " candidate) = "Color Picker"
            && DllCall("GetWindow", "ptr", candidate, "uint", 4, "ptr") = 0
        if owned || picker
            candidates.Push(candidate)
    }
    return candidates
}
