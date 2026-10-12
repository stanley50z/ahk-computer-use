# Illustrator Pen and Export: v0.5 full round, 2026-10-12

## Outcome

**15 scheduled trials, all 15 launched and finished: 8 reviewed successes and 7 failures.** No replacement, provider/model fallback, parent coaching or mid-trial repair was used. The original automated checker passed 11 attempts; method review and parent dispositions determine the final cohort.

14 output PNGs were produced; 14 pass the automated image checks. A valid image does not override conduct or authoring-method failures. Unexpected provider failures: **0**. Original histories, PNGs, automatic verdicts and metrics are preserved.

The focused live integration test passed before this round (1 test, 98.82 seconds). It checked initial primary-monitor maximization, optional maintainer calibration, the real ownerless Color Picker, protected-handle refusal and owned-resource cleanup. Fixture evidence: `.pi/illustrator-pen-export-validation/native-check-3adafa28/`; round log: `desktop-validation.log`. This validates the initial-window and cleanup changes, not the unconfirmed cause of later resizing. The explicit fixture export is outside the benchmark; normal trial preparation did not calibrate or prime PNG settings.

Final cleanup verified all recorded workers/actors and the orchestrator have exited, owned process trees stopped, task documents/application cleaned up, no visible CUA lifecycle remaining, no active benchmark lock, and no private credential copies. Shared services and pre-existing unrelated applications were preserved. External task scratch files were handled separately with retained copies and hashes; see `scratch-cleanup.json`.

## Successful-cohort averages

| Configuration | Successes / 3 | Retained n | Total API tokens | Code/output % | CU calls | CU busy s | CU sum s | IoU |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Pi + ACU | 3/3 | 3 | 466,792 | 46.33 | 16.00 | 66.07 | 66.07 | 0.9394 |
| Pi + CUA | 0/3 | 0 | — | — | — | — | — | — |
| Pi + Codex computer use | 0/3 | 0 | — | — | — | — | — | — |
| Claude Code + ACU | 3/3 | 3 | 698,703 | 21.87 | 15.67 | 79.69 | 79.69 | 0.9286 |
| Claude Code + CUA | 2/3 | 2 | 2,300,622 | 25.01 | 38.50 | 346.06 | 346.06 | 0.9369 |

Every success is retained, including token and quality extremes. A failed slot is excluded, never replaced. The same cohort is used for all metrics; one missing value makes that cohort metric unknown rather than changing its sample. A dash means unavailable, not zero. An arm with zero successes has no successful-cohort average. Code share never selects successes.

### Token breakdown of those same cohorts

| Configuration | Uncached input | Cache read | Cache write | Output including reasoning | Reasoning subset (not added again) |
|---|---:|---:|---:|---:|---:|
| Pi + ACU | 48,673 | 414,891 | 0 | 3,229 | 526 |
| Pi + CUA | — | — | — | — | — |
| Pi + Codex computer use | — | — | — | — | — |
| Claude Code + ACU | 51 | 647,820 | 40,343 | 10,489 | 4,195 |
| Claude Code + CUA | 87 | 2,193,938 | 88,906 | 17,691 | 5,392 |

### Shape observations for those same cohorts

| Configuration | Mean IoU | Mean boundary Manhattan px | Mean per-image p95 boundary px |
|---|---:|---:|---:|
| Pi + ACU | 0.9394 | 2.07 | 9.33 |
| Pi + CUA | — | — | — |
| Pi + Codex computer use | — | — | — |
| Claude Code + ACU | 0.9286 | 2.46 | 10.33 |
| Claude Code + CUA | 0.9369 | 2.17 | 7.00 |

Quality is unaligned, with no shape-pass threshold or post-hoc image trimming. Completion requires the requested PNG properties, not a minimum IoU. End-to-end time, model-response latency and tokens-per-second are not ranking metrics.

## Every trial

