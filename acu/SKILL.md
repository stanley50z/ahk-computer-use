---
name: acu
description: Operate this Windows desktop through AutoHotkey v2 scripts run by the ACU launcher. Look by listing a window's controls from its accessibility tree, or with a screenshot of one display, one window, or one rectangle; act by writing one short script per action chain, by control name before coordinates; check the effect. Use when asked to click, type into, open, read, or drive a Windows application or the desktop on this machine, or when a task names ACU or AutoHotkey.
---

# ACU

You supply the intelligence, ACU supplies the hands. Every action is a plain AutoHotkey v2 script that you write to a file and run through `run.py` in this directory. Use absolute paths to `run.py`, `tree.ahk`, and `screenshot.ahk`; they live beside this file.

## The loop

Look, act, check. Repeat until the user's postcondition is observed. The task is done when a window state, printed text, or screenshot shows the result, never because a script exited 0.

### 1. Look

Skip this when you already know the window and the control. Otherwise list the window's controls first:

```
python run.py tree.ahk -- "<WinTitle>" [--depth 25] [--max 300]
```

One line per control, depth first:

```
2,2,2,5,3 Button "Six" id="num6Button" @2073,1917 157x71 invoke
2,2,2,2 Text "Display is 0" id="CalculatorResults" @1700,1300 400x80
```

Path, type, name, id, value, screen bounds, then the actions the control supports (`invoke toggle value select expand scroll`) and its state (`disabled offscreen focused`). A name or id is what you put in the script; the path is for a control that has neither. Quoted fields are printed as AutoHotkey string contents, so paste them between quotes exactly as shown. `elements=` and `truncated=` close the dump; when truncated, raise `--max` or lower `--depth`.

Take a screenshot when the tree is empty or nameless, as in canvas apps, games, and icon-only toolbars, or when you need to see rather than list:

```
python run.py screenshot.ahk -- fullscreen [monitor]
python run.py screenshot.ahk -- app "<WinTitle>"
python run.py screenshot.ahk -- custom <x1> <y1> <x2> <y2>
```

It prints `saved=`, `image=`, `source=X,Y WxH`, and `scale=`. Read the saved PNG. A point (px, py) in the image is the screen point (X + px * scale, Y + py * scale). `app` renders a window even when another covers it and never changes the foreground. `custom` with `--max 0` is the close look at a small area.

### 2. Act

Write the whole chain as one script when you can predict the intermediate states: press the button, wait for the dialog it opens, act inside the dialog. When you cannot predict them, write one short script, then look again. Run it:

```
python run.py <script.ahk> [--timeout 30]
```

Reach for the control in this order:

1. **By name, no pointer.** `root := UIA.ElementFromHandle("<WinTitle>")`, then `root.FindElement({Type:"Button", Name:"Six"}).Invoke()`. Use `{AutomationId:"num6Button"}` when the dump shows an id, and `root.ElementFromPath("2,2,2,5,3")` for a nameless control. `.Value := "text"` sets a control flagged `value`; `.Toggle()` flips a `toggle`; `.Select()` picks a `select`; `.Expand()` opens an `expand`. None of these move the pointer or change the foreground.
2. **By bounds.** `.Click()` on an element from the tree clicks its center. Activate the window first.
3. **By screenshot coordinates.** `Click x, y` with the screen point you computed. Activate the window first.

Script shape:

- Plain AutoHotkey v2, no boilerplate. The prelude already set screen coordinates, per-monitor DPI awareness, zero mouse delay, an error handler, end-of-script restore, and the `UIA` class.
- Name the target window with WinTitle criteria: a title fragment, `ahk_exe notepad.exe`, or `ahk_id` with a handle. Before any pointer click or keystroke: `WinActivate`, then `WinWaitActive(target, , 2)`, and throw when it returns 0. A click aimed at a window that is not in front is a click into the wrong application.
- Wait with `WinWait` and `WinWaitActive` and timeouts of about 2 seconds. `Sleep` only when nothing observable marks the moment. A script should finish in well under the 30 second watchdog.
- Type text with `SendText`, which sends every character literally. Use `Send` only for keys and chords, such as `{Enter}` or `^s`.
- Variable names share one namespace with functions. `edit`, `click`, `send`, and `run` are taken; use `field`, `target`, `box`.
- Print what you observe with `FileAppend "title=" WinGetTitle("A") "`n", "*"` so the check happens inside the script and reaches you in the output.
- End at a stable state: no open menu, no half-typed field. The prelude restores the user's foreground window and cursor when the script exits. When the task is to leave an application showing, call `AcuKeepForeground()` anywhere in the script; the cursor still goes back.

### 3. Check

Read the state back through the tree in the same script: the `.Name` of a display text, the `.Value` of a field, the `.ToggleState` of a check box. An `Invoke()` that returned is not proof the application acted, and a pattern call returns before the control repaints, so read back after a short wait or poll for up to a second.

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
- A tree dump fetches the whole window before applying its budget. A large browser page costs about a second; a desktop application tens of milliseconds.
- Scripts run concurrently. Two of yours at the same time share one cursor and one keyboard focus, so run one at a time.
- Artifacts: run log `%LOCALAPPDATA%\ACU\logs\runs.jsonl`, crash reports with full output in `%LOCALAPPDATA%\ACU\crashes\`, screenshots taken without `--out` in `%LOCALAPPDATA%\ACU\shots\` with only the newest 30 kept. Script text is never logged.
