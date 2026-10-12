# Adobe Illustrator Pen and Export: first full four-configuration run

## Results

Ran fresh isolated Illustrator benchmark v0.3 actors sequentially on committed source `63ec02304c3155d107b526a500553848f27ad275`. All four requested configurations were exercised. Two completed and two reported blocked.

| Configuration | Model / reasoning | Outcome | Task time | Wall time | Computer-use calls | Reference IoU |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| Pi + ACU | GPT-6.1 / low | Completed; method reviewed | **338.71 s** | 381.61 s | 16 | **0.98554** |
| Claude Code + ACU | Opus 5.5 / low | Completed; method reviewed | **275.65 s** | 292.77 s | 12 | **0.98205** |
| Pi + CUA | GPT-6.1 / low | Blocked before artwork; observer cleanup needed recovery | 124.34 s attempt | 133.72 s | 7 | No output |
| Codex + native computer use | GPT-6.1 / low | Blocked after inconsistent Pen inputs | 459.25 s attempt | 487.95 s | 49 | No output |

**Failed-attempt times are not completion times.** Pi+CUA's shorter attempt is not a speed win. These are **one trial per configuration**, not medians, statistical evidence, or proof of universal backend capability/incapability. Claude+ACU was the faster completed trial; the Claude arm uses a different model, so this is not a runtime-only comparison.

The two completed runs saved editable AI and correct opaque white-background 800 × 800 PNG files. Independent method review found only hand-authored literal anchor/handle lists, coordinate conversion, and desktop Pen/Anchor Point editing. Neither used executable contour/parametric point generators, imports, hidden solution reads, actor Illustrator scripting, or raster substitution.

Numeric shape acceptance is still uncalibrated. Completed pilot verdicts remain `null` pending the existing acceptance calibration, not overall shape pass declarations.

## Fixed protocol and profiles

- Source commit: `63ec023`; no runtime/skill/source changes were made during these measured attempts.
- Illustrator benchmark v0.3 prompt SHA-256: `b6b38f65c7675f11b27fd94fa0fcbef75d38208c441a6914727ef97a6f3c254b`.
- Blank starter AI SHA-256: `d2197b639dd7c9d4528962f8252bdbb0e6d250551f16675324ea95e2e0d99445`.
- Separate JPEG SHA-256: `715a4a7e15cb0e5ecc3452ef53585971eb7cb9ca5e61334c10bf1de443333231`.
- ACU skill SHA-256, both ACU arms: `6da0c71eed43d96c3e349a61d1033876ed833a1691a767b603baec61cf9fbaeb`.
- CUA skill SHA-256: `020a1a68bef283354edf4a8dfe562af3a3a7b9130b919560aee395e1035bcc2f`.
- Native computer-use skill SHA-256: `8211e4b11a19a0dc4f0ace91096c74c5b36037ca4cb2c8988f0f535bb209e951` (installed native skill build `26.1007.21434`, as recorded in its plan).

Each actor received the same task and separate two-file input in a fresh workspace/config/session. The maintainer established the same blank Illustrator starting state, workspace/viewport/PNG options and English input before timing. Supporting actor actions, drawing, saving and export count continuously through the last computer-use result. No step subtraction, parent coaching or provider/model fallback occurred. The native arm used its configured SDK-helper transport.

Isolation audits pass for all four executed actors. Guarded-source fingerprints show no modification by the actors. As documented, this is configuration/prompt isolation, not an OS sandbox.

One earlier Pi+ACU **setup-only** attempt failed before actor launch: `20261011T150200Z-testbench-2-pi-acu-f85c0a` did not open the Other Script dialog immediately after Illustrator startup. Native recovery/cleanup succeeded and its task-started app exited. A fresh directory was used for the successful Pi+ACU trial. That setup failure has no actor/task timing and is not mixed into the results table.

## Completed ACU trials

### Pi + ACU

Run: `20261011T150351Z-testbench-2-pi-acu-199468`.

