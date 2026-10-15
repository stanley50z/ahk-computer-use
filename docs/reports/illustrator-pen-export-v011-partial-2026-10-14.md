# Adobe Illustrator Pen and Export v0.11: cancelled partial round

The user cancelled the remaining schedule after a reported session interruption and had already stopped OBS. No further actor, export, recovery, browser or OBS action was performed during collection.

**Collected: five reviewed successful trials, one maintainer export-integrity refusal, and nine cancelled unrun slots.** This is not a completed three-trial-per-configuration study.

## Existing trial results

| Trial | Result | Recorded API tokens | Code/output estimate | CU calls | CU sum / busy seconds | IoU |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 01-pi-acu | Reviewed success | Unknown | Unknown | 12 | 60.57 | 0.9763 |
| 01-pi-cua | Reviewed success | 2,835,192 | 39.49 | 31 | 291.86 | 0.9835 |
| 01-pi-computer-use | Reviewed success | 7,430,398 | 27.84 | 73 | 76.04 | 0.7974 |
| 01-claude-acu | Reviewed success | 295,383 | Unknown | Unknown | Unknown | 0.9555 |
| 01-claude-cua | Reviewed success | 1,563,036 | Unknown | Unknown | Unknown | 0.9494 |
| 02-pi-computer-use | Maintainer infrastructure refusal | 13,717,872 | 22.59 | 110 | 110.85 | Not collected |

The first five form one sample per configuration, not three-trial averages. Original all-request API usage and conservative code/call attribution flags are retained. Unknown fields are not zero, and no successful slot was replaced or benchmark restarted. Full component breakdowns and extraction notes are in `collection.json` and each original `metrics.json`.

## Why the schedule paused

The second Pi Codex computer-use actor completed successfully at the harness level (`capture.json`: exit 0, owned process tree stopped). The subsequent maintainer export guard refused collection with `Drawing changed during maintainer export; refusing cleanup`. The controller paused before launching slot seven. This recorded pause is an infrastructure refusal, not a terminal actor-provider authentication error. The user reported a session interruption when cancelling; the retained trial evidence does not establish main-session OAuth failure.

The retained export before/after record has the same document path, page-item count and artwork signature (`3957924934`). The only recorded changed field is `saved`: true before export, false afterward. That is evidence about the guard input, not a repaired or reclassified outcome. No diagnosis/fix/retry was performed in this collection-only task.

**The sixth owned drawing remains preserved in Illustrator; cleanup is not fully verified for that slot.** The original policy deliberately avoids destroying an uncollected drawing after an integrity refusal. Its raw native/encoded PNG attempt files and native anchor/handle evidence remain available, but they are not a validated final artifact and no replacement quality score was invented.

## First-repetition review

All five finished repetition-one histories were reviewed offline. Assigned runtime use, Pen construction, fill and native no-stroke checks passed. Ordinary recovery, Undo, editing and zoom were allowed under v0.11 and not penalized. Pi ACU has coincident endpoints on an open native path; Pi computer use has visibly inaccurate sections caused by missing handles. These are retained quality observations, not invented numerical pass thresholds.

## Cancellation and resources

- Remaining nine slots were prepared only and never launched. `stop.request` and `round-closed.json` prevent further schedule launches; status is `cancelled_by_user`.
- All six actor jobs are stopped. Recorded actors, workers and controller have exited; PID reuse was checked by start time. The benchmark active lock is absent and public CUA lifecycles are empty.
- First five trials have verified owned-document and cursor cleanup. The sixth restores the cursor but retains its unresolved drawing as described above.
- Frozen source and selected-skill fingerprints remain unchanged. Original trial summaries, events, metrics and attempt records were not rewritten.
- OBS is recorded as stopped by the user. Its recording path was not queried, and no OBS controls were used during collection.

## Evidence and debugging

Evidence root: `~/ahk-computer-use/.pi/rounds/illustrator-pen-export-v011-20261014T072837Z` in this checkout.

[Collected records and token breakdowns](../../.pi/rounds/illustrator-pen-export-v011-20261014T072837Z/collection.json) · [First-five drawings](../../.pi/rounds/illustrator-pen-export-v011-20261014T072837Z/review-method/batch01/contact-sheet.png) · [Method findings](../../.pi/rounds/illustrator-pen-export-v011-20261014T072837Z/review-method/batch01/findings.md)

[Export-refusal traceback](../../.pi/rounds/illustrator-pen-export-v011-20261014T072837Z/attempts/02-pi-computer-use/export-attempt-1-crash.txt) · [Infrastructure failure](../../.pi/rounds/illustrator-pen-export-v011-20261014T072837Z/attempts/02-pi-computer-use/infrastructure-failure.json) · [Export guard inputs](../../.pi/rounds/illustrator-pen-export-v011-20261014T072837Z/attempts/02-pi-computer-use/illustrator-export-31c165.json)

- Round controller logs: `orchestrator.log`, `orchestrator-crash.txt`; each attempt retains `worker.log`, `stderr.log`, `events.jsonl`, `stdout.jsonl`, `session.jsonl` or its harness transcript, native inspection/export records and `finished.json`.
- ACU persistent logs/crash reports remain under `%LOCALAPPDATA%/ACU/logs/runs.jsonl` and `%LOCALAPPDATA%/ACU/crashes/`.
- Collection validation output: `.pi/artifacts/illustrator-v011-round/collection.log`.
