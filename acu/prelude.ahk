; ACU prelude. acu/run.py injects this ahead of every agent script with AutoHotkey's /include switch,
; so the agent writes plain AutoHotkey v2 and never sees this boilerplate. It provides:
;   - screen coordinates and per-monitor-v2 DPI awareness, so screenshot pixels are click coordinates
;   - no injected delays, so a script occupies the desktop for as short a time as possible
;   - runtime errors printed to stderr with exit code 1, and load-time warnings printed to stdout, never a dialog
;   - cursor position and foreground left at the script's last action, so hover states survive between runs
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

; Consume only the two launcher-owned arguments; every later argument belongs to the script.
if (A_Args.Length < 2 || SubStr(A_Args[1], 1, 10) != "--acu-out=" || SubStr(A_Args[2], 1, 11) != "--acu-home=")
    ExitApp 3
AcuRedirectOutput(SubStr(A_Args.RemoveAt(1), 11))
EnvSet "ACU_HOME", SubStr(A_Args.RemoveAt(1), 12)
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
AcuInstallKeyboardGuard()

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
; Launch and wait

; Starts a program, allows startup windows up to 500 ms to settle within the timeout, and returns one new match.
; Existing windows are never selected. Persistent ambiguity reports every candidate rather than guessing.
AcuLaunch(command, winTitle, timeoutMs := 10000) {
    existing := Map()
    detection := A_DetectHiddenWindows
    DetectHiddenWindows true
    try {
        for hwnd in WinGetList()
            existing[hwnd] := true
    } finally
        DetectHiddenWindows detection
    candidates() {
        local matches := []
        for hwnd in WinGetList(winTitle)
            if !existing.Has(hwnd)
                matches.Push(hwnd)
        return matches
    }
    Run command
    deadline := A_TickCount + timeoutMs
    settleMs := Min(500, Max(0, timeoutMs // 3))
    quietMs := Min(150, settleMs)
    firstSeen := 0, stableSince := 0, previous := ""
    loop {
        found := candidates()
        now := A_TickCount
        key := ""
        for hwnd in found
            key .= hwnd "|"
        if (key != previous) {
            previous := key
            stableSince := now
        }
        if (found.Length && !firstSeen)
            firstSeen := now
        if (found.Length = 1 && now - firstSeen >= settleMs && now - stableSince >= quietMs) {
            elements := AcuTreeSettle(found[1], Max(1, deadline - now))
            current := candidates()
            if (current.Length = 1 && current[1] = found[1]) {
                target := "ahk_id " found[1]
                FileAppend AcuSnippetMarker(found[1]), "*"
                return {hwnd: found[1], pid: WinGetPID(target), title: WinGetTitle(target), class: WinGetClass(target), process: WinGetProcessName(target), elements: elements}
            }
        }
        if (A_TickCount >= deadline) {
            if (found.Length > 1)
                throw Error(AcuLaunchAmbiguity(found, winTitle))
            if !found.Length
                throw Error("no new window matching " winTitle " appeared within " timeoutMs " ms after: " command)
            throw Error("new window matching " winTitle " did not settle within " timeoutMs " ms")
        }
        Sleep Min(50, Max(1, deadline - A_TickCount))
    }
}

; Identifies the content owner for discovery. Store-app frames host a child window in the app's process.
; Keep the returned launch metadata about the top-level window unchanged. Discovery never fails the caller:
; a window whose owner cannot be identified (a suspended store app, a closed window) gets no marker.
AcuSnippetMarker(hwnd) {
    try {
        exe := WinGetProcessName(hwnd)
        if (exe = "ApplicationFrameHost.exe") {
            owners := Map()
            for child in WinGetControlsHwnd(hwnd) {
                try childExe := WinGetProcessName(child)
                catch
                    continue
                if (childExe != "ApplicationFrameHost.exe")
                    owners[childExe] := true
            }
            if (owners.Count != 1)
                return ""
            for name in owners
                exe := name
        }
        return "[acu:snippets] " exe "`n"
    }
    return ""
}

; Formats the observed candidates in a failed launch so the next look can select by identity.
AcuLaunchAmbiguity(found, winTitle) {
    text := found.Length " new windows match " winTitle "; select by observed title and class"
    for hwnd in found {
        target := "ahk_id " hwnd
        try
            text .= "`n  hwnd=" hwnd " title=" WinGetTitle(target) " class=" WinGetClass(target) " pid=" WinGetPID(target)
        catch as failure
            text .= "`n  hwnd=" hwnd " unavailable: " failure.Message
    }
    return text
}

; Waits until a window's control-view tree holds the same number of elements on two polls, normally 150 ms apart, or waitMs
; runs out, and returns the last count. A provider that is not answering yet counts as zero and is polled again.
AcuTreeSettle(hwnd, waitMs := 3000) {
    deadline := A_TickCount + waitMs
    previous := -1
    loop {
        try
            count := UIA.ElementFromHandle(hwnd).FindElements(UIA.TrueCondition).Length
        catch
            count := 0
        if (count > 0 && count = previous)
            return count
        if (A_TickCount >= deadline)
            return count
        previous := count
        Sleep Min(150, Max(1, deadline - A_TickCount))
    }
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

; First-party input-language guard; plain native send calls are checked before injecting keys.
#Include "%A_LineFile%\..\lib\keyboard.ahk"

; Opt-in target activation and paced input; native functions keep their existing behavior.
#Include "%A_LineFile%\..\lib\actions.ahk"

; First-party: AcuTree (lib/dump.ahk) and AcuScreenshot (lib/capture.ahk). tree.ahk and screenshot.ahk are their
; command-line wrappers, so a script can do in one run what the agent would otherwise spend a separate call on.
#Include "%A_LineFile%\..\lib\dump.ahk"
#Include "%A_LineFile%\..\lib\capture.ahk"
