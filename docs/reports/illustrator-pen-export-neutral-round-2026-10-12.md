# Illustrator Pen and Export: neutral v0.4 round, 2026-10-12

## Outcome

**25 scheduled slots: 24 launched, 23 actors started, 16 reviewed successes, 8 failed launched attempts, and 1 user-interrupted slot before launch.** No failed slot was replaced. The user stopped the round with only the final Claude + CUA slot unlaunched and explicitly asked to count it as user-interrupted. It is not a runtime failure or a zero-token actor execution.

There are 21 output PNGs: 20 meet the automated PNG checks and one has incorrect dimensions. A valid image does not override conduct or authoring-method failures. All original histories, PNGs, verdicts, logs and failures remain intact.

The final resource check found no Illustrator processes, no live recorded benchmark workers, no visible CUA sessions, no active benchmark lock and no private credential copies. The shared CUA daemon and unrelated applications were preserved. See `final-cleanup.json`.

## Successful-cohort aggregates

| Configuration | Successes / 5 slots | Failed started | User interrupted | Retained n | Mean total API tokens | Mean code/output % | Mean CU busy s | Mean CU sum s | Mean IoU |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Pi + ACU | 4/5 | 1 | 0 | 4 | 1,025,947 | 50.2 | 65.60 | 65.60 | 0.9386 |
| Pi + CUA | 0/5 | 5 | 0 | 0 | — | — | — | — | — |
| Pi + Codex computer use | 5/5 | 0 | 0 | 3 | 5,586,870 | 39.8 | 60.90 | 60.90 | 0.8283 |
| Claude Code + ACU | 4/5 | 1 | 0 | 4 | 865,615 | — | — | — | 0.9074 |
| Claude Code + CUA | 3/5 | 1 | 1 | 3 | 5,171,729 | — | — | — | 0.9119 |

A dash means unavailable, not zero. Claude code-share and CU-time aggregates remain unknown because retained runs have unresolved attribution. API usage and image quality remain available. Pi + CUA has no successful aggregate; its three valid images remain visible in the failed-attempt evidence.

Only Pi + Codex computer use achieved five successes: token-order trimming removes attempts 03 (4,785,030 tokens) and 01 (7,369,806), retaining 04, 02 and 05 for every metric. Pi + ACU retains 01, 02, 04, 05; Claude + ACU retains 01-04; Claude + CUA retains 01-03. There is no trimming for these arms because each has an unsuccessful slot. No metric uses a smaller, more favorable subset.

Within the matched Pi group, ACU used fewer API tokens and had higher mean image overlap in its retained successful cohort than Codex computer use. Codex computer use completed all five slots; ACU had one export-dimensions failure. These are joint reliability/quality/cost observations, not a single overall winner. The small samples, conditional cohorts, provider failures and route-dependent conduct policy limit generalization. Models differ across harnesses, so do not attribute cross-harness differences solely to the computer-use runtime.

## Every scheduled attempt

