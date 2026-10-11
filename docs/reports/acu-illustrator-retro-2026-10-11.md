# ACU follow-up from the Illustrator exploration

Specification: [issue #11](https://github.com/stanley50z/ahk-computer-use/issues/11). Architectural decision: [ADR-0009](../adr/0009-persistent-desktop-state-and-english-input.md).

## Decisions implemented

1. **Capture guidance:** `acu/SKILL.md` and `README.md` distinguish app-window `PrintWindow` rendering from live on-screen capture. App capture remains useful for covered document content. For menus, popups, and dialogs, activate the intended target and capture the screen or a rectangle after observing appearance/repaint. A native-menu check proves that the screen capture includes a popup absent from the parent-window render. No screenshot mode was removed or silently changed.
2. **Persistent desktop state:** removed cursor-position/focus restoration, takeover comparison, mouse tracking, and `AcuKeepForeground()`. Native mouse functions remain native. Normal exit, runtime errors, and timeouts leave desktop state at the last action. The user reconfirmed deletion rather than an optional restore mode, and reconfirmed keeping benchmark post-trial owned-resource cleanup and saved-cursor-scheme reload. Those benchmark implementations are unchanged.
3. **Automatic English input:** a first-party `acu/lib/keyboard.ahk` guard runs at startup and immediately before ordinary native send calls. It prepares the actual focused input window/control and the sending thread. For non-English input it prefers loaded English (United States), otherwise another loaded English keyboard. It verifies English before sending keys, preserves native send parsing/mode and Last Found Window semantics, and accepts the native omitted-Control form of `ControlSend`. It does not install layouts, change the configured language list, or restore the earlier language. Expected startup failures warn and still permit inspection/mouse actions; keyboard sends fail before input if preparation fails. Raw Win32/application-specific injection is outside this guard.
4. **Launch diagnostics:** `AcuLaunch` snapshots existing windows, including hidden ones, allows up to 500 ms of settling bounded by the requested timeout, rechecks the candidate set after tree polling, and lets multiple startup candidates clear until the deadline. Persistent ambiguity reports HWND, title, class, and PID for each candidate rather than guessing. A pre-existing hidden window that becomes visible is not a new window.

The keyboard guard is first-party code. Vendored `acu/lib/UIA.ahk` was not modified. The watchdog, UI Access, error reporting, and persistent runtime artifacts remain.

## Deferred investigations

- [Issue #12: sparse accessibility coverage in professional applications](https://github.com/stanley50z/ahk-computer-use/issues/12). Illustrator's main window exposed only frame/menu elements while some dialogs exposed useful controls. No broader tree/discovery implementation was added.
- [Issue #13: provider-advertised writability that fails](https://github.com/stanley50z/ahk-computer-use/issues/13). ACU derives the `value` flag from provider availability/read-only metadata. The original setter failure did not retain the underlying HRESULT, so fault cannot yet be conclusively assigned to the app versus a library incompatibility. No flag-format change, checked-edit helper, or vendor patch was added.

## Validation

The user explicitly approved focused desktop red/green checks with disposable windows and temporary selection of the installed Chinese IME. These are wrapper checks, not benchmark trials or a test of drawing the logo in Illustrator.

Final results:

- **29 focused desktop checks passed.** Cursor/focus persistence on success/error/timeout; Chinese-to-English input and literal Unicode text across six sending routes; a foreign application thread accepting/refusing the request; startup warning with read-only execution; omitted-Control and Last Found Window compatibility; single/transient/slow/persistent/revealed-existing launch cases; popup screen-vs-app capture; relevant prelude and watchdog checks.
- **27 quiet checks passed, 2 desktop checks intentionally deselected.** Skill/installer, CLI request validation, and focused benchmark cleanup/conduct checks.
- `git diff --check` passed.
- Cleanup verification reported `foreground_primary=9` (English) and `leftover_fixture_windows=0`. No task fixture processes remained; the pre-existing AutoHotkey process was preserved.

Final commands used the project's `uv` environment:

```bash
uv run pytest tests/test_desktop_state.py tests/test_keyboard.py tests/test_prelude.py tests/test_screenshot.py::test_on_screen_capture_contains_a_live_popup_missing_from_the_app_render tests/test_launcher.py::test_timeout_asks_script_to_exit_then_reports_124 tests/test_launcher.py::test_timeout_kills_script_that_ignores_close_request tests/test_launcher.py::test_globals_named_like_prelude_locals_produce_no_warning tests/test_launcher.py::test_runtime_error_is_printed_with_location_and_exits_nonzero --desktop -q
uv run pytest tests/test_skill.py tests/test_tool.py tests/test_bench_cleanup.py tests/test_bench_conduct.py -q
```

The desktop run was interrupted while the user needed the computer. Verified that no interrupted pytest/controller or fixture processes remained, then reran after the user asked to continue. Keep the interrupted logs separate from the final passing run. An earlier global-Python quiet run could not find that interpreter's `acu.exe`; running in the documented project environment resolved it without changing CLI tests or installing a global package.

Tests use real Windows APIs and the machine's installed Chinese IME with disposable application fixtures. The no-English enumeration branch is simulated at the Win32 API boundary rather than removing any configured language. The one-second switch verification was exercised here, not established as a universal timing guarantee for professional software. `SendPlay` retains native platform limitations and was not included among the six successful typing routes.

## Standards review

A read-only Fable 5.1 reviewer examined the tracked diff and relevant untracked code against fixed HEAD `bd56e0395a45e7d542965129c8b9f1176a841ba6`.

- Fixed stale glossary/ADR restoration references, merged the extra skill prose check into the existing check, and renamed the replacement state tests to `test_desktop_state.py`.
- Kept the single-window/no-match launch check: its identity/readiness assertions are distinct from multi-window and hidden-window scenarios. The latter share one parameterized fixture.
- The omitted-Control concern was reproduced and fixed. An explicit empty string was separately tested and also rejected by the original native function, so it was not treated as a supported form.
- Resolved startup inspection blocking with warning-only startup preparation and strict send-time checks.
- Made candidate collection explicitly local to avoid overwriting the outer snapshot during rechecking; documented why Win32 calls use a callable API boundary.
- The send-function interception mechanism was verified through the public CLI. Fixtures keep independent input-state setup rather than calling the implementation to derive expectations.
- Settling overhead remains an intentional, bounded launch trade-off. Tree element counts remain best-effort observations, not guarantees that all custom UI or repaint has completed.

## Spec review

A separate read-only Fable 5.1 reviewer used the fetched issue #11 specification and the same fixed scope.

- Deferred observations are recorded in issues #12/#13 and this report, not implemented as UIA changes.
- Changed the initial early ambiguity rejection to wait until the deadline; added a slow-splash regression and protected revealed pre-existing hidden windows.
- Fixed omitted-Control handling and Last Found Window mutation with public-interface regressions.
- Allowed inspection after expected startup preparation warnings, while retaining explicit failure before keyboard injection.
- Bounded the startup settling period and tree polling by the remaining timeout rather than imposing a fixed minimum of 500 ms.
- Removed an unverified causal claim about AutoHotkey's key translation; the documented behavior is preparation/verification of destination and sender layouts.

The reviewers found no unrelated implementation scope creep. Their initial tracked scope excluded the starter assets and source-inspection report from the earlier task; those were preserved.

## Evidence and debugging paths

Persistent local validation evidence:

`C:\Users\13982\ahk-computer-use\.pi\logs\acu-illustrator-fixes\`

Final logs: `final-desktop-resumed.log`, `final-quiet.log`, and `final-state.log`. Red/green logs cover restoration removal, input switching, ControlSend compatibility, Last Found Window/startup warnings, capture guidance, and launch settling/hidden-window protection. Native preparation/diagnostic probes are retained as evidence rather than actor input. The initial review snapshot is `review.patch`, with the fetched spec in `review-spec.json`.

Normal runtime log: `C:\Users\13982\AppData\Local\ACU\logs\runs.jsonl`.

Runtime failure reports with output and stack traces: `C:\Users\13982\AppData\Local\ACU\crashes\`. Focused pytest runs route runtime artifacts into their temporary `ACU` folders; complete test-failure output is preserved in the persistent validation logs above.

No full desktop suite, benchmark trial, temporary server, commit, push, or Wiki regeneration was performed.
