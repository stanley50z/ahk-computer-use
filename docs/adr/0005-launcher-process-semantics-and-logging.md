# The launcher waits for the process, asks before it kills, and logs without script text

Superseded in part by 0008: output now arrives through a file the prelude writes rather than a pipe. Waiting on the process rather than on its output, the close request before the kill, and the logging rules stand.

The launcher reads the script's output on a thread and waits for the AutoHotkey process rather than for end of file, because a program the script starts inherits the output pipe and would otherwise hold the launcher open until that program exited. At the time limit it posts a close request to the script's main window so the prelude's exit handler can restore the desktop, and kills one second later; exit code 124 marks either path. Every run appends one JSON line under `%LOCALAPPDATA%\ACU` and failures write a crash report with the output, but script text is never logged, only its hash, because a script carries whatever the agent typed, including secrets.

## Consequences

- The pipe reader is joined with a short grace period, not drained to end of file. That is deliberate; a "cleaner" `communicate()` reintroduces the stall.
- Crash reports quote the run's output, which can include fragments of a failing line, so they are sensitive too.
- Screenshots taken without an explicit path live in a managed folder that keeps only the newest thirty, for the same reason.
