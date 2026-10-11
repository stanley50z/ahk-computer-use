; Give disposable application fixtures a deterministic English input layout before showing their windows.
#Requires AutoHotkey v2.0
layoutCount := DllCall("GetKeyboardLayoutList", "int", 0, "ptr", 0, "int")
layoutBuffer := Buffer(layoutCount * A_PtrSize)
DllCall "GetKeyboardLayoutList", "int", layoutCount, "ptr", layoutBuffer, "int"
Loop layoutCount {
    inputLayout := NumGet(layoutBuffer, (A_Index - 1) * A_PtrSize, "uptr")
    if ((inputLayout & 0x3FF) = 9) {
        DllCall "ActivateKeyboardLayout", "uptr", inputLayout, "uint", 0, "ptr"
        break
    }
}
