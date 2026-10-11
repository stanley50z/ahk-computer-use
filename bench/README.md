# Computer-use test bench

**Testbench 1 means the Calculator task as a whole, across all four configurations below.** An individual configuration is an arm, not "Testbench 1" by itself. A request to run Testbench 1 means fresh sequential trials of all four arms unless the user explicitly selects a subset.

Compare four fresh agent configurations, not a knowledgeable parent agent solving the task:

| Arm | Harness | Only computer-use skill/runtime | Status |
| --- | --- | --- | --- |
| `pi-acu` | Pi | Project ACU skill and CLI | v1.1, three trials after the `Send`/settle fixes: median 15.90 s (15.02 to 16.68), six responses each; the first v1.1 trial took 44.13 s on a `Send` modifier mistake |
| `claude-acu` | Claude Code | Project ACU skill and CLI | v1.1 with Opus 5.5/low, four trials: median 17.0 s (16.18 to 19.54), four to five responses |
| `pi-cua` | Pi | Installed `cua-driver` skill and CLI | v1.1, four trials: median 104.97 s (88.28 to 107.75); daemon restarted before each |
| `codex-computer-use` | Codex CLI | Installed `computer-use` skill, native `@oai/sky` through `node_repl` | v1.1, four trials by keyboard: median 53.27 s (48.02 to 60.34) |

The GPT harnesses use **GPT-6.1 (`gpt-6.1-sol`) at low reasoning**; Pi uses the `openai` provider. This supersedes the earlier GPT-6 Astra acceptance-test choice for this bench only. Claude Code runs only Claude models, so `claude-acu` is the one exception: **Opus 5.5 (`claude-opus-5-5`) at low effort**, by the user's decision on 2026-10-10 after round 2, which had used Haiku 5.5 at high effort. No automatic provider/model fallback, parent coaching, or retry after a blocked trial. Each further desktop trial needs explicit approval.

Round 1 (2026-10-10, three arms) is in [its report](../docs/reports/testbench-1-2026-10-10.md); round 2 (all four arms, after the ACU changes) in [round 2](../docs/reports/testbench-1-round-2-2026-10-10.md); round 3 (in-script AcuTree/AcuScreenshot, Opus 5.5 on the Claude arm) in [round 3](../docs/reports/testbench-1-round-3-2026-10-10.md). Archived runs keep their original metrics; `analyse` replays them with the current task-time definition into `metrics-replayed.json`.

