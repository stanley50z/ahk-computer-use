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
│   ├── prepare-export.ahk          Explicit maintainer fixture check only
│   ├── run-jsx.ahk
│   ├── observer.jsx
│   ├── dismiss-dialogs.ahk
│   └── close.ahk
├── scenarios/                     Actor task prompts
│   ├── calculator.md
│   └── illustrator-pen-export.md
└── assets/
    └── illustrator-pen-export/    Blank AI, reference JPEG and provenance notes
```

Shared trial machinery stays at the root; application-specific AHK/JSX scripts live in their application folder. `illustrator_pen_export.py` coordinates those scripts and checks the submitted files. Maintainer observers run outside actor timing and are not tools available to the actor.

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

The user selected **GPT-6 Astra (`openai/gpt-6-astra`) at low reasoning** for the three Pi arms and retained **Opus 5.5 (`claude-opus-5-5`) at low effort** for Claude Code. This replaces the GPT-6.1/four-arm comparison for new trials; historical manifests and reports retain their original models and arm names. The standalone `codex-computer-use` arm is no longer a launch option. Its archived events remain analysable; Pi now hosts the Codex computer-use runtime for the matched GPT comparison.

No automatic provider/model fallback or parent coaching. Standing desktop approval covers needed tests and fresh reruns. Preserve failed/interrupted attempts separately from completed task timings. Existing prompts/assets, correctness checks, isolation and owned-resource cleanup remain unchanged. The measurement policy below supersedes elapsed task-time ranking.

[Five-profile integration validation](../docs/reports/benchmark-five-arm-integration-2026-10-11.md) records the Pi + Codex computer-use compatibility work and focused Calculator trials. These are integration checks, not a repeated performance study or a new Illustrator comparison.

Round 1 (2026-10-10, three arms) is in [its report](../docs/reports/testbench-1-2026-10-10.md); round 2 (all four arms, after the ACU changes) in [round 2](../docs/reports/testbench-1-round-2-2026-10-10.md); round 3 (in-script AcuTree/AcuScreenshot, Opus 5.5 on the Claude arm) in [round 3](../docs/reports/testbench-1-round-3-2026-10-10.md). Archived runs keep their original metrics; `analyse` prints a new-policy analysis from their original events without rewriting those files.

Specification: [issue #8](https://github.com/stanley50z/ahk-computer-use/issues/8). History: [first Calculator trials](../docs/reports/bench-calculator-2026-10-09.md). Comparison: [three-arm pilot and cursor incident](../docs/reports/computer-use-comparison-2026-10-09.md). Earlier ACU-only result: [CLI-only trial](../docs/reports/acu-cli-bench-2026-10-10.md). Round 1: [Calculator, three configurations](../docs/reports/testbench-1-2026-10-10.md). Time attribution and the subsequent overall-deadline removal: [latency analysis](../docs/reports/testbench-1-latency-2026-10-10.md). Latest complete benchmark: [scenario v1.1, all four configurations](../docs/reports/testbench-1-v1.1-2026-10-11.md). Earlier: [interim prompt](../docs/reports/testbench-1-v4-2026-10-11.md), and the last v1.0 run, [round 3](../docs/reports/testbench-1-round-3-2026-10-10.md).

The user reported an invisible cursor after the earlier comparison. The latest complete Calculator benchmark exercised identity-checked window/process cleanup and saved cursor-scheme restoration after all three arms. CUA's task-specific named CLI lifecycle was additionally ended explicitly outside timing; the shared daemon was preserved. The cursor check remains an OS showing-flag check, not pixel-level visibility proof, and the earlier incident's precise cause is still unproven.

## Isolation

Each run gets a new workspace, config directory, session and evidence folder under `.pi/bench/`. No global settings or discovery links are modified.

- Pi disables discovered extensions, other skills, context files, prompt templates and themes. ACU/CUA arms also disable MCP; only the selected skill and `read,bash,edit,write` are enabled. The Codex computer-use arm explicitly enables only `builtin:mcp`, one run-local `node_repl` server and its four direct tools, alongside those same file/shell tools. Codemode/tool search and other MCP servers remain disabled. The isolated agent directory contains no `AGENTS.md`, `SYSTEM.md` or `APPEND_SYSTEM.md`. Cache warming and automatic retry/compaction are off; provider-side prompt caching still occurs and is measured.
- Claude Code runs with a fresh `CLAUDE_CONFIG_DIR`, `--safe-mode` (no CLAUDE.md, skills, hooks, plugins or MCP), `--disable-slash-commands`, `--strict-mcp-config`, user-only setting sources, and exactly `Read,Write,Edit,Bash`. Only the selected ACU or CUA skill is declared by path in an appended system prompt. The stream's init event is audited for model, tools, MCP servers and skills, and the persisted transcript for effort, model and skill reads; the stream lists no memory files, so the CLAUDE.md exclusion rests on the flag. Claude Code's Bash tool uses Git Bash on Windows, like Pi.
- Pi + Codex computer use reuses the installed vendor `node_repl` executable, `@oai/sky` service and unmodified skill. Only `sky` is trusted; browser backends are disabled. Its fresh run-local `CODEX_HOME` is for the Codex computer-use runtime, not a Codex actor. The supported `--disable-sandbox` server flag matches the former Codex CLI arm's explicit full-access mode; without it the standalone MCP kernel returns `spawn EPERM` launching the helper. Pi lacks MCP form elicitation, so `native_mcp.py` forwards tool traffic unchanged and answers only recognized low-risk app-use approvals on the scenario's exact app allowlist, under standing user authorization. Unknown apps, URL elicitations, high-risk/audio and unrelated requests are declined. Decisions go to `native-approvals.jsonl`; crashes to `native-approvals.crash.txt`. This adapter and its overhead are part of the measured profile. It never implements or replaces the desktop helper protocol.
- Saved login credentials (Pi `auth.json` and Claude Code `.credentials.json`) are copied into the private config only while running, then deleted in `finally`. Do not commit or share a run directory while a run is active. Commands and manifests contain credential paths, never credential values.
- This is **configuration and prompt isolation, not an OS security sandbox**. The shell is capable of arbitrary commands; method compliance also needs transcript/script review. The desktop remains shared. Run one controller at a time on an idle desktop.

Installed versions at initial setup: Pi 1.1.0; Codex CLI 0.162.0; cua-driver 0.34.0; Codex computer-use skill build 26.901.51231; Claude Code 2.1.295 when the `claude-acu` arm was added. ACU source was `eae5264`. Plans save the exact selected skill path, skill SHA-256, scenario SHA-256, launch command and configuration paths.

## Calculator

Scenario **v1.1** (2026-10-11, by the user's decision) is the task plus the result file, with every safeguard sentence removed. The actor receives exactly:

```text
Open a new Windows Calculator window and calculate:

