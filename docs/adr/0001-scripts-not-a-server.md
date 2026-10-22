# A script is the primary unit of action; ACU is CLI-only

The agent expresses a predictable action chain as one AutoHotkey v2 script and ACU runs it through the launcher. Scripting, rather than an interactive call for each button or keystroke, is the primary interface. The calling agent supplies the intelligence.

A broader CLI/MCP operation list was an architectural proposal, not settled requirements. The user's direction was to keep only script-file execution, closest to the original launcher, and remove MCP for now. [ADR-0010](0010-reusable-snippets.md) adds read-only snippet discovery beside execution. ACU therefore provides the installed `acu` CLI command, with no server implementation or harness MCP configuration. Python is an internal runtime detail, not the normal command the agent types.

## Consequences

- The agent calls `acu run SCRIPT.ahk [--timeout 30] [-- ARG ...]` through its shell tool. It uses the prelude, UI Access launcher, watchdog, and logging. [ADR-0009](0009-persistent-desktop-state-and-english-input.md) replaces conditional restoration with persistent desktop state and English input preparation.
- Installation provides the `acu` console executable and its Python environment. uv is used for installation/development, not each desktop action. The CLI has no runtime Python package dependencies.
- The agent writes and manages its files. No inline-code input, maintained-script-ID registry, general discovery/description operations, or engine selector is part of the interface. `acu snippets list <app> [keyword...]` is the read-only discovery exception; it lists ordinary external script files.
- `tree.ahk` and `screenshot.ahk` remain ordinary scripts passed to `run`. Their output is returned as text; the agent reads a saved PNG separately.
- No AHK process or script variables persist between runs. CLI script runs reject overlaps through a Windows session-local lease; snippet listing does not take that lease; the low-level development launcher remains outside that lease.
- A successful run is not proof of the user's postcondition. Observe the resulting state. Other operations or transports require a separate design decision before implementation.
