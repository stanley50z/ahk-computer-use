<h1 align="center">ACU</h1>

<h3 align="center">A Script-first Computer Use Agent tool for Windows, built on top of AutoHotkey</h3>

<p align="center">
  Find controls through Windows UI Automation, use the mouse and keyboard, and take screenshots to check the result.
</p>

<p align="center">
  <a href="#getting-started">Getting started</a> ·
  <a href="#usage">Usage</a> ·
  <a href="#debugging-artifacts">Debugging</a> ·
  <a href="bench/README.md">Benchmarks</a> ·
  <a href="https://stanley50z.github.io/ahk-computer-use/reports/latest/">Latest report</a>
</p>

## Built on top of

- [AutoHotkey v2](https://github.com/AutoHotkey/AutoHotkey) runs the scripts and provides Windows automation.
- [UIA-v2](https://github.com/Descolada/UIA-v2) by Descolada gives scripts access to Windows accessibility trees and controls.

## Getting started

### Requirements

- Windows with AutoHotkey v2 installed, including its UI Access option.
- Python 3.12 or newer.
- [uv](https://docs.astral.sh/uv/) for the installation commands below, or another Python package installer that provides console commands.

The AutoHotkey installation should contain `C:\Program Files\AutoHotkey\v2\AutoHotkey64_UIA.exe` beside `AutoHotkey64.exe`. For a different installation location, set `ACU_AHK` to the UI Access executable and keep the plain build beside it. Windows requires the UI Access executable to be signed and installed under Program Files; copying it elsewhere will not work.

### Install the CLI

From this checkout:

```sh
uv tool install --editable .
acu --help
```

Make sure uv's tools bin directory is on `PATH`; `uv tool dir --bin` shows its location. The editable install follows changes in this checkout. ACU uses Python's standard library and your existing AutoHotkey installation, with no Python runtime package dependencies.

After installation, run `acu` directly. You do not need to prefix commands with `uv run` or `python`. To uninstall, run `uv tool uninstall acu-desktop`.

### Connect your agent

Install the CLI first, then link the skills for agent sessions inside this repository:

```sh
python install_skill.py
```

This links `acu` and `retro-acu` under `.agents/skills/` for Pi, Codex, and OpenCode, and `.claude/skills/` for Claude Code. The links are gitignored. Restart your agent session, or use `/reload` in Pi, to pick them up.

To make the skills available outside this repository, use `python install_skill.py --global`. That links them into the user-level skill directories for those harnesses. Use `--remove` to remove the repository links, or `--global --remove` to remove the global links.

The [ACU skill](acu/SKILL.md) is the complete agent-facing manual. [retro-acu](retro-acu/SKILL.md) is an optional, user-invoked review of a completed session that proposes reusable snippets and repairs. It changes the snippet store only after approval.

The skill installer and `retro-acu/` are included in the source distribution, not the wheel. The wheel contains the `acu` package and its skill.

## Usage

ACU runs each script with a timeout and captures its output and errors. It works through the `acu` CLI; there is no server or MCP setup.

Run an AutoHotkey v2 script:

```sh
acu run action.ahk --timeout 30
```

ACU runs files you supply; it does not create or delete your action scripts. Arguments after `--` reach the script as `A_Args`:

```sh
acu run action.ahk -- "argument for the script"
```

Two bundled scripts let you inspect an application without writing your own:

```sh
acu run tree.ahk -- "ahk_exe CalculatorApp.exe"
acu run tree.ahk -- "ahk_exe CalculatorApp.exe" --find Six
acu run screenshot.ahk -- app "ahk_exe CalculatorApp.exe"
```

These examples require Calculator to be open. Replace the target with an application's executable name, window title, or `ahk_id <handle>`. A local file named `tree.ahk` or `screenshot.ahk` takes precedence over the bundled copy.

The tree lists control names, IDs, bounds, available actions, and values. Values are printed in full, including document text. Use `--find <text>`, `--type <Type>`, `--depth <n>`, or `--max <n>` to narrow the dump. Applications vary in how much they expose through accessibility; screenshots and pointer input are still needed when a control is absent from the tree.

Screenshots support `app "<target>"`, `fullscreen [monitor]`, and `custom <x1> <y1> <x2> <y2>`. Add `--out <path.png>` to choose a destination or `--max <pixels>` to change the longest image side (default 1280, `0` for full resolution). Output includes the PNG path and the mapping between image and screen coordinates. App capture can omit separate menus and dialogs; use an on-screen capture for those.

`acu run` returns one JSON result with the script output, outcome, exit code, duration, and artifact paths. A successful script exit does not prove that the application did what you wanted; check the tree or screenshot afterward. Timeouts must be greater than zero and no more than 300 seconds, and cover validation plus script execution. Overlapping CLI runs are rejected with a `busy` error.

### What ACU prepares for each script

The [prelude](acu/prelude.ahk) loads automatically, so scripts need no setup boilerplate. It provides the `UIA` class, screen-based mouse and pixel coordinates, per-monitor DPI awareness, and error reporting without modal dialogs. Helpers include `AcuLaunch` for opening a new application window, `AcuWaitUntil` for polling a condition, `AcuTree` for reading controls, and `AcuScreenshot` for capturing images. Optional paced input helpers live in `acu/lib/actions.ahk`.

Scripts run through AutoHotkey's signed UI Access build. They can inspect and interact with elevated applications without running as administrator, but cannot reach the UAC consent prompt on its separate desktop. The launcher checks for load-time errors with the plain AutoHotkey build before execution. On timeout or Ctrl+C, it asks the script to close, then kills it one second later if needed and verifies that it exited before releasing the desktop lock. A timeout returns exit code 124; Ctrl+C or Ctrl+Break returns 130 and records the interrupted run. Captured output from an executing script is retained; interrupted validation may have no recoverable output. Validation is bounded too, including load-time warning dialogs. If Windows refuses shutdown, ACU reports and persists the failure, then retains the process handle and desktop lock until exit can be verified; further console interrupts do not abandon it. Force-killing the launcher bypasses its cleanup; ACU is not a process sandbox and does not automatically stop applications a script launched.

ACU leaves the cursor and foreground window where the script leaves them, including after errors and timeouts. It prepares a loaded English keyboard layout before keyboard input and does not restore the previous layout. If it cannot verify English input, keyboard sends fail before sending keys; inspection and mouse actions remain available. ACU does not install keyboard layouts.

ACU controls your real desktop. It is not a sandbox or an access-control boundary.

### Saved snippets

```sh
acu snippets list <app> [keyword...]
```

Snippets are ordinary `.ahk` files stored in `~/.ahk-computer-use/snippets/<exe name>/`. Listing searches app names, filenames, and leading comment fields such as `does`, `args`, `needs`, `effect`, `check`, and `tested`. It prints plain text and does not launch AutoHotkey. `ACU_SNIPPETS_ROOT` overrides the store location.

ACU also lists an app's snippets when a script calls `AcuLaunch` or runs an unfiltered bundled `tree.ahk` dump. To disable discovery, put this in `~/.ahk-computer-use/settings.json` or a project's `.ahk-computer-use/settings.json`:

```json
{ "snippets": { "enabled": false } }
```

The nearest project settings file, searched upward from the command's working directory, overrides the global setting. This controls discovery, not permission to run a saved script by path. See [the snippet design](docs/adr/0010-reusable-snippets.md) for storage and lifecycle details.

### Session review

```sh
acu history <session-file.jsonl>
```

History reads a native Pi, Codex, or Claude Code session alongside ACU's run log. It summarizes app activity, repeated attempts that may be worth saving as snippets, changed snippets, and snippets with frequent failures. It does not use the desktop or modify the store. Missing or ambiguous evidence stays unknown. Run `acu history --help` for the matching rules and thresholds.

New run records include `app`, captured from snippet markers before discovery expands them. It is the process name, or `null` when no marker identifies a single app. `ApplicationFrameHost.exe` does not identify an app; repeated names ignore case, and markers naming different apps remain unknown. This works even when snippet listing is disabled or the store is missing. History uses the recorded value, including `null`, without inferring a different app from captured output or script selectors. Only older records without `app` (and unmatched requests) use the legacy inference from script selectors, snippet paths, dump headers, and snippet listings. Run logs still contain no script text.

## Debugging artifacts

| Artifact | Default location |
| --- | --- |
| Run log, one JSON line per run | `%LOCALAPPDATA%\ACU\logs\runs.jsonl` |
| Script errors and timeouts, with full output | `%LOCALAPPDATA%\ACU\crashes\<timestamp>-<script hash>.json` |
| Tool failures, with Python stack traces | `%LOCALAPPDATA%\ACU\crashes\<timestamp>-tool.json` |
| Screenshots taken without `--out`, newest 30 kept | `%LOCALAPPDATA%\ACU\shots\<timestamp>-<action>.png` |

Set `ACU_HOME` to move these locations. Screenshots saved outside the managed shots folder are never pruned.

The run log records a script's SHA-256, not its source. Crash reports include output, which can contain sensitive text or fragments of a failing line. Accessibility dumps and screenshots can contain document content too. Review these before sharing them. If saving a tool crash report fails, the JSON response includes a `diagnostic_error` alongside the original error.

## Development

```sh
uv sync
uv run pytest -q
uv build
```

The default tests do not run AutoHotkey or interact with the desktop. Desktop integration tests require `--desktop` and can open windows, move the cursor, and change focus. Run them on an available desktop, choosing only the checks relevant to your change:

```sh
uv run pytest --desktop tests/test_tool.py -q
```

Tests require pytest; screenshot tests also require Pillow.

For launcher development, the low-level entry point remains available:

```sh
python acu/run.py script.ahk [--timeout 30] [-- arguments for the script]
```

It returns merged stdout/stderr followed by an `[acu]` status trailer, rather than the CLI's JSON. It does not take the CLI's desktop lease. Scripts do not inherit the launcher's environment through Windows ShellExecute; pass values as arguments. `ACU_HOME` is passed through explicitly.

### Vendored code

`acu/lib/UIA.ahk` is copied from Descolada's UIA-v2 at commit `2846a9b` (2026-04-23), under the MIT license in [UIA-LICENSE.txt](acu/lib/UIA-LICENSE.txt). One line, marked `; ACU patch:`, fixes single-segment numeric paths in `ElementFromPath`. To update the library, copy the upstream file and reapply that line. The other ACU helpers are first-party code.

## License and third-party assets

ACU's first-party code and materials are licensed under the [MIT license](LICENSE). Third-party files retain their original ownership and terms; ACU's license does not relicense them.

- **UIA-v2:** MIT, copyright Descolada. Its [license notice](acu/lib/UIA-LICENSE.txt) is retained with the vendored library.
- **GUI-360 Office templates:** copied from [vyokky/GUI-360](https://huggingface.co/datasets/vyokky/GUI-360). The [dataset card at the revision used here](https://huggingface.co/datasets/vyokky/GUI-360/blob/1c46362efaae836c601004e77b98a1aba89a530f/README.md) explicitly declares MIT, but the dataset supplies no separate `LICENSE` file at that revision. See the [template provenance](bench/assets/gui360/README.md) for exact sources and hashes. This upstream declaration does not independently establish rights in any third-party content within the templates or grant Windows/Microsoft Office licenses.
- **Cloud9 logo reference:** the Illustrator benchmark's reference image is third-party artwork, so this repository does not include it. `bench/build_reference.py` builds it locally from the icon in [Cloud9's official brand assets](https://cloud9.gg/brand-assets/). Cloud9's artwork and marks remain subject to its [terms](https://cloud9.gg/terms-of-service/) and brand guidelines; this repository grants no rights to them and claims no affiliation or endorsement. See [reference provenance](bench/assets/illustrator-pen-tool/README.md).

Attribution and this disclaimer are not permission to redistribute third-party assets. Establish the applicable rights before reuse or redistribution.

## Benchmarks and project notes

The [computer-use test bench](bench/README.md) compares ACU, CUA, and Codex computer use on Calculator, Adobe Illustrator Pen drawing, and TB3.1–TB3.4 Office tasks. Its guide covers scenarios, commands, measurement limits, and cleanup. Results and investigations are indexed in [docs/reports/](docs/reports/README.md); experiments include [click delivery while the cursor is moving](experiments/jiggle/).

**[Latest report: Illustrator and TB3.1–TB3.4](https://stanley50z.github.io/ahk-computer-use/reports/latest/)** — the 20–21 October 2026 rounds, with metrics, output comparisons and silent web-optimized video clips.

Publishing every trial's output is not required. Raw native session archives remain local. Historical reports may retain curated turn-by-turn command/output evidence and cite local-only artifacts.

For project background, see the [domain context](CONTEXT.md), [architectural decisions](docs/adr/), [original design notes](docs/design/acu-brainstorm-2026-10-08.md), and [research](docs/research/README.md).

## Inspiration and reference

- [browser-harness](https://github.com/browser-use/browser-harness) for agent-driven browser control through scripts.
- [CUA](https://github.com/trycua/cua) for computer-use tooling and comparisons.
- [Hammerspoon](https://github.com/Hammerspoon/hammerspoon) for scriptable desktop automation on macOS. ACU currently supports Windows only.
