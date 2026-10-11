; Normalize and verify English input on the exact Illustrator destination before every arm, outside timing.
hwnd := Integer(A_Args[1])
target := "ahk_id " hwnd
if !WinExist(target) || WinGetPID(target) != Integer(A_Args[2])
    throw Error("Illustrator identity changed")
WinActivate target
if !WinWaitActive(target, , 3)
    throw Error("Illustrator did not activate")
destination := AcuFocusedInputWindow(hwnd)
AcuEnsureEnglishInput(destination)
threadId := DllCall("GetWindowThreadProcessId", "ptr", destination, "ptr", 0, "uint")
layout := DllCall("GetKeyboardLayout", "uint", threadId, "uptr")
if (layout & 0x3FF) != 9
    throw Error("Illustrator input is not English")
FileAppend "input_hwnd=" destination "`ninput_thread=" threadId "`nkeyboard_layout=" Format("0x{:X}", layout) "`nenglish=1`n", "*"
