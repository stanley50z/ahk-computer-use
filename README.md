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

For development, `uv sync` installs the quiet-test dependencies, `uv run pytest ...` runs focused checks, and `uv build` creates an installable wheel containing the launcher, scripts, vendored UIA library, and ACU skill. These are setup/build commands, not the agent-facing interface. Uninstall the CLI with `uv tool uninstall acu-desktop`.

## Agent interface

ACU is CLI-only. It runs existing AutoHotkey v2 script files and lists saved snippets without using the desktop. The agent writes one predictable action chain, calls the CLI through its shell tool, and reads observed facts back. The file stays under the caller's ownership; ACU neither creates nor deletes action scripts.

```
acu run action.ahk [--timeout 30] [-- arguments for the script]
acu run tree.ahk -- "ahk_id 12345" --find Save
acu run screenshot.ahk -- app "ahk_id 12345"
```

Use absolute paths for your own scripts from an agent session. Arguments after `--` are literal strings passed to `A_Args`. `tree.ahk` and `screenshot.ahk` are ordinary scripts passed to the same command, not separate operations; named without a directory, they resolve to the bundled copies unless a file of that name exists in the current directory. A screenshot script prints its saved PNG path and coordinate mapping in `output`; read the PNG separately. Authoring and inspection guidance is in `acu/SKILL.md`, which is the complete agent-facing manual.

There is no server or MCP integration, inline-code input, engine selector, maintained-script-ID registry, or general discovery/description operation. Snippet listing and session history are the read-only exceptions. Other operations require a separate design decision before implementation.

`acu run` stdout is one JSON result containing `engine` (always `ahk`), `outcome`, `exit_code`, `output`, `trailer`, `duration_ms`, and `artifacts` paths. Exit codes preserve the script's exit code (124 for timeout); invalid requests exit 2 and tool infrastructure failures exit 1. This uses the same prelude and launcher as before. Successful execution alone does not verify the task's effect.

Timeouts must be finite and greater than zero, at most 300 seconds. A Windows session-local mutex rejects overlapping CLI runs with a `busy` error; actions are not queued against stale state. The low-level launcher remains available and does not take this tool-level lease. ACU is not a sandbox or an access-control boundary. There is no persistent desktop-control session, background server, or localhost listener.

## List saved snippets

```
acu snippets list <app> [keyword...]
```

Snippets are ordinary `.ahk` files in `~/.ahk-computer-use/snippets/<exe name>/`. App matching ignores case and an optional `.exe` suffix. An exact executable-name match wins; otherwise ACU searches partial executable names and their FileDescription. ACU looks for the executable in running processes first, then registry App Paths. Unresolvable folders remain searchable by exe name. Unknown apps show existing folders; ambiguous matches ask you to choose one.

The header is the leading block of `;` comments before code, with fields `does`, `args`, `needs`, `effect`, `check`, and `tested` written as `; key: value` (key case ignored). Other comment lines are ignored. With no keywords, listing shows every snippet. Keywords search filenames and header values using case-insensitive substring matches; more distinct hits come first, with ties by filename.

Listing prints plain text, not the run-result JSON:

```text
snippets C:\Users\you\.ahk-computer-use\snippets\Editor.exe
open.ahk | args: path | does: Open a document
old.ahk | no header
wide.ahk | unreadable: 'utf-8' codec can't decode byte 0xff in position 0: invalid start byte
```

A snippet ACU cannot read as UTF-8 text is listed as `unreadable` and searched by filename only; the other snippets still list. Missing stores are reported without creating them. Listing never starts AutoHotkey or takes the desktop lease, so it can run while a script owns that lease. `ACU_SNIPPETS_ROOT` overrides only the snippets directory; `ACU_HOME` still controls diagnostic artifacts. Unexpected listing failures use the existing tool crash reports described below. Snippet storage and lifecycle decisions are in [ADR-0010](docs/adr/0010-reusable-snippets.md).

`acu run` also shows the full list when a script calls `AcuLaunch` or runs an unfiltered bundled `tree.ahk` dump. In-script `AcuTree` calls do not print snippets. Tree depth and element limits do not limit snippets. `--find` and `--type` suppress automatic listing. Missing stores or app folders add nothing; an empty app folder adds only its folder line. A settings or store error becomes one `[acu] ...` line in place of the list, and the run result is kept. Discovery uses the content-owning executable, including the hosted app process for `ApplicationFrameHost.exe` windows, without changing launch metadata or the tree's window heading.

