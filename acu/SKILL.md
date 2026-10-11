---
name: acu
description: Operate this Windows desktop through AutoHotkey v2 script files run by ACU. Write one short action chain, run it, and check the observed result. Use when asked to click, type into, open, read, or drive a Windows application or the desktop on this machine, or when a task names ACU or AutoHotkey.
---

# ACU

You supply the intelligence, ACU supplies the hands. Every action is a whole scripted action chain in one `.ahk` file, not a tool call for every button. You write and manage the script; ACU runs it under the launcher protections and preserves the file. This file is the whole manual: nothing else needs reading before your first script.

## Call ACU

Call the installed CLI through your shell tool: `acu run "<absolute script.ahk>" [--timeout 30] [-- arguments]`. Arguments after `--` reach the script in `A_Args`. There are no script IDs, inline-code input, or separate inspection operations. The bundled `tree.ahk` and `screenshot.ahk` can be named without a path: `acu run tree.ahk -- …`. If `acu` is not on PATH, report the installation prerequisite; setup is in the repository's `README.md` (resolve this skill directory's link and take its parent).

A model turn costs seconds; a file write or an `acu run` costs milliseconds to a few seconds. Spend turns on looking and deciding, not on ceremony:

- Write a script and run it in **one shell call**: in bash, a quoted heredoc followed by `acu run`; in PowerShell, `Set-Content` with a here-string followed by `acu run`. Do not issue the write and the run as two tool calls in one response: harnesses may run them in parallel, so the run can start before the file exists.
- Fold the first look into the launch script. After `AcuLaunch`, print the controls you will need through the `UIA` class instead of spending a turn on a separate tree dump:

```bash
cat > "C:/work/launch.ahk" <<'EOF'
window := AcuLaunch("calc.exe", "Calculator")
FileAppend "hwnd=" window.hwnd " pid=" window.pid " class=" window.class " process=" window.process "`n", "*"
root := UIA.ElementFromHandle(window.hwnd)
for element in root.FindElements({Type:"Button"})
    FileAppend element.Name " id=" element.AutomationId "`n", "*"
