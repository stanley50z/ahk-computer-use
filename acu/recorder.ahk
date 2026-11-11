; ACU recorder: a tray app that records what the user does and how the window's accessibility tree changes, so an
; agent can later learn from it which actions work in an app and which snippets are worth saving. `acu recorder`
; starts it under the UI Access build; `acu recording [folder]` prints a recording as a timeline with tree changes.
;
; Start recording (a click on the tray icon, or its menu) captures step 0: the tree of the window the user was in and
; a screenshot of that window's monitor. Each user action then joins the next step, which is captured once input has
; been quiet for a moment: SETTLE_MS after a click, scroll or hotkey, TYPING_IDLE_MS after other keys, so a typed
; series is captured once, after its last key. Mouse movement is never recorded. Stop recording captures the final
; step at once; exiting the app while recording does the same.
;
; A recording is <ACU_HOME>\recordings\<yyyyMMdd-HHmmss>\ holding steps.jsonl, one JSON object per step, and per step
; NNN-tree.txt (an AcuTree dump) and NNN.png (screenshot). Each action's target is the element's dump line, path
; included, so it matches the same element in the tree files. Failures go to <ACU_HOME>\logs\recorder.log, and
; unexpected errors also to <ACU_HOME>\crashes\<timestamp>-recorder.txt with their stack.
;
; Input comes from Raw Input on the script's own window, as in bench/input_recorder.py. There is no input hook, which
; would make ACU's SendInput fall back to SendEvent. Raw Input cannot tell the user's input from injected input.
; Usage: AutoHotkey64_UIA.exe recorder.ahk [--acu-home=<folder>] [--record]   (--record starts recording at once)
#Requires AutoHotkey v2.0
#SingleInstance Ignore
#Warn All, OutputDebug
#Warn LocalSameAsGlobal, Off
Persistent
FileEncoding "UTF-8-RAW"
DllCall("SetThreadDpiAwarenessContext", "ptr", -4, "ptr")  ; screen pixels, as in every ACU script
CoordMode "Mouse", "Screen"

#Include "%A_LineFile%\..\lib\UIA.ahk"
#Include "%A_LineFile%\..\lib\dump.ahk"
#Include "%A_LineFile%\..\lib\capture.ahk"

SETTLE_MS := 600
TYPING_IDLE_MS := 1200
TREE_MAX := 2000
SHOT_MAX := 1280
; Windows whose clicks belong to the tray icon rather than to the recorded task.
TRAY_CLASSES := Map("Shell_TrayWnd", 1, "Shell_SecondaryTrayWnd", 1, "NotifyIconOverflowWindow", 1, "TopLevelWindowForOverflowXamlIsland", 1)
JSON_TRUE := {json: "true"}

startNow := false
for arg in A_Args {
    if (SubStr(arg, 1, 11) = "--acu-home=")
        EnvSet "ACU_HOME", SubStr(arg, 12)
    else if (arg = "--record")
        startNow := true
}

rec := {on: false, stopping: false, exiting: false, capturing: false, dir: "", step: 0, startTick: 0, queue: [], pending: [], open: Map(), due: 0
    , mods: Map("ctrl", 0, "alt", 0, "shift", 0, "win", 0), lone: 0, subject: 0, pid: DllCall("GetCurrentProcessId", "uint")}

OnError RecorderCrash
OnExit RecorderExit
OnMessage 0x00FF, OnRawInput  ; WM_INPUT
ICON_IDLE := DotIcon(0x909090), ICON_RECORDING := DotIcon(0x2020E0)
A_TrayMenu.Delete()
A_TrayMenu.Add("Start recording", ToggleRecording)
A_TrayMenu.Add("Open recordings folder", (*) => (DirCreate(RecordingsRoot()), Run(RecordingsRoot())))
A_TrayMenu.Add()
A_TrayMenu.Add("Exit", (*) => ExitApp())
A_TrayMenu.Default := "Start recording"
A_TrayMenu.ClickCount := 1
ShowIdle()
SetTimer TrackSubject, 250
TrackSubject()
if startNow
    StartRecording()

; ---------------------------------------------------------------------------------------------------
; Recording lifecycle

; The tray's default item: starts a recording, or asks the running one to stop at its next tick.
ToggleRecording(*) {
    if !rec.on
        StartRecording()
    else
        rec.stopping := true
}

