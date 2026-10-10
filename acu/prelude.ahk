; ACU prelude. acu/run.py injects this ahead of every agent script with AutoHotkey's /include switch,
; so the agent writes plain AutoHotkey v2 and never sees this boilerplate. It provides:
;   - screen coordinates and per-monitor-v2 DPI awareness, so screenshot pixels are click coordinates
;   - no injected delays, so a script occupies the desktop for as short a time as possible
;   - runtime errors printed to stderr with exit code 1, and load-time warnings printed to stdout, never a dialog
;   - the user's foreground window and cursor restored when the script ends, unless the user took over
;     or the script called AcuKeepForeground() because its job was to leave a window showing
;   - UI Automation through the UIA class, so a script can find a control by name and act on it
;   - AcuLaunch, which starts a program and returns the one new window it opened, and AcuWaitUntil, an observed
;     wait that replaces a fixed Sleep
;   - AcuTree and AcuScreenshot, the same dump and capture that tree.ahk and screenshot.ahk print, callable from
;     inside an action chain so looking does not cost a separate run
; Scripts run under AutoHotkey's UI Access build, which can see and drive elevated windows. Windows starts such a
; program only through ShellExecute, with no standard output and without the launcher's environment, so the launcher
; passes an output file and ACU_HOME as leading arguments: the prelude sends stdout and stderr to the file, sets
; ACU_HOME, and strips both. Load-time errors are caught by the launcher's validate pass.
#Requires AutoHotkey v2.0
#NoTrayIcon
#SingleInstance Off
; A load-time warning, such as a call to a function that does not exist, is a modal dialog by default. It
; appears before the script has a main window, so the launcher's close request cannot reach it. Print it instead.
; LocalSameAsGlobal stays off, as it is by default: a script that names a global like one of the prelude's
; locals would otherwise print a warning that is not about the script.
#Warn All, StdOut
#Warn LocalSameAsGlobal, Off

FileEncoding "UTF-8-RAW"

while (A_Args.Length && SubStr(A_Args[1], 1, 6) = "--acu-") {
    if (SubStr(A_Args[1], 1, 10) = "--acu-out=")
        AcuRedirectOutput(SubStr(A_Args[1], 11))
    else if (SubStr(A_Args[1], 1, 11) = "--acu-home=")
        EnvSet "ACU_HOME", SubStr(A_Args[1], 12)
    A_Args.RemoveAt(1)
}
; The launcher's close request comes from a process with a lower integrity level than a UI Access program, which
; Windows would otherwise filter out. Let WM_CLOSE through so the timeout still runs the exit handler.
DllCall("ChangeWindowMessageFilterEx", "ptr", A_ScriptHwnd, "uint", 0x10, "uint", 1, "ptr", 0)

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

; Sends everything written to "*" and "**" into the launcher's output file, in order. A program the script starts
; inherits the handle, so the file is shared for deletion too; the launcher must not wait on that program. Without
; an output there is nowhere to report a failure here, so the exit code has to say it.
AcuRedirectOutput(path) {
    handle := DllCall("CreateFileW", "wstr", path, "uint", 0x40000000, "uint", 7, "ptr", 0, "uint", 4, "uint", 0x80, "ptr", 0, "ptr")
    if (handle = -1)
        ExitApp 3
    DllCall("SetStdHandle", "int", -11, "ptr", handle)
    DllCall("SetStdHandle", "int", -12, "ptr", handle)
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
    static keepForeground := false  ; set by AcuKeepForeground(): leave the foreground where the script put it
}

; For a script whose purpose is to leave an application showing. Call it anywhere; at exit the foreground
; window is left alone and only the cursor goes back.
AcuKeepForeground() {
    AcuState.keepForeground := true
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
    if !AcuState.keepForeground
        AcuRestoreForeground()
    MouseMove AcuState.entryX, AcuState.entryY
    return 0
}

; Puts the entry window back in front, unless an unrelated window came forward on its own.
AcuRestoreForeground() {
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

; ---------------------------------------------------------------------------------------------------
; Launch and wait

; Starts a program and returns the one new top-level window matching winTitle, as an object with hwnd, pid, title,
; class and process, so a script never guesses which window it opened. The windows that exist before the launch are
; snapshotted and never selected. Throws when no new matching window appears within timeoutMs, or when several do.
AcuLaunch(command, winTitle, timeoutMs := 10000) {
    existing := Map()
    for hwnd in WinGetList()
        existing[hwnd] := true
    Run command
    deadline := A_TickCount + timeoutMs
    found := []
    loop {
        found := []
        for hwnd in WinGetList(winTitle)
            if !existing.Has(hwnd)
                found.Push(hwnd)
        if (found.Length || A_TickCount >= deadline)
            break
        Sleep 50
    }
    if (found.Length = 0)
        throw Error("no new window matching " winTitle " appeared within " timeoutMs " ms after: " command)
    if (found.Length > 1)
        throw Error(found.Length " new windows match " winTitle "; list the windows and select one by its observed title and class")
    target := "ahk_id " found[1]
    return {hwnd: found[1], pid: WinGetPID(target), title: WinGetTitle(target), class: WinGetClass(target), process: WinGetProcessName(target)}
}

; Polls predicate until it returns a true value, for at most timeoutMs, and returns that value, or 0 when the time
; ran out. The observed wait that replaces a fixed Sleep: AcuWaitUntil(() => display.Name != before).
AcuWaitUntil(predicate, timeoutMs := 2000, intervalMs := 25) {
    deadline := A_TickCount + timeoutMs
    loop {
        value := predicate()
        if value
            return value
        if (A_TickCount >= deadline)
            return 0
        Sleep intervalMs
    }
}

; ---------------------------------------------------------------------------------------------------
; UI Automation

; Descolada's UIA-v2 library (MIT, see lib/UIA-LICENSE.txt). It costs about 30 ms per script and gives every
; script the accessibility tree: UIA.ElementFromHandle(target).FindElement({Type:"Button", Name:"Six"}).Invoke()
#Include "%A_LineFile%\..\lib\UIA.ahk"

; First-party: AcuTree (lib/dump.ahk) and AcuScreenshot (lib/capture.ahk). tree.ahk and screenshot.ahk are their
; command-line wrappers, so a script can do in one run what the agent would otherwise spend a separate call on.
#Include "%A_LineFile%\..\lib\dump.ahk"
#Include "%A_LineFile%\..\lib\capture.ahk"
