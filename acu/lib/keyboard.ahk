; English-input preparation for ACU scripts. The native send functions retain their parsing and SendMode;
; their Call methods are guarded so a window activated after startup is checked immediately before input.
#Requires AutoHotkey v2.0

; Installs the input guard once in the prelude and prepares the foreground window before script actions.
AcuInstallKeyboardGuard() {
    nativeCall := GetMethod(Send, "Call")
    for fn in [Send, SendInput, SendEvent, SendPlay, SendText, ControlSend, ControlSendText]
        fn.DefineProp("Call", {Call: AcuKeyboardSend.Bind(nativeCall)})
    if (hwnd := DllCall("GetForegroundWindow", "ptr"))
        AcuEnsureEnglishInput(AcuFocusedInputWindow(hwnd), false)
}

; Checks the send's actual destination, then calls the original built-in without changing its semantics.
AcuKeyboardSend(nativeCall, fn, args*) {
    controlled := fn.Name = "ControlSend" || fn.Name = "ControlSendText"
    if controlled {
        destination := args.Clone()
        destination.RemoveAt(1)
        if args.Has(2) {
            hwnd := ControlGetHwnd(destination*)
        } else {
            ; Omitted Control means the window itself; preserve the native WinTitle/default-window lookup.
            if destination.Length
                destination.RemoveAt(1)
            hwnd := WinGetID(destination*)
        }
    } else {
        foreground := DllCall("GetForegroundWindow", "ptr")
        hwnd := foreground ? AcuFocusedInputWindow(foreground) : 0
    }
    if !hwnd
        throw Error("no target window for keyboard input")
    AcuEnsureEnglishInput(hwnd)
    if (!controlled && DllCall("GetForegroundWindow", "ptr") != foreground)
        throw Error("foreground changed while preparing English input; inspect before retrying")
    return nativeCall(fn, args*)
}

; Selects an already-loaded English keyboard for this window's thread. Warns and stops before input when
; no English keyboard is available; never installs a layout or changes the user's configured language list.
AcuEnsureEnglishInput(hwnd, required := true) {
    ; Use a callable Win32 boundary; AHK can pre-resolve literal DllCall sites, bypassing API interception.
    api := DllCall
    thread := api("GetWindowThreadProcessId", "ptr", hwnd, "ptr", 0, "uint")
    if !thread
        throw OSError()
    current := api("GetKeyboardLayout", "uint", thread, "uptr")
    if !current
        throw OSError()
    if ((current & 0x3FF) = 9) {
        return AcuEnglishSendingThread(current, required)
    }
    count := api("GetKeyboardLayoutList", "int", 0, "ptr", 0, "int")
    if !count
        throw OSError()
    layouts := Buffer(count * A_PtrSize)
    count := api("GetKeyboardLayoutList", "int", count, "ptr", layouts, "int")
    if !count
        throw OSError()
    english := 0
    Loop count {
        layout := NumGet(layouts, (A_Index - 1) * A_PtrSize, "uptr")
        if ((layout & 0x3FF) = 9) {
            english := layout
            if ((layout & 0xFFFF) = 0x0409)
                break
        }
    }
    if !english {
        return AcuInputPreparationFailure("active input is non-English and no English keyboard is loaded; add an English keyboard in Windows before retrying. No keys were sent.", required)
    }
    if (thread = api("GetCurrentThreadId", "uint")) {
        if !api("ActivateKeyboardLayout", "uptr", english, "uint", 0, "ptr")
            return AcuInputPreparationFailure("Windows did not activate the English keyboard; no keys were sent", required)
    } else {
        ; Windows posts this request to the focused control, not necessarily the top-level window.
        requestWindow := AcuFocusedInputWindow(hwnd)
        if !api("PostMessageW", "ptr", requestWindow, "uint", 0x50, "ptr", 0, "uptr", english, "int")
            return AcuInputPreparationFailure("Windows did not accept the English input-language request; no keys were sent", required)
    }
    if !AcuWaitUntil(() => (api("GetKeyboardLayout", "uint", thread, "uptr") & 0x3FF) = 9, 1000)
        return AcuInputPreparationFailure("target window did not switch to English input; no keys were sent", required)
    if !AcuEnglishSendingThread(english, required)
        return false
    AcuNote("input: switched hwnd=" hwnd " to English keyboard " Format("0x{:X}", english))
    return true
}

; Reads the thread's actual keyboard focus without changing the script's Last Found Window or app focus.
AcuFocusedInputWindow(hwnd) {
    api := DllCall
    thread := api("GetWindowThreadProcessId", "ptr", hwnd, "ptr", 0, "uint")
    if !thread
        throw OSError()
    info := Buffer(8 + 6 * A_PtrSize + 16, 0)
    NumPut "uint", info.Size, info
    if !api("GetGUIThreadInfo", "uint", thread, "ptr", info, "int")
        throw OSError()
    focused := NumGet(info, 8 + A_PtrSize, "ptr")
    return focused ? focused : hwnd
}

; Keeps the sending thread in English as well as the destination, before invoking native input functions.
AcuEnglishSendingThread(layout, required := true) {
    api := DllCall
    if ((api("GetKeyboardLayout", "uint", 0, "uptr") & 0x3FF) != 9
        && !api("ActivateKeyboardLayout", "uptr", layout, "uint", 0, "ptr"))
        return AcuInputPreparationFailure("Windows did not activate English input for the sending thread; no keys were sent", required)
    if ((api("GetKeyboardLayout", "uint", 0, "uptr") & 0x3FF) != 9)
        return AcuInputPreparationFailure("sending thread did not switch to English input; no keys were sent", required)
    return true
}

; Startup reports expected preparation failures so inspection still works; actual keyboard sends must stop.
AcuInputPreparationFailure(message, required) {
    AcuNote("warning: " message)
    if required
        throw Error(message)
    return false
}