The AHK helpers emit an internal `[acu:snippets] <exe>` line. `acu/tool.py` replaces it with the shared Python listing before returning output or recording crash output. Settings are resolved from the `acu run` working folder, not the script's directory; disabled discovery removes the marker. The low-level `acu/run.py` development entry point leaves these markers unexpanded.

### Snippet settings

Snippets are enabled by default. Set a global default in `~/.ahk-computer-use/settings.json`, or override it in `<project>/.ahk-computer-use/settings.json`:

```json
{ "snippets": { "enabled": false } }
```

ACU searches upward from the call's working folder and uses the nearest project settings file. Its `snippets.enabled` value wins over the global value; an omitted value leaves the global default unchanged. Set it to `true` to enable snippets again. Invalid JSON or a non-boolean enabled value produces an error naming the file. Explicit listing fails; automatic discovery replaces its marker with one error line and preserves the completed run result. When disabled, `acu snippets list` prints `Snippets are off.` without reading the snippet store. This controls discovery, not permission to run a script by path.

`ACU_SETTINGS_FILE` overrides the global settings file location for tests or isolated environments. The home settings file is not treated as a project file during upward search, including when this override is set. `ACU_HOME` still controls only diagnostic artifacts, and `ACU_SNIPPETS_ROOT` still controls only snippet storage. Benchmark preparation writes the disabled setting into every trial workspace before starting the actor, without changing global settings.

For automatic discovery, reuse `acu.settings.snippets_enabled(working_folder)`; omitting the folder uses the current working directory. It returns a boolean or raises `ValueError` naming an invalid settings file.

## Summarize a session

```
acu history <session-file.jsonl>
```

History reads one native Pi, Codex, or Claude Code session plus `acu_home()/logs/runs.jsonl` (normally `%LOCALAPPDATA%\ACU\logs\runs.jsonl`). It prints compact app totals, candidate chains, each snippet run and outcome, changed snippets, and existing snippets with frequent failures. It does not launch AutoHotkey, take the desktop lease, modify the store, execute captured shell commands, or print script text or raw tool output. Unexpected failures use the tool crash-report location in **Debugging artifacts** below.

Fixed rules (also in `acu history --help`):

- A candidate is a per-app sequence since the previous successful action or unknown outcome, ending at an `ok` action run, with at least **one error/timeout or two looks**. A look is a separate `tree.ahk` or `screenshot.ahk` run. The report gives the final script path and physical line count, including comments and blank lines. An `ok` exit is not proof that the user's task succeeded.
- A frequently failing snippet has **at least 3 error/timeout runs and a failure rate of at least 50%** across all retained log entries for that path, including runs outside this session. The file must still exist under `snippets_root()`; deleted files are not proposed.
- Outcomes join by case-insensitive full script path and the tool request-to-result timestamp interval. Repeated runs in one call join in timestamp order only when counts agree. Missing results, absent logs, and ambiguous matches remain `unknown`; they never imply success. Bare bundled tree/screenshot names use the CLI resolver with the captured working folder, including local-file precedence. Shell paths expand `$PWD`, `${PWD}` and `~`; other variables stay literal. Bundled paths from another installation can remain unknown. Concurrent ambiguous intervals are not guessed.
- App identity comes from the snippet's folder, a literal `ahk_exe` selector in captured source/arguments, a tree's `window=` output, or the folder named by a printed snippet list. Output evidence comes only from the run's own CLI result line: a shell call's results pair with its runs in order, and none are used when their counts differ. `ApplicationFrameHost.exe` names no app, so a store app's looks group under its own process when other evidence names it. Conflicting or absent evidence goes under `unknown app`, which produces no candidates. There is no inference from document titles or adjacent apps.
- Source length comes from captured write/edit arguments, shell heredocs, literal Python `-c` writes, or captured patch hunks. A current on-disk script is used only when its SHA-256 matches the run log, and only when it decodes as UTF-8 or as UTF-16 with a byte-order mark. Captured Python that does not parse leaves its writes unknown. When the recorded hash disagrees with captured text, that text is discarded. Missing source is reported as `length unknown`.

