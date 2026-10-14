# Adobe Illustrator Pen and Export v0.8: one success per configuration

Date: 2026-10-13. Historical alias: TB2.

## Requested run policy

The user requested one and only one successful fresh trial for each of the five configurations, with failed attempts retained and retried after diagnosis/fix. This request overrides the documented three-scheduled-trials/no-replacement rule for this run only. The actor prompt, neutral skills, models, reasoning, input assets, isolation, grading and cleanup policies were not changed. Historical evidence was not modified. The frozen per-trial plans retain the default three-attempt policy metadata; this report and the request manifest record the actual single-success cohort. `bench/aggregate.py` was not used because it requires three scheduled attempts per configuration.

All five configurations have exactly one reviewed successful trial. Every successful trial passed native drawing checks, conduct checks, maintainer as-is export, owned-resource cleanup and cursor restoration. Captured actor commands and generated helpers were reviewed for assigned-runtime compliance and genuine Pen-created Bézier curves. No final drawing used many short straight segments to approximate reference curves.

This is one successful sample per configuration, not a statistical performance study. Shape accuracy is an observation, not a quality threshold. No elapsed-task-time ranking is made.

## Measurements

Updated through additive offline replay after the measurement-gap repair. Original trial metrics/events/images/verdicts remain byte-identical; no actor was rerun. All five captured execution ledgers are now supported. The static estimator does not execute actor code or read final workspace files. Unsupported source transformations remain explicit review gaps.

| Configuration | Successes | API tokens | Uncached input | Cache read | Cache write | Output incl. reasoning | Code share | CU calls | CU sum seconds | CU busy seconds | IoU |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| pi-acu | 1 | 295,217 | 38,743 | 252,928 | 0 | 3,546 | 44.30% | 11 | 51.80 | 51.80 | 0.990244 |
| pi-cua | 1 | ≥ 9,915,655 | ≥ 328,865 | ≥ 9,580,032 | ≥ 0 | ≥ 6,758 | Unknown | 61 | 159.62 | 159.62 | 0.980543 |
| pi-computer-use | 1 | 13,796,930 | 299,282 | 13,489,536 | 0 | 8,112 | 24.94% | 101 | 98.01 | 98.01 | 0.939967 |
| claude-acu | 1 | 271,766 | 28 | 237,664 | 27,213 | 6,861 | 18.89% | 7 | 38.84 | 38.84 | 0.932867 |
| claude-cua | 1 | 2,927,673 | 132 | 2,840,874 | 71,048 | 15,619 | 18.78% | 38 | 225.68 | 225.68 | 0.892787 |

Pi CUA API components remain recorded lower bounds after a recovered stream interruption. Retained terminal error records contain no recoverable request usage, so its exact total and code-share percentage remain unknown. Its 1,946 estimated code tokens, 61 execution calls and 159.62 seconds are supported independently. No missing usage is replaced with zero.

Pi ACU failed-edit source replay is repaired; its code-share estimate is 44.30%. Pi CUA gains 39 formerly omitted helper calls; Claude CUA gains two shell-helper calls and now has an 18.78% code-share estimate. Code uses the o200k_base reference tokenizer, not billing-token attribution. Call duration includes top-level host setup/inspection overhead, not model response time. Sum and busy union are equal in these traces.

[Replay manifest and evidence hashes](../../.pi/artifacts/measurement-gap-fix/reanalysis.json) · [Provider usage gap](../../.pi/artifacts/measurement-gap-fix/provider-gap.json)

## Attempts and evidence

### pi-acu: failed

[Evidence directory](../../.pi/bench/20261013T190116Z-illustrator-pen-export-pi-acu-f1d345/)

Infrastructure-only failure before actor or desktop preparation: system Python missing tiktoken. Fixed by using uv environment.

[Startup traceback](../../.pi/bench/20261013T190116Z-illustrator-pen-export-pi-acu-f1d345/crash.txt). Fixed the interpreter selection by launching all subsequent trials with `uv run python bench/start.py`. This failure occurred before actor startup or desktop preparation; no application cleanup was needed.

### pi-acu: success

[Evidence directory](../../.pi/bench/20261013T190156Z-illustrator-pen-export-pi-acu-d8b447/)

Full captured command and script review: Illustrator interactions used ACU; closed Pen path with direction-handle drags; no faceted-curve approximation, off-runtime interaction or asset modification. Native path, export image and conduct audit reviewed; cleanup passed.

[Exported drawing](../../.pi/bench/20261013T190156Z-illustrator-pen-export-pi-acu-d8b447/grading/Cloud9-Recreated.png)

Unaligned boundary error: mean 0.324 px; p95 1 px.

### pi-cua: success

