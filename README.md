# ACU

A minimal computer-use tool for AI agents, built on AutoHotkey v2. The agent writes a plain AutoHotkey v2 script for each logical action chain; ACU runs it with the right defaults, a watchdog, and captured output. The agent supplies the intelligence, ACU supplies the hands.

Vocabulary: `CONTEXT.md`. Decisions and why: `docs/adr/`. Design record: `docs/design/acu-brainstorm-2026-10-08.md`. Research notes: `docs/research/`.

## Requirements

- Windows with AutoHotkey v2 installed at `C:\Program Files\AutoHotkey\v2\AutoHotkey64.exe`, or set `ACU_AHK` to the executable.
- Python 3.12 or newer. The launcher uses only the standard library.

## Install the skill

`acu/` is also the agent skill: `acu/SKILL.md` sits beside the launcher and scripts and teaches an agent the loop. Link it where the coding harnesses look inside this repository:

```
python install_skill.py
```

That creates two directory junctions (symlinks outside Windows), `.agents/skills/acu` for Pi, Codex, and OpenCode and `.claude/skills/acu` for Claude Code. Both are gitignored, so run the command once per checkout. Only sessions started inside this repository see the skill; other agent sessions on the machine are untouched. `python install_skill.py --remove` deletes the links. Restart a running harness, or `/reload` in Pi, to pick up a change.

To make the skill available from every directory on the machine, `python install_skill.py --global` links into `~/.agents/skills`, `~/.claude/skills`, and `~/.config/opencode/skills` instead. Not used while ACU is being tested.

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
- Runtime errors are printed with their message, file, line, and stack, and the script exits with code 1. No dialog ever appears. Load-time syntax errors are printed the same way by AutoHotkey itself, and load-time warnings, such as a call to a function that does not exist, go to the output too. By default those warnings are modal dialogs that appear before the script has a window, so nothing could close them.
- The `UIA` class from Descolada's UIA-v2 library, so a script can find a control by name and act on it without the pointer. See below.
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

## Finding controls by name

`acu/tree.ahk` lists a window's controls from its accessibility tree, the same tree a screen reader uses. Modern applications draw their own buttons inside one blank window, so this is the only programmatic way to find them.

```
python acu/run.py acu/tree.ahk -- "<WinTitle>" [--find <text>] [--type <Type>] [--depth 25] [--max 300]
```

The first line is `window=<hwnd> "<title>" <exe>`. Then one line per element of the control view, depth first:

```
2,2,2,5,3 Button "Six" id="num6Button" @2073,1917 157x71 invoke
2,2,2,2 Text "Display is 0" id="CalculatorResults" @1700,1300 400x80
```

Path, type, name when present, `id=` when present, `value=` when present and in full, screen bounds, then the actions the element supports (`invoke toggle value select expand scroll`) and its state (`disabled offscreen focused selected`). `value` means the element's value is writable; a read-only value is still printed. Values are never cut or withheld, document text included: the owner's call is that the agent sees everything the window publishes. Quoted fields are printed as AutoHotkey string contents, with quotes, backticks, and line breaks escaped the way a script would write them, so a name can be pasted into `FindElement` as it is. Paths number the control view, which is the view `ElementFromPath` walks; a raw-view numbering was tried and does not resolve on Calculator.

`--find` keeps elements whose name or id contains the text, and `--type` keeps one control type; the element budget counts printed lines, so a narrowed dump of a file dialog fits where the full one did not. The dump ends with `elements=N` and `truncated=no|max|depth|max+depth`, naming the limit that cut it.

Every script has the `UIA` class, so acting needs no include:

```autohotkey
root := UIA.ElementFromHandle("Calculator")
root.FindElement({Type:"Button", Name:"Six"}).Invoke()      ; by name
root.FindElement({AutomationId:"num6Button"}).Invoke()         ; by id
root.ElementFromPath("2,2,2,5,3").Click()                       ; by path from the dump; Click moves the pointer
root.FindElement({Type:"Edit"}).Value := "text"                ; a control flagged value
```

