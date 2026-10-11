; Opt-in target-bound input for applications that sample modifier/button state after queued events.
#Requires AutoHotkey v2.0

; Activate exactly one intended window before input; refuse an owned dialog even when its parent frame stays enabled.
AcuActivate(winTitle, timeoutMs := 2000) {
    windows := WinGetList(winTitle)
    if windows.Length != 1
        throw Error("Expected exactly one input target; observed " windows.Length)
    hwnd := windows[1]
    target := "ahk_id " hwnd
    pid := WinGetPID(target)
    for dialog in WinGetList("ahk_class #32770 ahk_pid " pid)
        if dialog != hwnd && (DllCall("GetWindow", "ptr", dialog, "uint", 4, "ptr") = hwnd
            || DllCall("GetAncestor", "ptr", dialog, "uint", 3, "ptr") = hwnd)
            throw Error("Target has an owned dialog: " WinGetTitle("ahk_id " dialog) " (" dialog ")")
    ; A dialog can disappear before its parent is re-enabled. Wait on that transition, not a fixed pause.
    if !AcuWaitUntil(() => DllCall("IsWindowEnabled", "ptr", hwnd), timeoutMs)
        throw Error("Target remains disabled; inspect its dialog instead")
    if !WinActive(target)
        WinActivate target
    if !WinWaitActive(target, , timeoutMs / 1000)
        throw Error("Input target did not activate")
    return hwnd
}

; Send keys/chords with an explicit press duration; use SendText for literal text and observe the effect afterwards.
AcuKeys(target, keys, pressMs := 30) {
    if pressMs < 1 || pressMs > 1000
        throw ValueError("Key press duration must be between 1 and 1000 ms")
    AcuActivate(target)
    previousDelay := A_KeyDelay
    previousDuration := A_KeyDuration
    try {
        SetKeyDelay 0, pressMs
        SendEvent keys
    } finally
        SetKeyDelay previousDelay, previousDuration
}

; Click with a bounded button contact rather than an instantaneous down/up; coordinates are screen pixels.
AcuClick(target, x, y) {
    AcuDrag(target, x, y, x, y, 0)
}

; Replay a drag between authored endpoints, retaining contact through the last movement so apps consume its full extent.
; The interpolation moves the pointer only; it does not choose anchors/handles or create vector geometry.
AcuDrag(target, x1, y1, x2, y2, durationMs := 150) {
    if durationMs < 0 || durationMs > 1000
        throw ValueError("Drag movement duration must be between 0 and 1000 ms")
    x1 := Round(x1), y1 := Round(y1), x2 := Round(x2), y2 := Round(y2)
    left := SysGet(76), top := SysGet(77), right := left + SysGet(78), bottom := top + SysGet(79)
    for point in [[x1, y1], [x2, y2]]
        if point[1] < left || point[1] >= right || point[2] < top || point[2] >= bottom
            throw ValueError("Pointer endpoint is outside the virtual desktop")
    hwnd := AcuActivate(target)
    AcuCheckPointerTarget(hwnd, x1, y1)
    AcuCheckPointerTarget(hwnd, x2, y2)
    previousMode := A_SendMode
    previousDelay := A_MouseDelay
    held := false
    release := (*) => held ? Click("Up") : 0
    OnExit release
    try {
        SendMode "Event"
        SetMouseDelay -1
        MouseMove x1, y1, 0
        Sleep 50  ; Pointer dwell before contact, not a document-ready wait.
        AcuCheckPointerTarget(hwnd, x1, y1)
        Click "Down"
        held := true
        Sleep 50
        if x1 != x2 || y1 != y2 {
            steps := Max(1, Ceil(durationMs / 15))
            loop steps {
                if !WinActive("ahk_id " hwnd)
                    throw Error("Pointer target lost activation during the drag")
                MouseMove Round(x1 + (x2 - x1) * A_Index / steps), Round(y1 + (y2 - y1) * A_Index / steps), 0
                if durationMs
                    Sleep Round(durationMs / steps)
            }
            ; Some canvas tools commit the previous distinct move. Approach again from one pixel away,
            ; leaving both the pointer and that cached sample at the authored endpoint's pixel precision.
            MouseMove x2 = left ? x2 + 1 : x2 - 1, y2, 0
            Sleep 30
            MouseMove x2, y2, 0
            Sleep 100  ; Keep contact at the endpoint before release.
        }
        if !WinActive("ahk_id " hwnd)
            throw Error("Pointer target lost activation before release")
        Click "Up"
        held := false
        Sleep 50
    } finally {
        if held
            Click "Up"
        OnExit release, 0
        SetMouseDelay previousDelay
        SendMode previousMode
    }
}



; Refuse stale coordinates that would press another window; child controls and windows owned by this target are valid.
AcuCheckPointerTarget(hwnd, x, y) {
    if !WinActive("ahk_id " hwnd)
        throw Error("Pointer target lost activation")
    point := Buffer(8)
    NumPut "int", x, "int", y, point
    receiver := DllCall("WindowFromPoint", "int64", NumGet(point, 0, "int64"), "ptr")
    root := receiver ? DllCall("GetAncestor", "ptr", receiver, "uint", 2, "ptr") : 0
    if !root || (root != hwnd && DllCall("GetAncestor", "ptr", root, "uint", 3, "ptr") != hwnd)
        throw Error("Pointer target does not own coordinate " x "," y)
}
