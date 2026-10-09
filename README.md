# ACU

A minimal computer-use tool for AI agents, built on AutoHotkey v2. The agent writes a plain AutoHotkey v2 script for each logical action chain; ACU runs it with the right defaults, a watchdog, and captured output. The agent supplies the intelligence, ACU supplies the hands.

Design record: `docs/design/acu-brainstorm-2026-10-08.md`. Research notes: `docs/research/`.

## Requirements

- Windows with AutoHotkey v2 installed at `C:\Program Files\AutoHotkey\v2\AutoHotkey64.exe`, or set `ACU_AHK` to the executable.
- Python 3.12 or newer. The launcher uses only the standard library.

## Install the skill

`acu/` is also the agent skill: `acu/SKILL.md` sits beside the launcher and scripts and teaches an agent the loop. Link it where the coding harnesses look:

```
python install_skill.py
```

That creates directory junctions (symlinks outside Windows) at `~/.agents/skills/acu` for Pi and Codex, `~/.claude/skills/acu` for Claude Code, and `~/.config/opencode/skills/acu` for OpenCode, so the installed skill always matches the checkout. `python install_skill.py --remove` deletes the links. Restart a running harness, or `/reload` in Pi, to pick it up.

## Usage

```
python acu/run.py script.ahk [--timeout 30] [-- arguments for the script]
```

Arguments after `--` reach the script in `A_Args`. The output is the script's stdout and stderr, merged in order, followed by one trailer line:

```
[acu] ok 213ms
[acu] exit 1 185ms
[acu] timeout 30s: closed on request
[acu] timeout 30s: killed
```

The exit code is the script's own, or 124 when the watchdog fired. At the timeout the script is first asked to close so its exit handler runs, and killed one second later if it has not exited.

The trailer is always the last line. The prelude's own notes, such as an error report or a restore decision, also start with `[acu]` but appear in the body, so the agent can tell them from the script's output.

## What every script gets

`acu/prelude.ahk` is included ahead of the script, so the script contains no boilerplate.

- Mouse and pixel coordinates are screen coordinates, and the thread is per-monitor-v2 DPI aware. A pixel position in a screenshot is a click position.
- No injected delays: `SetMouseDelay -1` and `SetDefaultMouseSpeed 0`. Clicks and moves are single jumps even when AutoHotkey falls back from SendInput to SendEvent, which it does whenever another AutoHotkey script on the machine has a keyboard or mouse hook.
- Runtime errors are printed with their message, file, line, and stack, and the script exits with code 1. No dialog ever appears. Load-time syntax errors are printed the same way by AutoHotkey itself.
- No tray icon, and several scripts may run at once.
- The foreground window and cursor position from the start of the script are restored when it ends, including on errors and on the watchdog's close request. See the rules below.

## Seeing the screen

`acu/screenshot.ahk` is the agent's eyes. It saves a PNG and reports where that image sits on the screen, so a point the agent picks in the image converts to a click position mechanically.

```
python acu/run.py acu/screenshot.ahk -- fullscreen [monitor]
python acu/run.py acu/screenshot.ahk -- app "<WinTitle>"
python acu/run.py acu/screenshot.ahk -- custom <x1> <y1> <x2> <y2>
```

- `fullscreen` captures one display, by AutoHotkey monitor number, default 1.
- `app` captures one window by any WinTitle, such as `ahk_exe notepad.exe` or a title fragment. The window renders itself into the image, so it shows its own content even when another window covers it, and the foreground never changes. The image is cropped to the visible frame. A minimized window is an error; restore or activate it first.
- `custom` captures the screen rectangle from (x1, y1) to (x2, y2), exclusive, in screen pixels. This is the zoom: a small rectangle comes back at full resolution.

Options for every action: `--out <path.png>` and `--max <pixels>`, the longest side of the saved image, default 1280, 0 to keep full size.

The script prints four lines before the launcher trailer:

```
saved=C:\Users\you\AppData\Local\ACU\shots\20261008-213055-123-fullscreen.png
image=1280x720
source=0,0 3840x2160
scale=3
```

