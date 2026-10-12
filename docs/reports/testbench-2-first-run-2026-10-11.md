# Adobe Illustrator Pen and Export first runs and ACU improvement

## Result

The runnable Illustrator benchmark pilot now completes the Illustrator task with fresh isolated actors. A matched three-trial Claude+ACU comparison achieved the requested measurable improvement:

| Median measurement | Baseline | Final ACU | Change |
| --- | ---: | ---: | ---: |
| Continuous task time | 369.36 s | 265.93 s | **28.0% lower** |
| Process wall time | 390.69 s | 282.74 s | 27.6% lower |
| Computer-use calls | 17 | 16 | 5.9% lower |
| Foreground mask IoU against supplied JPEG | 0.94655 | 0.96836 | +0.02181 |
| Symmetric mean boundary Manhattan distance | 1.808 px | 1.063 px | 41.2% lower |
| Boundary p95 | 7 px | 3 px | Lower |

All six matched runs saved editable RGB AI and opaque white-background 800 × 800 PNG, passed export/native/isolation checks, and completed owned-document/cursor cleanup. Final method review found literal visually authored coordinates and desktop Pen/Anchor Point operations, with no executable contour/parametric point generators, imported vectors, actor Illustrator scripting, raster substitutes, or hidden solution reads.

This meets the predeclared 20% median task-time target without lower median drawing quality. It is a small, task-specific sample, **not a claim of statistical significance** or a four-arm comparison. The measured change is the ACU runtime **and skill-guidance bundle**; these trials do not isolate each contribution. Numeric shape pass thresholds remain uncalibrated, so original overall pilot verdicts remain `null`, not a manufactured pass.

