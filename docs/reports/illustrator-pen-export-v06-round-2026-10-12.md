# Illustrator Pen and Export: v0.6 full round, 2026-10-12

## Outcome

**15 scheduled slots, all 15 launched and finished: 10 reviewed successes and 5 unsuccessful slots.** 10 passed the original automated checks. No failed slot was replaced; no provider/model fallback, parent coaching or mid-trial repair was used.

11 output PNGs were recorded; 10 pass the requested image/export checks. **4 slots ended with unexpected provider failures**, separate from ordinary export/method/runtime problems. Known usage for interrupted requests remains partial, not zero. All original files/verdicts/metrics and failure causes are retained.

This is the revised task: the new lossless-source 800 × 800 reference, explicit Workspace/Scratch folder/Final output paths, Pen drawing and assigned-tool interactions with Illustrator, fill #00AEEF and the stated Export As settings. Off-app image analysis/code and generated coordinates are allowed. GUI smoothing/redraws are allowed. Scratch placement, a particular stroke/opacity control choice, and manual artboard-suffix renaming are not extra method disqualifiers. No historical v0.5 literal-geometry restrictions were applied.

Every trial recorded owned-resource cleanup and cursor-scheme restoration. The final independent resource/source check found no recorded benchmark workers/actors or orchestrator alive, no owned Illustrator process, no active lock or private credential copies, and no public CUA lifecycle left. Shared services and unrelated apps were preserved. External task scratch is documented separately in `scratch-cleanup.json`; no runtime-managed logs/crash reports were purged.

## Successful-cohort averages

| Configuration | Successes / 3 | Unexpected provider failures | Retained n | Mean API tokens | Mean code/output % | CU busy s | CU sum s | Mean IoU |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Pi + ACU | 2/3 | 0 | 2 | 640,390 | 44.51 | 106.34 | 106.34 | 0.9777 |
| Pi + CUA | 1/3 | 2 | 1 | 15,547,865 | — | — | — | 0.9458 |
| Pi + Codex computer use | 1/3 | 2 | 1 | 16,426,589 | 30.16 | 85.62 | 85.62 | 0.9619 |
| Claude Code + ACU | 3/3 | 0 | 3 | 807,183 | 22.85 | 144.24 | 144.24 | 0.9816 |
| Claude Code + CUA | 3/3 | 0 | 3 | 3,557,272 | — | — | — | 0.9489 |

All successful trials are averaged without token/image trimming. Failures remain in evidence and never enter an average. Every metric uses the same retained cohort; an unavailable value makes that cohort metric unknown rather than changing the sample. Zero successes has no aggregate. Dashes mean unavailable, never zero. Code share is descriptive, not a success filter. End-to-end time, model latency and tokens-per-second are not ranking metrics.

### Token breakdown, same cohorts

| Configuration | Uncached input | Cache read | Cache write | Output including reasoning | Reasoning subset, not added again |
|---|---:|---:|---:|---:|---:|
| Pi + ACU | 56,555 | 579,072 | 0 | 4,762 | 1,195 |
| Pi + CUA | 213,622 | 15,326,080 | 0 | 8,163 | 1,022 |
| Pi + Codex computer use | 379,864 | 16,039,808 | 0 | 6,917 | 1,699 |
| Claude Code + ACU | 59 | 754,001 | 43,705 | 9,418 | 2,032 |
| Claude Code + CUA | 124 | 3,438,996 | 95,329 | 22,823 | 4,921 |

### Call count and shape observations, same cohorts

| Configuration | Mean CU call count | Mean boundary Manhattan px | Mean per-image p95 boundary px |
|---|---:|---:|---:|
| Pi + ACU | 19.50 | 0.74 | 3.50 |
| Pi + CUA | — | 1.86 | 7.00 |
| Pi + Codex computer use | 116.00 | 1.30 | 4.00 |
| Claude Code + ACU | 18.33 | 0.61 | 1.33 |
| Claude Code + CUA | — | 1.71 | 4.00 |

Shape metrics are unaligned observations without a pass threshold. Incorrect-size PNGs are not resized/repaired to invent a comparable shape score. The contact sheet resizes images only for display and labels original dimensions.

## Every scheduled trial

