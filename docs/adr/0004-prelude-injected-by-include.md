# Every script runs under a prelude the launcher injects

The agent writes plain AutoHotkey v2 and the launcher prepends the prelude with AutoHotkey's `/include` switch, so screen coordinates, per-monitor DPI awareness, zero mouse delay, error and warning reporting, English input preparation, and the UI Automation class exist in every script without boilerplate. The alternative, a template the agent copies, drifts the moment the agent edits it.

## Deliberate deviations from AutoHotkey's defaults

- Coordinates are screen coordinates. AutoHotkey's default is the active window's client area, which would silently reinterpret every screenshot coordinate against whichever window happened to be active.
- The thread is per-monitor-v2 DPI aware. AutoHotkey v2.0 is only system aware, which scales window geometry on mixed-DPI setups.
- Warnings print to stdout instead of a dialog. A load-time warning dialog appears before the script has a window, so nothing the launcher does could close it; one category stays off because it fires for the prelude's own locals.
- Runtime errors print to stderr with exit code 1. `/ErrorStdOut` covers only load-time errors.
