# Select an observed window

Run `windows.list` to print each current handle, title, class, and process. Retain the intended handle as `ahk_id <handle>` for inspection, waits, activation, and cleanup.

A process name is not necessarily the top-level window's process: CalculatorApp.exe may appear under ApplicationFrameHost.exe. Select from observed titles and classes rather than guessing an executable filter. If the intended window is ambiguous, inspect further or report the ambiguity before acting.

For a new-window task, snapshot existing handles before launching and identify a new matching handle. Preserve existing windows. A successful listing is only an observation, not proof of task completion.
