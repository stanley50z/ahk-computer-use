# ACU handoff

## State at handoff

Latest commit on `main`, pushed: `eae5264` (`feat: Run scripts with UI Access and capture scaled windows as shown`). The working tree is clean apart from this untracked handoff file. GitHub reported no open issues.

**Committed in `eae5264`, 2026-10-09: scripts now run under AutoHotkey's UI Access build** (user decision, implemented test-first; see ADR 0008). Changed: `acu/run.py` (ShellExecuteEx launch, validate pass under the plain build, output file, `--acu-out=` and `--acu-home=` leading arguments, `plain_ahk_exe()`), `acu/prelude.ahk` (consumes those arguments, `SetStdHandle` redirect, `WM_CLOSE` message-filter allowance), `tests/conftest.py` (stand-in windows use the plain build), `tests/scripts/restore_probe.ahk` and `click_own_button.ahk` plus their tests (scenario via script arguments, since the environment no longer crosses the launch), new `tests/scripts/uiaccess.ahk` with `test_scripts_run_with_ui_access_so_elevated_windows_are_reachable`, README, SKILL (elevated-window fact, exit 2 row), CONTEXT (UI Access term), ADR 0008, note in ADR 0005. Then, same day, on the user's instruction: the end-to-end run through the launcher against an elevated Notepad++ passed (`.pi/logs/e2e-chain.log`: 67 tree elements, typing, click, undo, and even `WinClose` worked; no misattributed takeover note). The `app` capture fix landed in `acu/screenshot.ahk`: `CaptureWindow` reads the window's size in its own DPI awareness context, which is the size `PrintWindow` renders, and stretches that to the on-screen size; the DPI-comparison approach was tried first and was wrong, because Windows can display a system-aware window scaled even on a monitor whose DPI equals the window's. Test `test_app_capture_of_a_window_windows_scales_matches_what_is_on_screen` compares the app capture with a screen capture of the same rectangle; it skips unless a monitor differs from the system DPI, so run it with `python .pi/logs/setdpi.py set DISPLAY2 100` and restore to 200 after. `helper_window.ahk` gained `ACU_TEST_MONITOR` and `ACU_TEST_DPI_AWARENESS`. The remaining skill text feedback was applied (reserved names `menu`/`gui`, full path in `File name:`, poll for the save). Final full desktop suite: 43 passed, 1 skipped at uniform DPI (`.pi/logs/final-full.log`); the skipped test passed at mixed DPI. All of it is in `eae5264`.

The user requested this handoff, not another feature or desktop operation. There is no currently authorized next live task. Do not automatically start another full-suite run or GUI experiment.

## Read these instead of reconstructing the conversation

- `AGENTS.md`: current project policy, especially **Development**. This contains the user's latest decisions and supersedes earlier testing/install advice in this conversation.
- `README.md`: commands, installation scope, output contracts, debugging artifacts, and current test policy.
- `acu/SKILL.md`: the project-local skill agents actually use.
- `CONTEXT.md` and `docs/adr/`: terminology and architectural rationale. Read `docs/agents/domain.md` before exploring them.
- `docs/design/acu-brainstorm-2026-10-08.md`: historical starting point, not current completion status.
- `docs/reports/acu-progress-2026-10-08.html`: updated visual progress report. Some historical wording remains; source and current instructions take precedence.
- `docs/agents/issue-tracker.md`: GitHub issue workflow.

Closed specifications and implementation notes:

| Work | Record |
| --- | --- |
| Launcher/prelude | https://github.com/stanley50z/ahk-computer-use/issues/1 |
| Jiggle measurement | https://github.com/stanley50z/ahk-computer-use/issues/2 |
| Three screenshot actions | https://github.com/stanley50z/ahk-computer-use/issues/3 |
| Four-harness skill discovery; later changed to project-local | https://github.com/stanley50z/ahk-computer-use/issues/4 |
| First live-task fixes | https://github.com/stanley50z/ahk-computer-use/issues/5 |
| UI Automation/tree implementation | https://github.com/stanley50z/ahk-computer-use/issues/6 |
| Second live-task fixes and latest policy overrides | https://github.com/stanley50z/ahk-computer-use/issues/7 |

Read issue comments as well as bodies: issue #7 originally proposed suppressing document values, which the user explicitly rejected. The final implementation preserves full values. Its closing comment records the validation limitations and revised testing policy.

## Interaction lessons that matter next session

- Live acceptance exercises are meant to test a **fresh subagent following the ACU skill**, not the parent solving the task with its implementation knowledge. The user corrected the parent when it attempted the Calculator task itself. Give the child a self-contained task, bounded permissions, ownership/cleanup requirements, and ask for evidence plus blunt skill feedback.
- The latest interruption was about repeated desktop takeover during validation. Respect the focused, explicit-opt-in policy now in `AGENTS.md`; do not restore the earlier habit of running the full interactive suite after each change. Previously passed checks are not a reason to rerun them on every turn.
- The skill must remain project-local during development. Global ACU discovery links were removed. Do not run the installer's optional global mode without a new request.
- Editor testing preferences are recorded in `AGENTS.md`. Earlier claims that Notepad++ and Markpad were not installed were unsupported: only a default executable location and PATH were checked. Locate existing installations before proposing installation.
- Keep updates concise. Earlier responses often repeated plans and speculated about causes before verifying them; avoid repeating that pattern.