Specification: [issue #10](https://github.com/stanley50z/ahk-computer-use/issues/10). Assets and maintainer source differences: [source inspection](testbench-2-source-inspection-2026-10-11.md).

## What remained fixed

- Native Claude Code arm `claude-acu`, `claude-opus-5-5`, low effort.
- Fresh workspace, configuration, credentials copy, session and transcript for every trial. No parent coaching inside a trial or reuse of a knowledgeable actor.
- Exact Illustrator benchmark v0.3 actor prompt and its SHA-256, recorded in every `plan.json`/`prompt.txt`.
- Blank 800 × 800-point RGB starter, ordinary white-fill/black-stroke defaults; the actor selects `#00AEEF`, no stroke and 100% opacity.
- Separate supplied JPEG, SHA-256 `715a4a7e15cb0e5ecc3452ef53585971eb7cb9ca5e61334c10bf1de443333231`. No output resizing, auto-alignment or registration.
- Common Getting Started workspace, 100% starting viewport, actual GUI calibration export, and verified English input before the actor starts.
- Continuous task-time definition: session start through the last computer-use result, including actor setup, appearance, drawing, saving and export. Result evidence/final answer are excluded under the existing definition; no step subtraction was introduced.

The actor may place the separate JPEG as a tracing aid, but must remove it before saving. Code may map/replay hand-authored literal anchor/handle positions, not generate those positions. The official vector/package/provenance report never enters the actor workspace.

## Matched trial data

Run directory names below resolve under `C:\Users\13982\ahk-computer-use\.pi\bench\`.

| Version | Run suffix | Task time | Calls | Reference IoU | Mean boundary error |
| --- | --- | ---: | ---: | ---: | ---: |
| Baseline | `20261011T093925Z-testbench-2-claude-acu-e283aa` | 281.31 s | 17 | 0.92834 | 2.457 px |
| Baseline | `20261011T094624Z-testbench-2-claude-acu-234015` | 504.20 s | 17 | 0.96488 | 1.170 px |
| Baseline | `20261011T095627Z-testbench-2-claude-acu-6d82eb` | 369.36 s | 18 | 0.94655 | 1.808 px |
| Final | `20261011T111507Z-testbench-2-claude-acu-fac394` | 281.64 s | 19 | 0.96836 | 1.063 px |
| Final | `20261011T112047Z-testbench-2-claude-acu-468dca` | 265.93 s | 16 | 0.97937 | 0.686 px |
| Final | `20261011T112614Z-testbench-2-claude-acu-a42c12` | 239.83 s | 15 | 0.94161 | 1.979 px |

Baseline range: 281.31–504.20 s. Final range: 239.83–281.64 s. The third final drawing is weaker than the first two; the report retains it rather than choosing only favorable outcomes.

Final saved-AI/render-to-submitted-PNG foreground IoU: **0.99741 / 0.99718 / 0.99768**. Minor differences are consistent with renderer/antialiasing behavior. The saved-file inspection uses a copy of the on-disk AI, not potentially unsaved in-memory artwork.

The second baseline's circular-looking literals and numeric row scans leave limited uncertainty about mental authoring; no executable coordinate generator exists in its commands. Observable method compliance is the literal list plus replay, not a claim to inspect the actor's internal reasoning. Independent audits distinguish that from the excluded executable generators below.

## Intermediate variants and exclusions

| Stage | Trials | Median task time | Median calls | Median IoU | Disposition |
| --- | ---: | ---: | ---: | ---: | --- |
| Baseline | 3 | 369.36 s | 17 | 0.94655 | Matched baseline |
| Paced v1 | 3 | 302.98 s | 15 | 0.94093 | 18.0% faster, below target and slightly lower quality; retained, not declared a win |
| Paced v2 | 2 | 171.74 s | 12 | 0.92547 | Faster but poorer curve/line joins; paused for guidance/safety fixes |
| Final | 3 | 265.93 s | 16 | 0.96836 | Target met with higher median quality |

Additional preparation/prompt-development attempts are not mixed with these v0.3 timings:

- Pi+ACU `7d08c6`: OpenAI stream ended before a terminal response event after drawing; no finished outputs.
- Pi+ACU `fe785c`: preparation-only failure from an AHK variable named `thread`, which collides with the built-in function. Fixed; no actor timing.
- Pi+ACU `e84727`: user reported accidental desktop clicks. Excluded as interrupted, not an ACU performance failure.
- Pi+ACU `aa5d74`: upstream HTTP 507 (`exceeded request buffer limit while retrying upstream`). Excluded as infrastructure failure.
- Claude+ACU v0.1 `464f4d`: artifact checks passed and IoU was 0.98278, but `trace.py` extracted/simplified the raster contour and replayed generated points. Method disqualified.
- Claude+ACU v0.2 `6a2842`: artifact checks passed and IoU was 0.97256, but an analytic arc generator computed anchors/handles. Conservatively disqualified; v0.3 clarified that positions must be literals authored from inspection.

The switch from interrupted GPT attempts to the existing Claude arm was explicit. It was not a silent model/provider fallback within an arm; baseline/final comparisons use only the same Claude profile.

## ACU changes

`acu/lib/actions.ahk` adds opt-in operations while leaving native AHK functions unchanged:

- `AcuActivate`: exactly one window; refuses an owned dialog, waits for a dialog's parent to re-enable after closure, then verifies activation.
- `AcuKeys`: target activation plus nonzero `SendEvent` press duration, using the English-input guard and restoring caller key timing.
- `AcuClick` / `AcuDrag`: bounded contact and pointer movement, screen-coordinate hit tests against the target's child/owned windows, abort/release on activation loss, and release on normal script exit/error. Native mouse timing and SendMode are restored; cursor/foreground are not restored.

### Saved-handle regression

A literal 150-point horizontal Pen handle reproduced as **135 points** in saved Illustrator geometry with an unsettled 10-step gesture. The discrepancy existed before closing the path. A 500 ms final dwell, uncoalesced SendInput moves, and a duplicate identical endpoint did not fix it. Approaching again from one pixel away and returning to the authored endpoint produced **149.5 points**, within one physical pixel on this 2× desktop.

Horizontal endpoint error fell **15.0 → 0.5 points (96.7% lower)**. The retained implementation uses native mouse operations, not the unsuccessful lower-level SendInput experiment. Focused regression checks inspect saved AI anchor/control-point coordinates and verify restored caller input settings.

The skill adds generic guidance on target/owned-dialog handling, current-directory scripts, paced input, Pen curve/line joins, caller-observed readiness, and the installed English Illustrator Save As/Export As route. It contains no Cloud9 solution coordinates or geometry generator. Guidance changes also prevent misdiagnosing poor curve fitting as an input-duration problem.

## Runnable benchmark and verification

`bench/run.py` / `bench/start.py` accept `--scenario calculator|illustrator-pen-export`; Calculator remains the default. Offline preparation copies only actor assets into the fresh workspace, freezes the grading JPEG outside it, and records hashes. Existing isolation, task-time and process ownership machinery is reused.

Maintainer-only JSX opens/prepares/inspects/closes task documents through Illustrator's Other Script UI. A real blank GUI export commits repeatable PNG options because preference setters alone do not reliably update the cached dialog state. Export settings can change again during actor workflows; the actor is still instructed to select all required settings.

PNG checks cover format/dimensions, opacity, white background, solid blue, non-interlacing and available ppi metadata. Foreground classification is R < 128, G > 100, B > 150, alpha > 127. Appearance checks tolerate antialiasing (at least 95% of foreground pixels are the exact specified blue; at least 99% of nonforeground pixels are opaque white), independently of an uncalibrated shape verdict. Exact saved-vector appearance is checked natively.

Native inspection checks RGB/single 800-point artboard, editable paths with no raster/placed substitutes, visible 100%-opacity appearance/no stroke/#00AEEF, and an independent PDF-compatible header check. Manifest fields/types and declared output paths are verified. Complete path/control-point data are retained as evidence, not an anchor-count/topology pass rule.

## Review and conduct findings

### Standards

The review found that merely activating a target did not bind absolute pointer coordinates to it. The helper could press a different window. The fix hit-tests before contact, checks activation during drags, and is covered by disposable same-process/different-window tests. Script-exit button release and English-input behavior also have focused desktop checks.

Native and Python cleanup independently revalidate document ownership. Duplicate native document identities now fail explicitly immediately before close; the duplication is intentional defense across the process boundary.

### Spec

Missing/incomplete result manifests were accepted by the first checker. The fix requires the requested fields/types and paths matching inspected files. Shape thresholds and post-run method/consistency review remain intentionally separate and pending numeric calibration.

Two automatic conduct false positives were corrected, without rewriting original evidence:

1. Paced v2 `f6a0be` flagged new HWND `29625038` as non-Illustrator; the raw probe binds it to the same Illustrator PID `65728`. Floating panels/contextual task bars are application UI.
2. Final `a42c12` flagged vanished pre-existing HWND `10887762`. Actor output at 122.808357 s identifies it as `SysShadow`; the first drawing command dismisses a Fill/Stroke onboarding tooltip. Only exact Illustrator-owned `SysShadow` auxiliaries are exempted. Main frames, actual user windows and document identities remain protected.

Original `conduct.json` / `summary.json` are unchanged; `conduct-replayed.json` / `summary-replayed.json` preserve the corrected verdict and evidence rationale. The independent final method audit confirmed the shadow correction. All matched final trials have successful corrected conduct verdicts and empty pre-existing-document-change lists.

The audit is not an OS security sandbox. Some actors wrote scripts outside their workspaces or later removed their own temporary directories; complete command arguments remain in transcripts. The skill now directs default script/capture placement into the current workspace, but heuristics cannot prove arbitrary shell behavior safe. Geometry signatures cover path positions/common appearance/text/layer state, not every possible complex Illustrator object property.

## Focused checks and debugging evidence

Quiet checks use the project `uv` environment and exclude desktop integration by default. Final focused quiet run: **62 passed, 3 desktop tests deselected** (`tests/test_bench*.py`, `tests/test_skill.py`, `tests/test_tool.py`). Final combined native run: **5 passed**, covering the real starter/Pen input/saved AI/export/modal refusal/menu route/owned cleanup, pointer-window rejection, exit release, English input, and unchanged native prelude defaults. An additional focused pointer-safety run passed **3 tests**, including activation-loss abort/release. No full desktop suite was used as a completion gate.

Persistent artifacts:

- Per-trial evidence: `C:\Users\13982\ahk-computer-use\.pi\bench\<run-id>\` (`plan.json`, `prompt.txt`, `scenario.md`, fingerprints, native snapshots, `metrics.json`, `verification.json`, original/replayed conduct and summaries, raw events/transcripts, output files, observer logs, cleanup/finished records).
- Preparation/regression/prototype logs: `C:\Users\13982\ahk-computer-use\.pi\tb2-validation\` (RED/GREEN logs, saved-handle experiments, `comparison.json`, `replay-conduct.log`).
- ACU runtime log: `C:\Users\13982\AppData\Local\ACU\logs\runs.jsonl`.
- ACU crash reports with stacks: `C:\Users\13982\AppData\Local\ACU\crashes\`.
- Native script errors preserve stack/line data in run-local `illustrator-*.json`; worker failures retain `crash.txt`, `capture-crash.txt`, `worker.log` and `observer-*.log`.

Interrupted runs and cleanup failures are preserved with later `recovery-cleanup.json`; recovery is not retroactively represented as the original successful cleanup. Private run credentials are deleted in `finally`; no saved login values belong in this report. A final scan found no private credential copies in run directories. All **17 run records** are finished, captured owned actor trees were stopped, the active lock is released, and the task-started Illustrator main process **PID 65728 exited** after native verification of zero remaining documents. Final cleanup/reload/process evidence is in `.pi/tb2-validation/final-cleanup.log`, `final-app-cleanup/`, and `process-cleanup-verified.json`. Only task-authored files were copied from `C:/tmp/c9` into the baseline evidence and removed; its parent directory was preserved. No test/dev server or fixed localhost port was started.

## Remaining work

- Calibrate numeric shape acceptance on known-good and deliberately incorrect outputs before declaring future trials overall pass/fail.
- Continue explicit post-run method and saved-AI/PNG agreement review, or build a separate reliable audit when evidence supports it.
- Extend the actual Illustrator benchmark comparison to the other arms when that is the requested next experiment. The runner supports them, but this measured improvement is Claude+ACU only.
- Application-dependent issues #12/#13 remain outside this benchmark implementation except where the measured input behavior directly required the opt-in helpers.

No commit/push is implied by these results; the work is left in the requested checkout.

## API sources used during implementation

- [Illustrator Application workspace methods](https://ai-scripting.docsforadobe.dev/jsobjref/Application/).
- [Adobe: straight lines followed by curves](https://helpx.adobe.com/illustrator/desktop/draw-shapes-and-paths/draw-shapes/draw-straight-lines-followed-by-curves.html).
- [Adobe: curves followed by straight lines](https://helpx.adobe.com/illustrator/desktop/draw-shapes-and-paths/draw-shapes/draw-curves-followed-by-straight-lines.html).
- [Microsoft MOUSEINPUT flags](https://learn.microsoft.com/en-us/windows/win32/api/winuser/ns-winuser-mouseinput), investigated for coalescing; that lower-level experiment was not retained.