98765 * 432 / 1234 * 56 / 789 + 6543 - 4321

When done, write result.json in the workspace with these fields: observed_result (the displayed text), observed_expression, input_method, and hiccups (an array of concrete problems encountered).
```

The answer with normal precedence is 4676.0458…; left-to-right evaluation gives a different number, which is how a mode mistake shows. The file's first line is its title and version for people; `prepare` sends only the body and writes the exact text to `prompt.txt` in the run directory, with `prompt_sha256` and `scenario_version` in `plan.json`. Nothing is said about input routes, skill reading, ownership files, preserving other windows, or leaving the window open: whether an actor needs those guards is unknown, so none is added back without the user's approval. Instead the bench runs a **conduct audit** around every trial and records it in `conduct.json`: a SHA-256 fingerprint of `acu/`, `bench/`, `tests/`, the READMEs and the arm's installed skill directory, taken before and after, so any edit to the skill or tool is caught whatever route made it; the transcript's write/edit tool calls, which must stay inside the workspace, plus a heuristic list of shell commands pairing a write verb with an outside path; and a window diff, flagging pre-existing visible windows that vanished and new non-Calculator windows left open. Changed guarded files, an outside write tool call, a closed pre-existing window or a leftover window fail the trial (`conduct_passed` in `summary.json`); the heuristic command list is reported only. This is detection after the fact, not prevention. The bench therefore finds the actor's window itself, the one visible Calculator that appeared during the trial, reads its display, and closes only that window; `result.json` is required, `ownership.json` is honoured when written. None or several new Calculator windows is an explicit failure, never a guess. The bench records which input routes each workspace script used in `verification.json` for the report; it does not fail a trial for any route.

Scripts remain in the actor's workspace. The independent observer runs **outside actor token/call measurements**, reads the actor's window (claimed, or the one new Calculator), captures it, and checks the display against a fixed reference. It uses the same observer for every arm; it is not an extra tool available to the actor.

Cleanup protects every pre-existing top-level handle, including hidden windows, and checks the independently observed native PID again before closing, and validates an actor-provided PID when present. It never kills a shared frame host. Unclaimed or ambiguous windows cause an explicit cleanup failure; they are not automatically closed. Windows agent descendants are contained in a job object before execution and terminated/verified even if their parent exits first. Broker-launched application windows are handled separately. `finished.json` distinguishes worker exit from successful cleanup. After owned controllers/windows stop, cleanup reloads the saved Windows cursor scheme and checks the OS showing flag. Cursor-restoration evidence is required; a cleanup exception also clears an overall-pass summary. The mitigation passed user-confirmed emergency recovery, quiet checks, and the latest complete Calculator benchmark. Before either CUA arm, the worker restarts the shared `cua-driver` daemon (`stop`, then `autostart kick`) outside actor timing and records `daemon-restart.json`, by the user's decision on 2026-10-10: the daemon remembers ended session labels, every fresh actor had named its first session after the scenario, and each trial after the first paid a rejected call of 4 to 11 s. After a CUA arm, also end only its newly created named CLI lifecycle outside actor timing, checking the public result; the worker does not automatically end daemon-backed CLI sessions. No other shared service is stopped. These cleanup checks are not a visual guarantee.

Versions: **v1.0** is the button-only prompt that rounds 1 to 3 used, with the expression `128+465*12387/138473-12343` and the evidence-file protocol in the prompt (its 2026-10-09 drafts tightened ownership and then allowed semantic Invoke alongside pointer clicks; the archived run directories keep each draft and its hash). A one-round interim text that listed allowed input routes, and whose title line "Calculator buttons" was sent to the actors, is recorded in [its report](../docs/reports/testbench-1-v4-2026-10-11.md) and superseded. **v1.1** is the two-line task above with a new expression. Comparisons across versions are across prompts and expressions. Preserve original verdicts and prompt hashes; this is not an exact-prompt statistical comparison.

## Adobe Illustrator Pen and Export

Use `--scenario illustrator-pen-export`. The [v0.5 task](scenarios/illustrator-pen-export.md) asks for a Pen drawing and **one exported PNG**, with ordinary revisions and redraws allowed. No `result.json`, report, or editable-AI save is required from the actor. The blank starter and separate JPEG remain the only inputs; provenance, official vectors and maintainer inspection stay outside actor context.

The actor approximates the reference with the Pen tool, then sets the required blue fill, no stroke and opacity before exporting. The starter remains white-fill/black-stroke; preparation does not supply the target color. No particular color-control route is required. The v0.4 single-drawing-attempt, no-redraw and no-refinement restrictions are removed. The actor receives concrete appearance/export settings, not grading thresholds or geometry advice. The completed v0.4 round remains historical evidence under its original rules; do not pool it with v0.5.

The checker reads `workspace/Cloud9-Recreated.png` directly. It reports whether the requested PNG was produced with the specified format/dimensions/appearance, its quality measurements, and observed problems. It never reads an actor manifest or requires saved AI. Unaligned foreground IoU and boundary error are **post-run observations**, not shape pass thresholds or a signal sent back to the actor. Incorrect/missing PNGs fail completion; a rough but valid export is not failed merely for a lower quality score.

The compact run summary contains the output image, extracted metrics, and safeguard violations, with one completion outcome. Detailed logs remain debugging evidence, not extra actor obligations. Review the full session for Pen-only compliance; record violations in the maintainer's round manifest before aggregation. Pixels alone cannot prove the method.

Preparation and post-run cleanup remain maintainer work: a common blank document, primary-monitor maximized window, centered 100% document view and English input; preserve pre-existing documents, close only task-owned resources, restore the cursor scheme. `illustrator-window.json` and `observer-window.log` record initial geometry. Normalization runs before actor startup only; it does not repair later actor/runtime resizing. The exact cause of later upper-left-quarter resizing is not established by this setup change.

Normal trials no longer perform a blank calibration export or preset PNG export preferences. The earlier live check verified cached dialog settings, but also changed the export directory to `grading/`. The starter already has a recorded blank-export validation; a maintainer may explicitly recheck it using the desktop-marked fixture test, which retains `grading/blank-calibration.png` and `fixture-export-options.json`. Export settings remain actor work. The original PNG preferences are still snapshotted and restored during cleanup.

Cleanup must **never repair or advance an actor's task**. Cleanup recognizes the ownerless Color Picker from [#14](https://github.com/stanley50z/ahk-computer-use/issues/14) only in the exact Illustrator PID, with the standard dialog class/title, an enabled newly observed handle absent from the visible/hidden baseline, and unique OK/Cancel/Color Swatches controls. It refuses ambiguous or unrecognized dialogs and invokes only Cancel for the picker. This also works when the main frame remains enabled; pre-existing pickers stay protected. The marked desktop integration check exercises the real picker and protected-handle refusal; live validation of this fix is still deferred. Its evidence stays under `.pi/illustrator-pen-export-validation/native-check-*/`: `observer-dismiss-dialogs-protected-picker.log`, `observer-dismiss-dialogs-ownerless-picker.log`, `picker-state.json`, and `picker-result.json`; a JSX fixture error writes `picker-result.json.crash.txt`. It is not a Codex computer-use workaround. No vendor behavior is patched to make a blocked attempt succeed.

### Neutral skill policy

ACU skills/prompts must not contain Illustrator-, Pen-tool-, or benchmark-specific recipes, menu shortcuts, geometry advice or solutions. General input, focus, popup and sparse professional-application UI-tree guidance is allowed. Earlier runs used application-specific skill guidance; they remain historical development evidence, **not a neutral baseline**. New prompt and skill hashes identify this reset.

### Three trials per configuration

A full round is exactly **15 trials: three for each of the five configurations**, regardless of success. No replacement/retry trials are added to fill failed or interrupted slots. This supersedes the earlier five-trial/conditional-trimming policy for new rounds; historical results are unchanged.

- Average **every successful trial**. Never drop the lowest/highest token runs or the best/worst images.
- Use the same successful cohort for every metric: three successes means an average of three, two means two, one means one.
- Failed and interrupted trials remain in the evidence but are excluded from averages. With zero successes, there is no aggregate.
- Missing metric values remain unknown; do not substitute zero or silently use different subsets per metric. Unknown tokens do not prevent reporting another metric that is complete for the whole successful cohort.
- Code share is descriptive. It is never used to declare success or select which runs to keep.

`bench/aggregate.py` is offline and never launches/retries a trial. Its maintainer-authored manifest has an `attempts` array of 15 entries, in original trial order. Each entry contains a `run_dir` (absolute or relative to the manifest) and an explicit `safeguard_violations` array from session review; `[]` means no reviewed violation. This JSON is controller bookkeeping, **not a deliverable requested from the actor**. Recorded or reviewed violations exclude that attempt from averages.

```bash
uv run python bench/aggregate.py ".pi/rounds/round.json" > ".pi/rounds/aggregate.json"
```

The extractor requires finished v0.5 runs stamped `benchmark-neutral-v1`, matching prompt/assets, matched models/reasoning within each harness, and matched skill/policy within each configuration. Historical protocols, including the neutral but single-attempt v0.4 protocol, are rejected even when their hashes match one another. Plans must also match the three-trial/all-successes policy; stale five-trial profiles are rejected. It preserves the raw evidence and lists failed and retained runs, without trimming. Errors persist beside the manifest as `*.aggregate-crash.txt`.

Terminal provider-response errors are **unexpected provider failures**, not evidence that the model, harness or desktop runtime cannot perform the task. They can terminate the actor session. The controller never resumes, retries, switches provider/model, or replaces the slot. `failure.json` is written before verification/cleanup, so a later observer failure cannot hide the provider error; summaries and offline analysis expose `unexpected_failure`. Aggregation lists `unexpected_failure_ids` separately while retaining the fixed three-slot/no-replacement rule. The existing `failures` count means unsuccessful slots of any cause, not a runtime fault count. Ordinary tool errors and user aborts are not provider failures.

**The next full round and desktop validation are paused until the user announces PC availability.** Current v0.5 checks are offline only. See [the completed v0.4 round](../docs/reports/illustrator-pen-export-neutral-round-2026-10-12.md) and [v0.5 scope, issue #20](https://github.com/stanley50z/ahk-computer-use/issues/20). The metric policy, five configurations, three scheduled trials per configuration, PNG-only deliverable and neutral skill rule remain unchanged.

## Commands

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

Attribution uses captured structured tool arguments. It follows Write/Edit source, shell heredocs and script edits, Python helper imports/subprocess command prefixes, and persistent Codex computer-use JavaScript helpers. It does not rely on the final workspace contents, so moving/deleting a helper after execution does not erase its provenance.

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

This regenerates the new measurements from original events and does **not** overwrite the saved `metrics.json` or historical verdicts. The old `--reference-tps` CLI normalization is removed. Archived Codex CLI events remain readable as historical evidence.

See [token/call-time policy and replay results](../docs/reports/benchmark-token-policy-2026-10-11.md) for the recorded Illustrator attempts under this policy.

## Evidence and debugging

ACU's per-script cursor-position and foreground restoration was removed after the archived Calculator benchmark runs, by [issue #11](https://github.com/stanley50z/ahk-computer-use/issues/11). New scripts leave desktop state in place and prepare English input automatically. The bench's post-trial owned-resource cleanup and saved-cursor-scheme reload remain unchanged. Preserve the archived skill fingerprints and measurements rather than treating older trials as runs of the new runtime.

Every run preserves:

- `plan.json`, frozen `scenario.md`, selected configuration and skill/scenario fingerprints;
- `stdout.jsonl`, `events.jsonl` with monotonic receipt timestamps, `stderr.log`, `session.jsonl` for Pi, the Claude Code transcript under `agent-home/projects/`, or archived Codex CLI rollouts under `agent-home/sessions/`;
- `metrics.json` and `summary.json` with `benchmark` token/code-share/call-duration ledgers, plus `isolation.json` and `verification.json`;
- `workspace/` with original actor scripts, ownership and result files;
- screenshots and `observer-*.log` outside actor timing;
- `state.json`, `launch.json`, `capture.json`, `cleanup.json`, `finished.json`;
- `worker.log`, `crash.txt` or `capture-crash.txt` with tracebacks on failure; `failure.json` for an observed terminal provider error, independent of later cleanup errors.

Interrupted runs retain raw events and report terminal failure. Usage for an unfinished model request can be unavailable; reported completed-message tokens are a lower bound, not a complete total. Evidence can contain screen content and should be treated as sensitive.

ACU also retains its normal runtime logs at `%LOCALAPPDATA%\ACU\logs\runs.jsonl` and crash reports at `%LOCALAPPDATA%\ACU\crashes\`.

Focused quiet checks:

```bash
python -m pytest tests/test_bench*.py -q
```

These tests exercise profiles, usage/timing, ownership checks, Codex computer-use audit parsing, cancellation and descendant cleanup using ordinary Python stand-ins. They do not launch AutoHotkey, open applications, or interact with the desktop. Real desktop evidence comes from explicitly approved trials, not a routine full integration suite.
