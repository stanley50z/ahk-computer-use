# Computer-use test bench

The benchmarks are **Calculator** (`calculator`, the default) and **Adobe Illustrator Pen and Export** (`illustrator-pen-export`). Each benchmark compares the five configurations below. An individual configuration is an arm; a request to run a benchmark means fresh sequential trials of all five arms unless the user explicitly selects a subset.

Historical reports call these "Testbench 1" and "Testbench 2" (or "TB2"). Those are historical aliases, not current CLI identifiers; `--scenario testbench-2` is no longer accepted. Report titles and prose use the descriptive names; report filenames, recorded trial IDs, evidence paths and measurements retain their historical values. Saved trial evidence is unchanged. The Illustrator rename changes its human-readable heading and scenario identifier, not the v0.3 actor prompt body or input-file bytes.

## File structure

```text
bench/
├── README.md
├── __init__.py
├── run.py                         Shared controller, profiles, timing and audits
├── start.py                       Background trial entry point
├── stop.py                        Cancellation and cleanup acknowledgement
├── processes.py                   Owned child-process lifecycle
├── native_mcp.py                  Codex computer-use app-approval MCP adapter
├── probe.ahk                      Shared desktop/window observer
├── restore_cursor.ahk             Shared post-trial cursor restoration
├── calculator/
│   ├── verify.ahk                 Calculator display verification
│   └── cleanup.ahk                Owned Calculator window cleanup
├── illustrator_pen_export.py      Illustrator preparation, grading and cleanup
├── illustrator/                   Maintainer-only application automation
│   ├── ensure.ahk
│   ├── input-state.ahk
│   ├── window.ahk                  Initial primary-monitor maximization
│   ├── prepare-export.ahk          Retained manual PNG-dialog calibration tool (not run by trials/tests)
│   ├── run-jsx.ahk
│   ├── observer.jsx
│   ├── dismiss-dialogs.ahk
│   └── close.ahk
├── scenarios/                     Actor task prompts
│   ├── calculator.md
│   └── illustrator-pen-export.md
└── assets/
    └── illustrator-pen-export/    Blank AI, reference PNG and provenance notes
```

Shared trial machinery stays at the root; application-specific AHK/JSX scripts live in their application folder. `illustrator_pen_export.py` coordinates those scripts and checks the drawing and maintainer-rendered evidence. Maintainer observers run outside actor timing and are not tools available to the actor.

Generated transcripts, screenshots, metrics, logs and crash reports belong in `.pi/bench/<run-id>/`, not here. Written comparison reports live in `docs/reports/`.

## Comparison configurations

Compare five fresh configurations, grouped by a fixed model and harness. Compare ACU, CUA and Codex computer use within Pi; compare ACU and CUA within Claude Code. Do not use a knowledgeable parent session as the actor:

| Arm | Harness / model | Only computer-use skill/runtime |
| --- | --- | --- |
| `pi-acu` | Pi / GPT-6 Astra, low reasoning | Project ACU skill and CLI |
| `pi-cua` | Pi / GPT-6 Astra, low reasoning | Installed `cua-driver` skill and CLI |
| `pi-computer-use` | Pi / GPT-6 Astra, low reasoning | Codex computer use: installed `computer-use` skill and `@oai/sky` through `node_repl` MCP |
| `claude-acu` | Claude Code / Opus 5.5, low effort | Project ACU skill and CLI |
| `claude-cua` | Claude Code / Opus 5.5, low effort | Installed `cua-driver` skill and CLI |

The user selected **GPT-6 Astra (`openai-codex/gpt-6-astra`) at low reasoning** for all three Pi arms and retained **Opus 5.5 (`claude-opus-5-5`) at low effort** for Claude Code. The explicit legacy `openai-codex` provider replaces `openai` for new Pi profiles after the latter returned an OAuth refresh `invalid_grant` during a benchmark actor run. This is a requested provider choice, not an automatic fallback or a main-session authentication failure. Prepared plans record `provider`, and launch/isolation/aggregation reject the wrong provider; old cancelled profiles are not resumed or silently pooled. Model ID, low reasoning, task and computer-use runtimes are unchanged, but provider-specific model metadata/context limits may differ, so comparisons must retain the provider identity. This also supersedes the GPT-6.1/four-arm configuration for new trials; historical manifests and reports retain their original providers, models and arm names. The standalone `codex-computer-use` arm is no longer a launch option. Its archived events remain analysable; Pi now hosts the Codex computer-use runtime for the matched GPT comparison.

No automatic provider/model fallback or parent coaching. Standing desktop approval covers needed tests and fresh reruns. Preserve failed/interrupted attempts separately from completed task timings. Existing prompts/assets, correctness checks, isolation and owned-resource cleanup remain unchanged. The measurement policy below supersedes elapsed task-time ranking.

