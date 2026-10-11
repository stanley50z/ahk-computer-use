# ACU

A script-first computer-use tool for AI agents, available through the `acu` CLI. The agent writes a plain AutoHotkey v2 script for each logical action chain and passes its file path to the single `run` operation. ACU manages execution with the right defaults, a watchdog, and captured output. The agent supplies the intelligence, ACU supplies the hands. Execution is through AutoHotkey v2.

Vocabulary: `CONTEXT.md`. Decisions and why: `docs/adr/`. Design record: `docs/design/acu-brainstorm-2026-10-08.md`. Research notes: `docs/research/`.

## Requirements

- Windows with AutoHotkey v2 installed with its UI Access option, so that `C:\Program Files\AutoHotkey\v2\AutoHotkey64_UIA.exe` exists beside `AutoHotkey64.exe`. Or set `ACU_AHK` to the UI Access executable; the plain build must sit beside it. Windows grants UI Access only to a signed program under Program Files, so a copy elsewhere will not do.
- Python 3.12 or newer. The CLI and launcher use only the standard library.
- [uv](https://docs.astral.sh/uv/) for the installation/development commands below, or another Python package installer that provides console commands.

## Install the CLI

From this checkout:

```
uv tool install --editable .
acu --help
```

This installs the `acu` command in uv's user-level tools bin directory, with its own Python environment. That directory must be on `PATH`; `uv tool dir --bin` reports its location. Editable installation follows changes in this checkout. It does not install the agent skill globally or modify harness settings.

Normal use is `acu run ...`, not a Python/package-manager wrapper. Python is the implementation language; the installed console launcher starts its interpreter internally. **uv is an installer/development tool, not part of the runtime command.** ACU has no Python runtime package dependencies; it uses the standard library and the existing AutoHotkey installation.

For development, `uv sync` installs the quiet-test dependencies, `uv run pytest ...` runs focused checks, and `uv build` creates an installable wheel containing the launcher, scripts, vendored UIA library, and skill. These are setup/build commands, not the agent-facing interface. Uninstall the CLI with `uv tool uninstall acu-desktop`.

## Agent interface

ACU is CLI-only and exposes one operation: run an existing AutoHotkey v2 script file. The agent writes one predictable action chain, calls the CLI through its shell tool, and reads observed facts back. The file stays under the caller's ownership; ACU neither creates nor deletes action scripts.

```
acu run action.ahk [--timeout 30] [-- arguments for the script]
acu run tree.ahk -- "ahk_id 12345" --find Save
acu run screenshot.ahk -- app "ahk_id 12345"
```

Use absolute paths for your own scripts from an agent session. Arguments after `--` are literal strings passed to `A_Args`. `tree.ahk` and `screenshot.ahk` are ordinary scripts passed to the same command, not separate operations; named without a directory, they resolve to the bundled copies unless a file of that name exists in the current directory. A screenshot script prints its saved PNG path and coordinate mapping in `output`; read the PNG separately. Authoring and inspection guidance is in `acu/SKILL.md`, which is the complete agent-facing manual.

There is no server or MCP integration, inline-code input, engine selector, maintained-script-ID registry, discovery, or description operation. Other operations require a separate design decision before implementation.

CLI stdout is one JSON result containing `engine` (always `ahk`), `outcome`, `exit_code`, `output`, `trailer`, `duration_ms`, and `artifacts` paths. Exit codes preserve the script's exit code (124 for timeout); invalid requests exit 2 and tool infrastructure failures exit 1. This uses the same prelude and launcher as before. Successful execution alone does not verify the task's effect.

Timeouts must be finite and greater than zero, at most 300 seconds. A Windows session-local mutex rejects overlapping CLI runs with a `busy` error; actions are not queued against stale state. The low-level launcher remains available and does not take this tool-level lease. ACU is not a sandbox or an access-control boundary. There is no persistent desktop-control session, background server, or localhost listener.

## Install the skill

`acu/` is also the agent skill: `acu/SKILL.md` sits beside the launcher and scripts and teaches an agent the loop. Link it where the coding harnesses look inside this repository:

```
python install_skill.py
```

That creates two directory junctions (symlinks outside Windows), `.agents/skills/acu` for Pi, Codex, and OpenCode and `.claude/skills/acu` for Claude Code. Both are gitignored, so run the command once per checkout. Only sessions started inside this repository see the skill; other agent sessions on the machine are untouched. `python install_skill.py --remove` deletes the links. Restart a running harness, or `/reload` in Pi, to pick up a change.

To make the skill available from every directory on the machine, `python install_skill.py --global` links into `~/.agents/skills`, `~/.claude/skills`, and `~/.config/opencode/skills` instead. Not used while ACU is being tested.

## Low-level launcher usage

Agents normally use the `acu run` CLI above. The existing launcher remains the implementation and development entry point:

```
python acu/run.py script.ahk [--timeout 30] [-- arguments for the script]
```

Arguments after `--` reach the script in `A_Args`. They are the only way to pass a script something: it does not inherit the launcher's environment, because Windows starts the UI Access build through ShellExecute (see below). `ACU_HOME` is the one variable the launcher passes through. The output is the script's stdout and stderr, merged in order, followed by one trailer line:

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
- `AcuLaunch(command, winTitle, timeoutMs := 10000)` starts a program and returns the one new top-level window matching `winTitle` as an object with `hwnd`, `pid`, `title`, `class`, and `process`. Pre-existing windows are snapshotted first and never selected; no new window, or several, is an error rather than a guess. Every fresh agent in Testbench 1 had hand-written this loop, and one got it wrong. Before returning it waits, within the same timeout, until the window's accessibility tree holds the same element count on two polls 150 ms apart, and reports that count as `elements`: Calculator's frame exists before its buttons, and a dump taken at once showed only the title bar.
- `AcuWaitUntil(predicate, timeoutMs := 2000, intervalMs := 25)` polls until the predicate returns a true value and returns it, or 0 after the timeout: an observed wait in place of a fixed `Sleep`.
- `AcuTree(target, {find, type, depth, max})` returns the same dump `tree.ahk` prints, as text, and `AcuScreenshot({app: target} | {monitor: n} | {rect: [x1, y1, x2, y2]}, outPath, maxSide)` saves the same PNG `screenshot.ahk` does and returns its mapping. Both live in `acu/lib/` and let an action chain end with the evidence it needs; in Testbench 1 the separate screenshot call was the last non-essential model turn.
- No tray icon, and several scripts may run at once.
- The foreground window and cursor position from the start of the script are restored when it ends, including on errors and on the watchdog's close request. See the rules below.
- UI Access. The script runs under AutoHotkey's signed UI Access build, so an elevated window, such as an installer running as administrator, is in the tree and accepts input, without the script being elevated and without a UAC prompt. The UAC consent prompt itself is on a separate desktop and stays out of reach. Windows starts a UI Access program only through ShellExecute, which gives it no standard output, so the launcher names an output file in a leading argument that the prelude strips and redirects stdout and stderr into. Load-time errors and warnings happen before the prelude runs, so the launcher first loads the script without running it under the plain build, which has a pipe; a syntax error ends there with exit code 2.

## Seeing the screen

`acu/screenshot.ahk` is the agent's eyes. It saves a PNG and reports where that image sits on the screen, so a point the agent picks in the image converts to a click position mechanically. The script only parses arguments; the capture is `AcuScreenshot` in `acu/lib/capture.ahk`, which every script can call.

```
python acu/run.py acu/screenshot.ahk -- fullscreen [monitor]
python acu/run.py acu/screenshot.ahk -- app "<WinTitle>"
python acu/run.py acu/screenshot.ahk -- custom <x1> <y1> <x2> <y2>
```

- `fullscreen` captures one display, by AutoHotkey monitor number, default 1.
- `app` captures one window by any WinTitle, such as `ahk_exe notepad.exe` or a title fragment. The window renders itself into the image, so it shows its own content even when another window covers it, and the foreground never changes. The image is cropped to the visible frame. An application that is not per-monitor DPI aware renders at the size it believes it has, and Windows scales that on a monitor with another DPI; the capture is scaled the same way, so it matches the screen and `source` stays a click position. A minimized window is an error; restore or activate it first.
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

`acu/tree.ahk` lists a window's controls from its accessibility tree, the same tree a screen reader uses. Modern applications draw their own buttons inside one blank window, so this is the only programmatic way to find them. The script only parses arguments; the dump is `AcuTree` in `acu/lib/dump.ahk`, which every script can call. A Chromium or Electron window exists before its UI Automation provider answers, and the first full-subtree request then fails with `UIA_E_TIMEOUT`; the dump nudges the provider with a plain root query and retries for up to five seconds before reporting that the application may still be starting.

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
root.ElementFromPath("2,2,2,5,3").Invoke()                      ; by path from the dump
root.FindElement({Type:"Edit"}).Value := "text"                ; a control flagged value
```

`element.Click()` without an argument is semantic as well: the library routes it to Invoke, Toggle, or Select. Pointer input is `element.Click("left")`, which moves the cursor to the element's center and needs the window in the foreground.

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

`acu/lib/dump.ahk` and `acu/lib/capture.ahk` are first-party. `acu/lib/UIA.ahk` is Descolada's UIA-v2 library, copied from https://github.com/Descolada/UIA-v2 at commit 2846a9b (2026-04-23), MIT, license in `acu/lib/UIA-LICENSE.txt`. The prelude includes it, which costs about 30 ms per script. One line is changed, marked `; ACU patch:` in the element indexer: a single-segment numeric path such as `"3"` now resolves like `"3,2"` already did, so every path the tree dump prints is accepted by `ElementFromPath`. To update, copy the upstream file over it, re-apply that line, and run the tests.

## Debugging artifacts

| Artifact | Location |
| --- | --- |
| Run log, one JSON line per run | `%LOCALAPPDATA%\ACU\logs\runs.jsonl` |
| Crash reports for errors and timeouts, with the full output | `%LOCALAPPDATA%\ACU\crashes\<timestamp>-<script hash>.json` |
| Tool infrastructure failures with Python stack traces | `%LOCALAPPDATA%\ACU\crashes\<timestamp>-tool.json` |
| Screenshots taken without `--out`, newest 30 kept | `%LOCALAPPDATA%\ACU\shots\<timestamp>-<action>.png` |

Set `ACU_HOME` to move these locations. ACU does not log script text, only its SHA-256, because scripts can contain secrets. A harness may independently record tool-call arguments. A crash report does quote the run's output, and an error message can cite fragments of the failing line, so treat crash reports as sensitive too. If tool crash-report persistence itself fails, the original error remains in the JSON response together with an explicit `diagnostic_error`.

## Computer-use test bench

`bench/` prepares isolated Pi/ACU, Claude Code/ACU, Pi/CUA, and Codex/native profiles. The GPT harnesses use GPT-6.1 at low reasoning; Claude Code runs only Claude models, so its arm uses Opus 5.5 at low effort. Each live trial needs approval and records raw transcripts, token usage, timing, verification and cleanup. The primary measurement is task time, from the actor's session start to its last computer-use call; writing result evidence and the final answer are outside it. See [bench/README.md](bench/README.md) for commands and measurement limits, [the first Calculator results](docs/reports/bench-calculator-2026-10-09.md), and [the latest complete Testbench 1](docs/reports/testbench-1-2026-10-10.md). The two initial ACU attempts did not reach calculation: one stopped on confirmed concurrent mouse use, and one used the wrong top-level window process assumption.

## Tests

Run checks relevant to the change. The default includes skill/installer and quiet benchmark checks, with no AutoHotkey execution or desktop input:

```
uv run pytest -q
```

All AutoHotkey integration tests carry the `desktop` marker and are deselected unless `--desktop` is supplied, even if their file is explicitly selected. With approval for desktop use, run a focused check, for example:

```
uv run pytest --desktop tests/test_tool.py -q
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