Parsing mirrors the bench's native tool-call envelopes, ID correlation, heredoc separation and shell command-position rules. Quoted mentions such as `echo 'acu run ...'` are not runs. Parallel tool wrappers are expanded. Direct write/edit tools and literal shell writes/patches identify changed snippets only when their result shows success. Codex results have no error flag, so history reads the `Exit code: N` line, patch `exit_code` metadata or a known failure message; any other output leaves the write unconfirmed. An `Add File` patch supplies the new file's source; paths must belong to the configured snippets root, not merely contain a `snippets` folder. This is static analysis of literal calls, not a shell interpreter: dynamically constructed commands, scripts launched inside other programs, and generated paths may remain unresolved. Shell requests that cannot be parsed fail explicitly rather than claiming a complete summary. Keep the session and retained run log for investigating unknown entries. No new history log is written.

## Install the skills

`acu/` is also the agent skill: `acu/SKILL.md` sits beside the launcher and scripts and teaches an agent the loop. The sibling `retro-acu/SKILL.md` is user-invoked only. After a session, invoke `retro-acu` with its session-file path to review `acu history` findings and propose new snippets, repairs, and deletions. It changes the snippet store only after approval; it does not read raw session files or logs itself.

Link both skills where the coding harnesses look inside this repository:

```
python install_skill.py
```

That creates four directory junctions (symlinks outside Windows): `acu` and `retro-acu` under both `.agents/skills/` for Pi, Codex, and OpenCode and `.claude/skills/` for Claude Code. All are gitignored, so run the command once per checkout. Only sessions started inside this repository see the skills; other agent sessions on the machine are untouched. `python install_skill.py --remove` deletes the links. Restart a running harness, or `/reload` in Pi, to pick up a change.

To make both skills available from every directory on the machine, `python install_skill.py --global` links each into `~/.agents/skills`, `~/.claude/skills`, and `~/.config/opencode/skills` instead (six links). `--global --remove` removes those links only. Not used while ACU is being tested. The repository's Pi, Claude Code, and OpenCode settings hide only `cua-driver`; they leave `retro-acu` available for explicit invocation.

Only the source distribution includes `retro-acu/` beside `acu/`, together with `install_skill.py`. The wheel installs the `acu` package only.

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

The trailer is always the last line. The prelude's own notes, such as an error report or an input-language warning, also start with `[acu]` but appear in the body, so the agent can tell them from the script's output.

## What every script gets

`acu/prelude.ahk` is included ahead of the script, so the script contains no boilerplate.