## Validation: what is and is not established

The changed tree behaviors and skill/installer checks passed in a focused run. The new default test selection was also verified without executing AutoHotkey. See the actual outputs rather than older chat claims of a fully green suite:

- `.pi/logs/issue-7-focused.log`
- `.pi/logs/issue-7-default-collection.log`
- `.pi/logs/issue-7-desktop-collection.log`
- `.pi/logs/issue-7-safe-default.log`
- `.pi/logs/issue-7-safe-final.log`

Broader runs **were not fully green**. Existing cursor/foreground restore assertions failed intermittently:

- `.pi/logs/issue-7-full.log`
- `.pi/logs/issue-7-full-rerun.log`
- `.pi/logs/issue-7-restore-diagnostic.log`

The diagnostic output includes `restore skipped: cursor moved by someone else`. No restore implementation was changed to hide the failures. These logs are local and gitignored; preserve them.

**Resolved 2026-10-09.** The user said they had been using the computer during those runs and authorized a hands-off rerun. The three previously failing tests (`tests/test_restore.py` and `test_timeout_asks_script_to_exit_then_reports_124`) passed twice in a row with no code changes:

- `.pi/logs/restore-verify-2026-10-09.log`
- `.pi/logs/restore-verify-2026-10-09-rerun.log`

The failed runs had landed the cursor at arbitrary screen positions, consistent with a human moving the mouse. Treat the intermittent restore failures as explained by concurrent desktop use; do not open an issue for them.