; Opens a new recording folder, starts listening for input and captures step 0.
StartRecording() {
    base := RecordingsRoot() "\" FormatTime(, "yyyyMMdd-HHmmss")
    rec.dir := base
    while DirExist(rec.dir)  ; a second recording within the same second
        rec.dir := base "-" (A_Index + 1)
    DirCreate rec.dir
    rec.on := true, rec.stopping := false, rec.step := 0, rec.queue := [], rec.pending := [], rec.open := Map(), rec.due := 0
    for name in ["ctrl", "alt", "shift", "win"]
        rec.mods[name] := 0
    rec.lone := 0
    rec.startTick := DllCall("GetTickCount", "uint")
    ; Listen before step 0 is captured, so an action taken during the capture still lands in step 1.
    RegisterRawInput(0x100, A_ScriptHwnd)  ; RIDEV_INPUTSINK: input for every window, not only ours
    A_TrayMenu.Rename("Start recording", "Stop recording")
    A_TrayMenu.Default := "Stop recording"
    TraySetIcon "HICON:*" ICON_RECORDING
    A_IconTip := "ACU recorder: recording`n" rec.dir
    Capture([])
    SetTimer Tick, 50
}

; Stops listening, drops the trailing clicks that reached the tray icon, and captures the final step.
StopRecording() {
    SetTimer Tick, 0
    RegisterRawInput(0x1, 0)  ; RIDEV_REMOVE
    ProcessQueue()
    rec.open := Map()  ; a button still held has no result to record
    while (rec.pending.Length && rec.pending[rec.pending.Length].Has("_tray"))
        rec.pending.Pop()
    Capture(rec.pending, true)
    rec.pending := [], rec.on := false
    ShowIdle()
    TrayTip "Saved " rec.step " steps to " rec.dir, "ACU recorder"
}

; Runs every 50 ms while recording. Timers never interrupt themselves, so input processing and captures happen one
; at a time here, while the WM_INPUT handler only queues events.
Tick() {
    ProcessQueue()
    if rec.stopping {
        StopRecording()
        if rec.exiting
            ExitApp
        return
    }
    ReleaseLostButtons()
    if (rec.due && A_TickCount >= rec.due && !rec.open.Count) {
        rec.due := 0
        actions := rec.pending, rec.pending := []
        Capture(actions)
    }
}

; Exit while recording stops the recording first. A capture in progress sits below this thread, so the exit waits for
; Tick to finish it and stop, rather than writing the final step over it.
RecorderExit(*) {
    if !rec.on
        return 0
    if rec.capturing {
        rec.stopping := true, rec.exiting := true
        return 1  ; cancel this exit; Tick exits after stopping
    }
    StopRecording()
    return 0
}

ShowIdle() {
    if !rec.on && A_TrayMenu.Default = "Stop recording" {
        A_TrayMenu.Rename("Stop recording", "Start recording")
        A_TrayMenu.Default := "Start recording"
    }
    TraySetIcon "HICON:*" ICON_IDLE
    A_IconTip := "ACU recorder: idle (click to record)"
}

; ---------------------------------------------------------------------------------------------------
; Capture

; Writes one step: the actions since the last capture, a screenshot of the subject window's monitor, its tree and,
; when it is the foreground window, its focused element. A failed part is recorded as an error and logged; the step is still written.
Capture(actions, final := false) {
    rec.capturing := true
    try
        CaptureStep(actions, final)
    finally
        rec.capturing := false
}