Measured on Calculator: one button by name in 47 ms, all 48 buttons in 31 ms, the whole tree of 77 elements in 32 ms, and 6 × 7 = through `Invoke()` alone with the result read back from the display element. A Chrome window with 136 elements took 0.8 s, because the dump fetches the whole subtree in one round trip before applying `--depth` and `--max`; the budget bounds the output, not the fetch.

## Restore rules

The prelude restores the entry foreground window and cursor at exit, with two exceptions:

1. If the cursor is not where ACU last placed it, someone else moved it. The user has taken over, so nothing is restored and the prelude prints `[acu] restore skipped: cursor moved by someone else`.
2. If ACU clicked at least once and the foreground window belongs to a process ACU never clicked, an unrelated window came forward. The foreground is left alone, the cursor is restored, and the prelude prints `[acu] foreground left on <process> (ACU never clicked it)`.

To know where it placed the cursor without installing a hook, the prelude shadows `Click`, `MouseMove`, `MouseClick`, and `MouseClickDrag`. Each delegates to `Send "{Click ...}"`, which shares the built-in option parser, so the documented syntax works unchanged. Two consequences:

- The `speed` argument of the mouse functions is ignored. Moves are instant by policy.
- A `{Click}` written directly inside `Send`, and any `WinActivate`, are not tracked. A script that only activates a window and types relies on the cursor check alone.

Scripts should end at a stable state. A script whose purpose is to leave an application showing calls `AcuKeepForeground()` anywhere in its body; the foreground is then left where the script put it and only the cursor is restored. Takeover detection still applies: if the user moved the cursor, nothing is restored.

## Third-party code

`acu/lib/UIA.ahk` is Descolada's UIA-v2 library, copied from https://github.com/Descolada/UIA-v2 at commit 2846a9b (2026-04-23), MIT, license in `acu/lib/UIA-LICENSE.txt`. The prelude includes it, which costs about 30 ms per script. One line is changed, marked `; ACU patch:` in the element indexer: a single-segment numeric path such as `"3"` now resolves like `"3,2"` already did, so every path the tree dump prints is accepted by `ElementFromPath`. To update, copy the upstream file over it, re-apply that line, and run the tests.

## Debugging artifacts

| Artifact | Location |
| --- | --- |
| Run log, one JSON line per run | `%LOCALAPPDATA%\ACU\logs\runs.jsonl` |
| Crash reports for errors and timeouts, with the full output | `%LOCALAPPDATA%\ACU\crashes\<timestamp>-<script hash>.json` |
| Screenshots taken without `--out`, newest 30 kept | `%LOCALAPPDATA%\ACU\shots\<timestamp>-<action>.png` |

Set `ACU_HOME` to move both. Script text is never logged, only its SHA-256, because scripts can contain secrets. A crash report does quote the run's output, and an error message can cite fragments of the failing line, so treat crash reports as sensitive too.

## Tests

Run checks relevant to the change. The default is the skill/installer checks, with no AutoHotkey execution:

```
python -m pytest -q
```

All AutoHotkey integration tests carry the `desktop` marker and are deselected unless `--desktop` is supplied, even if their file is explicitly selected. With approval for desktop use, run a focused check, for example:

```
python -m pytest --desktop tests/test_uia.py -k tree_find_and_type -q
```

These tests can open windows, move the cursor, and change focus. Do not run the full desktop suite after every change. Keep useful regressions available, consolidate repetitive checks, and remove redundant tests. A full run (`python -m pytest --desktop`) is reserved for deliberate validation on an idle desktop. Tests require pytest; screenshot tests also require Pillow.

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

Milestone 1: launcher, prelude, a click that lands on both monitors, the jiggle measurement above, the screenshot script, and the skill. Milestone 2: the accessibility tree, so an agent finds controls by name before it reads a screenshot. The decisions the code confirmed are recorded in `docs/adr/` and the vocabulary in `CONTEXT.md`. The second live task completed a Save As workflow using the tree; its findings added filtered dumps, explicit truncation reasons, and selection/writability flags.