| Attempt | Reviewed outcome | Valid PNG | Recorded API tokens | IoU | Note |
|---|---|---:|---:|---:|---|
| 01-pi-acu | success | yes | 907,153 | 0.9555 | Passed PNG, isolation, conduct and method review. |
| 01-pi-cua | failed | no | 933,389 (partial) | — | Provider stream ended before a terminal response event; no PNG. Post-run ownerless Color Picker cleanup failed, then recovered separately.; Cloud9-Recreated.png missing; Original cleanup failed or was unverified; later recovery does not change the attempt outcome. |
| 01-pi-computer-use | success | yes | 7,369,806 | 0.7921 | Passed PNG, isolation, conduct and method review. |
| 01-claude-acu | success | yes | 939,568 | 0.9090 | Passed PNG, isolation, conduct and method review. |
| 01-claude-cua | success | yes | 4,563,729 | 0.8767 | Passed PNG, isolation, conduct and method review. |
| 02-pi-acu | success | yes | 1,441,385 | 0.9334 | Passed PNG, isolation, conduct and method review. |
| 02-pi-cua | failed | yes | 11,478,216 | 0.9563 | write tool used outside the workspace |
| 02-pi-computer-use | success | yes | 5,642,275 | 0.8363 | Passed PNG, isolation, conduct and method review. |
| 02-claude-acu | success | yes | 725,401 | 0.8473 | Passed PNG, isolation, conduct and method review. |
| 02-claude-cua | success | yes | 5,784,506 | 0.9200 | Passed PNG, isolation, conduct and method review. |
| 03-pi-acu | failed | no | 368,283 | — | PNG check failed: dimensions |
| 03-pi-cua | failed | yes | 5,512,388 | 0.9044 | write tool used outside the workspace |
| 03-pi-computer-use | success | yes | 4,785,030 | 0.8859 | Passed PNG, isolation, conduct and method review. |
| 03-claude-acu | success | yes | 784,894 | 0.9439 | Passed PNG, isolation, conduct and method review. |
| 03-claude-cua | success | yes | 5,166,953 | 0.9390 | Passed PNG, isolation, conduct and method review. |
| 04-pi-acu | success | yes | 1,053,605 | 0.9289 | Passed PNG, isolation, conduct and method review. |
| 04-pi-cua | failed | no | 176,372 (partial) | — | OpenAI HTTP 503 subscription_sharing_user_unavailable interrupted the actor before drawing.; Cloud9-Recreated.png missing |
| 04-pi-computer-use | success | yes | 5,139,214 | 0.7838 | Passed PNG, isolation, conduct and method review. |
| 04-claude-acu | success | yes | 1,012,597 | 0.9297 | Passed PNG, isolation, conduct and method review. |
| 04-claude-cua | failed | yes | 5,121,976 | 0.8592 | Automatic smooth conversion replaced visually chosen Pen handles: Direct Selection plus Properties > Convert to smooth at 273.586 s (toolu_01MCCG2hagEcbPsfFXrShTER); see review-04.json. |
| 05-pi-acu | success | yes | 701,644 | 0.9367 | Passed PNG, isolation, conduct and method review. |
| 05-pi-cua | failed | yes | 3,509,408 | 0.9313 | write tool used outside the workspace |
| 05-pi-computer-use | success | yes | 5,979,121 | 0.8646 | Passed PNG, isolation, conduct and method review. |
| 05-claude-acu | failed | no | — | — | Illustrator main window did not settle within 45000 ms during preparation; actor never launched.; Original cleanup failed or was unverified; later recovery does not change the attempt outcome. |
| 05-claude-cua | user_interrupted_before_launch | no | — | — | User interrupted this scheduled slot before launch. Not a runtime failure. |

## Review decisions and limits

- **04-claude-cua is excluded after method review.** The initial Pen drags produced a closed polygon without handles. The actor then selected curve anchors and used Properties > Convert to smooth, which supplied handles automatically instead of replaying its visually chosen handle positions. Original screenshots and calls at 240.652 s / 273.586 s establish this, beyond the final self-description. Missing input permits retries; it does not change the required construction method. No additional full-redraw or repeated-refinement violation is claimed. The original automated pass remains untouched; the reviewed manifest adds the violation.
- **Workspace enforcement is route-dependent.** The frozen policy fails outside-workspace Write/Edit tool calls but reports shell-write heuristics only. Three Pi + CUA runs fail the former check. Claude runs also created outside-workspace shell helpers; these are disclosed observations under the frozen policy, not newly invented failure criteria. Reviewers initially proposed additional shell-write failures in 02/03 Claude + CUA; the parent disposition keeps the predeclared policy. This asymmetry weakens any claim that the success counts measure drawing/export capability alone.
- **Export correction is not another drawing attempt.** Several actors first exported without effective artboard inclusion, then corrected the export. No second geometry pass was found in those cases. Rough curves are retained; no quality threshold was used. Early repeated drags with evidence of missing handles remain allowed input-retry cases or explicit uncertainty, not invented refinement failures.
- **Interruptions are separate causes.** 01 Pi + CUA ended on an OpenAI stream termination before drawing, then hit the known ownerless Color Picker cleanup defect. Its exact new picker was cancelled only after the actor stopped and its task document/application were cleaned up; the original failure was retained. 04 Pi + CUA stopped on OpenAI HTTP 503 `subscription_sharing_user_unavailable`. 05 Claude + ACU failed the 45-second Illustrator startup settling check before actor launch. No actor/provider/runtime retry or fallback was used.
- **Attribution is incomplete in some histories.** Shell wrappers, variable/loop commands, and nested Python subprocess helpers can escape static attribution. A Python `1<<20` expression is also mistaken for a heredoc in three Claude CUA calls. Retained Claude cohorts already have unresolved gates, so all code-token/share and CU-count/time averages remain unknown. The failed 05 Pi CUA run demonstrates hidden undercoverage even though its original completeness flags are true. Those original estimates remain diagnostic only. The reviewed Pi ACU and retained Pi Codex CU cohorts have no concrete omissions found by the bounded audit.
- **Timing means host-call durations.** Mixed setup/inspection overhead inside a CU-containing host call is included. Busy time unions overlapping intervals; sum time adds durations. Neither is end-to-end task time, isolated input-event latency, or a model-speed ranking. Code share uses estimated generated code/argument tokens divided by recorded output tokens including reasoning; reasoning is not counted twice.
- **PNG grading is observational beyond completion checks.** IoU and boundary distances have no pass threshold and no alignment/rescaling. The exact-blue/antialiasing heuristic remains a limitation; no false color rejection was observed in this round.
- **Cleanup evidence is additive.** The startup-failed slot originally recorded unverified cleanup. Final process inspection found no Illustrator process and no remaining benchmark workers, but does not turn that attempt into a success. Referenced external scratch files created during this round were copied byte-for-byte into `scratch-preserved/` before removal; older files were preserved. Runtime-managed ACU logs/crash reports were not removed.

