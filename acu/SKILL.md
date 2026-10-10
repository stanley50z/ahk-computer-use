---
name: acu
description: Operate this Windows desktop through ACU's script-first CLI or MCP tools. Discover maintained scripts and instructions, execute a short AutoHotkey v2 action chain, and check the observed result. Use when asked to click, type into, open, read, or drive a Windows application or the desktop on this machine, or when a task names ACU or AutoHotkey.
---

# ACU

You supply the intelligence, ACU supplies the hands. The primary action is a whole scripted action chain in one execution, not a tool call for every button. ACU manages inline script files and runs them through its launcher protections. AHK is the only execution engine currently supported.

## Call ACU

Use the connected ACU MCP tools (`discover`, `describe`, `run`, `execute`, `tree`, `screenshot`). In Pi their names are `mcp__acu__<operation>`. If MCP is not configured, use the CLI: `uv run --project "<absolute repo root>" python -m acu <operation>`. Resolve this skill directory's link and take its parent to locate the repository. The installed console command is `acu`; examples below use that spelling.

Find relevant capabilities with `discover(query)` / `acu discover "query"`; summaries distinguish maintained implementations from instructions only. Read a selected capability with `describe(id)` / `acu describe <id>`. Run a maintained implementation with `run(id, parameters)` / `acu run <id> --params '<JSON object>'`. Instructions-only capabilities require you to draft code and call `execute`; ACU does not generate a fallback script. Discovery grants no permission to act.

Before drafting your first script, describe `ahk.action-chain` for targeting, waits, UIA patterns, restore, and verification guidance. Use only the desktop actions the user authorized.

## The loop

Look, act, check. Repeat until the user's postcondition is observed. The task is done when a window state, printed text, or screenshot shows the result, never because an execution exited zero.

### 1. Look

Find the window before its controls. `Run` returns before a program's window appears; allow up to 10 seconds. Discover by title or class, then retain the exact handle (`ahk_id`) for the tree, waits, activation and cleanup. Use an executable filter only when the top-level window's process name has been observed: Calculator's app process can be `CalculatorApp.exe` while its window belongs to `ApplicationFrameHost.exe`.

Run the maintained `windows.list` capability to list identities without activation. In a script, the equivalent is:

```autohotkey
for hwnd in WinGetList() {
    target := "ahk_id " hwnd
    FileAppend hwnd " | " WinGetTitle(target) " | " WinGetClass(target) " | " WinGetProcessName(target) "`n", "*"
}
```

Select the intended window from its observed title/class and inspect its tree. For a new-window task, snapshot existing handles before `Run` and select a new matching handle; preserve existing windows. If no unique intended window can be identified, report that ambiguity instead of acting on a guess. A store app may restore previous documents, so check its content before typing.

Skip the tree dump when you already know the window and control. Otherwise call `tree(target, find?, type?, depth?, max?)`, or:

```
acu tree "<WinTitle or ahk_id>" [--find <text>] [--type <Type>] [--depth 25] [--max 300]
```

Describe `uia.tree` when interpreting a dump: it explains control-view paths, full values, action/state flags, AHK-escaped names, and truncation. Prefer named controls and semantic UIA actions, then element bounds, then screenshot coordinates. Before pointer input or keys, activate the target and verify `WinWaitActive`; throw rather than click into another application.

Use `screenshot` for an empty/nameless tree, canvas content, or visual confirmation. Describe `screen.capture` for capture modes and coordinate mapping:

```
acu screenshot --mode fullscreen [--monitor 1]
acu screenshot --mode app --target "<WinTitle or ahk_id>"
acu screenshot --mode custom --rect <x1> <y1> <x2> <y2>
```

MCP returns the PNG and metadata; CLI returns its saved path. An explicit `out` may overwrite a file; use only an authorized path. An image point (px,py) is the screen point (sourceX + px * scale, sourceY + py * scale). App capture never activates the window. Use `max=0` / `--max 0` for an unscaled close look.

### 2. Act

Write the whole chain when you can predict intermediate states: press a button, wait for its dialog, act inside it. Otherwise execute a short script, then look again.

MCP example (plain AHK v2, no boilerplate):

```json
{"code":"root := UIA.ElementFromHandle(\"<observed Calculator target>\")\nfor buttonId in [\"clearButton\", \"num6Button\", \"multiplyButton\", \"num7Button\", \"equalButton\"]\n    root.FindElement({Type:\"Button\", AutomationId:buttonId}).Invoke()", "engine":"ahk", "timeout":30}
```

For the CLI, supply code on stdin with `acu execute --file - [--timeout 30]`. `--code` supports short inline snippets; command-line arguments may be visible to other processes, so prefer stdin for sensitive text. An existing script can be run with `acu execute --file "<absolute script.ahk>"`; caller-owned files are preserved. Put `--args` last to forward literal strings to `A_Args`.

End at a stable state. The prelude restores the user's foreground window and cursor. Call `AcuKeepForeground()` when the purpose is to leave an application or transient menu showing; the cursor still returns.

### 3. Check

Print facts with `FileAppend ..., "*"` and read state back in the script. Poll briefly after UIA patterns: an Invoke returning is not proof of effect. The JSON result includes `outcome`, `exit_code`, `output`, `trailer`, `duration_ms`, and artifact paths. MCP also sets `isError` on failed execution. A `cleanup_error` preserves the real execution outcome and identifies a leftover script; do not repeat an already-completed chain.

- `ok`, exit 0: the script ran; observed facts establish whether it worked.
- `error`, exit 1: runtime error with location and stack; fix the failing script.
- `error`, exit 2: parse error; nothing ran.
- `timeout`, exit 124: watchdog fired; inspect before acting again.
- `error` without an execution outcome: invalid request, unavailable engine, or tool failure; read the diagnostic. A `busy` error means another tool execution owns the desktop: inspect before retrying.

If output says `restore skipped: cursor moved by someone else`, stop and ask before continuing. If it says an unrelated foreground was left alone, look before acting again.

## Operational facts

- Tool executions share cursor/focus and are serialized across CLI and MCP; overlapping calls fail busy, rather than queue stale actions. The low-level `run.py` launcher remains available for development but does not enforce this tool-level lease.
- UI Access reaches elevated windows, not the secure-desktop UAC prompt.
- Scripts inherit only `ACU_HOME`; pass other values in arguments. The launcher waits for its script, not programs that script starts.
- Run log: `%LOCALAPPDATA%\ACU\logs\runs.jsonl`. MCP diagnostics: `logs\mcp.log`. Crash reports with output/stacks: `crashes\`. Managed screenshots: `shots\`, newest 30 kept. Set `ACU_HOME` to relocate them. Script text is never deliberately logged; output/crash reports may contain sensitive fragments.
- Implementation files beside this skill: `run.py`, `tree.ahk`, `screenshot.ahk`. CLI/MCP setup and detailed launcher behavior are in the repository's `README.md`.