| Slot / trial | Reviewed outcome | Valid PNG | Recorded API tokens | IoU | Original result and reviewed note |
|---|---|---:|---:|---:|---|
| 01 / 01-pi-acu | failed | no | 305,681 | — | PNG check failed: dimensions; Actual PNG 550 × 381, RGB, DPI (71.9836, 71.9836). |
| 02 / 01-pi-cua | failed | no | 3,093,740 (known partial/unknown) | — | Cloud9-Recreated.png missing; OpenAI Responses stream ended before a terminal response event; Unsupported comparison values withheld; see metric review. |
| 03 / 01-pi-computer-use | failed | no | 9,086,124 (known partial/unknown) | — | Cloud9-Recreated.png missing; OpenAI API error (507): 507 exceeded request buffer limit while retrying upstream; Unsupported comparison values withheld; see metric review. |
| 04 / 01-claude-acu | success | yes | 688,407 | 0.9805 | PNG, capture, isolation, conduct, cleanup and reviewed method passed. |
| 05 / 01-claude-cua | success | yes | 2,705,962 | 0.9627 | PNG, capture, isolation, conduct, cleanup and reviewed method passed.; Unsupported comparison values withheld; see metric review. |
| 06 / 02-pi-computer-use | failed | no | 12,878,681 (known partial/unknown) | — | Cloud9-Recreated.png missing; OpenAI API error (503): 503 upstream connect error or disconnect/reset before headers. reset reason: connection termination; Unsupported comparison values withheld; see metric review. |
| 07 / 02-claude-acu | success | yes | 1,102,132 | 0.9822 | PNG, capture, isolation, conduct, cleanup and reviewed method passed. |
| 08 / 02-claude-cua | success | yes | 4,433,433 | 0.9643 | PNG, capture, isolation, conduct, cleanup and reviewed method passed. |
| 09 / 02-pi-acu | success | yes | 625,591 | 0.9904 | PNG, capture, isolation, conduct, cleanup and reviewed method passed. |
| 10 / 02-pi-cua | success | yes | 15,547,865 | 0.9458 | PNG, capture, isolation, conduct, cleanup and reviewed method passed.; Unsupported comparison values withheld; see metric review. |
| 11 / 03-claude-cua | success | yes | 3,532,422 | 0.9196 | PNG, capture, isolation, conduct, cleanup and reviewed method passed.; Unsupported comparison values withheld; see metric review. |
| 12 / 03-pi-acu | success | yes | 655,188 | 0.9649 | PNG, capture, isolation, conduct, cleanup and reviewed method passed. |
| 13 / 03-pi-cua | failed | no | 19,363,470 (known partial/unknown) | — | Cloud9-Recreated.png missing; OpenAI API error (503): 503 upstream connect error or disconnect/reset before headers. retried and the latest reset reason: remote connection failure, transport failure reason: delayed connect error: Connection refused; Unsupported comparison values withheld; see metric review. |
| 14 / 03-pi-computer-use | success | yes | 16,426,589 | 0.9619 | PNG, capture, isolation, conduct, cleanup and reviewed method passed. |
| 15 / 03-claude-acu | success | yes | 631,011 | 0.9820 | PNG, capture, isolation, conduct, cleanup and reviewed method passed. |

## Failure attribution and review limits

- **Provider failures are explicit.** The first Pi + CUA session ended before a terminal provider response. The first native computer-use session returned HTTP 507 "exceeded request buffer limit while retrying upstream"; its second returned HTTP 503 connection termination before headers. These are recorded provider responses, not proof that a desktop runtime cannot draw/export. Any later provider failures appear separately in the table and original `failure.json`. The controller did not retry or switch endpoints; upstream retry wording does not indicate a replacement benchmark slot.
- **The first ACU export failed artboard dimensions.** Its actual PNG is 550 × 381 RGB at about 72 ppi, rather than the 800 × 800 artboard export implied by Use Artboards at 72 ppi. This is consistent with artwork-bound export, but the exact UI cause is not asserted merely from its pixels. The source/action history and reviewer uncertainties are retained. No external resizing or re-export was provided.
- **Method review follows v0.6 only.** Full histories are checked for Pen construction and the assigned Illustrator interaction route. Generated coordinates, contour analysis, shape formulas, normal GUI smoothing and refinement are allowed. Original automated outcomes stay unchanged; extra concrete method violations, if any, appear only in the reviewed manifest.
- **Metric gates apply to the full success cohort.** The independent ledger review matches structured execution arguments, generated helpers/edits, token payload hashes/counts, recorded usage and timing intervals. Missing/ambiguous spans or code attribution are masked in this additive `aggregate.json`, not silently declared complete. Original estimates remain in `metrics.json` and `aggregate-original-metrics.json`. One unresolved success withholds that metric for its entire cohort, while other complete metrics still average every same success. The fresh audit found 82 omitted invocation calls across three histories: 21 environment-prefixed helper calls in successful `02-pi-cua`, one environment-prefixed set_value call in successful `03-claude-cua`, and 60 environment-prefixed/nested-helper calls in provider-failed `03-pi-cua`. Missing helper source/edit payloads and a help-only overcount in `01-claude-cua` are also documented. Consequently Pi + CUA and Claude + CUA withhold all five CU code/count/timing comparison values; API-token and image-quality averages remain supported.
- **Timing and code share have bounded meanings.** CU spans are top-level tool request-to-result time, including mixed setup/inspection/analysis overhead inside an identified execution call. Busy time unions overlap; sum adds spans. Code-token estimates use fixed tiktoken/o200k_base, not an exact billing tokenizer, divided by recorded output including reasoning. Static attribution is not an instruction-level trace.
- **Do not pool protocols or overgeneralize.** Small three-slot conditional cohorts, provider interruptions, different models across harnesses and changed prompt/reference limit comparisons. This round is not a regrade or pool of v0.5. Offline reviewer processes and their model requests ran concurrently, without desktop input; unrelated desktop applications and shared services remained present. Provider failures were not causally diagnosed from correlations in task/context size.
- **The supplied scratch location was used without a hidden location failure.** All 15 original conduct records contain zero outside-workspace Write/Edit calls. No surviving literal external scratch candidates were identified in the inspected completed source arguments. Workspace scripts and runtime-managed artifacts remain evidence; these observations are not a proof of all filesystem writes or a new pass criterion.
- **Coverage and safety limits remain visible.** Configuration isolation is not an OS sandbox. Full textual source/history and audits were reviewed; not every embedded screenshot was individually inspected. Claude memory exclusion rests on the recorded safe-mode flag. Initial window normalization does not establish or fix later resizing causes; no runtime/vendor patches or mid-attempt rescues were introduced.

