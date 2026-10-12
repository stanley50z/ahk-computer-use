# Adobe Illustrator Pen and Export: five-configuration run

## Result

Ran the requested five-configuration Illustrator benchmark with fresh isolated actors, the same v0.3 prompt and input files, GPT-6 Astra/low in Pi, and Opus 5.5/low in Claude Code. The native Pi arm had one additional fresh retry after a provider interruption.

| Configuration | Outcome | Continuous task / attempt time | Reference foreground IoU |
| --- | --- | ---: | ---: |
| Pi + GPT-6 Astra + ACU | Completed; artifact and method checks support compliance | **418.63 s** (6m 58.6s) | **0.98807** |
| Pi + GPT-6 Astra + CUA | Completed; artifact and method checks support compliance | **1284.31 s** (21m 24.3s) | **0.96973** |
| Pi + GPT-6 Astra + native computer use | Fresh retry reported blocked; no final AI/PNG | **198.85 s attempt** | No output |
| Claude Code + Opus 5.5 + ACU | AI/PNG saved, but invalid result manifest; original grading failed | **278.70 s** (4m 38.7s) | **0.95784**, separate artifact review only |
| Claude Code + Opus 5.5 + CUA | Completed; artifact and method checks support compliance | **651.87 s** (10m 51.9s), reviewed endpoint | **0.95069** |

The native arm's earlier attempt was interrupted by **OpenAI HTTP 507** after 379.44 s of task activity, without final files. It is retained separately, not treated as a completed or representative task time.

The Claude+CUA controller originally reported **658.99 s**. Its final evidence-only Bash command mentioned `cua-driver` inside the JSON it wrote, causing a false runtime match. The reviewed task endpoint is the preceding actual export/input result, yielding **651.87 s**. This follows the existing continuous-task definition; no individual setup, drawing, save or export steps were subtracted. Original metrics are untouched, and the endpoint correction is recorded separately below.

**These are single trials, not medians or statistical claims.** In the Pi pair that completed, CUA took about **3.07×** the ACU time and produced a slightly lower shape score. Claude+ACU produced artwork sooner than Claude+CUA, but its malformed manifest prevents treating that as a clean valid-submission speed win. The blocked native attempt is not a fast completion.

Numeric shape pass thresholds remain uncalibrated. A completed pilot with successful structural/export checks and a supported method is not an unconditional numeric shape pass.

## Frozen configuration

Both scenario names/file organization and the five-profile integration were uncommitted changes atop `63ec02304c3155d107b526a500553848f27ad275`. The round therefore identifies its implementation by a **frozen source copy and file fingerprints**, not by claiming clean-commit reproducibility.

Round evidence root:

`C:\Users\13982\ahk-computer-use\.pi\illustrator-five-arm\20261011T195048Z\`

- `source/acu/` and `source/bench/`: the implementation used for the round.
- `manifest.json`: five offline profiles, source fingerprints and asset/model/skill hashes.
- `profiles/`: isolated offline preparations, without login credentials.
- `results.json`: raw measurements and post-run source/cleanup checks.

After all six attempts, the fingerprinted ACU, benchmark, tests and steering files still matched the pre-round snapshot. Every trial matched its expected model, reasoning, skill hash and prompt/asset hashes. No runtime/skill fix or parent coaching was applied mid-round.

| Setting | Value |
| --- | --- |
| Pi model | `openai/gpt-6-astra`, low reasoning |
| Claude Code model | `claude-opus-5-5`, low effort |
| Actor prompt | Adobe Illustrator Pen and Export v0.3 |
| Prompt SHA-256 | `b6b38f65c7675f11b27fd94fa0fcbef75d38208c441a6914727ef97a6f3c254b` |
| Blank starter AI SHA-256 | `d2197b639dd7c9d4528962f8252bdbb0e6d250551f16675324ea95e2e0d99445` |
| Separate JPEG SHA-256 | `715a4a7e15cb0e5ecc3452ef53585971eb7cb9ca5e61334c10bf1de443333231` |

All actors started with the same blank 800-point RGB document, common viewport/workspace/PNG preparation, and verified English input. The actor selected fill/stroke, drew, saved and exported within continuous task time. Placing the reference as a removable tracing aid was permitted; these actors instead inspected the separate image. Literal hand-authored anchor/handle positions and coordinate mapping/replay were permitted; executable contour/parametric point generators and vector imports were not.

Pi/native used the installed `computer-use` skill and `node_repl` / `@oai/sky` runtime through the documented benchmark app-approval adapter. The actual Illustrator requests were approved as low-risk app-use requests with empty form schemas; no denial explains either native attempt's failure.

## Per-configuration findings

### Pi + Astra + ACU

Run: `20261011T195049Z-illustrator-pen-export-pi-acu-73df8d`.

- Native inspection found **one closed editable path, 35 anchors**, correct appearance and PDF compatibility. PNG checks passed: 800×800, opaque white background, requested blue, non-interlaced and 72-ppi metadata.
- Reference boundary mean error: **0.396 px**, p95 **1 px**.
- Saved-AI render versus submitted PNG: foreground IoU **0.996917**, p95 **1 px**.
- Method audit inspected every tool command and retained `workspace/evidence/pen-path-coordinates.ahk`. Coordinates were literal; arithmetic only maps them to screen pixels. No observed generator/import/actor JSX/raster substitution/hidden solution read.
- The actor recovered from Color Picker value-setting failure and initial uneven curves, then redrew with separately authored handles/curve-to-line joins. Export anti-aliasing dropdown activation required recovery, and AI save completion lagged the export.
- A broad home-directory filename search and unguarded keyboard recovery were unnecessary risks. No collateral modification was detected, but the conduct audit is not a sandbox or exhaustive safety proof.

Original isolation, conduct and cleanup checks pass. Task time is 418.63 s; wall time is 449.57 s.

### Pi + Astra + CUA

Run: `20261011T200005Z-illustrator-pen-export-pi-cua-86ed44`.

- Native inspection found **one closed editable path, 56 anchors**, correct appearance and PDF compatibility; PNG export checks pass.
- Reference boundary mean error: **1.012 px**, p95 **3 px**.
- AI-render/PNG foreground IoU: **0.99756**, p95 **1 px**.
- Retained `workspace/evidence/pen.py`, `final-pen.py`, `refine.py` and `corners.py` use literal coordinate lists, affine screen mapping and desktop input replay. No executable coordinate generator or prohibited source/automation route was observed.
- Accessibility queries repeatedly timed out. The actor used screenshots and desktop captures, switched from ineffective background text/initial synthetic dragging to foreground input, and recovered from a handle-refinement attempt that selected Scissors. It discarded its draft and redrew.
- Export required further menu/input recovery. The task-specific `cloud9` session ended with `active:false`; no CUA sessions remained in the follow-up check.

Original isolation, conduct and cleanup checks pass. Task time is 1284.31 s; wall time is 1299.27 s. All elapsed actor work remains counted. This run shows CUA can complete this task; it does not support describing CUA as universally unable to operate Illustrator.

### Pi + Astra + native computer use

First run: `20261011T202303Z-illustrator-pen-export-pi-computer-use-d80af2`.

The actor made progress through a literal point list, but the provider ended the session with **HTTP 507: exceeded request buffer limit while retrying upstream**. No `result.json` or final AI/PNG existed. The last native call completed at receipt time 381.687 s; task activity was 379.44 s and wall time 382.71 s. This is an upstream/provider interruption, not independent proof of a desktop-runtime drawing defect.

Fresh retry: `20261011T203051Z-illustrator-pen-export-pi-computer-use-644b6d`.

- The actor recovered from Color Picker targeting and a coordinate request outside a **260×284** screenshot region by targeting the modal screenshot explicitly.
- It replayed literal Pen anchors/handles, but reported that drag actions created corners/straight segments rather than the intended handles; a later drag on an existing point made only an outgoing handle.
- It reported Shift+C selecting Scissors instead of Anchor Point, then stopped rather than submit an unfinished drawing. Native tool calls near the end returned without transport errors; the missing-handle/tool-selection diagnosis is the actor's screenshot interpretation, not a proven low-level transport cause.
- The retry's `result.json` explicitly says `blocked`, with no final AI/PNG. No prohibited generation/import/actor JSX was found.

The adapter accepted **93** app-approval requests in the interrupted attempt and **39** in the retry, with no declines. Both attempts passed isolation/conduct and cleaned up their one unsaved task item/document and task-started Illustrator process. Retry task activity: 198.85 s; wall time: 223.86 s. No failed attempt is counted as a completed task.

### Claude Code + Opus + ACU

Run: `20261011T203547Z-illustrator-pen-export-claude-acu-acf1f8`.

The actor saved both requested artwork files, but its final Bash heredoc wrote `C:\Cloud9-Recreated.ai` inside a JSON string without escaping the backslash. Original `result.json` is invalid:

`Invalid \escape: line 11 column 82 (char 966)`

The automatic grader therefore crashed before producing `verification.json`, the final conduct audit or after-fingerprint. This remains a failed original submission; no successful original overall/manifest verdict is implied.

A **separate forensic copy** was created under the round evidence root's `claude-acu-artifact-review/`. Only that copy's one invalid escape was repaired so the existing artifact checker could inspect unchanged AI/PNG bytes. The original manifest SHA-256 remains:

`dd72ea28030b425dd226b42db81af6d63cfd81e65c061afa18f7a66552e5986d`

Forensic findings:

- Export and native vector/appearance/PDF-compatible checks pass.
- Reference IoU **0.957839**, boundary mean **1.437 px**, p95 **4 px**.
- AI-render/PNG IoU **0.997426**.
- Native inspection found **six PathItems, one open**, not the actor's claimed seven separate components. The task does not require a particular path count, merged topology or every path closed, so this is not itself a method violation.
- Captured drawing/rework commands use literal coordinates mapped to screen pixels. No executable contour/parametric generator, geometry import, hidden source read, actor JSX or raster substitute was observed. The overlapping/filler Pen paths are allowed.

The actor also encountered AHK x/y parameter collisions, closure-handle problems and mis-targeting of the Color Picker. A malformed Save As path attempted the C-root location; the permission prompt was answered No before correcting the workspace destination. No root-file damage is evidenced. The absence of a completed original conduct audit means broader conduct cannot be called passed, even though source fingerprints for the entire round remained unchanged.

Task time through the last desktop/export result: **278.70 s**; wall time **303.68 s**. Isolation and original cleanup pass. The artwork score is forensic only, not a repaired original benchmark pass.

### Claude Code + Opus + CUA

Run: `20261011T204220Z-illustrator-pen-export-claude-cua-199839`.

- Native inspection found **three closed editable paths**, with 17/16/18 anchors, requested appearance and PDF compatibility; export checks pass.
- Reference boundary mean error: **1.945 px**, p95 **4 px**.
- AI-render/PNG foreground IoU **0.997410**, p95 **1 px**. The two renderings are not byte/pixel-identical; agreement is close, not exact.
- Method review found literal anchor/handle lists, revised to shorter arc segments, with only coordinate mapping/replay. Circular-looking literals are not evidence of an executable parametric generator. No prohibited route/source was found.
- Background key delivery failed; foreground input worked. It recovered from missing session-bound screenshot context, an unsuccessful initial curve approximation, Color Picker UIA failure, and a Save dialog Invoke that did not close the dialog.
- Ctrl+Alt+E opened Export for Screens, not Export As. Menu invocation and pixel/scope failures led to keyboard-mnemonic navigation.

Original isolation, conduct and cleanup pass. The actor wrote temporary scripts/captures under `/tmp`, outside its workspace, despite the conduct check not listing them as outside writes. The heuristic pass is not exhaustive conduct proof. The shared CUA daemon remained available; no task sessions remained afterwards.

Raw task time: 658.99 s. Reviewed continuous endpoint: **651.87 s**. Wall time: 669.16 s.

## Measurement qualifications discovered in this round

Tracked in [issue #17](https://github.com/stanley50z/ahk-computer-use/issues/17). No timing-classifier fix was applied mid-round.

1. **Quoted runtime name creates a false endpoint.** Claude+CUA's last actual desktop/export call `toolu_01Lh321EJjkBws6CWB1quMiB` ended at **653.0760642 s**, after the actor started at **1.2030531 s**. The final call `toolu_018R93mmsA67yTR69c1v3ioo` only writes/validates result JSON, but its `input_method` text contains `cua-driver`, so the raw regex classifier extended timing to **660.1881939 s**. The corrected endpoint yields **651.8730111 s**. `timing-review.json` records the evidence; original metrics remain unchanged.
2. **Moved/imported wrappers undercount computer-use calls.** Pi+CUA moved `ui.py`/`pen.py` and other helpers into `workspace/evidence/` before grading. The classifier searches original root-level filenames and does not recursively resolve imports. Its raw **12 computer-use calls** is not an actual desktop-call count. The explicit final `cua-driver end_session` still fixes the last-call endpoint for that run, so the reported1284.31s is retained under the existing definition.

For this reason, runtime-call counts are not used for performance ranking here. Model response and all-tool request counts remain separate observable units:

| Attempt | Model responses | All tool requests | Raw computer-use classification |
| --- | ---: | ---: | ---: |
| Pi + ACU | 37 | 37 | 19 |
| Pi + CUA | 93 | 94 | 12, undercounts moved/imported wrappers |
| Pi + native, HTTP507 attempt | 54 | 56 | 50 |
| Pi + native, blocked retry | 27 | 29 | 22 |
| Claude + ACU | 30 | 33 | 20 |
| Claude + CUA | 68 | 68 | 47, includes the evidence-only false positive |

These are not actual ACU CLI execution counts or counts of individual clicks/drags. One shell call may execute several scripts or hundreds of desktop actions. Continuous timing includes all elapsed work from start to the selected endpoint, regardless of how many intermediate calls the heuristic recognizes.

## Cleanup and evidence

All **six** controllers finished. Captured owned actor process trees were stopped, all six task-started Illustrator PIDs exited, task documents closed, cursor schemes restored, private credential copies removed, and the benchmark active lock released. No temporary server or localhost port was started. No task-specific CUA sessions remained after either CUA trial. Unrelated applications and pre-existing documents were preserved by the cleanup policy; broader conduct remains limited as described above.

Raw run directories resolve under:

`C:\Users\13982\ahk-computer-use\.pi\bench\`

They retain plans, frozen prompts, raw events/transcripts, metrics, input/output files, native inspection, isolation/conduct when reached, worker/capture state, observer logs, cleanup and crash evidence. Original machine verification records still require method/consistency review and have no calibrated shape pass; independent read-only reviews supply the method conclusions in this report without rewriting those records.

Additional persistent evidence:

- `.pi/illustrator-five-arm/preflight.log` and `20261011T195048Z/manifest.json`: expected profiles and frozen source/asset hashes.
- `.pi/illustrator-five-arm/results.log` and `20261011T195048Z/results.json`: raw values and source/cleanup verification.
- `.pi/illustrator-five-arm/claude-artifact-review.log` and round-local `claude-acu-artifact-review/verification-forensic.json`: explicitly separate repaired-copy artifact inspection.
- `.pi/illustrator-five-arm/timing-tail.log`, `timing-review.log` and round-local `timing-review.json`: endpoint correction evidence.
- `.pi/illustrator-five-arm/pi-cua-sessions-after.json` / `claude-cua-sessions-after.json`: no active sessions after each CUA trial.
- ACU log: `%LOCALAPPDATA%\ACU\logs\runs.jsonl`; stack/crash reports: `%LOCALAPPDATA%\ACU\crashes\`.
- Per-run native approval decisions: `native-approvals.jsonl`; worker errors: `crash.txt` / `worker.log`; observer results/logs retain native failure details.

A progress-monitor stdout encoding failure occurred during Pi+CUA polling. It affected only the parent's display and was avoided with explicit UTF-8; it did not interrupt the actor or its raw event capture.

## Interpretation

The new experiment answers the requested comparison more narrowly and more usefully than the previous four-arm run:

- With **Pi + Astra held fixed**, ACU and CUA both completed. ACU was substantially quicker in this single trial and produced the closer contour. Native computer use was available in Pi, but one attempt hit a provider error and the retry stopped on drawing/tool-state recovery.
- With **Claude Code + Opus held fixed**, both runtimes produced the artwork. CUA submitted a valid manifest; ACU did not. ACU's artifact-generation time and higher contour score do not erase its submission failure.
- Runtime/harness/model are not the only changing influences across independent agents. Different chosen coordinates, planning, repairs, screenshot cadence and app state contribute. Repeated trials are needed before a general performance claim.

Specification and configuration: [issue #15](https://github.com/stanley50z/ahk-computer-use/issues/15), [integration report](benchmark-five-arm-integration-2026-10-11.md). Historical GPT-6.1 results remain unchanged and are not pooled with these Astra trials. This report is uncommitted; no commit/push was requested for the run.
