# Scripts run under AutoHotkey's UI Access build, started through ShellExecute

An ordinary process cannot see an elevated window's tree or send it input; Windows drops both silently, and the prelude then misread the dropped cursor move as a user takeover. Running scripts elevated would fix that at the price of a UAC prompt per run or a weakened UAC policy, elevated child programs, and the same launch problem. Windows has a mechanism for exactly this case, UI Access, which AutoHotkey ships as a signed `AutoHotkey64_UIA.exe`; it runs at normal integrity and may read and drive elevated windows, so the launcher runs every script under it. The UAC consent prompt itself is on a separate desktop and remains out of reach.

## Consequences

- Windows refuses to start a UI Access program from a plain `CreateProcess`, so the launcher uses `ShellExecuteEx` and gets neither a stdout pipe nor environment inheritance. It passes exactly two internal arguments, an output file and `ACU_HOME`, that the prelude consumes in that order; caller arguments after them remain literal even when they start with `--acu-`. The prelude redirects stdout and stderr into the file with `SetStdHandle`, which keeps `FileAppend "*"` and the error path unchanged. Anything else a script needs is an argument after `--`.
- Syntax errors and load-time warnings appear before the prelude runs and would be lost, so the launcher first loads the script without running it, under the plain build with a pipe. A script that does not parse ends there with exit code 2.
- A UI Access program sits above the launcher's integrity level, so the prelude lets `WM_CLOSE` through its message filter; otherwise the timeout's close request would be dropped and every timeout would be a kill.
- The plain build remains in use for the validate pass and for the tests' stand-in windows, and must sit beside the UI Access build.
- The UI Access build must be the signed copy under Program Files; Windows grants nothing to a copy elsewhere.
