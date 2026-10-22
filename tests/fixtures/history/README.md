# Session history samples

These small, sanitized JSONL samples preserve native envelopes inspected on this machine:

- Pi: `~/.pi/agent/sessions`, session cwd, assistant `toolCall`, and `toolResult` correlated by `toolCallId`.
- Codex: `~/.codex/sessions`, `session_meta`, `response_item` with JSON-string `arguments`, and outputs correlated by `call_id`.
- Claude Code: `~/.claude/projects`, assistant `tool_use` and user `tool_result` correlated by `tool_use_id`; cwd is on the outer entry.

Messages unrelated to the test were removed. IDs, timestamps, paths, script bodies, and outputs were replaced with neutral test values; there is no document text, account data, credential, or original task content. The shell/patch variants combine these envelopes into small regression cases. `SNIPPETS` is replaced by the test's temporary store path. Run-log rows are constructed in the tests using the fields written by `acu/run.py::record`.
