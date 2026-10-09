---
name: acu
description: Operate this Windows desktop through AutoHotkey v2 scripts run by the ACU launcher. Look with a screenshot of one display, one window, or one rectangle; act by writing one short script per action chain; check the effect. Use when asked to click, type into, open, read, or drive a Windows application or the desktop on this machine, or when a task names ACU or AutoHotkey.
---

# ACU

You supply the intelligence, ACU supplies the hands. Every action is a plain AutoHotkey v2 script that you write to a file and run through `run.py` in this directory. Use absolute paths to `run.py` and `screenshot.ahk`; they live beside this file.

## The loop

Look, act, check. Repeat until the user's postcondition is observed. The task is done when a window state, printed text, or screenshot shows the result, never because a script exited 0.

### 1. Look

Skip this when you already know the window and the control. Otherwise take one screenshot:

```
python run.py screenshot.ahk -- fullscreen [monitor]
python run.py screenshot.ahk -- app "<WinTitle>"
python run.py screenshot.ahk -- custom <x1> <y1> <x2> <y2>
```

It prints `saved=`, `image=`, `source=X,Y WxH`, and `scale=`. Read the saved PNG. A point (px, py) in the image is the screen point (X + px * scale, Y + py * scale). `app` renders a window even when another covers it and never changes the foreground. `custom` with `--max 0` is the close look at a small area.

### 2. Act

Write the whole chain as one script when you can predict the intermediate states: click the button, wait for the dialog it opens, click inside the dialog. When you cannot predict them, write one short script, then look again. Run it:

```
python run.py <script.ahk> [--timeout 30]
```

Script shape:

- Plain AutoHotkey v2, no boilerplate. The prelude already set screen coordinates, per-monitor DPI awareness, zero mouse delay, an error handler, and end-of-script restore.
- Name the target window with WinTitle criteria: a title fragment, `ahk_exe notepad.exe`, or `ahk_id` with a handle. `WinActivate`, then `WinWaitActive(target, , 2)`, and throw when it returns 0. A click aimed at a window that is not in front is a click into the wrong application.
- Wait with `WinWait` and `WinWaitActive` and timeouts of about 2 seconds. `Sleep` only when nothing observable marks the moment. A script should finish in well under the 30 second watchdog.
- Reach for classic controls first: `ControlClick`, `ControlSetText`, `ControlGetText` with a ClassNN from `WinGetControls`. They need no pointer movement and no foreground change. Coordinate clicks are for windows that expose no controls, which is most modern applications.
- Type text with `SendText`, which sends every character literally. Use `Send` only for keys and chords, such as `{Enter}` or `^s`.
- Print what you observe with `FileAppend "title=" WinGetTitle("A") "`n", "*"` so the check happens inside the script and reaches you in the output.
- End at a stable state: no open menu, no half-typed field. The prelude restores the user's foreground window and cursor when the script exits.

### 3. Check

The last line of the output is the launcher's verdict; the exit code matches it.

| Last line | Exit | Meaning |
| --- | --- | --- |
| `[acu] ok` | 0 | The script ran. Your printed facts say whether it worked. |
| `[acu] exit 1` after `[acu] error: ... at file:line` | 1 | A runtime error. Fix the script at that line. |
| `[acu] timeout` | 124 | A wait never ended. Look again before acting. |

Two prelude notes can appear in the body:

- `[acu] restore skipped: cursor moved by someone else` means the user took the mouse during the script. Stop and ask before continuing.
- `[acu] foreground left on <process>` means an unrelated window came forward. Look before acting again.

## Facts the environment does not confess

- Clicks on elevated windows, such as a UAC prompt or an installer running as administrator, are dropped silently by Windows. Report it; retrying changes nothing.
- The launcher waits for the script, not for programs the script starts. `Run "notepad.exe"` returns at once; follow it with `WinWaitActive "ahk_exe notepad.exe", , 5`.
- Scripts run concurrently. Two of yours at the same time share one cursor and one keyboard focus, so run one at a time.
- Artifacts: run log `%LOCALAPPDATA%\ACU\logs\runs.jsonl`, crash reports with full output in `%LOCALAPPDATA%\ACU\crashes\`, screenshots taken without `--out` in `%LOCALAPPDATA%\ACU\shots\` with only the newest 30 kept. Script text is never logged.
