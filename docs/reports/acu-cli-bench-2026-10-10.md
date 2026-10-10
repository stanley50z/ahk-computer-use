# ACU CLI benchmark rerun

An ACU-only trial of Testbench 1, not a complete three-configuration benchmark. One user-authorized rerun of the first arm (`pi-acu`), using source `de19715` and the current CLI-only skill. Fresh Pi session, `openai/gpt-6.1-sol`, low reasoning, scenario v3. No parent coaching, automatic retry, or implementation/skill edits during the timed run.

Run: `20261010T050432Z-pi-acu-f39190` (UTC).

## Result

**Task, configuration isolation, and recorded cleanup passed.** Calculator showed:

```text
128 + 465 × 12387 ÷ 138473 − 12343
= -12,173.403768243628721844691744961
```

The independent observer read the display and captured a matching screenshot. Input was UI Automation Invoke on Calculator's number/operator buttons, with no keyboard, clipboard, direct field-value input, or arithmetic outside the application. The newly opened window was already in Scientific mode; mode-change handling was not exercised.

## Actual ACU use

The actor made exactly four shell calls, all through the installed `acu run` command:

1. Its own `workspace/launch.ahk`, discovering a unique new Calculator handle and writing ownership before input.
2. ACU's ordinary `tree.ahk` script, passing that observed handle.
3. Its own `workspace/calculate.ahk`, invoking all 27 number/operator buttons as one action chain and reading the result back.
4. ACU's ordinary `screenshot.ahk` script, then reading its saved PNG.

It loaded only the ACU skill and its scripting/tree/screenshot guides. No `uv run`, Python launcher command, MCP, or alternate desktop tool was used by the actor. The bench's independent observer still uses the low-level launcher outside actor timing.

The only reported hiccup was accessibility expression wording: subtraction appeared as `Minus (` in the element's Name. Screenshot verification confirmed a normal minus sign and no parenthesis. The actor reported that ACU otherwise worked reliably. No fix was applied during or after this run.

## Measurements

| Measurement | Previous successful ACU pilot | Current CLI-only rerun |
| --- | ---: | ---: |
| Wall time | 43.61 s | 75.64 s |
| Model response time | 34.668 s | 59.727 s |
| Tool busy time | 7.659 s | 7.297 s |
| Model responses | 8 | 13 |
| Harness tool calls | 7 | 12 |
| Uncached input tokens | 15,709 | 18,983 |
| Cached input tokens | 28,288 | 59,904 |
| Output tokens, including reasoning | 1,066 | 1,275 |
| Reasoning subset, already included in output | 0 | 13 |
| Total tokens | 45,063 | 80,162 |
| Effective output per model-response second | 30.75 tok/s | 21.35 tok/s |

This rerun took longer while measured tool busy time stayed similar. More model responses and a larger measured model-response total account for the main difference in these recorded fields; the result does not establish that the CLI itself became slower. Each column is one pilot, with different skill content, prompt version, and cache/latency conditions. The previous run used v2 and was reassessed under the user's clarified v3 input rule. This is not a controlled performance comparison.

Tokens are cumulative API usage across turns, not unique prompt size or final context length. Effective throughput includes response latency and reasoning, not pure decoding speed. Wall time excludes independent verification and cleanup.

## Cleanup and validation limits

Before actor timing, the parent ran the saved-cursor-scheme restoration routine through the CLI. It succeeded and the OS showing flag was set. The bench then performed its automatic cleanup after the actor finished:

- Closed only the claimed new Calculator window (`hwnd=598732`), after checking its independently observed identity.
- Found no remaining new Calculator windows.
- Reloaded the saved Windows cursor scheme and checked the OS showing flag.
- Stopped and verified the owned actor process tree; independent process inspection found worker PID 53464 and actor PID 30024 no longer running.
- Deleted the temporary credential copy and released the controller lock.

The cursor check is not pixel-level proof of visible rendering. This run validates the cleanup path for the ACU arm, not the lifecycle of CUA or native Computer Use. No additional desktop suite was run. Original scripts and evidence were retained as the scenario requires.

## Evidence

Local, gitignored artifacts (may contain desktop/account metadata):

- [Summary and complete metrics](../../.pi/bench/20261010T050432Z-pi-acu-f39190/summary.json).
- [Independent verification](../../.pi/bench/20261010T050432Z-pi-acu-f39190/verification.json), [screenshot](../../.pi/bench/20261010T050432Z-pi-acu-f39190/calculator-result.png).
- [CLI/transcript audit](../../.pi/bench/20261010T050432Z-pi-acu-f39190/cli-audit.json), [isolation audit](../../.pi/bench/20261010T050432Z-pi-acu-f39190/isolation.json), [native session](../../.pi/bench/20261010T050432Z-pi-acu-f39190/session.jsonl).
- [Cleanup](../../.pi/bench/20261010T050432Z-pi-acu-f39190/cleanup.json), [finished record](../../.pi/bench/20261010T050432Z-pi-acu-f39190/finished.json), [worker log](../../.pi/bench/20261010T050432Z-pi-acu-f39190/worker.log).
- [Cursor preflight](../../.pi/artifacts/acu-bench-rerun/cursor-preflight.json).

ACU run logs remain in `%LOCALAPPDATA%\ACU\logs\runs.jsonl`; failures would produce reports under `%LOCALAPPDATA%\ACU\crashes\`. Specification: [issue #8](https://github.com/stanley50z/ahk-computer-use/issues/8).
