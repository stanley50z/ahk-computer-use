# Adobe Illustrator Pen and Export: v0.9 full round

All 15 scheduled trials finished: three per configuration, with no replacement trials, provider/model fallback, parent coaching or mid-trial repair. **2 reviewed successes and 13 unsuccessful trials.**

The current task requires genuine Pen-tool Bézier curves and only the Pen tool in Illustrator, with chosen fill-colour methods as the sole tool/command exception. No actor export/save/result file is requested. The unchanged live drawings were exported by the maintainer after actors stopped.

## Successful-cohort statistics

All successes are retained without trimming. The zero-success configurations have no averages. Claude ACU code/call values below are additive independently reviewed estimates resolving a false filename-triggered warning; raw metrics remain untouched.

| Configuration | Successes / 3 | API tokens | Code/output % | CU calls | CU sum / busy seconds | IoU |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| pi-acu | 0/3 | — | — | — | — | — |
| pi-cua | 0/3 | — | — | — | — | — |
| pi-computer-use | 1/3 | 3,251,181 | 20.46 | 50 | 37.37 | 0.8939 |
| claude-acu | 1/3 | 158,522 | 14.99 | 7 | 31.88 | 0.9087 |
| claude-cua | 0/3 | — | — | — | — | — |

## Every scheduled attempt

| Slot | Trial | Reviewed | Recorded API tokens | IoU | Original checks / additional review |
| ---: | --- | --- | ---: | ---: | --- |
| 1 | 01-pi-acu | failed | 226,153 | 0.9753 | Drawing check failed: white_background |
| 2 | 01-pi-cua | failed | 11,633,260 (lower bound) | 0.9641 | Drawing check failed: white_background; pre-existing windows closed; new non-Illustrator windows left open |
| 3 | 01-pi-computer-use | success | 3,251,181 | 0.8939 | Passed |
| 4 | 01-claude-acu | failed | 300,020 | 0.9276 | Drawing check failed: white_background |
| 5 | 01-claude-cua | failed | 2,261,497 | 0.8756 | pre-existing windows closed; clk.sh clicked toolbar position (20,83) intending the Selection tool, then clicked the canvas at (483.5,517). The actor's next message states the icon was the Artboard tool and the canvas click created an extra artboard. Purpose established by the actor's own text (L3745).; cua-driver hotkey ctrl+z sent to pid 18204 (driver summary 'Pressed ctrl+z on pid 18204 via SendInput'). Actor text: 'I'll undo that accidental change with Ctrl+Z' and afterwards 'The extra artboard is gone'. Purpose established by source. |
| 6 | 02-pi-computer-use | failed | 3,263,693 | 0.8194 | new non-Illustrator windows left open |
| 7 | 02-claude-acu | failed | 210,307 | 0.8942 | Drawing check failed: white_background |
| 8 | 02-claude-cua | failed | 423,004 | 0.8836 | pre-existing windows closed; Undo used as a drawing command outside the Pen tool and outside the fill exception. |
| 9 | 02-pi-acu | failed | 91,721 | 0.9205 | Drawing check failed: white_background |
| 10 | 02-pi-cua | failed | 1,361,089 | 0.9575 | Drawing check failed: white_background |
| 11 | 03-claude-cua | failed | 1,217,163 | 0.9359 | Drawing check failed: white_background |
| 12 | 03-pi-acu | failed | 120,250 | 0.9764 | Drawing check failed: white_background |
| 13 | 03-pi-cua | failed | 7,109,829 (lower bound) | 0.9486 | Drawing check failed: white_background |
| 14 | 03-pi-computer-use | failed | 2,683,160 | 0.9448 | Drawing check failed: white_background |
| 15 | 03-claude-acu | success | 158,522 | 0.9087 | Passed |

## Appearance and method findings

- Every final drawing contains genuine Bézier curves; no final all-polygon tracing or many-short-straight approximation was found by full-session review.
- Ten original trials fail the rendered `white_background` check. The frozen checker classifies non-blue pixels as background and requires at least 99% of them to be pure white. A default thin dark stroke and its antialiased edge pixels can therefore fail the check even when the visible blank artboard is white. All four corners of every PNG are white. Exact fractions are retained in `attempt-statistics.json`. Original failures were not cleared, no stroke rule was invented by the method reviewers, and no drawing or exporter was repaired.
- 01-Claude CUA accidentally used the Artboard tool and then Undo to revert it. 02-Claude CUA used about 35 Undo hotkeys to erase a failed path before redrawing. Both violate the current non-Pen/non-fill command restriction; source/line evidence is in method reviews. Final native geometry alone does not establish whole-session compliance.
- Original window-diff failures remain preserved. 01-Pi CUA spans an Explorer restart: a File Explorer window, taskbar and desktop handles disappeared and replacement Explorer handles appeared. No actor command targets Explorer, so actor causation is unproven. The second repetition spans Xbox Game Bar overlay windows appearing and disappearing; no actor command targets them. Do not charge unattributed window changes as proven actor actions or silently regrade their original failures.
- 02-Claude CUA created eight new home-directory screenshot files via relative daemon destinations. External scratch is allowed; these are observations, not additional violations. No pre-existing file was overwritten. The eight proven new files were archived then removed with byte-hash/time verification; unrelated files were preserved.