[Five-profile integration validation](../docs/reports/benchmark-five-arm-integration-2026-10-11.md) records the Pi + Codex computer-use compatibility work and focused Calculator trials. These are integration checks, not a repeated performance study or a new Illustrator comparison.

Round 1 (2026-10-10, three arms) is in [its report](../docs/reports/testbench-1-2026-10-10.md); round 2 (all four arms, after the ACU changes) in [round 2](../docs/reports/testbench-1-round-2-2026-10-10.md); round 3 (in-script AcuTree/AcuScreenshot, Opus 5.5 on the Claude arm) in [round 3](../docs/reports/testbench-1-round-3-2026-10-10.md). Archived runs keep their original metrics; `analyse` prints a new-policy analysis from their original events without rewriting those files.

Specification: [issue #8](https://github.com/stanley50z/ahk-computer-use/issues/8). History: [first Calculator trials](../docs/reports/bench-calculator-2026-10-09.md). Comparison: [three-arm pilot and cursor incident](../docs/reports/computer-use-comparison-2026-10-09.md). Earlier ACU-only result: [CLI-only trial](../docs/reports/acu-cli-bench-2026-10-10.md). Round 1: [Calculator, three configurations](../docs/reports/testbench-1-2026-10-10.md). Time attribution and the subsequent overall-deadline removal: [latency analysis](../docs/reports/testbench-1-latency-2026-10-10.md). Latest complete benchmark: [scenario v1.1, all four configurations](../docs/reports/testbench-1-v1.1-2026-10-11.md). Earlier: [interim prompt](../docs/reports/testbench-1-v4-2026-10-11.md), and the last v1.0 run, [round 3](../docs/reports/testbench-1-round-3-2026-10-10.md).

The user reported an invisible cursor after the earlier comparison. The latest complete Calculator benchmark exercised identity-checked window/process cleanup and saved cursor-scheme restoration after all three arms. CUA's task-specific named CLI lifecycle was additionally ended explicitly outside timing; the shared daemon was preserved. The cursor check remains an OS showing-flag check, not pixel-level visibility proof, and the earlier incident's precise cause is still unproven.

## Isolation

Each run gets a new workspace, config directory, session and evidence folder under `.pi/bench/`. No global settings or discovery links are modified.

- Pi disables discovered extensions, other skills, context files, prompt templates and themes. ACU/CUA arms also disable MCP; only the selected skill and `read,bash,edit,write` are enabled. The Codex computer-use arm explicitly enables only `builtin:mcp`, one run-local `node_repl` server and its four direct tools, alongside those same file/shell tools. Codemode/tool search and other MCP servers remain disabled. The isolated agent directory contains no `AGENTS.md`, `SYSTEM.md` or `APPEND_SYSTEM.md`. Cache warming is off; normal within-session retry and compaction are enabled. Pi profiles freeze three transient-response retries with 2/4/8-second backoff (60-second cap), provider-level retries at zero, and automatic compaction with the normal 16384 reserve/20000 recent-token budgets. Provider-side prompt caching still occurs and is measured. `plan.json::recovery_policy` records these settings; Claude Code keeps its native default recovery behavior.
- Claude Code runs with a fresh `CLAUDE_CONFIG_DIR`, `--safe-mode` (no CLAUDE.md, skills, hooks, plugins or MCP), `--disable-slash-commands`, `--strict-mcp-config`, user-only setting sources, and exactly `Read,Write,Edit,Bash`. Only the selected ACU or CUA skill is declared by path in an appended system prompt. The stream's init event is audited for model, tools, MCP servers and skills, and the persisted transcript for effort, model and skill reads; the stream lists no memory files, so the CLAUDE.md exclusion rests on the flag. Claude Code's Bash tool uses Git Bash on Windows, like Pi.
- Pi + Codex computer use reuses the installed vendor `node_repl` executable, `@oai/sky` service and unmodified skill. Only `sky` is trusted; browser backends are disabled. Its fresh run-local `CODEX_HOME` is for the Codex computer-use runtime, not a Codex actor. The supported `--disable-sandbox` server flag matches the former Codex CLI arm's explicit full-access mode; without it the standalone MCP kernel returns `spawn EPERM` launching the helper. Pi lacks MCP form elicitation, so `native_mcp.py` forwards tool traffic unchanged and answers only recognized low-risk app-use approvals on the scenario's exact app allowlist, under standing user authorization. Unknown apps, URL elicitations, high-risk/audio and unrelated requests are declined. Decisions go to `native-approvals.jsonl`; crashes to `native-approvals.crash.txt`. This adapter and its overhead are part of the measured profile. It never implements or replaces the desktop helper protocol.
- Saved login credentials (Pi `auth.json` and Claude Code `.credentials.json`) are copied into the private config only while running, then deleted in `finally`. Pi uses the selected provider's credential from that private file; switching the benchmark provider does not change the main session's provider or global defaults. `pi auth check --provider openai-codex --model gpt-6-astra --json --no-refresh` reports readiness without printing credential values; never use credential-output flags in benchmark logs. Do not commit or share a run directory while a run is active. Commands and manifests contain credential paths, never credential values.
- This is **configuration and prompt isolation, not an OS security sandbox**. The shell is capable of arbitrary commands; method compliance also needs transcript/script review. The desktop remains shared. Run one controller at a time on an idle desktop.

Installed versions at initial setup: Pi 1.1.0; Codex CLI 0.162.0; cua-driver 0.34.0; Codex computer-use skill build 26.901.51231; Claude Code 2.1.295 when the `claude-acu` arm was added. ACU source was `eae5264`. Plans save the exact selected skill path, skill SHA-256, scenario SHA-256, launch command and configuration paths.

## Calculator

Scenario **v1.1** (2026-10-11, by the user's decision) is the task plus the result file, with every safeguard sentence removed. The actor receives exactly:

```text
Open a new Windows Calculator window and calculate:

98765 * 432 / 1234 * 56 / 789 + 6543 - 4321

When done, write result.json in the workspace with these fields: observed_result (the displayed text), observed_expression, input_method, and hiccups (an array of concrete problems encountered).
```

The answer with normal precedence is 4676.0458…; left-to-right evaluation gives a different number, which is how a mode mistake shows. The file's first line is its title and version for people; `prepare` sends only the body and writes the exact text to `prompt.txt` in the run directory, with `prompt_sha256` and `scenario_version` in `plan.json`. Nothing is said about input routes, skill reading, ownership files, preserving other windows, or leaving the window open: whether an actor needs those guards is unknown, so none is added back without the user's approval. Instead the bench runs a **conduct audit** around every trial and records it in `conduct.json`: a SHA-256 fingerprint of `acu/`, `bench/`, `tests/`, the READMEs and the arm's installed skill directory, taken before and after, so any edit to the skill or tool is caught whatever route made it; the transcript's write/edit tool calls, which must stay inside the workspace, plus a heuristic list of shell commands pairing a write verb with an outside path; and a window diff, flagging pre-existing visible windows that vanished and new non-Calculator windows left open. Changed guarded files or a Calculator write tool call outside the workspace fail the trial (`conduct_passed` in `summary.json`). Window-handle changes are diagnostic only (`window_audit_policy: diagnostic-only-v1`), as is the heuristic command list: Explorer restarts and transient overlays do not fail a trial. Window baselines remain necessary for identifying owned resources; identity-checked cleanup and protection of pre-existing documents are unchanged. This is detection after the fact, not prevention. The bench therefore finds the actor's window itself, the one visible Calculator that appeared during the trial, reads its display, and closes only that window; `result.json` is required, `ownership.json` is honoured when written. None or several new Calculator windows is an explicit failure, never a guess. The bench records which input routes each workspace script used in `verification.json` for the report; it does not fail a trial for any route.

Scripts remain in the actor's workspace. The independent observer runs **outside actor token/call measurements**, reads the actor's window (claimed, or the one new Calculator), captures it, and checks the display against a fixed reference. It uses the same observer for every arm; it is not an extra tool available to the actor.

Cleanup protects every pre-existing top-level handle, including hidden windows, and checks the independently observed native PID again before closing, and validates an actor-provided PID when present. It never kills a shared frame host. Unclaimed or ambiguous windows cause an explicit cleanup failure; they are not automatically closed. Windows agent descendants are contained in a job object before execution and terminated/verified even if their parent exits first. Broker-launched application windows are handled separately. `finished.json` distinguishes worker exit from successful cleanup. After owned controllers/windows stop, cleanup reloads the saved Windows cursor scheme and checks the OS showing flag. Cursor-restoration evidence is required; a cleanup exception also clears an overall-pass summary. The mitigation passed user-confirmed emergency recovery, quiet checks, and the latest complete Calculator benchmark. Before either CUA arm, the worker restarts the shared `cua-driver` daemon (`stop`, then `autostart kick`) outside actor timing and records `daemon-restart.json`, by the user's decision on 2026-10-10: the daemon remembers ended session labels, every fresh actor had named its first session after the scenario, and each trial after the first paid a rejected call of 4 to 11 s. After a CUA arm, also end only its newly created named CLI lifecycle outside actor timing, checking the public result; the worker does not automatically end daemon-backed CLI sessions. No other shared service is stopped. These cleanup checks are not a visual guarantee.

Versions: **v1.0** is the button-only prompt that rounds 1 to 3 used, with the expression `128+465*12387/138473-12343` and the evidence-file protocol in the prompt (its 2026-10-09 drafts tightened ownership and then allowed semantic Invoke alongside pointer clicks; the archived run directories keep each draft and its hash). A one-round interim text that listed allowed input routes, and whose title line "Calculator buttons" was sent to the actors, is recorded in [its report](../docs/reports/testbench-1-v4-2026-10-11.md) and superseded. **v1.1** is the two-line task above with a new expression. Comparisons across versions are across prompts and expressions. Preserve original verdicts and prompt hashes; this is not an exact-prompt statistical comparison.

## Adobe Illustrator Pen and Export

Use `--scenario illustrator-pen-export`. The identifier and benchmark heading remain stable, but the [v0.11 actor task](scenarios/illustrator-pen-export.md) is **Pen drawing only**. The actor recreates the reference with genuine Pen-tool Bézier curves, fill #00AEEF and no stroke, then leaves the finished document open. No actor export, AI save or result manifest is requested. The separate Curvature Tool is not the requested tool. Short straight-line segments approximating reference curves are prohibited. By the user's selected simpler direction, v0.11 states the drawing task and required appearance without a blanket other-tool/command ban. Undo, ordinary editing/recovery and zoom/panning are not separately prohibited. The shape must still be Pen-created with genuine Bézier handles, and every Illustrator interaction must use the assigned computer-use runtime. The no-stroke instruction remains beside the fill-color requirement. Window-handle changes are diagnostic only, not pass/fail inputs. These changes apply equally to all five configurations and do not retroactively change earlier verdicts.

The blank starter and separate 800 × 800 reference PNG remain the only inputs. Provenance, official vectors and maintainer inspection stay outside actor context. [Asset notes](assets/illustrator-pen-export/README.md) freeze the lossless reference transform and hashes. Workspace and Scratch folder paths are rendered into the prompt; there is no actor Final output path. Bench-authored references beneath the current user's home use `~/...`, not a literal account directory. Claude Code's selected-skill declaration uses the same home-relative form. The controller derives the home from `Path.home()` and the checkout from its source location, so neither is tied to a username. Paths outside the home retain their supplied location because they have no home-relative equivalent. Internal launch/configuration paths and private evidence remain resolved; harness-generated context or tool output can still expose absolute paths, so this is not blanket provider-side path redaction. Off-app analysis/code/generated geometry and external scratch remain allowed. Normal GUI revisions, smoothing, redraws and navigation are permitted; the v0.9/v0.10 blanket Pen-and-appearance-only command restriction is superseded. Pen construction, genuine curves, assigned-runtime interaction and final appearance remain the task requirements. Every Illustrator interaction must still use the assigned computer-use runtime; no benchmark recipes are added to ACU or vendor skills.

After the actor stops, the controller audits its conduct **before** maintainer export/close actions. Cleanup binds exactly one independently owned live document, inspects its actual path anchors/direction handles, and exports that drawing **as-is** through maintainer-only native Illustrator scripting. It never reopens a saved copy, alters geometry/fill/curves, imports a replacement, changes the artboard or resizes/composites the image. The `plan.json::export_policy` freezes two export attempts, artifact ownership/path and PNG properties; a modified policy or ambiguous/foreign document is an explicit refusal.

The output is maintainer evidence at `grading/Cloud9-Recreated.png`, not a submitted actor workspace file. Export uses artboard clipping, 100% scale, anti-aliasing, opaque white matte and non-interlaced PNG. A lossless Pillow encoding pass sets 72-ppi metadata and verifies unchanged RGBA pixel bytes; it does not repair a drawing. Cleanup verifies the PNG before closing the document. All inspection/export/encoding/retry work is outside actor token/call measurements. Numeric IoU and boundary errors remain unaligned post-run observations without a quality pass threshold.

`drawing-verification.json` and `verification.json` record drawing checks and full native control-point evidence. Noncollinear Bézier segments are counted; an all-straight drawing fails. **Full-session review must still reject faceted approximations of reference curves in mixed paths**: one curved segment is not proof that every reference curve meets the prompt. No arbitrary anchor-count or curved-segment-ratio threshold is imposed. `native_checks`, `rendered_checks` and `assessment_source` label where drawing evidence came from; their combined appearance verdict is separate from format/export checks. A wrong-fill or straight-segment drawing is still exported unchanged as failure evidence; it is not reclassified as a broken exporter.

`export.json` retains every export attempt, format checks, `appearance_checks` and the verified artifact; `drawing-verification.json` labels native/rendered evidence and carries the drawing verdict. Unsupported native fill representations remain unknown until rendering, rather than imposing a new RGB-only color-type rule. Hidden or off-artboard working references are not final drawing content. A missing/invalid export after at most two attempts becomes `infrastructure-failure.json` (`maintainer_export_failure`), separately from `drawing_passed` and provider/safeguard failures. Drawing/pixel/reference integrity refusals stop immediately, retain their stack and never retry against changed evidence; the controller also never re-enters an already-refused collection from its `finally` block. It excludes the slot from comparison averages without pretending the actor failed to draw. Collection refusals before the export loop are recorded as `maintainer_collection_failure`, not invented actor conduct. Cleanup restores PNG preferences/cursor state but preserves the unexported drawing and reports `passed:false`, so the next trial must pause until that owned-resource situation is resolved. Never silently synthesize an artifact, destroy an unexported drawing or replace the slot. If no owned drawing was left open at all, record a missing-drawing task failure rather than reopening the blank starter or inventing an exporter failure.

Preparation establishes a common blank document, primary-monitor maximized window, centered 100% view, English input, and enabled **Smart Guides** and **Snap to Point** before every trial. Setup sets and reads back those two preferences rather than blindly toggling shortcuts; failure to enable either stops preparation. `illustrator-prepared.json::snapping` records the verified starting state. Snap to Grid and Snap to Pixel are not changed. Actors remain free to change snapping during their trial; no snapping instructions are added to the actor prompt or skill. Cleanup does not re-enable snapping; the next trial's setup does. `illustrator-window.json` and `observer-window.log` record initial geometry. Normalization runs before actor startup only; it does not force the actor to retain maximization. The [first v0.7 resize diagnosis](../docs/reports/illustrator-window-resize-v07-2026-10-13.md) proves the 02:19 recording transition was an actor-authored `WinRestore` / `WinMove(0,0,1600,1000)` command, not failed initial maximization. The actor's more specific motivation is not established. No ACU/DPI fix or new window-size constraint was introduced.

Normal preparation does not perform a blank calibration export or preset PNG preferences. `prepare-export.ahk` remains an explicit manual PNG-dialog calibration tool; normal trials and focused fixture tests do not call it. Original preferences are snapshotted and restored even when export fails. Cleanup still protects all pre-existing documents, windows and application instances, closes only owned resources and restores the saved cursor scheme. The real desktop-marked fixture now checks an unsaved Pen-created curve, as-is export, a failed destination followed by retry, PNG properties, protected ownerless Color Picker refusal/cancellation and owned teardown; it does not require an actor-style save/export or duplicate GUI calibration.

The earlier rule that cleanup must never advance an actor deliverable is superseded **only for this maintainer-owned as-is export**, by explicit user confirmation in [issue #23](https://github.com/stanley50z/ahk-computer-use/issues/23). All other repair/coaching prohibitions remain. Cleanup recognizes the ownerless Color Picker from [#14](https://github.com/stanley50z/ahk-computer-use/issues/14) only in the exact Illustrator PID, with standard class/title, an enabled new handle absent from the baseline and unique OK/Cancel/Color Swatches controls; it invokes only Cancel, preserving protected or ambiguous dialogs. Fixture evidence remains under `.pi/illustrator-pen-export-validation/native-check-*/`.

Historical v0.10 and older prompts, artifacts, verdicts and measurements remain unchanged and are never pooled or silently regraded under v0.11. The compact summary separates drawing completion, maintainer infrastructure failure, output image/quality and safeguard violations; detailed logs remain debugging evidence, not actor obligations.

### Neutral skill policy

ACU skills/prompts must not contain Illustrator-, Pen-tool-, or benchmark-specific recipes, menu shortcuts, geometry advice or solutions. General input, focus, popup and sparse professional-application UI-tree guidance is allowed. Earlier runs used application-specific skill guidance; they remain historical development evidence, **not a neutral baseline**. New prompt and skill hashes identify this reset.

### Three trials per configuration

A full round is exactly **15 trials: three for each of the five configurations**, regardless of success. No replacement/restart trials are added to fill failed or interrupted slots. Normal provider retries and compaction continue inside that same scheduled session, not as extra trials. This supersedes the earlier five-trial/conditional-trimming policy for new rounds; historical results are unchanged.

- Average **every successful trial**. Never drop the lowest/highest token runs or the best/worst images.
- Use the same successful cohort for every metric: three successes means an average of three, two means two, one means one.
- Failed and interrupted trials remain in the evidence but are excluded from averages. With zero successes, there is no aggregate.
- Missing metric values remain unknown; do not substitute zero or silently use different subsets per metric. Unknown tokens do not prevent reporting another metric that is complete for the whole successful cohort.
- Code share is descriptive. It is never used to declare success or select which runs to keep.

`bench/aggregate.py` is offline and never launches/retries a trial. Its maintainer-authored manifest has an `attempts` array of 15 entries, in original trial order. Each entry contains a `run_dir` (absolute or relative to the manifest) and an explicit `safeguard_violations` array from session review; `[]` means no reviewed violation. This JSON is controller bookkeeping, **not a deliverable requested from the actor**. Recorded or reviewed violations exclude that attempt from averages.

```bash
uv run python bench/aggregate.py ".pi/rounds/round.json" > ".pi/rounds/aggregate.json"
```

The extractor requires finished v0.11 simple drawing-and-appearance runs with the diagnostic-only window audit policy stamped `benchmark-neutral-v1`, matching prompt templates/assets, matched models/reasoning within each harness, the explicit `openai-codex` provider for Pi, and matched skill/policy within each configuration. `prompt-template.txt` and `prompt_template_sha256` freeze the shared text; `prompt.txt` and `prompt_sha256` freeze its exact per-run path expansion. The extractor validates both hashes and the expansion, so different workspace locations are allowed but different instructions are not. The expansion uses the same current-user-root renderer as preparation, and ownership/skill-read audits resolve `~` before comparing paths. Historical protocols, including v0.4/v0.5/v0.6/v0.7/v0.8/v0.9/v0.10, are rejected even when their hashes match one another. Recovery policy must match the current normal-session settings; disabled-recovery profiles cannot be mixed into the cohort. Plans must also match the maintainer export policy, empty actor-deliverable list and three-trial/all-successes policy; stale five-trial profiles are rejected. It validates the canonical maintainer output path, preserves raw evidence and lists failed/retained slots and separate `infrastructure_failure_ids`, without trimming. `attempts`, `failures` and `failed_ids` retain their scheduled-slot meaning (including provider/infra/safety interruptions), not an actor-failure score; report infrastructure separately rather than charging it to the actor. Errors persist beside the manifest as `*.aggregate-crash.txt`.

Terminal provider-response errors are **unexpected provider failures**, not evidence that the model, harness or desktop runtime cannot perform the task. Pi first uses its normal retry/compaction recovery within the same session and desktop state. Earlier errors remain in raw history and `model_errors`; a later successful response moves them to `recovered_provider_errors` instead of poisoning task completion. The controller never restarts the task, switches provider/model or replaces the slot. Only unrecovered terminal provider errors produce `unexpected_failure` and `failure.json`, persisted before verification/cleanup so later observer failure cannot hide the cause. Cancellation (including host stop during backoff) and generic compaction failure are tracked separately. Pi completion requires a final successful stop response and `agent_settled`; intermediate `agent_end` or tool-use responses do not establish completion. Claude Code completion uses its final successful result, so earlier recovered stream errors do not poison it either. Aggregation exposes recovered errors and lists terminal `unexpected_failure_ids` separately. The existing `failures` count means unsuccessful slots of any cause, not a runtime fault count.

Reported compaction usage is included once from `compaction_end.result.usage`; intermediate stream/native copies are not counted again. Retry/compaction events remain in `metrics.json::recovery_events`. A successfully recovered task can pass with incomplete API consumption: unreported failed-request or summary usage remains unknown, not zero, and withholds that successful cohort's affected API/code-share averages. Complete computer-use spans and image quality may still be averaged over the same full cohort. Model-rate diagnostics are withheld when compaction provider timing is not exposed.

**No new trial starts automatically after a prompt change.** v0.11's simpler no-stroke task and diagnostic-only window policy are a new protocol revision; no actor trial has started under it. The completed [v0.9 full round](../docs/reports/illustrator-pen-export-v09-round-2026-10-14.md) retains its original records: all 15 drawings retained strokes, and ten failed the existing white-background proxy. Native no-stroke validation is distinct from that proxy; adding the prompt sentence does not silently change the grader or historical outcomes. v0.8's drawing/export infrastructure retains its focused offline and real Illustrator fixture validation. A fresh full round requires a new user request. See [v0.8 scope, issue #23](https://github.com/stanley50z/ahk-computer-use/issues/23), [v0.7 scope, issue #22](https://github.com/stanley50z/ahk-computer-use/issues/22), and the [completed v0.7 round](../docs/reports/illustrator-pen-export-v07-round-2026-10-13.md). The metric/recovery policy, five configurations, three scheduled trials each, all-successes aggregation, assets and neutral skills are unchanged; actor export and the prior PNG-only deliverable are replaced by drawing-only completion and maintainer artifact collection.

## Commands

Install the benchmark dependencies once with `uv sync` in the checkout. The `start.py` and `run.py` CLIs select this checkout's `.venv` Python, even when invoked with system `python`. They verify `tiktoken` and Pillow before preparing a trial or launching its worker. Help and desktop-approval checks still run before environment selection. A missing environment or dependency stops with an explicit `uv sync --project` instruction; the bench does not install packages automatically or fall back to system Python. `stop.py` remains dependency-light so cancellation does not need the benchmark environment.

Offline preparation only; no credentials copied and no desktop operation:

```bash
python bench/run.py prepare --arm pi-acu
python bench/run.py prepare --arm claude-acu
python bench/run.py prepare --arm pi-cua
python bench/run.py prepare --arm pi-computer-use
python bench/run.py prepare --arm claude-cua
```

With desktop authorization (the current Illustrator benchmark work has standing approval), start in the background without opening another terminal:

```bash
python bench/start.py --arm pi-acu --desktop-approved
```

Replace the arm only when the corresponding task/run is authorized. `start.py` prints the run directory and worker PID. For `pi-computer-use`, `--native-transport app-pipe` uses the running ChatGPT/Codex desktop app's own computer-use pipe instead of the shipped SDK helper; the worker refuses to start if that pipe is not open. The default remains the SDK helper. There is no overall actor time limit. Stop a stalled or unwanted run explicitly with `stop.py`; per-script watchdogs and backend request/startup timeouts remain separate protections. A run directory is never reused for another trial.

Stop only that run, allowing its worker to terminate owned processes and perform cleanup:

```bash
python bench/stop.py "C:/path/to/the/run-directory"
```

Synchronous equivalent:

```bash
python bench/run.py run --arm pi-acu --desktop-approved
```

No benchmark server or new fixed localhost port is required. Existing CUA/Codex host services are not stopped by this bench.

## Benchmark measurements

The comparison policy is **tokens-and-computer-use-v1**, by the user's decision. End-to-end task time, provider response time and tokens-per-second estimates are **not benchmark ranking metrics**. Old reports retain their original measurements; raw process/response timestamps remain diagnostic evidence.

Report these values for each task attempt, alongside correctness and quality:

1. **Total API tokens:** cumulative input + cache reads/writes + output, using the harness's recorded usage. Show the breakdown. Reasoning is already included in output and must not be added twice. This is token consumption, not money or final context length.
2. **Computer-use code share:** estimated tokens in generated computer-use code/arguments divided by **recorded output tokens including reasoning**, multiplied by 100. Use only code payloads, not all tokens of responses that happened to invoke a tool. Input/context tokens are not the denominator.
3. **Computer-use call duration:** request-to-result duration for every identified execution call; report both their sum and their busy-time union so overlapping calls are not double-counted. Model-response latency is outside these intervals.

`metrics.json` and `summary.json` expose these under `benchmark`. New summaries no longer use `task_s`; their process wall time is explicitly diagnostic. `plan.json` freezes the policy name. Source is `bench/efficiency.py`.

### Attribution and its limits

The numerator uses the fixed **tiktoken / o200k_base reference encoding**, with tokenizer version recorded. It is an estimate, not a claim to match Astra's or Opus's billing tokenizer. Model/tokenizer differences limit precision. A higher code share does not automatically mean better work: bloated or failed code can have a high share.

Attribution uses captured structured tool arguments. It follows applied Write/Edit source (failed mutations never alter replayed state), shell heredocs and script edits, Python imports and literal nested subprocess/helper prefixes, shell helper invocations, and persistent Codex computer-use JavaScript helpers. Shell substitutions, loop/condition bodies and environment assignments preserve their actual command prefixes. Captured literal Path/open copies with string replacements and literal sed substitutions preserve source provenance without reading final workspace files or executing actor code. Moving/deleting a helper after execution does not erase its provenance. Unsupported wrappers or source mutations remain explicit review gaps; unresolved mutations invalidate cached source rather than attributing a stale helper.

- A source payload is counted once when identified calls use it, even if the script runs repeatedly. Newly re-emitted source and edits still consume generated tokens; old edit-match text is not counted as newly generated code.
- Read results, reasoning, prose/final answers, and standalone result-file writes are excluded. Mentioning `cua-driver` in a result JSON string does not make that write a computer-use call.
- Mixed shell/code invocation payloads are counted as a unit, including their inline script creation and ancillary code. Their execution durations likewise include shell/setup/inspection overhead. These are **top-level tool-call durations**, not isolated mouse-event latency or runtime CPU time.
- Static attribution is reviewable, not a general interpreter or instruction-level execution trace. Unsupported/ambiguous forms carry review notes and withhold the percentage; known token/span totals remain available as partial evidence. Inspect the token payload ledger and selected call IDs before making close comparisons.
- Incomplete/unknown output usage produces no percentage, not zero. Interrupted requests may have unreported tokens; recorded totals then describe only known usage. Unfinished tool spans are marked incomplete.
- Failed/blocked attempts remain failed/blocked. Lower tokens or shorter call durations cannot turn them into successful completions.

The code-token ledger retains source call IDs, token estimates, text lengths and hashes. The call ledger retains each selected request/result span and error indication. Actual ACU script launches and CUA subprocess invocations can be batched inside one host tool call; do not confuse these units.

### Reanalyse without rerunning the desktop

Install the project dev dependencies with `uv sync`, then:

```bash
uv run python bench/run.py analyse --run-dir "C:/path/to/run" > "C:/path/to/new-analysis.json"
```

This regenerates the new measurements from original events and does **not** overwrite the saved `metrics.json` or historical verdicts. Additive reanalysis of the five v0.8 trials resolves the source/helper attribution gaps. Under the default all-request policy, Pi CUA's unreported interrupted-request usage remains a lower bound, with no invented code-share denominator. See [v0.8 results](../docs/reports/illustrator-pen-export-v08-one-success-2026-10-13.html). The old `--reference-tps` CLI normalization is removed. Archived Codex CLI events remain readable as historical evidence.

For the user's requested Pi CUA exclusion, use `analyse --exclude-interrupted-turns`. This opt-in offline mode excludes assistant responses with error/aborted stop reasons from counted token usage and `model_turns`, retains them in `excluded_model_turns`, and preserves raw errors and recovery evidence. Its policy is `tokens-and-computer-use-excluding-interrupted-turns-v1`, not the default all-request policy. `token_counts_complete` then describes the counted cohort; `full_request_consumption_complete` remains false when a response was excluded. Do not label these counts as total request consumption or silently mix their policy with all-request cohorts. Missing usage in a retained successful compaction still remains unknown. Exclusion is supported only for Pi's per-response usage, not other harnesses' aggregate totals, and cannot be used with `prepare` or `run`.

```bash
uv run python bench/run.py analyse --run-dir "C:/path/to/pi-run" --exclude-interrupted-turns > "C:/path/to/counted-analysis.json"
```

For the current Pi CUA trial, one interrupted response is excluded: counted API tokens are 9,915,655 and estimated code/output share is 28.80%. All 61 actual computer-use execution calls remain counted; the interrupted response dispatched no execution calls. Original trial metrics/events/PNG and the default all-request report are preserved.

See [token/call-time policy and replay results](../docs/reports/benchmark-token-policy-2026-10-11.md) for the recorded Illustrator attempts under this policy.

## Evidence and debugging

ACU's per-script cursor-position and foreground restoration was removed after the archived Calculator benchmark runs, by [issue #11](https://github.com/stanley50z/ahk-computer-use/issues/11). New scripts leave desktop state in place and prepare English input automatically. The bench's post-trial owned-resource cleanup and saved-cursor-scheme reload remain unchanged. Preserve the archived skill fingerprints and measurements rather than treating older trials as runs of the new runtime.

Every run preserves:

- `plan.json`, frozen `scenario.md`, `prompt-template.txt`, rendered `prompt.txt`, selected configuration and skill/scenario/template/rendered-prompt fingerprints;
- `stdout.jsonl`, `events.jsonl` with monotonic receipt timestamps, `stderr.log`, `session.jsonl` for Pi, the Claude Code transcript under `agent-home/projects/`, or archived Codex CLI rollouts under `agent-home/sessions/`;
- `metrics.json` and `summary.json` with `benchmark` token/code-share/call-duration ledgers, plus `isolation.json` and `verification.json`;
- `workspace/` with original actor scripts, ownership and result files;
- screenshots and `observer-*.log` outside actor timing;
- for Illustrator: `illustrator-prepared.json` with initial snapping read-back, `drawing-verification.json`, `export.json`, `grading/Cloud9-Recreated.png`, native/encoded attempt files and `export-attempt-*-crash.txt`; `infrastructure-failure.json` on exporter exhaustion;
- `state.json`, `launch.json`, `capture.json`, `cleanup.json`, `finished.json`;
- `worker.log`, `crash.txt` or `capture-crash.txt` with tracebacks on failure; `failure.json` for an observed terminal provider error, independent of later cleanup errors.

Interrupted runs retain raw events and report terminal failure. Usage for an unfinished model request can be unavailable; reported completed-message tokens are a lower bound, not a complete total. Evidence can contain screen content and should be treated as sensitive.

Environment/setup failures before a trial exists append their stack traces to `.pi/bench/runtime-preflight.log`. They do not create a trial directory, start an actor or touch the desktop. Once a trial starts, its normal per-run logs and crash reports above apply.

ACU also retains its normal runtime logs at `%LOCALAPPDATA%\ACU\logs\runs.jsonl` and crash reports at `%LOCALAPPDATA%\ACU\crashes\`.

Focused quiet checks:

```bash
python -m pytest tests/test_bench*.py -q
```

These tests exercise profiles, usage/timing, ownership checks, Codex computer-use audit parsing, cancellation and descendant cleanup using ordinary Python stand-ins. They do not launch AutoHotkey, open applications, or interact with the desktop. Real desktop evidence comes from explicitly approved trials, not a routine full integration suite.