[Evidence directory](../../.pi/bench/20261013T190632Z-illustrator-pen-export-pi-cua-7134cd/)

Full session and helper review: all Illustrator interactions use cua-driver; foreground Pen drags create genuine curved arcs, not faceted approximations. Recovered malformed generation retained in history. Export image, native checks and conduct audit passed; cleanup passed.

[Exported drawing](../../.pi/bench/20261013T190632Z-illustrator-pen-export-pi-cua-7134cd/grading/Cloud9-Recreated.png)

Unaligned boundary error: mean 0.644 px; p95 2 px.

### pi-computer-use: success

[Evidence directory](../../.pi/bench/20261013T192848Z-illustrator-pen-export-pi-computer-use-e95c6a/)

Full captured session review: Illustrator interactions exclusively sky via node_repl MCP; Pen drags and normal direction-handle edits create curved paths, not straight-segment faceting. Native checks, exported drawing, conduct and cleanup passed.

[Exported drawing](../../.pi/bench/20261013T192848Z-illustrator-pen-export-pi-computer-use-e95c6a/grading/Cloud9-Recreated.png)

Unaligned boundary error: mean 2.035 px; p95 5 px.

### claude-acu: success

[Evidence directory](../../.pi/bench/20261013T194641Z-illustrator-pen-export-claude-acu-642f07/)

Full session and draw.ahk review: all Illustrator interactions via ACU; single closed Pen path with direction-handle drags for curved sections, not short straight-segment approximations. Shape has visibly flatter/lopsided arcs and a closure notch; retained quality observations, no arbitrary quality threshold. Native checks, image, conduct and cleanup passed.

[Exported drawing](../../.pi/bench/20261013T194641Z-illustrator-pen-export-claude-acu-642f07/grading/Cloud9-Recreated.png)

Unaligned boundary error: mean 2.303 px; p95 10 px.

### claude-cua: success

[Evidence directory](../../.pi/bench/20261013T194916Z-illustrator-pen-export-claude-cua-ffdff6/)

Full session, helper and coordinate review: all Illustrator interactions via cua-driver; three Pen-created closed paths with genuine dragged-handle curves, no many-short-straight-segment faceting. Background-input false start deleted by actor before final drawing. Squarer arcs, angular tips and small seam retained as quality observations. Native checks, exported image, conduct and cleanup passed.

[Exported drawing](../../.pi/bench/20261013T194916Z-illustrator-pen-export-claude-cua-ffdff6/grading/Cloud9-Recreated.png)

Unaligned boundary error: mean 3.997 px; p95 14 px.

## Recording

I mistakenly stopped the original OBS recording before the benchmark. The user restarted recording and clarified that it must run through the benchmark. No further recording controls were used until all five trials, session reviews and desktop cleanup finished. OBS then confirmed Start Recording and saved the playthrough to:

[E:/Videos/2026-10-13 15-00-58.mp4](file:///E:/Videos/2026-10-13%2015-00-58.mp4)

[Post-benchmark OBS evidence](../../.pi/artifacts/obs-stop/after-benchmark-result.json)

## Debugging paths

- [Request manifest](../../.pi/artifacts/tb2-one-success/round.json) records every attempt, reviewed outcomes, metrics and the policy override.
- Each trial directory retains `worker.log`, `stdout.jsonl`, `events.jsonl`, `stderr.log`, `summary.json`, `metrics.json`, `drawing-verification.json`, `conduct.json`, `cleanup.json` and `finished.json`.
- Crashes retain `crash.txt` or other `*-crash.txt` tracebacks; the only failed attempt in this request has `crash.txt`.
- ACU runtime logs: `~/AppData/Local/ACU/logs/runs.jsonl`; runtime crash reports: `~/AppData/Local/ACU/crashes/`.
- Recorded worker and actor PIDs were checked after completion; none remained. The benchmark started no test server or fixed localhost port. Existing applications and shared host services were preserved.

## Earlier Claude methods and accepted quality

The user accepts the current Claude drawings; no redraw, prompt/skill tuning or grading change was made. The pre-v0.7 inspection disproves "always polygonal": v0.6 had six polygonal Claude trials, but v0.5 had five handle-authoring trials and one polygonal trial; neutral v0.4 had seven handle-authoring trials and one automatically smoothed polygon; v0.3 includes saved native Bézier geometry. A successful v0.3 Claude ACU trial (`313e20`) retains 32 anchors, 30 with direction handles and 24 curved cubic segments. Historical model metadata identifies Opus 5.5. These records show that Claude has used genuine curves, not that every such trial was compliant or accurate.

[Full pre-v0.7 inventory](../../.pi/artifacts/claude-pre-v07-history/findings.md)
