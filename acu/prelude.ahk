; ACU prelude. acu/run.py injects this ahead of every agent script with AutoHotkey's /include switch,
; so the agent writes plain AutoHotkey v2 and never sees this boilerplate. It provides:
;   - screen coordinates and per-monitor-v2 DPI awareness, so screenshot pixels are click coordinates
;   - no injected delays, so a script occupies the desktop for as short a time as possible
;   - runtime errors printed to stderr with exit code 1 instead of a dialog
;   - the user's foreground window and cursor restored when the script ends, unless the user took over
#Requires AutoHotkey v2.0
#NoTrayIcon
#SingleInstance Off

FileEncoding "UTF-8-RAW"

; Coordinates mean screen pixels everywhere, so the agent can use what a screenshot shows.
; Per-monitor-v2 DPI awareness keeps that true on mixed-DPI setups; AutoHotkey v2.0 is only system-aware by default.
DllCall("SetThreadDpiAwarenessContext", "ptr", -4, "ptr")
CoordMode "Mouse", "Screen"
CoordMode "Pixel", "Screen"

; Speed over ceremony: no pause between the events of a click (the SendEvent fallback inserts one) and no cursor animation.
SetMouseDelay -1
SetDefaultMouseSpeed 0

OnError AcuReportError
AcuSnapshotEntry()
OnExit AcuRestore

; ---------------------------------------------------------------------------------------------------
; Errors

; Prints a runtime error to stderr and exits with code 1, so the agent reads the message and never meets a dialog.
AcuReportError(thrown, mode) {
    if !(thrown is Error) {
        AcuNote("error: " String(thrown))
        ExitApp 1
    }
    text := "error: " thrown.Message "`n"
    if (thrown.Extra != "")
        text .= "  Specifically: " thrown.Extra "`n"
    text .= "  at " thrown.File ":" thrown.Line (thrown.What != "" ? " in " thrown.What : "")
    if (thrown.Stack != "")
        text .= "`n" thrown.Stack
    AcuNote(text)
    ExitApp 1
}

; One line of prelude output on stderr, prefixed so the agent can tell it from the script's own output.
AcuNote(text) {
    FileAppend "[acu] " text "`n", "**"
}

; ---------------------------------------------------------------------------------------------------
; Restore

; What the desktop looked like when the script started, and what ACU has done to it since.
class AcuState {
    static entryWindow := 0
    static entryX := 0
    static entryY := 0
    static placedX := ""     ; where ACU last put the cursor; "" until the first mouse action
    static placedY := ""
    static touched := Map()  ; process ids of the windows ACU clicked, plus the script's own
}

; Records the foreground window and cursor as they were before the script ran. Called once, at load.
AcuSnapshotEntry() {
    AcuState.entryWindow := WinExist("A")
    MouseGetPos &x, &y
    AcuState.entryX := x
    AcuState.entryY := y
    AcuState.touched[DllCall("GetCurrentProcessId")] := true
}

; Runs at every exit: normal, error, and the launcher's close request. Restores the entry foreground
; window and cursor unless the evidence says the user took over or an unrelated window came forward.
AcuRestore(reason, code) {
    CoordMode "Mouse", "Screen"  ; the script may have switched modes; the snapshot is in screen pixels
    MouseGetPos &x, &y
    AcuExpectedCursor(&expectedX, &expectedY)
    if (x != expectedX || y != expectedY) {
        AcuNote("restore skipped: cursor moved by someone else")
        return 0
    }
    try {
        current := WinExist("A")
        if (current && current != AcuState.entryWindow) {
            if (AcuState.placedX != "" && !AcuState.touched.Has(WinGetPID(current)))
                AcuNote("foreground left on " WinGetProcessName(current) " (ACU never clicked it)")
            else if WinExist(AcuState.entryWindow)
                WinActivate AcuState.entryWindow
        }
    } catch as failure {
        AcuNote("restore failed: " failure.Message)
    }
    MouseMove AcuState.entryX, AcuState.entryY
    return 0
}

; Where the cursor is if nobody but ACU has touched it: the last place ACU put it, else where it was at entry.
AcuExpectedCursor(&x, &y) {
    x := AcuState.placedX != "" ? AcuState.placedX : AcuState.entryX
    y := AcuState.placedY != "" ? AcuState.placedY : AcuState.entryY
}

; ---------------------------------------------------------------------------------------------------
; Mouse tracking

; The mouse functions are shadowed so the prelude learns where ACU put the cursor and which window it
; clicked, without installing a hook. Each delegates to Send's {Click} syntax, which shares the built-in
; Click's option parser, so agent scripts behave as the AutoHotkey documentation describes.
Click(options*) {
    joined := ""
    for option in options
        joined .= " " option
    AcuTrackMouse(joined)
    Send "{Click" joined "}"
}

MouseMove(x, y, speed := "", relative := "") {
    options := x " " y " 0" AcuRelWord(relative)
    AcuTrackMouse(options)
    Send "{Click " options "}"
}

MouseClick(button := "Left", x := "", y := "", count := 1, speed := "", downOrUp := "", relative := "") {
    coords := (x != "" && y != "") ? x " " y : ""  ; a lone number would otherwise be read as X with count as Y
    options := button " " coords " " count " " downOrUp AcuRelWord(relative)
    AcuTrackMouse(options)
    Send "{Click " options "}"
}

MouseClickDrag(button, x1, y1, x2, y2, speed := "", relative := "") {
    rel := AcuRelWord(relative)
    AcuTrackMouse(x1 " " y1 rel)
    Send "{Click " x1 " " y1 " " button " D" rel "}"
    AcuTrackMouse(x2 " " y2 rel)
    Send "{Click " x2 " " y2 " 0" rel "}"
    Send "{Click " button " U}"
}

; The {Click} word for a mouse function's Relative parameter. A bare R would mean the right button.
AcuRelWord(relative) {
    return relative = "R" ? " Rel" : ""
}

; Records where a Click-style option string leaves the cursor and which process owns the window there.
; Mirrors ParseClickOptions: the first two numbers are X and Y, a lone number is a repeat count.
; Assumes the prelude's screen coordinate mode; a script that switches CoordMode defeats takeover detection.
AcuTrackMouse(options) {
    numbers := []
    relative := false
    for word in StrSplit(options, [" ", ",", "`t"]) {
        if (word = "")
            continue
        if IsNumber(word)
            numbers.Push(Integer(Float(word)))
        else if (word = "Rel" || word = "Relative")
            relative := true
    }
    if (numbers.Length < 2)
        return
    x := numbers[1]
    y := numbers[2]
    if relative {
        AcuExpectedCursor(&baseX, &baseY)
        x += baseX
        y += baseY
    }
    AcuState.placedX := x
    AcuState.placedY := y
    AcuState.touched[AcuProcessAt(x, y)] := true
}

; Process id of the top-level window under a screen point, 0 if there is none.
AcuProcessAt(x, y) {
    hwnd := DllCall("WindowFromPoint", "int64", (x & 0xFFFFFFFF) | (y << 32), "ptr")
    if !hwnd
        return 0
    root := DllCall("GetAncestor", "ptr", hwnd, "uint", 2, "ptr")
    pid := 0
    DllCall("GetWindowThreadProcessId", "ptr", root, "uint*", &pid)
    return pid
}
