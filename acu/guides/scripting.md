# Compose an action chain

Write plain AutoHotkey v2: ACU supplies the prelude, screen coordinates, per-monitor DPI awareness, UIA class, zero mouse delays, runtime error reporting, and exit restore. Execute the entire predictable chain in one call; inspect again when intermediate states are unknown.

Select an observed target by title or `ahk_id`. Before pointer input or keystrokes, call `WinActivate`, then `WinWaitActive(target, , 2)` and throw if it returns zero. Use observable waits instead of fixed sleeps. A script should finish well within the default 30-second watchdog.

Prefer `UIA.ElementFromHandle(target)` and `FindElement({Type:"Button", Name:"..."}).Invoke()`. Use AutomationId or ElementFromPath for controls identified by the dump; combine selectors or search within a parent when IDs repeat. Value, Toggle, Select and Expand use the corresponding supported patterns. A tree element's Click uses its center and requires foreground activation. Screenshot coordinates are the last resort.

Use `SendText` for literal text and `Send` for keys/chords. Variable names share the namespace with functions/classes; use field, target, box, or bar rather than edit, click, send, run, menu, or gui.

Print observed facts using `FileAppend ..., "*"`. Poll for changed state for up to a second after a pattern call; successful execution alone does not prove the task worked. End at a stable state. Call `AcuKeepForeground()` when the purpose is to leave an application or transient menu showing; the cursor is still restored.

If output says `restore skipped: cursor moved by someone else`, stop and ask before continuing. If output says an unrelated foreground was left alone, inspect before acting again. UI Access reaches elevated windows, not the secure-desktop UAC prompt.

`Run` returns before the application's window appears. Allow up to ten seconds for discovery; store apps may restore documents, so inspect before typing. In a file dialog, set File name to a full path and invoke Save; verify the saved file or changed title, not just dialog closure.
