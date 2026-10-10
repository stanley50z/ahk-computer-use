# Computer-use test bench

Compare three fresh agent configurations, not a knowledgeable parent agent solving the task:

| Arm | Harness | Only computer-use skill/runtime | Status |
| --- | --- | --- | --- |
| `pi-acu` | Pi | Project ACU skill and launcher | Latest task passed under the user's clarified UI-button rule |
| `pi-cua` | Pi | Installed `cua-driver` skill and CLI | Task and isolation passed, 111.61 s |
| `codex-computer-use` | Codex CLI | Installed `computer-use` skill, native `@oai/sky` through `node_repl` | Corrected setup passed task/isolation, 234.25 s; cursor cleanup incident followed the comparison |

Every actor uses **GPT-6.1 (`gpt-6.1-sol`) at low reasoning**. Pi uses the `openai` provider. This supersedes the earlier GPT-6 Astra acceptance-test choice for this bench only. No automatic provider/model fallback, parent coaching, or retry after a blocked trial. Each further desktop trial needs explicit approval.

Specification: [issue #8](https://github.com/stanley50z/ahk-computer-use/issues/8). History: [first Calculator trials](../docs/reports/bench-calculator-2026-10-09.md). Latest: [three-arm comparison and cursor incident](../docs/reports/computer-use-comparison-2026-10-09.md).

Desktop cleanup must be validated before further trials: the user reported an invisible cursor after the comparison. Recovery succeeded; automatic scheme restoration and truthful cleanup markers were added with quiet coverage, but no new live run has validated that integration.

## Isolation

Each run gets a new workspace, config directory, session and evidence folder under `.pi/bench/`. No global settings or discovery links are modified.

- Pi disables discovered extensions, MCP, other skills, context files, prompt templates and themes. Only the selected skill and `read,bash,edit,write` are enabled. The isolated agent directory contains no `AGENTS.md`, `SYSTEM.md` or `APPEND_SYSTEM.md`. Cache warming and automatic retry/compaction are off; provider-side prompt caching still occurs and is measured.
- Codex uses a fresh `CODEX_HOME`, no shared agent daemon, no hooks/plugins/apps/memories/browser runtime, zero project-document budget and ignored exec-policy rules. The skip-host-discovery flag proved insufficient in the installed CLI; exact host/project/builtin skill files and directories are now explicitly disabled. Only the native node runtime is configured, with `sky` as its only trusted service. The CLI uses the shipped SDK-owned Windows helper transport, not a stale app-owned native pipe. The corresponding installed skill is declared explicitly. Actual model/reasoning and skill declarations are audited from the persisted native rollout; missing evidence fails the audit rather than assuming isolation succeeded.
- Saved login credentials are copied into the private config only while running, then deleted in `finally`. Do not commit or share a run directory while a run is active. Commands and manifests contain credential paths, never credential values.
- This is **configuration and prompt isolation, not an OS security sandbox**. The shell is capable of arbitrary commands; method compliance also needs transcript/script review. The desktop remains shared. Run one controller at a time on an idle desktop.

Installed versions at initial setup: Pi 1.1.0; Codex CLI 0.162.0; cua-driver 0.34.0; native computer-use skill build 26.901.51231. ACU source was `eae5264`. Plans save the exact selected skill path, skill SHA-256, scenario SHA-256, launch command and configuration paths.

## First scenario

`scenarios/calculator.md` asks the actor to open its own Calculator, calculate `128+465*12387/138473-12343` with normal precedence, and observe the result.

UI button activation only. The user clarified that semantic clicks/Invoke are allowed alongside pointer clicks; the intent is to exclude keyboard/text input, direct field values, shortcuts, clipboard input and arithmetic performed in code. No arithmetic in code. No instructions about Calculator's correct process/window identity are supplied by the parent.

The actor writes `ownership.json` before clicks and `result.json` after completion or blockage. Scripts remain in its workspace. The independent observer runs **outside agent timing**, reads the claimed window, captures it, and checks the display against a fixed reference. It uses the same observer for every arm; it is not an extra tool available to the actor.

Cleanup protects every pre-existing top-level handle, including hidden windows, and checks the independently observed native PID again before closing, and validates an actor-provided PID when present. It never kills a shared frame host. Unclaimed or ambiguous windows cause an explicit cleanup failure; they are not automatically closed. Windows agent descendants are contained in a job object before execution and terminated/verified even if their parent exits first. Broker-launched application windows are handled separately. `finished.json` distinguishes worker exit from successful cleanup. After owned controllers/windows stop, cleanup reloads the saved Windows cursor scheme and checks the OS showing flag. Cursor-restoration evidence is required; a cleanup exception also clears an overall-pass summary. This is a mitigation validated by user-confirmed emergency recovery and quiet checks, not a visual guarantee or another live cleanup trial.

Both initial trials used scenario **v1**. Ownership tightening gave **v2**. The user's clarification gave **v3**, allowing semantic UI button activation; native/CUA actors can provide returned window IDs, with PID bound by the independent observer when the tool does not expose it. The recorded successful ACU v2 trial was reassessed under the intended rule, not rerun with v3. Preserve original verdicts and prompt hashes; this pilot is not an exact-prompt statistical comparison.

## Commands

Offline preparation only; no credentials copied and no desktop operation:

```bash
python bench/run.py prepare --arm pi-acu
python bench/run.py prepare --arm pi-cua
python bench/run.py prepare --arm codex-computer-use
```

After approval for that specific trial, start in the background without opening another terminal:

```bash
python bench/start.py --arm pi-acu --desktop-approved
```

Replace the arm only when the corresponding run is authorized. `start.py` prints the run directory and worker PID. Default actor timeout is 240 seconds; each ACU script retains its own watchdog. A run directory is never reused for another trial.

Stop only that run, allowing its worker to terminate owned processes and perform cleanup:

```bash
python bench/stop.py "C:/path/to/the/run-directory"
```

Synchronous equivalent:

```bash
python bench/run.py run --arm pi-acu --desktop-approved
```

No benchmark server or new fixed localhost port is required. Existing CUA/Codex host services are not stopped by this bench.

## Measurements and estimates

- **Wall time**: spawning the actor CLI through process exit; includes CLI startup and shutdown, excludes observer/cleanup and parent analysis.
- **Agent elapsed time**: Pi `agent_start` through `agent_settled`.
- **Model response time**: sum of authoritative Pi assistant `durationMs`. Pi's `message_start` can arrive after the request has begun, so its receipt interval alone undercounts latency.
- **Tool busy time**: union of tool-execution receipt intervals, not a sum that double-counts parallel calls. Each call also retains the harness's duration where supplied.
- **Tokens**: final assistant usage summed once, never repeated streaming/turn-end totals. Pi uncached input, cache reads/writes, output, reasoning subset and total are separate. Reasoning is already in output and is not added twice. These are cumulative API usage across turns, not final context length.
- **Effective response throughput**: output tokens / full model-response seconds, including hidden reasoning. This includes queueing, prefill and first-token wait; it is not a pure decoding-rate measurement. End-to-end output tokens / wall seconds is recorded separately.
- **First visible delta**: receipt timing corrected using full response duration; includes the wait before observable text/tool arguments. It is not provider-side first-token telemetry.

Reanalyse saved Pi events without launching an agent or touching the desktop:

```bash
python bench/run.py analyse --run-dir "C:/path/to/run" --reference-tps 100
```

Two deliberately rough counterfactuals are returned:

1. Whole-response effective-rate normalization: `wall - model-response seconds + output tokens / reference TPS`. This scales queueing/prefill too; do not call it pure decoding normalization.
2. Visible-output normalization retaining first-visible-delta wait: replace only measured post-first-delta time with non-reasoning output / reference visible TPS. This preserves the observed initial wait and hidden reasoning delay, but chunking/receipt timing still makes it an estimate.

100 TPS is an illustrative reference, not a measured machine baseline. Failed/blocked attempts estimate only that attempt, never full-task completion time.

Codex `exec --json` provides final aggregate usage but no authoritative per-response model duration. Its end-to-end throughput is recorded. For the completed native pilot, a separate receipt-timestamp audit computes tool busy time and residual agent time minus tools as **estimated model plus orchestration time**; its rate and normalization are explicitly estimates, not exact decoding telemetry. Do not silently compare wall-inclusive throughput against Pi's response-only denominator. If no final native usage arrives, totals are unknown, not zero.

## Evidence and debugging

Every run preserves:

- `plan.json`, frozen `scenario.md`, selected configuration and skill/scenario fingerprints;
- `stdout.jsonl`, `events.jsonl` with monotonic receipt timestamps, `stderr.log`, `session.jsonl` for Pi or native rollouts under `agent-home/sessions/`;
- `metrics.json`, `isolation.json`, `verification.json`, `summary.json`;
- `workspace/` with original actor scripts, ownership and result files;
- screenshots and `observer-*.log` outside actor timing;
- `state.json`, `launch.json`, `capture.json`, `cleanup.json`, `finished.json`;
- `worker.log`, `crash.txt` or `capture-crash.txt` with tracebacks on failure.

Interrupted runs retain raw events and report terminal failure. Usage for an unfinished model request can be unavailable; reported completed-message tokens are a lower bound, not a complete total. Evidence can contain screen content and should be treated as sensitive.

ACU also retains its normal runtime logs at `%LOCALAPPDATA%\ACU\logs\runs.jsonl` and crash reports at `%LOCALAPPDATA%\ACU\crashes\`.

Focused quiet checks:

```bash
python -m pytest tests/test_bench*.py -q
```

These tests exercise profiles, usage/timing, ownership checks, native audit parsing, cancellation and descendant cleanup using ordinary Python stand-ins. They do not launch AutoHotkey, open applications, or interact with the desktop. Real desktop evidence comes from explicitly approved trials, not a routine full integration suite.