`source` is the captured screen rectangle, origin then size. `scale` is source pixels per image pixel. A point (px, py) in the image is the screen point (sourceX + px * scale, sourceY + py * scale). Without `--out`, files go to `%LOCALAPPDATA%\ACU\shots\`, a managed folder where only the newest 30 PNG files are kept, because screenshots can contain secrets. `--out` writes anywhere; files outside the managed folder are never pruned.

## Restore rules

The prelude restores the entry foreground window and cursor at exit, with two exceptions:

1. If the cursor is not where ACU last placed it, someone else moved it. The user has taken over, so nothing is restored and the prelude prints `[acu] restore skipped: cursor moved by someone else`.
2. If ACU clicked at least once and the foreground window belongs to a process ACU never clicked, an unrelated window came forward. The foreground is left alone, the cursor is restored, and the prelude prints `[acu] foreground left on <process> (ACU never clicked it)`.

To know where it placed the cursor without installing a hook, the prelude shadows `Click`, `MouseMove`, `MouseClick`, and `MouseClickDrag`. Each delegates to `Send "{Click ...}"`, which shares the built-in option parser, so the documented syntax works unchanged. Two consequences:

- The `speed` argument of the mouse functions is ignored. Moves are instant by policy.
- A `{Click}` written directly inside `Send`, and any `WinActivate`, are not tracked. A script that only activates a window and types relies on the cursor check alone.

Scripts should end at a stable state. There is no opt-out flag for restore yet.

## Debugging artifacts

| Artifact | Location |
| --- | --- |
| Run log, one JSON line per run | `%LOCALAPPDATA%\ACU\logs\runs.jsonl` |
| Crash reports for errors and timeouts, with the full output | `%LOCALAPPDATA%\ACU\crashes\<timestamp>-<script hash>.json` |
| Screenshots taken without `--out`, newest 30 kept | `%LOCALAPPDATA%\ACU\shots\<timestamp>-<action>.png` |

Set `ACU_HOME` to move both. Script text is never logged, only its SHA-256, because scripts can contain secrets. A crash report does quote the run's output, and an error message can cite fragments of the failing line, so treat crash reports as sensitive too.

## Tests

```
python -m pytest
```

About fifteen seconds. The tests open small windows on each attached monitor, click in them, move the cursor, and take screenshots, because they run real scripts through the real launcher. Several assert cursor positions, so keep hands off the mouse and keyboard during the run. A run with a human moving the mouse fails those assertions while the clicks themselves still land. The screenshot tests read PNGs with Pillow, the only test dependency: `pip install pillow`.

## Measured: clicks while the cursor keeps moving

`experiments/jiggle/run.py` fires 200 `Click x, y` at a 24x24 pixel button, one launcher process per click, while a second script moves the cursor to a random point on the primary monitor as fast as the injected-input path allows. Measured on 2026-10-08 on this machine: Windows 11, AutoHotkey 2.0.22, a 3840x2160 primary display at 200%.

| Condition | Send mode in effect | Cursor moves per second | Hits |
| --- | --- | --- | --- |
| Another AutoHotkey script holds the mouse hook | SendEvent fallback | 61 | 399 of 400 |
| Another AutoHotkey script holds the mouse hook | SendEvent fallback | 380 | 198 of 200 |
| No other hook | SendInput | 371 to 387 | 393 of 400 |

No launcher failures in any run. Mean script time per click, including process start, was 100 to 138 ms.

Reading: about 99 percent in both modes, and the difference between them is within noise at this sample size. That supports the design decision to optimize for short scripts rather than for injection mode. The misses in SendInput mode show that even one atomic input batch does not guarantee a Win32 button registers the click; the likely mechanism is a cursor move reaching the button between its down and up messages, which clears its pushed state. Not investigated further. The target of one move per millisecond was out of reach because each injected move costs about 2.5 ms on this path; the rates above are what the jiggler achieved.

## Status

Milestone 1: launcher, prelude, a click that lands on both monitors, the jiggle measurement above, the screenshot script, and the skill. Not built yet: the accessibility-tree binding (UIA-v2).