Runtime logs and crash reports remain under `%LOCALAPPDATA%\ACU\logs\` and `%LOCALAPPDATA%\ACU\crashes\`; the exact contracts are in README.

## Fresh-agent acceptance exercise, 2026-10-09

A vanilla Pi session (`pi -ne -ns -nc --skill acu`, `openai/gpt-6-astra`, thinking low) completed the Notepad++ task from the skill text alone: start Notepad++, new document, type one line, save to a temp path, close. Verified independently: the file is 32 bytes with the exact content and no trailing newline, no Notepad++ window or process remains, the restored `appt.ics` tab was untouched (mtime unchanged), and the top-level window list before and after differs only in the terminal title. Evidence:

- Transcript with tool calls: `.pi/logs/fresh-session/*.jsonl`
- Stdout of the three turns: `.pi/logs/fresh-agent-stdout*.log`
- Scripts: `%LOCALAPPDATA%\Temp\acu-fresh-test\scripts\01..06-*.ahk`
- Window probes: `.pi/logs/probe-env-before.log`, `.pi/logs/probe-env-after.log`

The agent used handles, tree lookups, and `Invoke()` throughout; no coordinate clicks. The first attempt stopped correctly on `restore skipped: cursor moved by someone else`, which the user confirmed was their own mouse use. The agent's blunt skill feedback, each point checked against the transcript:

1. **Exit 2 is undocumented.** An AutoHotkey parse error exits 2 with the parser message in the body. The verdict table only lists 0, 1, and 124.
2. **Save completion races the dialog closing.** `WinWaitClose` on the Save As dialog returned before the file existed; `FileRead` then failed with exit 1. The second run found the file. The skill should say to poll for the saved title or the file.
3. **Full path in `File name:` works** and is simpler than the address-bar recipe the skill gives. The skill should mention it.
4. **Initial title is transient** when Notepad++ restores a session: `new 1` first, then the restored tab. Minor.
5. The agent objected to the wording "moved by someone else" as asserting an unproven cause. In this run the cause was real, so this is a wording preference, not a defect.

None of these were applied to the skill. They are candidate edits for the user to approve.

## Mixed-DPI verification, 2026-10-09

Monitor 2 was switched from 200% to 100% through the display configuration API (`.pi/logs/setdpi.py`, no GUI, no logoff) and restored afterwards. A fresh Notepad++ (`-multiInst -nosession`) was moved onto it. Results (`.pi/logs/mixed-dpi-a.log`, `mixed-*.log`, `mixed-*.png`):

- **Correct:** tree bounds are physical screen pixels inside the window rect; a `Click` at the File menu's tree center opened the menu and the cursor landed exactly there; `fullscreen 2` reports the monitor rect at scale 2; `custom` reports the exact rect at scale 1; the parametrised fullscreen pytest passed for both monitors at mixed DPI.
- **Defect:** `screenshot.ahk app` on a DPI-virtualized window is wrong. Notepad++ is system-DPI aware (`GetDpiForWindow` returned 192 on the 96 DPI monitor), so Windows draws it at 100% on screen, but `PrintWindow` returns the app's own 200% rendering cropped to the physical window size. Compare `mixed-app.png` (200%, cropped) with the same window in `mixed-full2.png` (100%). A point read from that image maps to the wrong screen pixel by a factor of two. Per-monitor-aware apps are unaffected. Candidate fix: when `GetDpiForWindow(hwnd)` differs from the window's monitor DPI, scale the PrintWindow bitmap by monitor/window DPI, or fall back to a screen capture when the window is unobscured. Not fixed; no issue filed yet.

## Elevated windows, 2026-10-09

An elevated Notepad++ (`-multiInst -nosession`) was started through one UAC prompt by `.pi/logs/elevated-npp.ps1` and ended by the same script. From non-elevated ACU (`.pi/logs/elevated-tree-npp.log`, `elevated-input.log`, `elevated-cursor.log`, `elevated-custom.png`):

- `tree.ahk` returns `elements=0` with no error. UIA `FindElement` finds nothing. `WinGetProcessName` throws access denied.
- `WinActivate` works. `SendText`, `Click`, UIA `.Value`, and `ControlSend` are all dropped silently; the editor still showed `length : 0` in a screen capture. `WinClose` is ignored. `screenshot.ahk app` fails with "PrintWindow failed"; `fullscreen` and `custom` capture it fine.
- **Misattribution:** while the elevated window is in front, `MouseMove` is dropped too, and a non-elevated window cannot take the foreground from it. The prelude then prints `restore skipped: cursor moved by someone else` because the cursor is not where it placed it. The skill tells the agent to stop and ask, which is wrong here: nobody touched the mouse. Candidate fix: before printing that note, check whether the foreground window belongs to a process that cannot be opened (access denied) and print `input dropped: foreground window is elevated` instead. Also an `elements=0` tree on a window whose process name cannot be read should say so.

**UI Access route, verified 2026-10-09, then implemented (see State at handoff).** The user asked whether ACU could always run elevated without UAC. The better mechanism is AutoHotkey's UI Access build, `C:\Program Files\AutoHotkey\v2\AutoHotkey64_UIA.exe` (installed, signature valid). Run through it against an elevated Notepad++ (`.pi/logs/uia-access-npp.log`): the tree returned 67 elements instead of 0, `WinGetProcessName` worked, `SendText` marked the document modified, and `MouseMove` landed exactly. Constraint: Windows refuses to start a UI Access binary from a plain `CreateProcess` (`WinError 740`), so `run.py`'s `subprocess.Popen` with stdout pipes cannot launch it as is; `os.startfile` (ShellExecute) works but gives no stdout pipe. A switch would need the launcher to start the UI Access build through ShellExecute and collect output through a file or named pipe instead of inherited stdout. Running fully elevated instead is worse: it needs a UAC prompt or a weakened UAC policy, every program a script starts would be elevated too, and the pipe problem is the same. Not implemented; the user's decision.

Other small findings from this session: `menu` and `gui` are reserved names like `edit` and `click` (script failed to parse with `menu :=`); a relative `--out` path resolves against the `acu` directory, not the caller's working directory.

## Local resources and ownership

- The user explicitly chose to **keep** `%USERPROFILE%\github repo ref\UIA-v2` for reference/updates. No further retention question is needed.
- The prior Notepad exercise restored existing user documents when the app launched. Its own test tab and scratch scripts were removed, but user tabs were deliberately left intact. Do not close that application or inspect those documents as test cleanup.
- No temporary server was started. Do not terminate unrelated AutoHotkey processes; the user's own hotkey script runs separately.
- Project skill junctions are gitignored and already installed in this checkout. Use README's local setup only if they are missing in a new checkout.

## Suggested continuation

Ask which remaining area the user wants next; none is automatically authorized. The restore failures are resolved, the fresh-agent exercise passed, and the UI Access launch and the scaled-window capture fix are committed and pushed (see above). The elevated-window misattribution is moot now that input reaches elevated windows. No open candidates remain from this session; this handoff file itself is untracked and the user has not said whether to keep, move, or delete it. Any desktop work needs approval for that specific run and should avoid Windows Notepad.

## Suggested skills

- **unslop**: apply to all user-facing prose.
- **writing-for-agents**: before editing the skill or project instructions.
- **tdd**: for implementation fixes, using the project's focused/opt-in testing policy.
- **subagents** and the project-local **acu** skill: for a user-approved fresh-agent desktop exercise. Prefer Pi with an explicitly selected GPT model and reasoning no higher than medium.
- **domain-modeling**: only when changing vocabulary or ADRs, not for routine fixes.
- **code-review**: for a requested or warranted review against a fixed commit/spec; reviewers must not run desktop tests themselves.
- **commit**: when finalizing authorized changes. Do not wait for or repair background Wiki publication; see `docs/openwiki-sync.md` only if Wiki work itself is requested.

This handoff intentionally does not reproduce the implemented APIs, ADR decisions, or issue acceptance criteria. Follow the linked artifacts for those details.