## Reproducibility and evidence

- Source commit: `d7258a3bde301635f05594b7cf5d223b40ea6b8b`. `acu/`, `bench/`, tests and guarded documentation fingerprints remained unchanged through final aggregation. No implementation or actor prompt was tuned during the round.
- Protocol: neutral v0.4, PNG only, one drawing attempt. Pi arms use `openai/gpt-6-astra` at low reasoning; Claude arms use `claude-opus-5-5` at low effort. Configurations were interleaved over five repetitions. Prompt, assets and per-configuration skills were frozen and matched.
- Exact prompt SHA-256: `a55b3c1f7791a31bfc7c36a3e07a4d334529ed5fd12b2640c6c769b8bb0855d1`.
- The user cutoff overrides the requirement for five actually launched attempts. Aggregation calls the existing `aggregate_configuration` and `comparison_statistics` functions over five explicit scheduled dispositions. The standard `aggregate_round` file loader requires a real start record; no fake `started_at`, worker or transcript was created to satisfy it. The cancellation is excluded from averages and disables trimming for Claude CUA, as an unsuccessful slot.
- Round folder: `C:\Users\13982\ahk-computer-use\.pi\rounds\illustrator-pen-export-20261012T014917Z`.
- Round files: `freeze.json`, `round.json`, `round-closed.json`, `aggregate.json`, `review-01.json` through `review-05.json`, `review-dispositions.json`, `metric-review.json`, `final-cleanup.json`, `scratch-cleanup.json`, and `all-outputs.png`.
- Each attempt retains its plan and original session/events, output image when produced, `metrics.json`, `verification.json`, conduct/isolation checks, `worker.log`, `finished.json` and any `crash.txt`. Failed setup has no invented actor history. The unlaunched final slot has `user-interruption.json`.
- Persistent ACU run log: `C:/Users/13982/AppData/Local/ACU/logs/runs.jsonl`; runtime crash stacks: `C:/Users/13982/AppData/Local/ACU/crashes/`. Metric/method reviews cite original tool IDs and event locations.
- Report/aggregation builder: `.pi/rounds/build-final-report.py`. It reads original evidence and writes additive reports only; it never launches a trial.

[All 25 output slots](file:///C:/Users/13982/ahk-computer-use/.pi/rounds/illustrator-pen-export-20261012T014917Z/all-outputs.png) · [Machine-readable aggregate](file:///C:/Users/13982/ahk-computer-use/.pi/rounds/illustrator-pen-export-20261012T014917Z/aggregate.json) · [Final cleanup verification](file:///C:/Users/13982/ahk-computer-use/.pi/rounds/illustrator-pen-export-20261012T014917Z/final-cleanup.json)
