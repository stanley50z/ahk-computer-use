# Script-first computer use on macOS

Research notes from 2026-10-22. Nothing here was prototyped or run on a Mac. The ACU source was inspected directly; claims about Hammerspoon and macOS are from its documentation, a short web search and general platform knowledge. Items marked **unverified** need checking before a prototype.

## Background questions

**Is AutoHotkey related to Lua?** No. AutoHotkey forked from AutoIt v2 in 2003, is written in C++, and has its own language. v1 inherited AutoIt's command syntax, and v2 moved to an expression syntax closer to JavaScript. Hammerspoon is an Objective-C macOS app that embeds a Lua interpreter and exposes macOS APIs as `hs.*` modules. Its site describes it as "a bridge between the operating system and a Lua scripting engine" ([hammerspoon.org](https://www.hammerspoon.org/)).

**Can one Lua script automate every OS?** Not in practice. Lua has no desktop access of its own, and a Hammerspoon config is calls to `hs.*`, which exists only on macOS. No mature Windows host offers the same API. On r/hammerspoon, the usual answer to "alternative for Windows?" is AutoHotkey ([thread](https://www.reddit.com/r/hammerspoon/comments/zaneff/alternative_for_windows/)). The language is the easy part. The OS automation APIs are the hard part:

| | Windows | macOS | Linux |
|---|---|---|---|
| Synthetic input and hotkeys | `SendInput`, keyboard hooks | `CGEvent`, event taps | X11 XTest; Wayland mostly blocks it |
| Reading UI elements | UI Automation | Accessibility `AXUIElement` | AT-SPI |
| Windows | Win32 `HWND` | `NSWorkspace` and AX | depends on the window manager |

Cross-platform tools either stay at the input-and-pixels level (`pyautogui`, `pynput`, nut.js, SikuliX), do one narrow job (Espanso for text expansion, Kanata for key remapping), or need per-OS backends for UI-tree work. Python is the most realistic single language: shared input libraries, with per-OS accessibility bindings behind a thin interface.

## How coupled ACU is to AutoHotkey

ACU is coupled in two layers. Agents write AutoHotkey v2, which is the product's interface. Everything below the scripts calls Win32 through AHK `DllCall` or Python `ctypes`, and AutoHotkey runs only on Windows.

| Layer | Size | Coupling |
|---|---|---|
| Interface: `acu/SKILL.md`, ADR-0001 | 136 lines | AHK language. ADR-0001 makes one AutoHotkey v2 script the unit of action. The skill teaches `SendText` vs `Send`, WinTitle syntax, `A_Args` and name collisions with built-in functions. Tree dumps print values as AutoHotkey string contents. Snippets are `.ahk` files. |
| Prelude and libraries: `prelude.ahk`, `lib/*.ahk`, `tree.ahk`, `screenshot.ahk` | about 900 first-party lines, plus 7,948 vendored `UIA.ahk` lines | AHK and Win32: UI Automation, GDI/`PrintWindow`/GDI+ capture, keyboard-layout switching, `WindowFromPoint`/`GetAncestor` pointer guards. |
| Launcher: `acu/run.py` | 246 lines | AHK `/include`, `/validate` and `/ErrorStdOut` switches; the UI Access build started through `ShellExecuteEx`; `WM_CLOSE` posted to `AutoHotkey`-class windows; output passed through a file because UI Access processes get no stdout. |
| CLI and tool: `cli.py`, `tool.py` | about 170 lines | Mostly neutral. The desktop lease is a Windows named mutex. Results carry `"engine": "ahk"`, but ADR-0001 rules out an engine selector. |
| Snippets: `snippets.py` | 197 lines | Win32 process enumeration, App Paths registry, file version info. The store and header format are neutral. |
| `history.py`, `settings.py` | about 590 lines | A few AHK-specific patterns such as `ahk_exe`. |
| Bench and tests | about 3,900 Python lines plus `.ahk` helpers and fixtures | Windows apps by design: Calculator, Illustrator, Office through COM. |

The architecture does not depend on AutoHotkey and would carry over:

- one script per action chain
- an injected prelude
- the watchdog and the ok/error/timeout outcomes
- the lease, run log and crash reports
- the perception ladder and the look-act-check loop
- the snippet store
- the bench harness

A port rewrites the prelude, libraries and launcher, plus the skill's language guidance.

## What the script-first pattern needs from an engine

On Windows, one AutoHotkey process per script does three jobs:

1. **Holds the privilege.** The UI Access build drives elevated windows.
2. **Provides the OS bindings:** UIA, `SendInput`, GDI capture.
3. **Is a disposable sandbox.** Script variables die with the process, and the watchdog can kill a hung script.

browser-harness splits these jobs: a persistent daemon holds the CDP connection, and each heredoc runs as a fresh Python process with helpers pre-imported. A macOS engine has to decide where each job lives.

## Recommendation: Hammerspoon as the engine

The agent loop is unchanged. Each turn writes a `.lua` file and runs `acu run script.lua -- args`. Exploration uses bundled `tree.lua` and `screenshot.lua`, or temp scripts. A sketch of the intended API (none of these `Acu*` functions exist yet):

```bash
cat > ./look.lua <<'EOF'
local win = AcuLaunch("com.apple.Notes", {title = "Notes"})
print("pid=" .. win.pid .. " id=" .. win.id)
print(AcuTree(win, {role = "AXButton"}))
EOF
acu run ./look.lua
```

| ACU on Windows | macOS with Hammerspoon |
|---|---|
| UI Access build holds the privilege | Hammerspoon.app gets Accessibility and Screen Recording once. Code runs inside it, so its grants apply whichever terminal or harness calls `acu`, and the harness needs no Accessibility grant. |
| `UIA.ahk` | `hs.axuielement`: roles, titles, `AXIdentifier`, values, frames, `AXPress`. The menu bar sits in each app's AX tree. |
| `SendText` / `Send` | `hs.eventtap.keyStrokes(text)` / `hs.eventtap.keyStroke(mods, key)`; the same text-vs-chord rule. |
| `PrintWindow` app capture | `hs.window:snapshot()` or `screencapture -l <windowID>`. **Unverified** on macOS 15 and later, where Apple is pushing capture toward ScreenCaptureKit. |
| English input guard | `hs.keycodes` to read and select input sources. |
| Prelude via `/include` | The launcher loads each script into a prelude environment (below). |
| Named-mutex lease | `flock` on a lock file, released if the holder dies. |
| UAC prompt is out of reach | Password and authorization prompts (SecurityAgent) ignore synthetic input. |

The agent would call Hammerspoon through its `hs` command-line tool (`hs.ipc`). **Unverified:** its exact flags, how it runs a file with arguments, and how `print` output returns to the caller.

### Where Hammerspoon breaks ACU's guarantees

Hammerspoon is one long-running process, and Lua runs on its main thread.

- **Isolation.** Load each script with `load(src, name, "t", env)`, where `env` is a fresh table that falls back to the prelude, so script variables do not persist. Timers and watchers a script creates outlive it. The prelude should wrap and stop them at the end of the run, or the skill should forbid them.
- **Watchdog.** A `debug.sethook` count hook can raise an error past the deadline, which stops runaway Lua loops. It cannot interrupt a blocking C call such as an AX query to a hung app. Set a short AX messaging timeout for that case. As the last resort, the launcher kills and relaunches Hammerspoon and reports `timeout`. That recovery is heavier than killing one AHK process, and it also restarts any personal Hammerspoon config.
- **Blocking.** Hammerspoon's own hotkeys freeze while a script runs. ADR-0002 already requires short scripts.

### Alternatives considered

- **JXA (`osascript -l JavaScript`).** Built in, with a fresh process per script, the closest process model to ACU. UI scripting through System Events costs one Apple event per property, so full tree dumps are slow. The Accessibility grant attaches to the responsible process (the terminal or harness), so every harness needs its own grant.
- **Python with pyobjc.** Has the same permission attribution problem, plus a dependency stack.
- **A small signed Swift runner embedding JavaScriptCore.** The most faithful port: fresh-process isolation, a real watchdog, agents writing JS, and its own TCC grants. To get its own grants, it must be launched as its own responsible process (as an app through `open`, or through launchd). That means no stdout, so it needs the output-file technique `run.py` already uses for UI Access. The AX, input and capture layers would all be first-party. Build it only if Hammerspoon's persistent-host failures matter in practice.

## Platform details a port must handle

- **Coordinates are points, not pixels.** AX and `CGEvent` both use top-left global points. Retina screenshots are 2x, so the printed `scale` matters more than on Windows.
- **Apps are single-instance.** Launching a running app activates it instead of starting a process. `AcuLaunch` must diff windows rather than processes and handle an app that reuses its one window.
- **Focus is per app**, and activation is less forceful than on Windows. `AcuActivate` needs its own observed wait.
- **Snippets** would be keyed by bundle ID instead of executable name.

The CLI, JSON result, trailer, run log, perception ladder, snippet header format and bench harness carry over unchanged.

## First checks before a prototype

1. The `hs` CLI's file-and-arguments invocation, output return, and behavior when Hammerspoon is blocked.
2. Window capture without activation on current macOS.
3. AX messaging timeout behavior against a deliberately hung app.
4. `debug.sethook` deadline overhead on a tree dump of a large app.