CaptureStep(actions, final) {
    name := Format("{:03}", rec.step)
    queued := rec.queue.Length
    step := Map("step", rec.step, "ms", Elapsed(), "time", FormatTime(, "yyyy-MM-ddTHH:mm:ss") "." A_MSec, "actions", actions)
    hwnd := CurrentSubject()
    if hwnd
        step["window"] := WindowInfo(hwnd)
    try {
        shot := AcuScreenshot({monitor: MonitorOf(hwnd)}, rec.dir "\" name ".png", SHOT_MAX)
        step["screenshot"] := Map("file", name ".png", "source", [shot.x, shot.y, shot.w, shot.h], "scale", Number(Round(shot.scale, 4)))
    } catch Error as failure
        step["screenshot_error"] := Logged("step " rec.step " screenshot", failure)
    if hwnd {
        try {
            FileAppend AcuTree(hwnd, {depth: 25, max: TREE_MAX}), rec.dir "\" name "-tree.txt"
            step["tree"] := name "-tree.txt"
        } catch Error as failure
            step["tree_error"] := Logged("step " rec.step " tree", failure)
        if (WinExist("A") = hwnd)  ; focus elsewhere, such as the tray flyout, says nothing about this window
            try step["focus"] := DescribeFocused(hwnd)
    } else
        step["tree_error"] := "no window to capture"
    if (rec.queue.Length > queued)
        step["input_during_capture"] := rec.queue.Length - queued
    if final
        step["final"] := JSON_TRUE
    FileAppend Json(step) "`n", rec.dir "\steps.jsonl"
    rec.step++
}

; Remembers the last foreground window that belongs to the task, so clicking the tray icon does not make the taskbar
; the subject of a capture. Runs on a timer whether or not a recording is on.
TrackSubject() {
    hwnd := WinExist("A")
    if IsTaskWindow(hwnd)
        rec.subject := hwnd
}

CurrentSubject() {
    hwnd := WinExist("A")
    if IsTaskWindow(hwnd)
        return rec.subject := hwnd
    return rec.subject && WinExist(rec.subject) ? rec.subject : 0
}

IsTaskWindow(hwnd) {
    try return hwnd && WinGetPID(hwnd) != rec.pid && !TRAY_CLASSES.Has(WinGetClass(hwnd))
    return false
}

; The AutoHotkey monitor number holding the window's centre, or the primary monitor.
MonitorOf(hwnd) {
    try {
        WinGetPos &x, &y, &w, &h, hwnd
        cx := x + w // 2, cy := y + h // 2
        loop MonitorGetCount() {
            MonitorGet A_Index, &left, &top, &right, &bottom
            if (cx >= left && cx < right && cy >= top && cy < bottom)
                return A_Index
        }
    }
    return MonitorGetPrimary()
}

; ---------------------------------------------------------------------------------------------------
; Input

; WM_INPUT handler. It only copies the event into the queue: the UI Automation calls that interpret it can pump
; messages, and a handler that is still running is not called again, so a slow handler would lose events.
OnRawInput(wParam, lParam, *) {
    static data := Buffer(64), size := Buffer(4)
    static buttons := [[0x1, "left", 1], [0x2, "left", 0], [0x4, "right", 1], [0x8, "right", 0], [0x10, "middle", 1]
        , [0x20, "middle", 0], [0x40, "x1", 1], [0x80, "x1", 0], [0x100, "x2", 1], [0x200, "x2", 0]]
    NumPut("uint", data.Size, size)
    if (DllCall("GetRawInputData", "ptr", lParam, "uint", 0x10000003, "ptr", data, "ptr", size, "uint", 24, "int") <= 0)
        return
    type := NumGet(data, 0, "uint")
    ms := (DllCall("GetMessageTime", "uint") - rec.startTick) & 0xFFFFFFFF
    pos := DllCall("GetMessagePos", "uint")
    x := pos & 0xFFFF, y := pos >> 16
    x := x >= 0x8000 ? x - 0x10000 : x, y := y >= 0x8000 ? y - 0x10000 : y
    if (type = 0) {  ; RIM_TYPEMOUSE: button and wheel bits; a pure move has none and is ignored
        flags := NumGet(data, 28, "ushort")
        if !flags
            return
        for entry in buttons
            if (flags & entry[1])
                rec.queue.Push({kind: "button", button: entry[2], down: entry[3], x: x, y: y, ms: ms})
        delta := NumGet(data, 30, "short")
        if (flags & 0x400)
            rec.queue.Push({kind: "wheel", axis: "vertical", delta: delta, x: x, y: y, ms: ms})
        if (flags & 0x800)
            rec.queue.Push({kind: "wheel", axis: "horizontal", delta: delta, x: x, y: y, ms: ms})
    } else if (type = 1)  ; RIM_TYPEKEYBOARD
        rec.queue.Push({kind: "key", scan: NumGet(data, 24, "ushort"), down: !(NumGet(data, 26, "ushort") & 1)
            , vk: NumGet(data, 30, "ushort"), ms: ms})
}

; Registers or removes the mouse and keyboard Raw Input devices for hwnd.
RegisterRawInput(flags, hwnd) {
    devices := Buffer(32, 0)
    for index, usage in [2, 6]  ; generic desktop: mouse, keyboard
        NumPut("ushort", 1, "ushort", usage, "uint", flags, "ptr", hwnd, devices, (index - 1) * 16)
    if !DllCall("RegisterRawInputDevices", "ptr", devices, "uint", 2, "uint", 16)
        throw OSError(A_LastError, -1, "RegisterRawInputDevices")
}

ProcessQueue() {
    while rec.queue.Length {
        event := rec.queue.RemoveAt(1)
        switch event.kind {
            case "button": OnButton(event)
            case "wheel": OnWheel(event)
            case "key": OnKey(event)
        }
    }
}

OnButton(event) {
    rec.lone := 0
    if event.down {
        rec.open[event.button] := {x: event.x, y: event.y, ms: event.ms, target: DescribeAt(event.x, event.y), upLastTick: false}
        return
    }
    if !rec.open.Has(event.button)  ; the release of the click that started the recording
        return
    start := rec.open.Delete(event.button)
    if (Abs(event.x - start.x) > SysGet(68) || Abs(event.y - start.y) > SysGet(69)) {  ; SM_CXDRAG, SM_CYDRAG
        AddAction(Map("kind", "drag", "button", event.button, "ms", start.ms, "from", [start.x, start.y], "to", [event.x, event.y]
            , "target", start.target, "drop", DescribeAt(event.x, event.y)), SETTLE_MS)
        return
    }
    AddClick(event.button, start)
}

; A click, or the second click of a double click when it follows the first within the system's time and distance.
AddClick(button, start) {
    last := LastAction()
    if (last && last["kind"] = "click" && last["button"] = button && start.ms - last["ms"] <= DllCall("GetDoubleClickTime", "uint")
        && Abs(start.x - last["x"]) <= SysGet(36) && Abs(start.y - last["y"]) <= SysGet(37)) {
        last["count"]++
        rec.due := A_TickCount + SETTLE_MS
        return
    }
    AddAction(Map("kind", "click", "button", button, "count", 1, "ms", start.ms, "x", start.x, "y", start.y, "target", start.target), SETTLE_MS)
}

; A drag whose button was released while its WM_INPUT was lost counts as a click where it was pressed. Tick calls it
; after ProcessQueue. A release during that Tick shows in GetAsyncKeyState before AutoHotkey's next message check
; dispatches its WM_INPUT, so a button counts as lost only when it is up, and its press still unmatched, at two
; consecutive ticks; by the second, a late release has been queued and processed.
ReleaseLostButtons() {
    static keys := Map("left", 1, "right", 2, "middle", 4, "x1", 5, "x2", 6)
    for button, start in rec.open.Clone()
        if (DllCall("GetAsyncKeyState", "int", keys[button], "short") & 0x8000)
            start.upLastTick := false
        else if start.upLastTick {
            rec.open.Delete(button)
            AddClick(button, start)
        } else
            start.upLastTick := true
}

; Consecutive wheel notches on one axis add up into one scroll.
OnWheel(event) {
    rec.lone := 0
    last := LastAction()
    if (last && last["kind"] = "scroll" && last["axis"] = event.axis) {
        last["delta"] += event.delta
        rec.due := A_TickCount + SETTLE_MS
        return
    }
    AddAction(Map("kind", "scroll", "axis", event.axis, "delta", event.delta, "ms", event.ms, "x", event.x, "y", event.y
        , "target", DescribeAt(event.x, event.y)), SETTLE_MS)
}

; Sorts a key press into a hotkey (Ctrl, Alt or Win held), typed text (a key that produces a character, and
; Backspace), or another key such as Enter, Tab or an arrow. A Win or Alt press released on its own is a key too.
OnKey(event) {
    static modifiers := Map(0x10, "shift", 0x11, "ctrl", 0x12, "alt", 0x5B, "win", 0x5C, "win")
    vk := event.vk
    if (vk = 0xFF || vk = 0)  ; part of an escaped scan code sequence
        return
    if modifiers.Has(vk) {
        name := modifiers[vk]
        if event.down {
            if !rec.mods[name]
                rec.lone := vk
            rec.mods[name] := 1
        } else {
            rec.mods[name] := 0
            if (rec.lone = vk && (name = "win" || name = "alt"))
                AddKey("key", "{" GetKeyName(Format("vk{:x}", vk)) "}", event.ms)
            rec.lone := 0
        }
        return
    }
    if !event.down
        return
    rec.lone := 0
    mods := rec.mods
    char := KeyChar(vk, event.scan)
    altGr := mods["ctrl"] && mods["alt"] && !mods["win"] && char != "" && Ord(char) >= 0x20
    if (!altGr && (mods["ctrl"] || mods["alt"] || mods["win"])) {
        AddKey("hotkey", (mods["ctrl"] ? "^" : "") (mods["alt"] ? "!" : "") (mods["shift"] ? "+" : "") (mods["win"] ? "#" : "") KeyText(vk), event.ms)
        return
    }
    if (vk = 0x08) {
        AddTyped("", event.ms)
        return
    }
    if (char != "" && Ord(char) >= 0x20 && char != Chr(0x7F)) {
        AddTyped(char, event.ms)
        return
    }
    AddKey("key", (mods["shift"] ? "+" : "") KeyText(vk), event.ms)
}

; The character a key produces in the foreground window's keyboard layout with the tracked modifiers, or "" when it
; produces none (a dead key, an arrow). Flag 4 leaves the layout's dead-key state alone.
KeyChar(vk, scan) {
    static state := Buffer(256, 0), out := Buffer(16)
    NumPut("uchar", rec.mods["shift"] ? 0x80 : 0, state, 0x10)
    NumPut("uchar", rec.mods["ctrl"] ? 0x80 : 0, state, 0x11)
    NumPut("uchar", rec.mods["alt"] ? 0x80 : 0, state, 0x12)
    NumPut("uchar", DllCall("GetKeyState", "int", 0x14, "short") & 1, state, 0x14)  ; Caps Lock toggle
    thread := DllCall("GetWindowThreadProcessId", "ptr", WinExist("A"), "ptr", 0, "uint")
    layout := DllCall("GetKeyboardLayout", "uint", thread, "ptr")
    count := DllCall("ToUnicodeEx", "uint", vk, "uint", scan, "ptr", state, "ptr", out, "int", 8, "uint", 4, "ptr", layout, "int")
    return count >= 1 ? StrGet(out, count, "UTF-16") : ""
}

; A key as AutoHotkey Send writes it: a single character as itself, anything else in braces.
KeyText(vk) {
    name := GetKeyName(Format("vk{:x}", vk))
    if (name = "")
        name := Format("vk{:x}", vk)
    return StrLen(name) = 1 ? StrLower(name) : "{" name "}"
}

; Repeated presses of one key, such as an arrow, count as one action with a count.
AddKey(kind, keys, ms) {
    last := LastAction()
    if (last && last["kind"] = kind && last["keys"] = keys) {
        last["count"]++
        rec.due := A_TickCount + (kind = "hotkey" ? SETTLE_MS : TYPING_IDLE_MS)
        return
    }
    AddAction(Map("kind", kind, "keys", keys, "count", 1, "ms", ms, "target", DescribeFocused()), kind = "hotkey" ? SETTLE_MS : TYPING_IDLE_MS)
}

; Typed characters join the step's current typing into one text; Backspace ("") removes the last one, or counts as
; erasing text that was there before. A password field's text is never stored, only its length.
AddTyped(char, ms) {
    last := LastAction()
    if !(last && last["kind"] = "type") {
        target := DescribeFocused()
        ; _text holds the text in memory; a password field writes only its length, as Json skips names starting with _.
        last := Map("kind", "type", "_text", "", "backspaces", 0, "ms", ms, "target", target)
        if target.Has("_password")
            last["masked"] := JSON_TRUE
        AddAction(last, TYPING_IDLE_MS)
    }
    if (char != "")
        last["_text"] .= char
    else if StrLen(last["_text"])
        last["_text"] := SubStr(last["_text"], 1, -1)
    else
        last["backspaces"]++
    if last.Has("masked")
        last["length"] := StrLen(last["_text"])
    else
        last["text"] := last["_text"]
    rec.due := A_TickCount + TYPING_IDLE_MS
}

AddAction(action, idleMs) {
    if action["target"].Has("_tray")
        action["_tray"] := true  ; does not end a step by itself; dropped if it is the last thing before Stop
    else
        rec.due := A_TickCount + idleMs
    rec.pending.Push(action)
}

LastAction() {
    return rec.pending.Length ? rec.pending[rec.pending.Length] : ""
}

Elapsed() {
    return (DllCall("GetTickCount", "uint") - rec.startTick) & 0xFFFFFFFF
}

; ---------------------------------------------------------------------------------------------------
; Elements

; The control-view element under a screen point, described against its top-level window.
DescribeAt(x, y) {
    root := DllCall("GetAncestor", "ptr", DllCall("WindowFromPoint", "int64", (y << 32) | (x & 0xFFFFFFFF), "ptr"), "uint", 2, "ptr")
    try
        return Describe(UIA.ElementFromPoint(x, y), root)
    catch Error as failure {
        target := Map("window", WindowInfo(root), "error", Logged("element at " x "," y, failure))
        if !IsTaskWindow(root)
            target["_tray"] := 1
        return target
    }
}

; The element with keyboard focus, described against the foreground window (or hwnd).
DescribeFocused(hwnd := 0) {
    root := hwnd ? hwnd : WinExist("A")
    try
        return Describe(UIA.GetFocusedElement(), root)
    catch Error as failure
        return Map("window", WindowInfo(root), "error", Logged("focused element", failure))
}

; {line, window}: line is the element's dump line, starting with its path in root's dump ("?" when the walk up
; does not reach root), so it can be found in the step's tree file. Tray-area targets are marked for StopRecording.
Describe(element, root) {
    static request := 0
    if !request {
        properties := AcuTreeProperties().Clone()
        properties.Push("IsPassword")
        request := UIA.CreateCacheRequest(properties, , UIA.TreeScope.Element)
    }
    walker := UIA.ControlViewWalker
    if (normal := walker.TryNormalizeElement(element))
        element := normal
    path := ElementPath(element, root)
    element := element.BuildUpdatedCache(request)
    target := Map("line", AcuTreeDescribe(element, path = "" ? "?" : path), "window", WindowInfo(root))
    if element.GetCachedPropertyValue(UIA.Property.IsPassword)
        target["_password"] := 1
    if !IsTaskWindow(root)
        target["_tray"] := 1
    return target
}

; The element's comma-separated path in the control view of root, as AcuTree numbers it, or "" when the walk does
; not reach root or takes more than 500 tree calls.
ElementPath(element, root) {
    if !root
        return ""
    walker := UIA.ControlViewWalker
    rootElement := UIA.ElementFromHandle(root, , 0)
    indexes := [], calls := 0
    while !UIA.CompareElements(element, rootElement) {
        index := 1, sibling := element
        while (sibling := walker.TryGetPreviousSiblingElement(sibling)) {
            index++
            if (++calls > 500)
                return ""
        }
        indexes.InsertAt(1, index)
        if !(element := walker.TryGetParentElement(element)) || (++calls > 500)
            return ""
    }
    path := ""
    for index in indexes
        path .= (path = "" ? "" : ",") index
    return path
}

WindowInfo(hwnd) {
    info := Map("hwnd", hwnd)
    try info["title"] := WinGetTitle(hwnd), info["exe"] := WinGetProcessName(hwnd), info["class"] := WinGetClass(hwnd)
    return info
}

; ---------------------------------------------------------------------------------------------------
; Files and diagnostics

RecordingsRoot() {
    home := EnvGet("ACU_HOME")
    return (home != "" ? home : EnvGet("LOCALAPPDATA") "\ACU") "\recordings"
}

LogDir(name) {
    home := EnvGet("ACU_HOME")
    dir := (home != "" ? home : EnvGet("LOCALAPPDATA") "\ACU") "\" name
    if !DirExist(dir)
        DirCreate dir
    return dir
}

; Appends a handled failure to recorder.log and returns its message for the step record.
Logged(context, failure) {
    text := FormatTime(, "yyyy-MM-dd HH:mm:ss") " " context ": " failure.Message (failure.Extra != "" ? " (" failure.Extra ")" : "")
    try FileAppend text "`n" failure.Stack "`n", LogDir("logs") "\recorder.log"
    return failure.Message
}

; Writes an unexpected error to a crash report and keeps the recorder running; the failed tick or event is lost.
RecorderCrash(thrown, mode) {
    text := thrown is Error
        ? thrown.Message "`n" (thrown.Extra != "" ? "Specifically: " thrown.Extra "`n" : "") "at " thrown.File ":" thrown.Line "`n" thrown.Stack
        : String(thrown)
    try {
        path := LogDir("crashes") "\" FormatTime(, "yyyyMMdd-HHmmss") "-" A_MSec "-recorder.txt"
        FileAppend "mode=" mode "`nrecording=" rec.dir "`n" text "`n", path
        FileAppend FormatTime(, "yyyy-MM-dd HH:mm:ss") " crash: " path "`n", LogDir("logs") "\recorder.log"
        TrayTip "Recorder error, see " path, "ACU recorder", 3
    }
    return 1
}

; A minimal JSON encoder for Maps, Arrays, numbers and strings. Map keys starting with _ are internal and skipped;
; JSON_TRUE writes true.
Json(value) {
    if (value is Map) {
        out := ""
        for key, item in value
            if (SubStr(key, 1, 1) != "_")
                out .= (out = "" ? "" : ",") JsonString(String(key)) ":" Json(item)
        return "{" out "}"
    }
    if (value is Array) {
        out := ""
        for item in value
            out .= (A_Index = 1 ? "" : ",") Json(item)
        return "[" out "]"
    }
    if IsObject(value)
        return value.json
    if (value is Number)
        return String(value)
    return JsonString(value)
}

JsonString(text) {
    text := StrReplace(StrReplace(text, "\", "\\"), '"', '\"')
    text := StrReplace(StrReplace(StrReplace(text, "`n", "\n"), "`r", "\r"), "`t", "\t")
    loop 31
        if InStr(text, Chr(A_Index))
            text := StrReplace(text, Chr(A_Index), Format("\u{:04x}", A_Index))
    return '"' text '"'
}

; A round tray icon of one colour (0xBBGGRR), drawn with GDI so the recorder ships no image files.
DotIcon(bgr) {
    size := 32
    screen := DllCall("GetDC", "ptr", 0, "ptr")
    dc := DllCall("CreateCompatibleDC", "ptr", screen, "ptr")
    color := DllCall("CreateCompatibleBitmap", "ptr", screen, "int", size, "int", size, "ptr")
    mask := DllCall("CreateBitmap", "int", size, "int", size, "uint", 1, "uint", 1, "ptr", 0, "ptr")
    brush := DllCall("CreateSolidBrush", "uint", bgr, "ptr")
    nullPen := DllCall("GetStockObject", "int", 8, "ptr")
    oldPen := DllCall("SelectObject", "ptr", dc, "ptr", nullPen, "ptr")
    oldBitmap := DllCall("SelectObject", "ptr", dc, "ptr", color, "ptr")
    DllCall("PatBlt", "ptr", dc, "int", 0, "int", 0, "int", size, "int", size, "uint", 0x42)  ; BLACKNESS
    oldBrush := DllCall("SelectObject", "ptr", dc, "ptr", brush, "ptr")
    DllCall("Ellipse", "ptr", dc, "int", 3, "int", 3, "int", size - 2, "int", size - 2)
    DllCall("SelectObject", "ptr", dc, "ptr", mask, "ptr")
    DllCall("PatBlt", "ptr", dc, "int", 0, "int", 0, "int", size, "int", size, "uint", 0xFF0062)  ; WHITENESS: transparent
    DllCall("SelectObject", "ptr", dc, "ptr", DllCall("GetStockObject", "int", 4, "ptr"), "ptr")  ; BLACK_BRUSH: opaque
    DllCall("Ellipse", "ptr", dc, "int", 3, "int", 3, "int", size - 2, "int", size - 2)
    DllCall("SelectObject", "ptr", dc, "ptr", oldBrush, "ptr")
    DllCall("SelectObject", "ptr", dc, "ptr", oldBitmap, "ptr")
    DllCall("SelectObject", "ptr", dc, "ptr", oldPen, "ptr")
    info := Buffer(32, 0)  ; ICONINFO
    NumPut("int", 1, info, 0)
    NumPut("ptr", mask, info, 16)
    NumPut("ptr", color, info, 24)
    icon := DllCall("CreateIconIndirect", "ptr", info, "ptr")
    DllCall("DeleteObject", "ptr", brush)
    DllCall("DeleteObject", "ptr", mask)
    DllCall("DeleteObject", "ptr", color)
    DllCall("DeleteDC", "ptr", dc)
    DllCall("ReleaseDC", "ptr", 0, "ptr", screen)
    return icon
}
