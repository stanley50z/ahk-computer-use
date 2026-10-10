---
name: acu
description: Operate this Windows desktop through AutoHotkey v2 script files run by ACU. Write one short action chain, run it, and check the observed result. Use when asked to click, type into, open, read, or drive a Windows application or the desktop on this machine, or when a task names ACU or AutoHotkey.
---

# ACU

You supply the intelligence, ACU supplies the hands. Every action is a whole scripted action chain in one `.ahk` file, not a tool call for every button. You write and manage the script; ACU runs it under the launcher protections and preserves the file.

## Call ACU

Call the installed CLI through your shell tool: `acu run "<absolute script.ahk>" [--timeout 30] [-- arguments]`. Arguments after `--` reach the script in `A_Args`. There are no script IDs, inline-code input, or separate inspection operations.

Use absolute paths for `tree.ahk` and `screenshot.ahk`, which live beside this skill. If `acu` is not on PATH, report the installation prerequisite; setup is in the repository's `README.md` (resolve this skill directory's link and take its parent).

Before drafting your first script, read `guides/scripting.md` beside this skill for targeting, waits, UIA patterns, restore, and verification guidance. Use only the desktop actions the user authorized.

## The loop

Look, act, check. Repeat until the user's postcondition is observed. The task is done when a window state, printed text, or screenshot shows the result, never because an execution exited zero.

### 1. Look

Find the window before its controls. `Run` returns before a program's window appears; allow up to 10 seconds. Discover by title or class, then retain the exact handle (`ahk_id`) for the tree, waits, activation and cleanup. Use an executable filter only when the top-level window's process name has been observed: Calculator's app process can be `CalculatorApp.exe` while its window belongs to `ApplicationFrameHost.exe`.

If a process search finds nothing, write and run a window-listing script before declaring launch failure:

```autohotkey
for hwnd in WinGetList() {
    target := "ahk_id " hwnd
    FileAppend hwnd " | " WinGetTitle(target) " | " WinGetClass(target) " | " WinGetProcessName(target) "`n", "*"
}
```

Select the intended window from its observed title/class and inspect its tree. For a new-window task, snapshot existing handles before `Run` and select a new matching handle; preserve existing windows. If no unique intended window can be identified, report that ambiguity instead of acting on a guess. A store app may restore previous documents, so check its content before typing.

Skip the tree dump when you already know the window and control. Otherwise run the ordinary `tree.ahk` script through the same CLI, passing its target and flags after `--`:

```
acu run "<skill dir>/tree.ahk" -- "<WinTitle or ahk_id>" [--find <text>] [--type <Type>] [--depth 25] [--max 300]
```

Read `guides/tree.md` beside this skill when interpreting a dump: it explains control-view paths, full values, action/state flags, AHK-escaped names, and truncation. Prefer named controls and semantic UIA actions, then element bounds, then screenshot coordinates. Before pointer input or keys, activate the target and verify `WinWaitActive`; throw rather than click into another application.

Run `screenshot.ahk` for an empty/nameless tree, canvas content, or visual confirmation. Read `guides/screenshot.md` for capture modes and coordinate mapping:

```
acu run "<skill dir>/screenshot.ahk" -- fullscreen [monitor]
acu run "<skill dir>/screenshot.ahk" -- app "<WinTitle or ahk_id>"
acu run "<skill dir>/screenshot.ahk" -- custom <x1> <y1> <x2> <y2>
```

The script prints the saved PNG path and coordinate metadata in `output`; read the PNG separately. An explicit `--out` may overwrite a file; use only an authorized path. An image point (px,py) is the screen point (sourceX + px * scale, sourceY + py * scale). App capture never activates the window. Use `--max 0` for an unscaled close look.

### 2. Act

Write the whole chain when you can predict intermediate states: press a button, wait for its dialog, act inside it. Otherwise run a short script, then look again. Plain AHK v2 needs no boilerplate; ACU supplies the prelude and UIA class.

Run the file through the CLI:

```
acu run "<script.ahk>" [--timeout 30] [-- arguments]
```

The script stays yours on success, error, or timeout. Remove only your own temporary scripts when finished, unless the task requires keeping them as evidence.

End at a stable state. The prelude restores the user's foreground window and cursor. Call `AcuKeepForeground()` when the purpose is to leave an application or transient menu showing; the cursor still returns.

### 3. Check

Print facts with `FileAppend ..., "*"` and read state back in the script. Poll briefly after UIA patterns: an Invoke returning is not proof of effect. The JSON result includes `outcome`, `exit_code`, `output`, `trailer`, `duration_ms`, and artifact paths.

- `ok`, exit 0: the script ran; observed facts establish whether it worked.
- `error`, exit 1: runtime error with location and stack; fix the failing script.
- `error`, exit 2: parse error; nothing ran.
- `timeout`, exit 124: watchdog fired; inspect before acting again.
- `error` without an execution outcome: invalid request or tool failure; read the diagnostic. A `busy` error means another tool call owns the desktop: inspect before retrying.

If output says `restore skipped: cursor moved by someone else`, stop and ask before continuing. If it says an unrelated foreground was left alone, look before acting again.

## Operational facts

- CLI runs share cursor/focus and reject overlaps across processes rather than queue stale actions. The low-level `run.py` launcher remains available for development but does not enforce this tool-level lease.
- UI Access reaches elevated windows, not the secure-desktop UAC prompt.
- Scripts inherit only `ACU_HOME`; pass other values in arguments. The launcher waits for its script, not programs that script starts.
- Run log: `%LOCALAPPDATA%\ACU\logs\runs.jsonl`. Crash reports with output/stacks: `crashes\`. Managed screenshots: `shots\`, newest 30 kept. Set `ACU_HOME` to relocate them. Script text is never deliberately logged; output/crash reports may contain sensitive fragments.
- Implementation files beside this skill: `run.py`, `tree.ahk`, `screenshot.ahk`. CLI setup and detailed launcher behavior are in the repository's `README.md`.