- Native inspection: one closed editable path, 34 anchors, requested fill/stroke/opacity and PDF compatibility.
- Reference boundary mean Manhattan distance: **0.484 px**, p95 **2 px**.
- Saved-AI render versus submitted PNG foreground IoU: **0.997459**, p95 **1 px**.
- PNG and manifest checks pass; original conduct and cleanup pass.
- Retained `workspace/finaldraw.ahk` contains literal coordinates; `pt()` only maps them to screen pixels. Alt-drag adjusts authored handles through normal desktop Pen operations.

Hiccups included a rejected Color Picker UIA value setter, uneven initial arc handles, a dropdown-triggered activation-loss guard, and export-dialog timing. After the guard rejected a main-window operation, the actor used untargeted native Send/Click in `finish2.ahk` without revalidating foreground. The subsequent tree showed the intended PNG dialog and no unrelated-app damage is evidenced, but this weakened focus protection; a passing conduct audit is not complete safety proof.

### Claude Code + ACU

Run: `20261011T151130Z-testbench-2-claude-acu-313e20`.

- Native inspection: one closed editable path, 32 anchors, requested appearance and PDF compatibility.
- Reference boundary mean Manhattan distance: **0.597 px**, p95 **2 px**.
- Saved-AI render versus submitted PNG foreground IoU: **0.997208**, p95 **1 px**.
- PNG/manifest/isolation/conduct/cleanup checks pass.
- Literal operation array in `pen.ahk`; only screen mapping/replay. Shift+C repair of the start anchor's existing authored handle is normal Anchor Point editing.

The start anchor's incoming handle collapsed on closure and needed repair. Appearance was selected after the first path inherited starter defaults. PNG anti-aliasing was corrected from Type Optimized to Art Optimized. The actor inspected a gridded reference rather than placing it. Deleted temporary scripts remain fully represented in captured tool arguments.

## Blocked Pi + CUA trial

Run: `20261011T151741Z-testbench-2-pi-cua-e86cd0`.

The actor reported blocked before creating artwork; no submitted AI/PNG exists. Captured failures are narrower than an unconditional claim that the backend cannot operate Illustrator:

- `double_click` rejected its exact-window target with `invalid_action_target` at **57.798 s** and **85.361 s**.
- Legacy targeting returned `screenshot_context_missing` at **68.077 s**; using the explicit `cloud9` session subsequently permitted clicks.
- Background input at **79.967 s** and **92.242 s** reported synthetic-event delivery with **effect=unverifiable**. That is not proof of no effect.
- A foreground retry failed at **101.536 s**, actual HWND `0x28040a`; the backend explicitly stated no mouse input was sent. The actor's JSON wrapper then threw `JSONDecodeError`.

### Missed Color Picker and cleanup gap

A maintainer read-only window inspection after the actor stopped identified actual foreground HWND `2622474` (`0x28040a`) as the **new Illustrator Color Picker**, PID `60468`, class `#32770`, **Win32 owner=0**. The main frame HWND `18877682` stayed enabled=1. The main-window capture did not show this separate picker; its presence contradicts a blanket "background clicks had no effect" conclusion.