| Trial | Reviewed outcome | Valid PNG | Recorded API tokens | IoU | Failure / review note |
|---|---|---:|---:|---:|---|
| 01-pi-acu | success | yes | 372,827 | 0.9650 | PNG, isolation, conduct, capture, cleanup and method review passed. |
| 01-pi-cua | failed | yes | 4,640,873 | 0.9168 | write tool used outside the workspace; new non-Illustrator windows left open; Incidental GameViewer handle is not demonstrated actor-owned; outside-workspace writes independently fail. |
| 01-pi-computer-use | failed | no | 388,854 | — | Cloud9-Recreated.png missing |
| 01-claude-acu | success | yes | 729,522 | 0.9433 | PNG, isolation, conduct, capture, cleanup and method review passed. |
| 01-claude-cua | success | yes | 2,863,633 | 0.9442 | PNG, isolation, conduct, capture, cleanup and method review passed. |
| 02-pi-acu | success | yes | 353,912 | 0.9330 | PNG, isolation, conduct, capture, cleanup and method review passed. |
| 02-pi-cua | failed | yes | 4,452,501 | 0.9441 | write tool used outside the workspace; Unknown after metric review: computer_use_code_tokens_estimate, code_share_percent_estimate, computer_use_call_count, computer_use_busy_s, computer_use_sum_call_s |
| 02-pi-computer-use | failed | yes | 17,431,256 | 0.9161 | Properties > Convert selected anchor points to smooth supplied handle positions rather than replaying visually chosen literal handle positions; late conversions at 674.899, 696.840, 711.654 and 726.187 seconds remained before export without subsequent individual handle positioning. |
| 02-claude-acu | success | yes | 661,744 | 0.9278 | PNG, isolation, conduct, capture, cleanup and method review passed. |
| 02-claude-cua | success | yes | 1,737,612 | 0.9296 | PNG, isolation, conduct, capture, cleanup and method review passed. |
| 03-pi-acu | success | yes | 673,638 | 0.9203 | PNG, isolation, conduct, capture, cleanup and method review passed. |
| 03-pi-cua | failed | yes | 17,224,325 | 0.9324 | write tool used outside the workspace; Unknown after metric review: computer_use_code_tokens_estimate, code_share_percent_estimate, computer_use_call_count, computer_use_busy_s, computer_use_sum_call_s |
| 03-pi-computer-use | failed | yes | 29,801,559 | 0.9332 | Convert selected anchor points to smooth at 950.037 seconds supplied handle geometry at the left outer top anchor; the literal left-handle correction at 964.733 seconds left its short conversion-supplied opposite handle in place without earlier literal ancestry or later replacement before export. |
| 03-claude-acu | success | yes | 704,843 | 0.9147 | PNG, isolation, conduct, capture, cleanup and method review passed. |
| 03-claude-cua | failed | yes | 3,138,421 | 0.8758 | Programmatic geometry generation from a parametric shape: generated three circular hole paths from center/radius/handle parameters rather than replaying individually authored literal Pen anchors and handles (v0.5). |

## Review decisions and limits

- **Automatic smoothing is not literal handle placement.** `02-pi-computer-use` passes the PNG checker but is excluded by the parent disposition after a second independent review and original-image inspection. Late Properties > Convert selected anchor points to smooth actions supplied handle positions without subsequent literal handle repositioning. v0.5 allows redraw/refinement but retains the visually chosen anchor/handle requirement. This is not a redraw, image-quality, scripting, parametric-code or provider failure. Exact IDs, before/after screenshots and interpretation limits are in `review-adjudication.md` and `review-dispositions.json`. `03-pi-computer-use` also has a narrower residual-handle failure: many pairs were manually corrected, but the left-outer-top conversion at 950.037 seconds retained a short automatic opposite handle after a literal left-side correction. This is not a blanket failure for conversion or for one-sided edits; counterevidence and moderate confidence are in `review-adjudication-03.md`. Both original automated passes remain unchanged.
- **Parametric holes violate the literal-point rule.** `03-claude-cua` generated three circle paths with a center/radius loop (`r=42; h=23; cx+r, cy-r`, etc.), executed that code after fixing session admission, and retained the holes through export. The outer contour was literal and allowed; the three generated inner paths are the failure. The valid PNG and final claim of no parametric generation do not override the executed source. Exact calls and successful execution evidence are in `review-method/03-claude-cua/note.json`.
- **Scratch enforcement remains route-dependent.** Original conduct fails outside-workspace Write/Edit tool calls; shell scratch heuristics remain descriptive. Do not read the Pi + CUA success count as drawing/export capability alone. All three Pi + CUA attempts created valid PNGs but are excluded by recorded outside-workspace writes. Shell-created scratch in other arms is disclosed by full-session review, not converted into a new rule midway through the round.
- **Incidental windows are not ownership proof.** The extra visible Qt handle in `01-pi-cua` belongs to an already-running GameViewer PID with hidden baseline handles. It was preserved. The original window-diff flag stays untouched, but is not attributed to the actor or CUA; independent write violations suffice for exclusion.
- **Actor explanations are not runtime diagnoses.** `01-pi-computer-use` stopped voluntarily after reporting drags produced straight segments and exported nothing. Tool/capture/cleanup completion and no provider error do not prove the underlying gesture cause or general runtime incapability. Recovered tool errors and focus/menu/dialog mistakes remain in each full history.
- **Metric completeness is reviewed, not presumed.** `review-metrics/reviews.json` compares all structured execution arguments with selected calls, helper sources/edits, payload hashes/token sums, API usage and interval unions. Known omitted/ambiguous values are masked only in this additive `aggregate.json`; original `metrics.json` and `aggregate-original-metrics.json` remain unchanged. The review found 24 omitted CU invocations despite automatic completeness: 15 exec-loaded Python helper calls in `02-pi-cua` and nine environment-prefixed helper calls in `03-pi-cua`. Their five CU code/call/timing comparison values are unknown, with supported API totals preserved. Both attempts already fail conduct, so these masks do not remove a metric from a successful cohort. Existing static review gates are never cleared merely by assumption. See the per-trial table. No final-state-only provenance reconstruction or zero substitution was used.
- **Call timing includes host overhead.** CU times are top-level request-to-result spans, including mixed shell/setup/inspection work. Busy time unions overlap; sum adds spans. Code share uses tiktoken/o200k_base estimates over recorded output including reasoning; it is not exact billing-token attribution or a quality score. Static provenance is not instruction-level tracing.
- **Small conditional cohorts limit inference.** Three trials per arm are not a general reliability estimate. Models are matched within each harness only; cross-harness differences cannot be assigned to runtime alone. Shared desktop applications and offline review processes remained present. Skills/runtimes are the installed frozen profiles; this v0.5 round is not pooled with historical v0.4 results.
- **Export path/name automation is still unimplemented.** Actors retained the exact task requirement to export/rename Cloud9-Recreated.png in their workspace. No mid-trial helper was introduced. Normal preparation performs no blank export; the preceding explicit integration fixture does export outside actor timing.
- **Review coverage has limits.** Full textual source histories and original audits were reviewed; not every embedded image was individually inspected. Targeted image inspection resolves the smoothing dispute. File/shell access is configuration isolation, not an OS sandbox; Claude memory exclusion rests on the recorded safe-mode launch flag.