- Mouse and pixel coordinates are screen coordinates, and the thread is per-monitor-v2 DPI aware. A pixel position in a screenshot is a click position.
- No injected delays: `SetMouseDelay -1` and `SetDefaultMouseSpeed 0`. Clicks and moves are single jumps even when AutoHotkey falls back from SendInput to SendEvent, which it does whenever another AutoHotkey script on the machine has a keyboard or mouse hook.
- Runtime errors are printed with their message, file, line, and stack, and the script exits with code 1. No dialog ever appears. Load-time syntax errors are printed the same way by AutoHotkey itself, and load-time warnings, such as a call to a function that does not exist, go to the output too. By default those warnings are modal dialogs that appear before the script has a window, so nothing could close them.
- The `UIA` class from Descolada's UIA-v2 library, so a script can find a control by name and act on it without the pointer. See below.
- `AcuLaunch(command, winTitle, timeoutMs := 10000)` starts a program and returns the one new top-level window matching `winTitle` as an object with `hwnd`, `pid`, `title`, `class`, and `process`. Pre-existing windows, including hidden ones, are snapshotted first and never selected; no new window, or persistent ambiguity, is an error rather than a guess. Startup candidates have up to 500 ms to settle, bounded by the requested timeout, and the set is rechecked after tree settling before returning. Multiple candidates may clear until the deadline. Ambiguity errors include every candidate's handle, title, class, and PID. Every fresh agent in the Calculator benchmark had hand-written this loop, and one got it wrong. Before returning it waits, within the same timeout, until the window's accessibility tree holds the same element count on two polls 150 ms apart, and reports that count as `elements`: Calculator's frame exists before its buttons, and a dump taken at once showed only the title bar.
- Opt-in paced input in `acu/lib/actions.ahk`: `AcuActivate(target)` requires one matching window and refuses an owned dialog; `AcuKeys(target, keys, pressMs := 30)` delivers key chords with nonzero press duration through the English-input guard; `AcuClick(target, x, y)` and `AcuDrag(target, x1, y1, x2, y2, durationMs := 150)` deliver bounded mouse contact/motion. Pointer helpers hit-test the target's child/owned windows before contact and abort/release on lost activation. They restore the caller's native timing/SendMode, not cursor position or foreground. Native AHK functions remain unchanged. These are physical input durations, not substitutes for observing UI readiness. [Illustrator's first-run report](docs/reports/testbench-2-first-run-2026-10-11.md) records the saved-AI handle regression and matched benchmark results.
- `AcuWaitUntil(predicate, timeoutMs := 2000, intervalMs := 25)` polls until the predicate returns a true value and returns it, or 0 after the timeout: an observed wait in place of a fixed `Sleep`.
- `AcuTree(target, {find, type, depth, max})` returns the same dump `tree.ahk` prints, as text, and `AcuScreenshot({app: target} | {monitor: n} | {rect: [x1, y1, x2, y2]}, outPath, maxSide)` saves the same PNG `screenshot.ahk` does and returns its mapping. Both live in `acu/lib/` and let an action chain end with the evidence it needs; in the Calculator benchmark the separate screenshot call was the last non-essential model turn.
- No tray icon, and several scripts may run at once.
- Cursor position and foreground stay where the script leaves them, on success, error, and timeout. Native mouse functions are no longer shadowed for tracking; there is no restore hook or keep-foreground opt-out.
- English input preparation at startup and immediately before native keyboard sends, including for a newly activated target. See the rules below.
- UI Access. The script runs under AutoHotkey's signed UI Access build, so an elevated window, such as an installer running as administrator, is in the tree and accepts input, without the script being elevated and without a UAC prompt. The UAC consent prompt itself is on a separate desktop and stays out of reach. Windows starts a UI Access program only through ShellExecute, which gives it no standard output, so the launcher names an output file in a leading argument that the prelude strips and redirects stdout and stderr into. Load-time errors and warnings happen before the prelude runs, so the launcher first loads the script without running it under the plain build, which has a pipe; a syntax error ends there with exit code 2.

## Seeing the screen

`acu/screenshot.ahk` is the agent's eyes. It saves a PNG and reports where that image sits on the screen, so a point the agent picks in the image converts to a click position mechanically. The script only parses arguments; the capture is `AcuScreenshot` in `acu/lib/capture.ahk`, which every script can call.

```
python acu/run.py acu/screenshot.ahk -- fullscreen [monitor]
python acu/run.py acu/screenshot.ahk -- app "<WinTitle>"
python acu/run.py acu/screenshot.ahk -- custom <x1> <y1> <x2> <y2>
```

- `fullscreen` captures one display, by AutoHotkey monitor number, default 1.
- `app` captures one window by any WinTitle, such as `ahk_exe notepad.exe` or a title fragment. The window renders itself into the image, so it shows its own content even when another window covers it, and the foreground never changes. The image is cropped to the visible frame. An application that is not per-monitor DPI aware renders at the size it believes it has, and Windows scales that on a monitor with another DPI; the capture is scaled the same way, so it matches the screen and `source` stays a click position. A minimized window is an error; restore or activate it first. App capture uses `PrintWindow` for that HWND and can omit separate menus, popups, and dialogs. Use an activated target's on-screen `fullscreen` or `custom` capture for transient UI, after observing its appearance or repaint; an unchanged immediate capture is not proof that the action failed.
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

## Desktop state and English input

ACU leaves cursor position and foreground at the script's last action. This applies to normal exit, runtime errors, and cooperative or forced timeouts. The previous restoration, takeover comparison, mouse tracking, and `AcuKeepForeground()` API have been removed by the user's decision in [ADR-0009](docs/adr/0009-persistent-desktop-state-and-english-input.md). Scripts written against the old API need that call removed. Hover menus and application focus can persist between action chains. The watchdog still asks the script to close before killing it so the script's own exit handlers can run.

Benchmark post-trial cleanup is separate: it still closes owned windows/processes and reloads the saved cursor scheme after a trial. It does not implement per-script cursor-position or focus restoration.

The prelude's first-party `acu/lib/keyboard.ahk` prepares English input at startup and immediately before `Send`, `SendInput`, `SendEvent`, `SendPlay`, `SendText`, `ControlSend`, or `ControlSendText`. It checks the actual destination thread, including a control-send target, and the sending thread's layout. Already-English input is left as-is. For non-English input it prefers a loaded English (United States) keyboard, otherwise another loaded English keyboard. It does not install layouts or alter the user's configured language list.

Foreign-thread changes use a posted `WM_INPUTLANGCHANGEREQUEST` to the focused control; Windows documents that the app may accept or reject the request. ACU verifies English input before sending keys. The same-thread path activates the loaded layout directly. Native send functions keep their original parsing and SendMode. Direct Win32 keyboard injection or application-specific APIs are outside this guard.

If no English keyboard is available, ACU emits a warning. An expected startup preparation failure still allows inspection and mouse actions; native keyboard sends fail before input until English preparation succeeds. If Windows or the app rejects the switch, the send reports an error and sends no keys. The earlier input language is not restored. Switching notes and failures are captured in the normal run output and crash reports.

## Third-party code

`acu/lib/dump.ahk`, `acu/lib/capture.ahk`, and `acu/lib/keyboard.ahk` are first-party. `acu/lib/UIA.ahk` is Descolada's UIA-v2 library, copied from https://github.com/Descolada/UIA-v2 at commit 2846a9b (2026-04-23), MIT, license in `acu/lib/UIA-LICENSE.txt`. The prelude includes it, which costs about 30 ms per script. One line is changed, marked `; ACU patch:` in the element indexer: a single-segment numeric path such as `"3"` now resolves like `"3,2"` already did, so every path the tree dump prints is accepted by `ElementFromPath`. To update, copy the upstream file over it, re-apply that line, and run the tests.

## Debugging artifacts

| Artifact | Location |
| --- | --- |
| Run log, one JSON line per run | `%LOCALAPPDATA%\ACU\logs\runs.jsonl` |
| Crash reports for errors and timeouts, with the full output | `%LOCALAPPDATA%\ACU\crashes\<timestamp>-<script hash>.json` |
| Tool infrastructure failures with Python stack traces | `%LOCALAPPDATA%\ACU\crashes\<timestamp>-tool.json` |
| Screenshots taken without `--out`, newest 30 kept | `%LOCALAPPDATA%\ACU\shots\<timestamp>-<action>.png` |

Set `ACU_HOME` to move these locations. ACU does not log script text, only its SHA-256, because scripts can contain secrets. A harness may independently record tool-call arguments. A crash report does quote the run's output, and an error message can cite fragments of the failing line, so treat crash reports as sensitive too. If tool crash-report persistence itself fails, the original error remains in the JSON response together with an explicit `diagnostic_error`.

## Computer-use test bench

`bench/` compares **Calculator** (`--scenario calculator`, the default) and **Adobe Illustrator Pen and Export** (`--scenario illustrator-pen-export`) across five profiles: Pi + GPT-6 Astra/low with ACU, CUA or Codex computer use; Claude Code + Opus 5.5/low with ACU or CUA. The benchmark reports total API tokens, estimated computer-use code tokens as a percentage of output including reasoning, and computer-use call durations. End-to-end/model-response times remain diagnostics, not performance scores. For Illustrator v0.8, the actor only draws genuine Pen-tool Bézier curves and leaves the document open; no save/export or report file is requested. Maintainer cleanup exports the unchanged live drawing outside actor measurements and records any export failure separately as infrastructure. Drawing revisions follow the versioned scenario in the benchmark guide. Quality and code share are observations, not pass thresholds. Three trials per configuration are aggregated by averaging every success, without trimming; see the benchmark guide. Standing desktop authorization covers the current benchmark work; the explicit CLI approval gate remains. See [bench/README.md](bench/README.md) for commands and measurement limits.

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