The observer's recognized-dialog cleanup requires main-frame ownership, so it missed this ownerless picker. Both native verification snapshot and `finally` cleanup failed with "Illustrator did not activate." This is a **maintainer observer/cleanup defect**, separate from the actor's targeting/perception failures; tracked in [issue #14](https://github.com/stanley50z/ahk-computer-use/issues/14).

The actor ended its own `cloud9` session at **126.499 s**, with the public result `active:false`. Outside timing, the maintainer verified the new picker handle/PID/title, invoked its observed Cancel button, and then recovered native cleanup. `recovery-cleanup.json` confirms the known blank document and task-started application closed. Original failed `cleanup.json` and `finished.json` remain unchanged. The shared CUA daemon is preserved, not blanket-stopped after the trial.

## Blocked Codex native trial

Run: `20261011T152757Z-testbench-2-codex-computer-use-e6017d`.

The actor attempted permitted literal-coordinate Pen drawing but reported that repeated drag inputs created corners/straight segments instead of faithful Bezier handles. It did not save/export a completed AI/PNG.

Evidence includes:

- UIA `set_value` failed at **86.298 s**, `Member not found (0x80020003)`.
- Literal anchor/handle tuples were defined at **130.474 s**; later arithmetic only scales/translates coordinates.
- A state at **269.551 s** exposed popup-first screenshots; the next operation at **279.619 s** rejected a main-window caption point against **259 × 323** bounds.
- Actor attempts to use Shift+C selected Scissors instead of Anchor Point; a flyout interaction restored a smaller window and did not select the expected tool. Window bindings/screenshots were refreshed, but the actor remained blocked.
- Native observer snapshots show one unsaved page item, not an independently verified completed logo. No prohibited generator/import/hidden grading read/actor JSX or outside-workspace write appears in captured calls.

### Unresolved conduct flag

Original `conduct.json` flags disappeared pre-existing HWND `1773844` and new HWNDs `15339894` / `28320084`. Raw probes bind all three to **PID 23000**, class `Qt51514QWindowIcon`, not the trial's Illustrator PID `27212`. A read-only identity check identifies surviving windows as **Weixin.exe**.

There is insufficient causal evidence to attribute these changes to Codex, user activity or autonomous app behavior. The flag is **retained and unresolved**, not blamed on Codex or silently waived. These unrelated windows were not closed by the maintainer. Task document/application cleanup and cursor restoration succeeded.

## Usage and timing limits

| Configuration | Uncached input | Cache read | Cache write | Output incl. reasoning | Reasoning subset |
| --- | ---: | ---: | ---: | ---: | ---: |
| Pi + ACU | 48,318 | 532,224 | 0 | 4,972 | 1,038 |
| Claude + ACU | 40 | 642,326 | 52,305 | 21,462 | 13,440 |
| Pi + CUA, blocked | 43,438 | 581,120 | 0 | 1,695 | 128 |
| Codex native, blocked | Input incl. cache 2,943,604 | 2,861,824 | Not exposed | 9,493 | Not exposed |

These are cumulative API tokens across turns, not final context size. Reasoning is already included in output; do not add it twice. Native CLI provides aggregate usage but no authoritative per-response server duration, so no pure model-decoding speed comparison is claimed. Completed versus blocked usage describes different amounts of work.

## Evidence and cleanup

Run names above resolve under `C:\Users\13982\ahk-computer-use\.pi\bench\`.

Persistent round data: `C:\Users\13982\ahk-computer-use\.pi\tb2-full\`:

- `20261011T150159Z/preflight.json`: all four profiles and matching prompt/asset fingerprints.
- `results.json` / `results.log`: captured result table and verified final cleanup state.
- `look-cua.log`, `cua-picker-buttons.log`, `cancel-cua-picker.log`, `cua-recovery.log`: ownerless-picker diagnosis and recovery.
- `conduct-window-identities.log`: read-only Weixin identity evidence.

Each trial retains original plans, exact prompt, raw events/transcript, metrics, isolation, native/PNG verification, conduct, outputs, observer logs, worker/crash records and cleanup/finished records. Native error JSON includes stacks/lines. Independent read-only method audits reviewed full captured command strings, not just result claims.

All **five** run directories (four actors plus one setup-only failure) have finished worker records. Captured owned actor trees are stopped; all task-started Illustrator PIDs exited; the active benchmark lock is released. CUA session `cloud9` is ended, its shared daemon remains available, and unrelated applications are preserved. No test/dev server or fixed localhost port was started. No source code fix was applied to improve a measured actor mid-run.

ACU persistent runtime log: `%LOCALAPPDATA%\ACU\logs\runs.jsonl`. Stack/crash reports: `%LOCALAPPDATA%\ACU\crashes\`. Private credential copies exist only during execution and are removed afterwards; do not publish active run directories or saved login values.

## Follow-up

- Fix the independently reproduced ownerless Color Picker observer/cleanup gap in issue #14, with native-boundary regression coverage.
- Investigate CUA popup perception/targeting and Codex drag/modifier/popup behavior as separate controlled experiments. Do not infer universal inability from one blocked trial.
- Repeat all arms if a multi-trial comparison is wanted; preserve these first outcomes rather than selecting only successful retries.
- Calibrate numeric shape acceptance before giving overall benchmark pass/fail verdicts.

The report is new, uncommitted documentation; the measured implementation remained at `63ec023` throughout this round.
