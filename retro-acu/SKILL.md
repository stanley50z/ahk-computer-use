---
name: retro-acu
description: Review a session and propose reusable snippets, repairs, and deletions for approval.
disable-model-invocation: true
---

# Review a session

## 1. Summarize the evidence

Run `acu history "<session file>"` for the session the user wants reviewed. Use the harness-provided session path when available; otherwise ask the user for it. Do not read raw logs or session files. History is the evidence source for candidates, snippet runs and outcomes, changed snippets, and frequently failing snippets across retained runs.

Summarize the report per app. Keep unknown outcomes and missing source explicit: an `ok` run is not proof that the intended effect occurred. If history fails, report its error and any diagnostic path instead of reconstructing the report from raw files.

## 2. Prepare proposals

Run `acu snippets list "<exe name>"` for each app in the report to check existing snippets before proposing duplicates. Read the candidate script files and relevant existing snippets, not raw logs. If a source file is missing or has changed since the session, ask for the working source or mark the proposal blocked; do not invent a successful action chain.

Use the process that owns the app's content as the folder's exe name, rather than a window host. Ask the user to resolve unknown app identity or a shared-host ambiguity before choosing a folder. Store snippets in `~/.ahk-computer-use/snippets/<exe name>/`, or beneath `ACU_SNIPPETS_ROOT` when set. Use the absolute folder printed by listing when available. `ACU_HOME` is for diagnostics, not snippets; keep app-specific scripts outside this repository.

Present these sections, explicitly saying when a section is empty:

- **New snippets:** For each history candidate, propose one plain AutoHotkey v2 `.ahk` script for one reusable action, or explain why the evidence is insufficient. Show its destination and complete proposed source. Read arguments from `A_Args`. Put all six header fields in the leading semicolon-comment block, before any code:

  ```autohotkey
  ; does: <one action>
  ; args: <argument order and meaning, or none>
  ; needs: <required app state and inputs>
  ; effect: <expected change>
  ; check: <observable result that proves the effect>
  ; tested: <date and observed evidence; identify untested changes>
  ```

  Implement the `needs` check before acting, stopping with an error that names the missing need. Implement a result check last, stopping with an error if the action had no effect. Header claims alone are not checks. Keep `tested` truthful: a working source chain does not establish that a newly parameterized proposal was tested. Consult the `acu` skill for script-authoring APIs when needed.

- **Changed snippets and repairs:** List every snippet history reports changed during the session, one path per entry, for the user to review. Explain the evidence available and any remaining failure. Show proposed repairs as diffs with a complete updated header, including `tested`, and retain executable needs and result checks. If a change cannot be reconstructed, say so rather than claiming to have reviewed it.

- **Deletion proposals:** For every frequently failing snippet in the history report, propose deletion with its path and reported failure count/rate across retained runs. Separate these from repairs so the user can choose. A failure count is grounds for a proposal, not permission to delete.

## 3. Ask for approval

Give each proposed new snippet, repair, and deletion a distinct identifier. Ask which identifiers the user approves, with the destination and operation visible. Wait for the user's explicit approval before writing, modifying, or deleting any snippet. Invocation of this skill alone is not approval. If the user changes a proposal, show the revised content and obtain approval for that version.

## 4. Apply only approved changes

Write only approved new snippets and repairs into the resolved app folder. Before replacing an existing file, confirm it still matches the version reviewed; if it changed, return to review. Delete only the exact snippets whose deletion the user approved. Leave unapproved snippets unchanged. Do not create an index: the header is the index.

Verify the resulting files and headers without replaying desktop actions merely to review a session. Report one line per written, repaired, or deleted snippet, with its absolute path. State which proposals remain unapproved or blocked and which code remains untested.
