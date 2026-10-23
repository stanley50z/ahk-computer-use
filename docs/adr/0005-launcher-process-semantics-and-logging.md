# The launcher waits for the script process, requests close before killing, and logs without script text

[ADR-0008](0008-ui-access-build-started-through-shellexecute.md) supersedes the original pipe reader with a file the prelude writes. The launcher still waits for the script process, not for output EOF or for programs the script starts. At the time limit it posts a close request to the script's main window so the script's own exit handlers can run, then kills it if it remains running after a one-second grace period. Exit code 124 marks either timeout path. This close request is not a request for user approval. [ADR-0009](0009-persistent-desktop-state-and-english-input.md) removes desktop restoration; the script's own exit handlers can still run.

Validation and execution share the caller's timeout budget. A stalled validator is killed and reaped, with its captured output returned as a validation timeout. Ctrl+C/Ctrl+Break stops and reaps the launched script before the CLI releases its desktop lease; it returns exit code 130 and records available output. Interrupted validation can have no recovered output. Console interruption is deferred across process creation until ownership is registered. Cleanup retries interrupted shutdown rather than abandoning the script. If shutdown fails, the failure and stack trace are persisted and reported, and the launcher retains the handle and desktop lease until the OS confirms exit. Subsequent console interrupts are deferred during that fail-closed wait. Force-killing the launcher bypasses this cleanup, and programs started by the script remain outside this script-process watchdog.

Every recorded run appends one JSON line to `%LOCALAPPDATA%\ACU\logs\runs.jsonl`. The entry includes the script's path and SHA-256, not its source text, because scripts may contain secrets. Errors and timeouts also produce a JSON crash report with full output under `%LOCALAPPDATA%\ACU\crashes\`. `ACU_HOME` overrides this diagnostic root. Unexpected CLI exceptions use the same crash directory for tool reports with Python stack traces.

## Historical pipe implementation

Before ADR-0008, the launcher read output on a thread and waited for the AutoHotkey process rather than for end of file. A program the script started could inherit the output pipe and otherwise hold the launcher open until that program exited. The reader was joined with a short grace period instead of draining to EOF; replacing that wait with an unbounded `communicate()` would have reintroduced the stall. This records the reason for the original implementation, not the current output transport. The plain-build validation pass still captures output through a pipe.

## Consequences

- Crash reports quote the run's output, which can include document text or fragments of a failing line, so they are sensitive too.
- Screenshots taken without an explicit path live in `%LOCALAPPDATA%\ACU\shots\`, where only the newest thirty are kept. Captures saved outside that managed folder are not pruned.
- The CLI returns diagnostic paths in its JSON result; the low-level launcher prints output followed by a trailer. Detailed paths and logging-failure behavior are in the root `README.md`.