EOF
acu run "C:/work/launch.ahk"
```

- Chain every step whose intermediate state you can predict into one script; look again only when you cannot. Looking is also available inside a script: `AcuTree(target, {find: "Save"})` returns the dump as text, and `AcuScreenshot({app: target}, outPath)` saves the picture and returns its mapping, so an action script can end with the evidence it needs instead of spending another turn on `tree.ahk` or `screenshot.ahk`.

## The loop

Look, act, check. Repeat until the user's postcondition is observed. The task is done when a window state, printed text, or screenshot shows the result, never because an execution exited zero. Use only the desktop actions the user authorized.

### 1. Look

Find the window before its controls. To open a program, call `AcuLaunch(command, winTitle, timeoutMs := 10000)`: it snapshots the existing top-level windows, runs the command, waits for exactly one new window matching `winTitle` (any AutoHotkey WinTitle, such as `"Calculator"` or `"ahk_class Notepad++"`), waits for that window's accessibility tree to stop growing, and returns an object with `hwnd`, `pid`, `title`, `class`, `process`, and `elements`, the tree size it settled at. A dump taken right after it sees the window's controls, not just its frame. Existing windows are never selected. It throws when no new window appears in time or several do; then list the windows and choose by observed title and class instead of guessing:

```autohotkey
for hwnd in WinGetList() {
    target := "ahk_id " hwnd
    FileAppend hwnd " | " WinGetTitle(target) " | " WinGetClass(target) " | " WinGetProcessName(target) "`n", "*"
}
```

Match on title or class, not on process name: Calculator's app process is `CalculatorApp.exe` while its top-level window belongs to `ApplicationFrameHost.exe`. Retain the exact handle (`ahk_id <hwnd>`) for the tree, waits, activation, and cleanup; preserve every pre-existing window. If no unique intended window can be identified, report that ambiguity instead of acting on a guess. A store app may restore previous documents, so check its content before typing.

Skip the tree dump when you already know the window and control. Otherwise run the ordinary `tree.ahk` script through the same CLI, passing its target and flags after `--`:

```
acu run tree.ahk -- "<WinTitle or ahk_id>" [--find <text>] [--type <Type>] [--depth 25] [--max 300]
```

Inside a script the same dump is `AcuTree(target, {find: "…", type: "Button", depth: 25, max: 300})`, returned as text. A browser or Electron window exists before its tree answers; the dump waits up to five seconds for it, then reports that the application may still be starting. The whole subtree is fetched before filtering; `--find` keeps elements whose name or id contains the text, `--type` keeps one control type. Each line gives a control-view path, type, name, id, full value, screen bounds, the actions the element supports (`invoke toggle value select expand scroll`; `value` means writable), and its state (`disabled offscreen focused selected`). Quoted fields are AutoHotkey string contents: paste them between quotes as printed. Check `truncated=` before concluding a control is absent; narrow the query or raise the limit. Names are screen-reader text, not the painted text: Calculator's expression reads `Minus (` where the screen shows a minus sign. Record what the tree says verbatim, and take a screenshot only when the task needs the visual text.

Run `screenshot.ahk` for an empty or nameless tree, canvas content, or visual confirmation:

```
acu run screenshot.ahk -- fullscreen [monitor]
acu run screenshot.ahk -- app "<WinTitle or ahk_id>"
acu run screenshot.ahk -- custom <x1> <y1> <x2> <y2>
```

Inside a script: `shot := AcuScreenshot({app: target}, outPath)`, or `{monitor: 2}`, or `{rect: [x1, y1, x2, y2]}`, with an optional third argument for the longest side; it returns `saved`, `x`, `y`, `w`, `h`, `scale`, and `text`, the same four lines the script prints. Rectangle coordinates are exclusive at the far edge. Options are `--max <pixels>` for the longest saved side (default 1280, `0` keeps full resolution) and `--out <path.png>`. The script prints `saved=`, `image=`, `source=`, and `scale=` in `output`; read the PNG separately. An image point (px,py) is the screen point (sourceX + px * scale, sourceY + py * scale). App capture never activates the window and can render a covered one; a minimized window is an error. Without `--out`, only the newest thirty managed screenshots are kept; an explicit `--out` may overwrite a file, so use only an authorized path.

### 2. Act

Write plain AutoHotkey v2: ACU supplies the prelude, screen coordinates, per-monitor DPI awareness, the `UIA` class, zero mouse delays, runtime error reporting, and exit restore. A script should finish well within the default 30-second watchdog.

Prefer named controls and semantic UI Automation actions, then element bounds, then screenshot coordinates:

```autohotkey
root := UIA.ElementFromHandle(target)
root.FindElement({Type:"Button", Name:"Six"}).Invoke()     ; by name
root.FindElement({AutomationId:"num6Button"}).Invoke()        ; by id from the dump
root.ElementFromPath("2,2,2,5,3").Invoke()                     ; by path from the dump
root.FindElement({Type:"Edit"}).Value := "text"               ; a control flagged value
```

Combine selectors or search within a parent when ids repeat. Toggle, Select, and Expand use the corresponding patterns. `element.Click()` with no argument is semantic too: it invokes, toggles, or selects. Pointer input is `element.Click("left")`, which moves the cursor to the element's center and needs the window in the foreground. Before pointer input or keys, call `WinActivate`, then `WinWaitActive(target, , 2)` and throw if it returns zero; never click into another application. **Type text with `SendText`, never `Send`.** `Send` reads `+ ^ ! #` as Shift, Control, Alt and Win and `{}` as key names, so `Send "2+3="` presses Shift+3 and Calculator shows `2^3`. `Send` is for keys and chords only: `Send "{Enter}"`, `Send "^s"`. Variable names share the namespace with functions and classes: use `field`, `target`, `box`, or `bar` rather than `edit`, `click`, `send`, `run`, `menu`, or `gui`.

Wait on observed state, not fixed sleeps. `AcuWaitUntil(predicate, timeoutMs := 2000, intervalMs := 25)` polls the predicate until it returns a true value and returns that value, or `0` when the time runs out. Pick a fact the action really changes:

```autohotkey
display := root.FindElement({AutomationId:"CalculatorResults"})
before := display.Name
root.FindElement({Type:"Button", Name:"Seven"}).Invoke()
if !AcuWaitUntil(() => display.Name != before)
    throw Error("the display did not change after Seven")
dialog := AcuWaitUntil(() => WinExist("Save As"), 5000)
```

`Run` returns before a program's window appears; `AcuLaunch` waits for it. In a file dialog, set File name to a full path and invoke Save; verify the saved file or the changed title, not just that the dialog closed.

End at a stable state. The prelude restores the user's foreground window and cursor. Call `AcuKeepForeground()` when the purpose is to leave an application or transient menu showing; the cursor still returns. The script stays yours on success, error, or timeout. Remove only your own temporary scripts when finished, unless the task requires keeping them as evidence.

### 3. Check

Print facts with `FileAppend ..., "*"` and read state back in the script. An Invoke returning is not proof of effect; poll the observed value or state. The JSON result includes `outcome`, `exit_code`, `output`, `trailer`, `duration_ms`, and artifact paths.

- `ok`, exit 0: the script ran; observed facts establish whether it worked.
- `error`, exit 1: runtime error with location and stack; fix the failing script.
- `error`, exit 2: parse error; nothing ran.
- `timeout`, exit 124: watchdog fired; inspect before acting again.
- `error` without an execution outcome: invalid request or tool failure; read the diagnostic. A `busy` error means another tool call owns the desktop: inspect before retrying.

If output says `restore skipped: cursor moved by someone else`, stop and ask before continuing. If it says an unrelated foreground was left alone, look before acting again.

## Operational facts

- CLI runs share cursor and focus and reject overlaps across processes rather than queue stale actions. The low-level `run.py` launcher remains available for development but does not enforce this tool-level lease.
- UI Access reaches elevated windows, not the secure-desktop UAC prompt.
- Scripts inherit only `ACU_HOME`; pass other values in arguments. The launcher waits for its script, not programs that script starts.
- Run log: `%LOCALAPPDATA%\ACU\logs\runs.jsonl`. Crash reports with output and stacks: `crashes\`. Managed screenshots: `shots\`, newest 30 kept. Set `ACU_HOME` to relocate them. Script text is never deliberately logged; output and crash reports may contain sensitive fragments.
- Implementation files beside this skill: `run.py`, `prelude.ahk`, `tree.ahk`, `screenshot.ahk`, and `lib/`. CLI setup and detailed launcher behavior are in the repository's `README.md`.
