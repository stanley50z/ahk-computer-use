# Read the accessibility tree

Run `tree.ahk` through ACU's `run` tool. Its first argument is the observed window title or `ahk_id <handle>`. Optional flags are `--find <text>`, `--type <Type>`, `--depth <N>`, and `--max <N>`. The whole subtree is fetched before filtering. Put the target and flags after `--` in `acu run`.

Each output line gives a control-view path, type, name, id, full value, screen bounds, supported actions, and state. Quoted fields are AutoHotkey string contents: paste them between quotes as printed. `value` means writable. Inspect `truncated` before assuming a control is absent; narrow the query or raise the indicated limit.

Use named controls and UI Automation patterns first, element bounds next, screenshot coordinates last. An Invoke returning is not proof of effect: poll the observed value or state after acting. Full document text is included by the user's decision.