## Reproducibility and debugging

- Source commit: `0878fa5dbb01b58e4735a3bb992b9b1fe8e96c17`; frozen source under `source/`. Guarded source/skills matched before/after; no implementation, prompt or skill tuning during the round.
- Protocol: neutral v0.5, PNG only, ordinary redraws/revisions allowed, retained Pen/literal geometry. Exactly three interleaved repetitions of the five fixed arms. All successes averaged; no trimming, replacements or automatic fallback.
- Pi: `openai/gpt-6-astra`, low reasoning. Claude Code: `claude-opus-5-5`, low effort. Native transport: shipped SDK helper, not app-pipe. Codex computer-use skill path in this freeze selects installed build `26.1007.21434`, whereas the historical v0.4 report used an earlier frozen profile; do not treat them as byte-identical runtime comparisons.
- Exact actor prompt SHA-256: `2f09a976f855a3c6ad4096c9fcb59465d92c2651ac8be276daafa384930edc19`. Skill/assets/model/policy hashes are matched in `freeze.json`, each `plan.json` and aggregation checks.
- Evidence root: `C:\Users\13982\ahk-computer-use\.pi\rounds\illustrator-pen-export-20261012T082944Z`.
- `round.json` is maintainer bookkeeping after session review, not an actor deliverable. Standard `bench/aggregate.py` validates finished v0.5, matching prompts/assets/profiles and the three-slot policy; metric review masks are then applied additively with the same successful cohorts.
- Each attempt preserves `events.jsonl`, transcript, `metrics.json`, `summary.json`, `capture.json`, `conduct.json`, `isolation.json`, `verification.json`, `finished.json`, output PNG if produced, observer logs and `worker.log`; any failures retain `failure.json` / `crash.txt` / `capture-crash.txt` as applicable.
- Round orchestration: `round-worker.py`, `orchestrator.log`, `status.json`, `orchestrator-launch.json`; orchestration exceptions persist `orchestrator-crash.txt`. Report exceptions persist `report-crash.txt`. Cleanup: `final-processes.json`, `final-cleanup.json`, `scratch-cleanup.json`.
- Reviews: `review-method/reviews.json` and `review.md`; `review-metrics/reviews.json` and `review.md`; `review-adjudication.md`; `review-adjudication-03.md`; `review-dispositions.json`. Review scripts and any stack reports stay beside their reviews.
- ACU runtime log: `C:/Users/13982/AppData/Local/ACU/logs/runs.jsonl`; runtime crashes/stacks: `C:/Users/13982/AppData/Local/ACU/crashes/`. These runtime-managed diagnostics are preserved.

[All output slots](file:///C:/Users/13982/ahk-computer-use/.pi/rounds/illustrator-pen-export-20261012T082944Z/all-outputs.png) · [Reviewed aggregate](file:///C:/Users/13982/ahk-computer-use/.pi/rounds/illustrator-pen-export-20261012T082944Z/aggregate.json) · [Final cleanup](file:///C:/Users/13982/ahk-computer-use/.pi/rounds/illustrator-pen-export-20261012T082944Z/final-cleanup.json)
