# UIA-v2 is vendored and included in every script; paths number the control view

Modern applications publish their buttons only through UI Automation, so the perception ladder starts with the tree. We vendored Descolada's UIA-v2, a single pure-AutoHotkey file under MIT, into `acu/lib` instead of writing our own COM bindings or adding a submodule, and the prelude includes it unconditionally because it costs about 30 ms per script and spares the agent an include it would forget. One line is patched and marked so a single-segment path resolves like a longer one.

Tree paths number the control view because that is the view the library's path resolver walks. Raw-view numbering was tried on a reviewer's suggestion and failed on Calculator; the round-trip test pins the choice.

## Consequences

- Updating the library means copying the upstream file and re-applying the marked line; the tests catch a drift.
- A dump fetches the whole subtree before applying its budget, so a large browser document costs about a second. A depth-bounded live walk is the fix if that matters.
- Keeping AutoHotkey as the core holds: the binding is AutoHotkey code reaching a Windows API that AutoHotkey lacks a built-in for.