## Measurement scope and limitations

- All recorded token sums, source-ledger arithmetic and selected-span sums/union reconcile in the frozen replay. No compaction occurred. Model-response/end-to-end speed is not a ranking metric.
- 01-Pi CUA and 03-Pi CUA recovered one zero-usage provider response each. Original all-request consumption remains a lower bound. Separate counted-response analyses exclude those responses by the earlier user decision; original errors and trial verdicts remain. They are labelled `tokens-and-computer-use-excluding-interrupted-turns-v1`, not full-request consumption.
- 01-Claude CUA omits one real top-level `bash pen.sh` execution after an unsupported source patch. That trial's code/call/time comparison fields are masked; its original values remain partial, not fabricated complete totals. It is unsuccessful and does not enter averages.
- 03-Claude ACU has one false note caused by the frozen sed-expression detector matching the filename `s.ahk`. Independent review verifies all seven spans and all 977 code tokens; the additive reviewed aggregate reports 977/6519 = about 14.99% while preserving the original note/raw aggregate. No measured source was changed.
- Reference encoding is tiktoken/o200k_base, not a per-tool billing tokenizer. Reasoning is inside output and is not added twice. Single successful samples in the two retained configurations do not establish typical performance.

## Recording and cleanup

OBS was started before preparation/actors and stayed recording through all 15 desktop playthroughs and owned-resource cleanup. It was stopped afterward, before the remaining offline reporting. OBS confirmed Start Recording and saved:

[E:/Videos/2026-10-13 19-18-40.mp4](file:///E:/Videos/2026-10-13%2019-18-40.mp4)

Video existence/size verified: 4,360,939,484 bytes. All recorded worker/actor/controller identities exited, all owned documents were closed, pre-existing documents were preserved, CUA lifecycles are empty, cursor schemes restored and the benchmark lock absent. Source/skill fingerprints match the frozen baseline. No shared service or unrelated app was terminated by maintainer cleanup.

## Persistent evidence

Evidence root: `~` is the current user root; this round is under `~/ahk-computer-use/.pi/rounds/illustrator-pen-export-v09-20261013T232505Z` in this checkout.

[All output slots](../../.pi/rounds/illustrator-pen-export-v09-20261013T232505Z/all-outputs.png) · [Raw aggregate](../../.pi/rounds/illustrator-pen-export-v09-20261013T232505Z/aggregate-raw.json) · [Reviewed aggregate](../../.pi/rounds/illustrator-pen-export-v09-20261013T232505Z/aggregate.json) · [All attempt statistics](../../.pi/rounds/illustrator-pen-export-v09-20261013T232505Z/attempt-statistics.json)

[Counted Pi response summaries](../../.pi/rounds/illustrator-pen-export-v09-20261013T232505Z/counted-pi-summary.json) · [Resource verification](../../.pi/rounds/illustrator-pen-export-v09-20261013T232505Z/resource-verification.json) · [Scratch cleanup](../../.pi/rounds/illustrator-pen-export-v09-20261013T232505Z/scratch-cleanup.json)

- Full source/skill/profile fingerprints, working-tree diff and original source snapshot: `freeze.json`, `source/`, `working-tree.diff`. The actual uncommitted snapshot, not HEAD alone, describes this run.
- Each attempt retains complete actor events/transcripts, workspace source, metrics, native drawing/control points, original conduct/verification/export/finished records and worker/observer logs.
- Independent method reviews: `review-method/batch01/`, `batch02/`, `batch03/`. Metric reviews: `review-metrics/`. Parent dispositions: `review-dispositions.json`. Reviewers only read finished evidence; no actor script or desktop operation ran during review.
- Setup/round failures persist in `preparation.log`, `orchestrator.log`, `orchestrator-crash.txt`/per-run `*-crash.txt` when present. ACU runtime logs: `%LOCALAPPDATA%/ACU/logs/runs.jsonl`; crash reports: `%LOCALAPPDATA%/ACU/crashes/`.
- OBS start/stop evidence is separate under `.pi/artifacts/obs-v09-round/`, not an actor prompt, trial or metric.
