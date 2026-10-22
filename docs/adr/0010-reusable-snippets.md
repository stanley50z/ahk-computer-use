# Reuse working action chains as external snippets

An agent can spend several attempts discovering one app action. [Spec #28](https://github.com/stanley50z/ahk-computer-use/issues/28) saves the working action chain as a plain AutoHotkey v2 snippet, rather than introducing a script registry or another execution engine. Snippets run through the existing launcher and take arguments from `A_Args`.

## Storage and headers

Snippets live in `~/.ahk-computer-use/snippets/<exe name>/`, outside the repository. The folder names the process that owns the app's content: a store app's own executable, not `ApplicationFrameHost.exe`. Shared hosts such as `msedge.exe` and `javaw.exe` remain unresolved until a real case needs a decision. No app-specific workflows belong in `acu/`.

The header is the index; there is no INDEX.md. As recorded on [#29](https://github.com/stanley50z/ahk-computer-use/issues/29), it is the leading block of semicolon comment lines before any code. Fields use `; <key>: <value>` with case-insensitive keys `does`, `args`, `needs`, `effect`, `check`, and `tested`; other comment lines are ignored. A snippet checks its needs first and names any missing need in an error. It checks its result last and stops if its action had no effect.

Logs, crash reports, and screenshots stay under `%LOCALAPPDATA%\ACU`; `ACU_HOME` continues to override that diagnostic location. `ACU_SNIPPETS_ROOT` independently overrides the snippets directory, including in tests. Listing does not create the store or change its files.

## Discovery

`acu snippets list <app> [keyword...]` reads snippets without starting AutoHotkey or taking the desktop lease. App matching ignores case, allows an omitted `.exe`, and searches executable names or FileDescription metadata. Resolve the executable path from a running process with that folder's exe name, then from registry App Paths if there is no running path. A folder with no resolvable path matches only by exe name. Unknown apps report existing folder names; ambiguous matches ask for one folder.

Without keywords, list every `.ahk` snippet. Otherwise search the filename and header for case-insensitive substrings and count each distinct keyword once per snippet. Keep snippets with at least one hit, sort by descending hit count, and break ties by filename. The common text format is:

```text
snippets <absolute folder path>
<file name> | args: <args> | does: <does>
<file name> | no header
<file name> | unreadable: <error>
```

`acu/snippets.py` owns listing and formatting so automatic discovery can reuse them. The following spec decisions are implemented by later tickets, not by the CLI listing ticket:

- `AcuLaunch` and unfiltered tree dumps print the full list, with no size limit. Filtered dumps (`--find`, `--type`) do not. The skill tells an agent that skips the tree to list snippets before exploring.
- Settings live in `~/.ahk-computer-use/settings.json` and `<project>/.ahk-computer-use/settings.json`, with project values winning. Search upward from the run's working directory for the project file. `{ "snippets": { "enabled": false } }` turns discovery off. Benchmark trial workspaces disable it.
- An agent repairs failed snippets, updates `tested`, and names every changed snippet in its final reply. It never deletes snippets or saves new ones on its own.
- A repository-local, user-invoked `retro-acu` skill proposes new snippets and deletions, then acts only on user approval. It is app-neutral and linked by `install_skill.py`.
- `retro-acu` uses `acu history <session file>` rather than raw session or run logs. That command summarizes Pi, Codex, and Claude Code sessions alongside `runs.jsonl` per app, without a model.

Snippets are not a sandbox or permission system. Measuring their benefit in the benchmark is outside this spec.
