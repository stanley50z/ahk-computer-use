# Read the accessibility tree

Pass the observed window title or `ahk_id <handle>` as `target`. Optional `find` and `type` filter printed elements; `depth` and `max` bound the dump. The whole subtree is fetched before filtering.

Each line gives a control-view path, type, name, id, full value, screen bounds, supported actions, and state. Quoted fields are AutoHotkey string contents: paste them between quotes as printed. `value` means writable. Inspect `truncated` before assuming a control is absent; narrow the query or raise the indicated limit.

Use named controls and UI Automation patterns first, element bounds next, screenshot coordinates last. An Invoke returning is not proof of effect: poll the observed value or state after acting. Full document text is included by the user's decision.