Specification: [issue #8](https://github.com/stanley50z/ahk-computer-use/issues/8). History: [first Calculator trials](../docs/reports/bench-calculator-2026-10-09.md). Comparison: [three-arm pilot and cursor incident](../docs/reports/computer-use-comparison-2026-10-09.md). Earlier ACU-only result: [CLI-only trial](../docs/reports/acu-cli-bench-2026-10-10.md). Round 1: [Testbench 1, three configurations](../docs/reports/testbench-1-2026-10-10.md). Time attribution and the subsequent overall-deadline removal: [latency analysis](../docs/reports/testbench-1-latency-2026-10-10.md). Latest complete benchmark: [scenario v1.1, all four configurations](../docs/reports/testbench-1-v1.1-2026-10-11.md). Earlier: [interim prompt](../docs/reports/testbench-1-v4-2026-10-11.md), and the last v1.0 run, [round 3](../docs/reports/testbench-1-round-3-2026-10-10.md).

The user reported an invisible cursor after the earlier comparison. The latest complete Testbench 1 exercised identity-checked window/process cleanup and saved cursor-scheme restoration after all three arms. CUA's task-specific named CLI lifecycle was additionally ended explicitly outside timing; the shared daemon was preserved. The cursor check remains an OS showing-flag check, not pixel-level visibility proof, and the earlier incident's precise cause is still unproven.

## Isolation

Each run gets a new workspace, config directory, session and evidence folder under `.pi/bench/`. No global settings or discovery links are modified.

- Pi disables discovered extensions, MCP, other skills, context files, prompt templates and themes. Only the selected skill and `read,bash,edit,write` are enabled. The isolated agent directory contains no `AGENTS.md`, `SYSTEM.md` or `APPEND_SYSTEM.md`. Cache warming and automatic retry/compaction are off; provider-side prompt caching still occurs and is measured.
- Claude Code runs with a fresh `CLAUDE_CONFIG_DIR`, `--safe-mode` (no CLAUDE.md, skills, hooks, plugins or MCP), `--disable-slash-commands`, `--strict-mcp-config`, user-only setting sources, and exactly `Read,Write,Edit,Bash`. The ACU skill is declared by path in an appended system prompt, as the Codex arm declares its skill. The stream's init event is audited for model, tools, MCP servers and skills, and the persisted transcript for effort, model and skill reads; the stream lists no memory files, so the CLAUDE.md exclusion rests on the flag. Claude Code's Bash tool uses Git Bash on Windows, like Pi.
- Codex uses a fresh `CODEX_HOME`, no shared agent daemon, no hooks/plugins/apps/memories/browser runtime, zero project-document budget and ignored exec-policy rules. The skip-host-discovery flag proved insufficient in the installed CLI; exact host/project/builtin skill files and directories are now explicitly disabled. Only the native node runtime is configured, with `sky` as its only trusted service. The CLI uses the shipped SDK-owned Windows helper transport, not a stale app-owned native pipe. The corresponding installed skill is declared explicitly. Actual model/reasoning and skill declarations are audited from the persisted native rollout; missing evidence fails the audit rather than assuming isolation succeeded.
- Saved login credentials (Pi `auth.json`, Codex `auth.json`, Claude Code `.credentials.json`) are copied into the private config only while running, then deleted in `finally`. Do not commit or share a run directory while a run is active. Commands and manifests contain credential paths, never credential values.
- This is **configuration and prompt isolation, not an OS security sandbox**. The shell is capable of arbitrary commands; method compliance also needs transcript/script review. The desktop remains shared. Run one controller at a time on an idle desktop.

Installed versions at initial setup: Pi 1.1.0; Codex CLI 0.162.0; cua-driver 0.34.0; native computer-use skill build 26.901.51231; Claude Code 2.1.295 when the `claude-acu` arm was added. ACU source was `eae5264`. Plans save the exact selected skill path, skill SHA-256, scenario SHA-256, launch command and configuration paths.

## Testbench 1: Calculator

Scenario **v1.1** (2026-10-11, by the user's decision) is the task plus the result file, with every safeguard sentence removed. The actor receives exactly:

```text
Open a new Windows Calculator window and calculate:

98765 * 432 / 1234 * 56 / 789 + 6543 - 4321

When done, write result.json in the workspace with these fields: observed_result (the displayed text), observed_expression, input_method, and hiccups (an array of concrete problems encountered).
```

The answer with normal precedence is 4676.0458…; left-to-right evaluation gives a different number, which is how a mode mistake shows. The file's first line is its title and version for people; `prepare` sends only the body and writes the exact text to `prompt.txt` in the run directory, with `prompt_sha256` and `scenario_version` in `plan.json`. Nothing is said about input routes, skill reading, ownership files, preserving other windows, or leaving the window open: whether an actor needs those guards is unknown, so none is added back without the user's approval. Instead the bench runs a **conduct audit** around every trial and records it in `conduct.json`: a SHA-256 fingerprint of `acu/`, `bench/`, `tests/`, the READMEs and the arm's installed skill directory, taken before and after, so any edit to the skill or tool is caught whatever route made it; the transcript's write/edit tool calls, which must stay inside the workspace, plus a heuristic list of shell commands pairing a write verb with an outside path; and a window diff, flagging pre-existing visible windows that vanished and new non-Calculator windows left open. Changed guarded files, an outside write tool call, a closed pre-existing window or a leftover window fail the trial (`conduct_passed` in `summary.json`); the heuristic command list is reported only. This is detection after the fact, not prevention. The bench therefore finds the actor's window itself, the one visible Calculator that appeared during the trial, reads its display, and closes only that window; `result.json` is required, `ownership.json` is honoured when written. None or several new Calculator windows is an explicit failure, never a guess. The bench records which input routes each workspace script used in `verification.json` for the report; it does not fail a trial for any route.

Scripts remain in the actor's workspace. The independent observer runs **outside agent timing**, reads the actor's window (claimed, or the one new Calculator), captures it, and checks the display against a fixed reference. It uses the same observer for every arm; it is not an extra tool available to the actor.

Cleanup protects every pre-existing top-level handle, including hidden windows, and checks the independently observed native PID again before closing, and validates an actor-provided PID when present. It never kills a shared frame host. Unclaimed or ambiguous windows cause an explicit cleanup failure; they are not automatically closed. Windows agent descendants are contained in a job object before execution and terminated/verified even if their parent exits first. Broker-launched application windows are handled separately. `finished.json` distinguishes worker exit from successful cleanup. After owned controllers/windows stop, cleanup reloads the saved Windows cursor scheme and checks the OS showing flag. Cursor-restoration evidence is required; a cleanup exception also clears an overall-pass summary. The mitigation passed user-confirmed emergency recovery, quiet checks, and the latest complete Testbench 1. Before a CUA arm, the worker restarts the shared `cua-driver` daemon (`stop`, then `autostart kick`) outside actor timing and records `daemon-restart.json`, by the user's decision on 2026-10-10: the daemon remembers ended session labels, every fresh actor had named its first session after the scenario, and each trial after the first paid a rejected call of 4 to 11 s. After a CUA arm, also end only its newly created named CLI lifecycle outside actor timing, checking the public result; the worker does not automatically end daemon-backed CLI sessions. No other shared service is stopped. These cleanup checks are not a visual guarantee.

Versions: **v1.0** is the button-only prompt that rounds 1 to 3 used, with the expression `128+465*12387/138473-12343` and the evidence-file protocol in the prompt (its 2026-10-09 drafts tightened ownership and then allowed semantic Invoke alongside pointer clicks; the archived run directories keep each draft and its hash). A one-round interim text that listed allowed input routes, and whose title line "Calculator buttons" was sent to the actors, is recorded in [its report](../docs/reports/testbench-1-v4-2026-10-11.md) and superseded. **v1.1** is the two-line task above with a new expression. Comparisons across versions are across prompts and expressions. Preserve original verdicts and prompt hashes; this is not an exact-prompt statistical comparison.

## Commands

Offline preparation only; no credentials copied and no desktop operation:

```bash
python bench/run.py prepare --arm pi-acu
python bench/run.py prepare --arm claude-acu
python bench/run.py prepare --arm pi-cua
python bench/run.py prepare --arm codex-computer-use
```

After approval for that specific trial, start in the background without opening another terminal:

```bash
python bench/start.py --arm pi-acu --desktop-approved
```

Replace the arm only when the corresponding run is authorized. `start.py` prints the run directory and worker PID. For the native arm, `--native-transport app-pipe` uses the running ChatGPT/Codex desktop app's own computer-use pipe instead of the shipped SDK helper; the worker refuses to start if that pipe is not open. The default remains the SDK helper. There is no overall actor time limit. Stop a stalled or unwanted run explicitly with `stop.py`; per-script watchdogs and backend request/startup timeouts remain separate protections. A run directory is never reused for another trial.

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

- **Task time**, the primary measurement: from the actor's session start (Pi `agent_start`, Claude Code `init`, Codex `thread.started`), when it holds the skill, to the receipt of its last computer-use tool call's result. A call counts as computer use when its arguments, or a workspace script those arguments run, contain the arm's route: `acu run`, `cua-driver`, or `sky.`. Writing `ownership.json` inside a computer-use call is inside the task; writing `result.json` and the final answer afterwards are not, because they only let the bench check the result. Recorded in `metrics.json` under `task` and in `summary.json` as `task_s`.
- **Wall time**: spawning the actor CLI through process exit; includes CLI startup and shutdown, evidence writing and the final answer, excludes observer/cleanup and parent analysis. Secondary.
- **Agent elapsed time**: Pi `agent_start` through `agent_settled`.
- **Model response time**: sum of authoritative Pi assistant `durationMs`. Pi's `message_start` can arrive after the request has begun, so its receipt interval alone undercounts latency. Claude Code exposes no server-side duration, so its responses are timed from the `requesting` status event to `message_stop` receipt; the result's `duration_api_ms` is kept beside it as a cross-check.
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

ACU's per-script cursor-position and foreground restoration was removed after the archived Testbench 1 runs, by [issue #11](https://github.com/stanley50z/ahk-computer-use/issues/11). New scripts leave desktop state in place and prepare English input automatically. The bench's post-trial owned-resource cleanup and saved-cursor-scheme reload remain unchanged. Preserve the archived skill fingerprints and measurements rather than treating older trials as runs of the new runtime.

Every run preserves:

- `plan.json`, frozen `scenario.md`, selected configuration and skill/scenario fingerprints;
- `stdout.jsonl`, `events.jsonl` with monotonic receipt timestamps, `stderr.log`, `session.jsonl` for Pi, the Claude Code transcript under `agent-home/projects/`, or native rollouts under `agent-home/sessions/`;
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