## Reproducibility and persistent debugging

- Source commit: `78d1ea2292612bbf3a6bf82b993f668d05d3a0e2`. Frozen source is under `source/`; final source/skill fingerprints matched. The clean checkout, prompt, assets and selected runtime profiles were not tuned during this round.
- Five fixed configurations: Pi `openai/gpt-6-astra` low reasoning; Claude Code `claude-opus-5-5` low effort. Native transport uses the shipped SDK helper. Selected skill paths/hashes, exact models/policies and common template hash are in `freeze.json` and each `plan.json`.
- Common actor template SHA-256: `fdb4f0b5de631da477c26757dab8e2112d420fe4d76a7bcb270cc0a02c7ae20e`. Reference PNG SHA-256: `03dd860809cbfa143c35b50bd78fbdb8e43346e47d76e9aba5afc94a4e00a32c`. Original output bytes and actor evidence were not regraded under another protocol.
- Fresh schedule: three sequential interleaved repetitions, rotated by two configurations per repetition; original launch order is preserved in the table, freeze and timezone-aware `run-attempt.json` records. Exactly three slots per configuration; no replacements or fallback.
- `prompt-template.txt` plus its hash freeze the shared instructions; `prompt.txt` plus its hash freeze the exact per-run path expansion. Standard aggregation verifies both hashes and rendering, with matched assets/profiles across the full round. It follows the actual recorded output filename, including a unique normal artboard suffix, without renaming.
- Evidence root: `C:\Users\13982\ahk-computer-use\.pi\rounds\illustrator-pen-export-v06-20261012T182338Z`. Actual exported files and original sessions, `events.jsonl`, `stdout.jsonl`, `metrics.json`, `summary.json`, `verification.json`, `conduct.json`, `isolation.json`, `capture.json`, `finished.json`, observer logs and `worker.log` remain per trial.
- Worker/provider failures persist `failure.json`, `crash.txt`, `capture-crash.txt` as applicable. Round scheduling: `round.py`, `orchestrator.log`, `orchestrator-launch.json`, `status.json`; errors persist `orchestrator-crash.txt`. Report errors persist `report-crash.txt`. Final resources/source: `final-processes.json`, `final-cleanup.json`, `scratch-cleanup.json` and `external-files-before.json`.
- Reviews: `review-method/reviews.json` and `review.md`; `review-metrics/reviews.json` and `review.md`, with exact source IDs/timestamps and their retained offline scripts/checks. Metric masks never overwrite original measurements.
- Normal ACU log: `C:/Users/13982/AppData/Local/ACU/logs/runs.jsonl`; runtime crash stacks: `C:/Users/13982/AppData/Local/ACU/crashes/`. Runtime-managed diagnostics are preserved. No fixed localhost server/port was started.

[All output slots](file:///C:/Users/13982/ahk-computer-use/.pi/rounds/illustrator-pen-export-v06-20261012T182338Z/all-outputs.png) · [Reviewed aggregate](file:///C:/Users/13982/ahk-computer-use/.pi/rounds/illustrator-pen-export-v06-20261012T182338Z/aggregate.json) · [Final cleanup](file:///C:/Users/13982/ahk-computer-use/.pi/rounds/illustrator-pen-export-v06-20261012T182338Z/final-cleanup.json)
