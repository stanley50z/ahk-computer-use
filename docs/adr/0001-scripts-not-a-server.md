# A script is the primary unit of action, regardless of transport

The agent expresses a predictable action chain as one script and ACU runs it through the launcher. Scripting, rather than an interactive tool call for each button or keystroke, is the primary agent interface: it collapses a predictable chain into one short execution while keeping the intelligence in the calling agent.

The first version used file-writing and shell tools directly and had no server. Clarified by the user on 2026-10-09: this decision is about scripting as the unit of action, not a prohibition on CLI or MCP interfaces. ACU now offers a JSON CLI and a thin stdio MCP adapter over the same implementation. MCP can stay connected, but no AHK process or desktop-control session persists between executions.

## Consequences

- `execute` accepts an entire agent-written action chain. ACU owns temporary files for inline code; an existing caller-owned script can also be executed.
- Discovery exposes maintained scripts and instruction-only capabilities. The agent may run a maintained implementation or read guidance and draft its own script. ACU does not contain a planning agent or silently generate fallback code.
- Tree and screenshot observations support the look–act–check loop; they do not replace script-first action chains with a button-by-button protocol.
- AHK remains the only execution engine initially. An engine name is part of the interface, but unsupported engines fail explicitly; another engine needs a concrete requirement rather than a speculative plugin framework.
- Scripts share cursor and keyboard focus. CLI/MCP executions take a Windows session-local lease and reject overlaps instead of queueing actions against stale state. The low-level development launcher remains outside that lease.
- Prelude defaults, short scripts, UI Access, watchdog, conditional restore, and sensitive-artifact logging decisions still stand. A successful execution is not proof of the user's postcondition.
