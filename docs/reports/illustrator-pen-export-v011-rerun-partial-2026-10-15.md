# Adobe Illustrator Pen and Export v0.11: cancelled rerun

Fresh rerun from commit `7ab422f`, separate from the earlier cancelled partial round. The user cancelled after the benchmark OpenAI login returned `invalid_grant` and confirmed OBS had already been stopped. No additional actors, model requests, authentication changes, or OBS actions were made to complete collection.

**9 slots consumed; 6 unstarted slots cancelled. Six automatic passes, three failures.** First-repetition method review additionally found a pre-existing-file overwrite in one automatic pass. This is a partial round, not a three-trial-per-configuration study.

## Existing results

| Trial | Original outcome | Recorded API tokens | Code share estimate | CU calls | CU busy seconds | IoU | Review |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| 01-pi-acu | Automatic pass | 256,385 | 47.19 | 10 | 55.81 | 0.9904 | Reviewed, no additional violations |
| 01-pi-cua | Automatic pass | 12,927,012 (recorded only) | Unknown | 76 | 269.24 | 0.9788 | Reviewed, no additional violations |
| 01-pi-computer-use | Actor/collection failure | 246,912 | 25.46 | 12 | 40.71 | Not collected | Review completed; original failure retained |
| 01-claude-acu | Maintainer collection failure | 263,852 | Unknown | Unknown | Unknown | Not collected | Review completed; original failure retained |
| 01-claude-cua | Automatic pass | 583,695 | Unknown | Unknown | Unknown | 0.8736 | Pre-existing screenshot overwrite |
| 02-pi-computer-use | Automatic pass | 4,560,280 (recorded only) | Unknown | 56 | 48.71 | 0.7543 | Method review not completed |
| 02-claude-acu | Automatic pass | 339,537 | 20.01 | 9 | 44.08 | 0.9170 | Method review not completed |
| 02-claude-cua | Automatic pass | 1,329,840 | Unknown | Unknown | Unknown | 0.9190 | Method review not completed |
| 02-pi-acu | Provider + infrastructure failure | 0 (recorded only) | Unknown | 0 | 0.00 | Not collected | Method review not completed |

Code-share/call/time fields stay unknown when the frozen extractor flags incomplete attribution. Recorded API consumption is not an exact total if usage completeness is false. There was no fresh independent metric review or three-trial aggregation for this cancelled rerun. A successful actor task and a successful full trial are different outcomes; missing summary/PNG is not silently converted to an actor failure score.

## Why the schedule paused

- `01-pi-computer-use`: the actor repeatedly failed to activate the captured window after opening a Color Picker and stopped without drawing. The actor job ended; a maintainer snapshot failed activation, and blank-document export then tripped the saved-flag integrity guard. Its original refusal remains. The blank AI was archived and closed during explicitly recorded owned-resource recovery, without replacing the slot.
- `01-claude-acu`: the actor drew the shape but left the Properties fill popup titled `Title` open. The maintainer dismissal routine refused that unrecognized popup, so final collection stopped before export. The unchanged drawing was archived as AI and closed through separate recovery. That archive is descriptive evidence, not a new passing export or repaired grade.
- `02-pi-acu`: OpenAI OAuth refresh returned HTTP 400 `invalid_grant` before the actor drew anything. It records no task-token usage. Maintainer export of the untouched blank also tripped the saved-flag guard. The blank was archived/closed. No login repair, provider fallback or slot retry was attempted.

## Review finding

The first repetition was independently reviewed offline from finished evidence. Pi ACU and Pi CUA have no additional violations and are reviewed successes. The native computer-use and Claude ACU consumed failures remain distinct from maintainer collection errors. The first Claude CUA actor overwrote the pre-existing user-home `s1.png` through a relative cua-driver screenshot destination; the initial file inventory and original creation time support this finding. That automatic pass is not a reviewed success. New `s2.png`, `s3.png` and `cp.png` are external scratch observations, not violations.

Remaining automatic passes in repetition two have not received a full method/safety review in this collection-only cancellation. Do not call all six automatic passes reviewed successes. Original actor scripts, statements, native geometry and command ledgers remain available for future offline review.

## Recording and resources

OBS start was verified before preparation and actor playthroughs. The user later confirmed recording was stopped; no stop/start, file query or other OBS operation was made after that cancellation. The recording filename was not collected.

All nine owned actor process jobs stopped. Recorded worker/controller process identities exited; PID reuse was checked by start time. CUA lifecycles are empty, the benchmark lock is absent, source/skill fingerprints are unchanged. Failed cleanup slots now have separate verified AI archives and owned-document closure; their original `finished.json` failures are preserved. No unrelated document/application was closed by maintainer recovery. Private credentials remain outside the report.

## Evidence and debugging

Root: `~/ahk-computer-use/.pi/rounds/illustrator-pen-export-v011-rerun-20261015T075843Z` in this checkout.

[Collection manifest and original hashes](../../.pi/rounds/illustrator-pen-export-v011-rerun-20261015T075843Z/collection.json) · [First-repetition method review](../../.pi/rounds/illustrator-pen-export-v011-rerun-20261015T075843Z/review-method/batch01/findings.md)

[OpenAI authentication failure](../../.pi/rounds/illustrator-pen-export-v011-rerun-20261015T075843Z/attempts/02-pi-acu/failure.json) · [Codex-slot crash](../../.pi/rounds/illustrator-pen-export-v011-rerun-20261015T075843Z/attempts/01-pi-computer-use/crash.txt) · [Claude-slot crash](../../.pi/rounds/illustrator-pen-export-v011-rerun-20261015T075843Z/attempts/01-claude-acu/crash.txt)

- Recovery evidence/AI archives: `maintenance/01-pi-computer-use/`, `maintenance/01-claude-acu/`, `maintenance/02-pi-acu/`; each consumed failure slot retains `maintainer-recovery.json` separately from its original records.
- Round logs: `orchestrator.log`, `orchestrator-crash.txt`; per-slot `worker.log`, `stderr.log`, `capture.json`, `metrics.json`, `events.jsonl`, `stdout.jsonl`, native inspector/export JSON and `*-crash.txt` when present.
- Collection log: `.pi/artifacts/illustrator-v011-rerun/collection.log`; recording-start evidence: `.pi/artifacts/illustrator-v011-rerun/obs/start-result.json`.
- ACU persistent runtime log: `%LOCALAPPDATA%/ACU/logs/runs.jsonl`; crash reports with stacks: `%LOCALAPPDATA%/ACU/crashes/`.
