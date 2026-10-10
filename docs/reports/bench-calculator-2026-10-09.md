# Calculator benchmark: first ACU trials

Two fresh Pi sessions used only the ACU skill, GPT-6.1 (`openai/gpt-6.1-sol`), and low reasoning. Both actual session audits passed: no other skill, context file, global addendum or computer-use extension was loaded. The actor had ordinary read/bash/edit/write tools; configuration isolation is not a filesystem sandbox.

Task: open a separate Calculator and calculate `128+465*12387/138473-12343` by physical button clicks, with no keyboard input or semantic invocation. Observe the result, preserve evidence and existing user windows, and let the bench verify/clean up the owned application. No parent coaching, implementation inspection or skill edits during either trial.

**Neither trial reached the calculation. There is no completed-task speed result yet.**

## Outcomes

| | Initial trial | Authorized hands-off trial |
| --- | --- | --- |
| Outcome | Blocked by takeover rule | Failed window discovery |
| Wall time | 30.75 s | 35.17 s |
| Active agent time | 22.42 s | 34.13 s |
| Model response time, including initial waits | 20.617 s | 22.036 s |
| Tool busy time | 1.335 s | 11.937 s |
| Model responses / tool calls | 5 / 4 | 5 / 4 |
| Uncached input tokens | 9,090 | 5,087 |
| Cached input tokens | 9,600 | 13,696 |
| Output tokens, including reasoning | 584 | 530 |
| Reasoning tokens, already in output | 26 | 23 |
| **Total tokens** | **19,274** | **19,313** |
| Effective output per model-response second | 28.33 tokens/s | 24.05 tokens/s |
| End-to-end output per wall second | 18.99 tokens/s | 15.07 tokens/s |
| Illustrative time at 100 visible tokens/s, retaining first-delta waits | 27.33 s | 31.92 s |

Token totals sum API usage across all five responses, including repeatedly supplied cached context; they are not unique prompt length or final context size. Throughput includes response latency and is not pure decoding speed. The normalized estimates concern these blocked attempts only and do not predict Calculator task completion.

The first timing implementation counted stream-start-to-end, which missed initial request waits. Metrics were reanalysed from immutable events using Pi's full `durationMs`; raw transcripts were not changed. Different startup/cache conditions mean these two attempts are not a controlled performance comparison.

## Trial 1: concurrent mouse use

Run: `20261009T225109Z-pi-acu-ac3ab9`.

The actor opened Calculator `hwnd=41419936`, wrote its ownership record, and received:

```text
[acu] restore skipped: cursor moved by someone else
```

It obeyed the skill and stopped. It performed no button clicks and did not invent a result. The user confirmed mouse movement during this trial and explicitly approved a fresh hands-off retry. This is an explained concurrent-input blockage, not a demonstrated restore implementation defect.

The observer saw `Display is 0`, captured it, closed only the created window, and confirmed no Calculator remained.

## Trial 2: the real hiccup

Run: `20261009T225329Z-pi-acu-f0901f`.

The actor's opening script enumerated all existing handles, launched `calc.exe`, then waited only for new windows matching:

```autohotkey
WinGetList("ahk_exe CalculatorApp.exe")
```

After ten seconds it threw `No separate Calculator window obtained`, wrote a blocked result and stopped. It did not broaden its discovery to the window's title, class or frame host.

**Calculator had opened.** Independent observation found the new window `hwnd=1055556`, owned by `ApplicationFrameHost.exe` (`pid=8044`), displaying zero. The process-name assumption was wrong for this machine's top-level Calculator window. This is a fresh-agent discovery/skill robustness failure, not evidence that ACU could not launch the app or click its buttons.

No initial Calculator existed; exactly one new Calculator appeared after the actor's recorded launch during the approved hands-off trial. The parent recorded that evidence, captured the window and closed that specific handle. It did not solve the calculation or coach/retry the actor. Automatic cleanup could not use an ownership record because the actor failed before writing one; this reconciliation is recorded separately rather than hidden as normal cleanup.

The arithmetic result would need to be observed in a later trial. No conclusion about physical-click accuracy or completed-task latency follows from these attempts.

## Bench improvements made after the trials

The actor-facing ACU skill and implementation were unchanged throughout these trials and the bench-hardening work below.

Read-only review found weaknesses in the new bench, which were addressed without another desktop run:

- Protect all pre-existing handles, not only a partial Calculator inventory; require a PID and check it before closing.
- Treat unclaimed/ambiguous windows as explicit cleanup failures, not automatically owned resources.
- Use a Windows job to contain descendants before execution, and terminate/verify it even after the root agent exits.
- Retain raw measurements and terminal failure for timeout/cancellation.
- Distinguish successful cleanup from a merely finished worker; stop callers report incomplete cleanup.
- Audit native Codex model/reasoning and skill declarations from persisted context instead of an always-failed placeholder.
- Disclose rate-normalization limitations, and offer a separate estimate retaining observed first-visible-delta waits.

Twelve focused quiet checks passed. They include real ordinary-Python process timeout/descendant cases, but no AutoHotkey or desktop integration run. The subsequent ownership-contract tightening changed scenario v1 to v2; future exact comparisons must use the same scenario hash across arms.

## Other arms and remaining work

Pi/CUA and Codex/native profiles are prepared but have not performed a live scenario. The native Codex configuration parsed with the intended feature isolation. Actual native skill/tool reach still needs its first runtime audit; it must not be called validated before that.

Codex exec exposes total usage and wall throughput, not a full per-model-response timing denominator. Model-only speed and decoding-rate normalization remain unknown for that arm. A native model-timing instrumentation path is still needed for a fair response-only throughput comparison; do not substitute wall throughput silently.

### Follow-up skill fix, 2026-10-09

On the user's instruction, ACU's skill now teaches window discovery before control lookup: use observed titles/classes, retain the exact handle, broaden an empty process-only search with a window listing, and preserve pre-existing handles when selecting a newly opened window. It explicitly explains the CalculatorApp.exe / ApplicationFrameHost.exe distinction. The launcher and UIA implementation did not change.

A quiet documentation-contract regression failed against the old skill and passed after the change; all six skill/installer checks passed. Logs: `.pi/logs/skill-window-discovery-red.log` and `.pi/logs/skill-window-discovery-green.log`. This guards the recipe, not fresh-agent behavior: at that point, no desktop trial had validated the new skill.

Next ACU follow-up: run a newly approved fresh trial with the updated skill. Preserve the failed trial above as the before-state. Alternatively, run the same v2 scenario with CUA or native Codex to see whether their own skill handles launch discovery better. No additional live run is currently authorized.

## Updated-skill rerun, 2026-10-09

The user authorized another hands-off trial after the window-discovery skill fix. Run `20261009T232142Z-pi-acu-fixed-d764a9` used a frozen copy of the staged ACU skill/runtime so concurrent CLI work could not alter the tested tool. It used scenario v2, only the ACU skill, GPT-6.1 at low reasoning, and no parent coaching.

Window discovery succeeded: the actor selected a new window by observed title, retained `ahk_id 1775912`, and recorded its PID. Calculator was already in Scientific mode. It entered the expression and the independent tree/screenshot check confirmed `-12,173.403768243628721844691744961`.

**The physical-input constraint failed.** The automated verifier initially reported pass, but post-run inspection found the actor used `root.FindElement(...).Click()` without an argument. In the exact vendored library, that defaults to semantic patterns; the Invoke-capable Calculator buttons are operated through `InvokePattern.Invoke()`. Physical mouse input requires an explicit button, such as `.Click("left")`. The skill's claim that argument-less `.Click()` is physical bounds input was inaccurate, and the bench's static scan missed the indirect invocation.

The derived verdict was corrected to failed method compliance. Original automated verdicts, actor claims, raw transcripts and frozen files remain preserved; the displayed arithmetic was correct. This establishes successful window discovery in this trial, not a completed physical-click-only baseline. No further tool/skill fix or desktop trial was performed in this test-only request.

| Measurement | Rerun |
| --- | ---: |
| Wall time | 43.61 s |
| Active agent time | 42.49 s |
| Model response time | 34.668 s |
| Tool busy time | 7.659 s |
| Model responses / tool calls | 8 / 7 |
| Uncached input tokens | 15,709 |
| Cached input tokens | 28,288 |
| Output tokens, including reasoning | 1,066 |
| Reasoning subset | 0 |
| **Total tokens** | **45,063** |
| Effective output per model-response second | 30.75 tokens/s |
| End-to-end output per wall second | 24.45 tokens/s |
| Illustrative time at 100 visible tokens/s, retaining first-delta waits | 38.83 s |

The owned Calculator window was closed, both actor and worker exited, job-contained descendants were stopped, credentials were deleted and the bench lock released. The remaining finding is the distinction between default semantic `.Click()` and explicit physical `.Click("left")`, plus the verifier gap; source code was not changed during the run.

Rerun evidence: [corrected summary](../../.pi/bench/20261009T232142Z-pi-acu-fixed-d764a9/summary.json), [original automated summary](../../.pi/bench/20261009T232142Z-pi-acu-fixed-d764a9/summary-automatic.json), [method audit](../../.pi/bench/20261009T232142Z-pi-acu-fixed-d764a9/method-audit.md), [screenshot](../../.pi/bench/20261009T232142Z-pi-acu-fixed-d764a9/calculator-result.png), [actor script](../../.pi/bench/20261009T232142Z-pi-acu-fixed-d764a9/workspace/calculate.ahk), [isolation audit](../../.pi/bench/20261009T232142Z-pi-acu-fixed-d764a9/isolation.json).

## Evidence

Local, gitignored artifacts:

- [Initial summary](../../.pi/bench/20261009T225109Z-pi-acu-ac3ab9/summary.json), [isolation audit](../../.pi/bench/20261009T225109Z-pi-acu-ac3ab9/isolation.json), [raw events](../../.pi/bench/20261009T225109Z-pi-acu-ac3ab9/events.jsonl), [user confirmation](../../.pi/bench/20261009T225109Z-pi-acu-ac3ab9/user-confirmation.json).
- [Hands-off summary](../../.pi/bench/20261009T225329Z-pi-acu-f0901f/summary.json), [isolation audit](../../.pi/bench/20261009T225329Z-pi-acu-f0901f/isolation.json), [opening script](../../.pi/bench/20261009T225329Z-pi-acu-f0901f/workspace/open.ahk), [raw events](../../.pi/bench/20261009T225329Z-pi-acu-f0901f/events.jsonl).
- [Independent frame-host observation](../../.pi/bench/20261009T225329Z-pi-acu-f0901f/observer-verify-unclaimed.log), [screenshot](../../.pi/bench/20261009T225329Z-pi-acu-f0901f/unclaimed-calculator.png), [cleanup reconciliation](../../.pi/bench/20261009T225329Z-pi-acu-f0901f/cleanup-reconciliation.json), [final window probe](../../.pi/bench/20261009T225329Z-pi-acu-f0901f/observer-probe-reconciled.log).

Both actor and worker processes were verified exited. Temporary credential copies were deleted, the bench lock was released, no test server was started, and existing unrelated applications/services were preserved. Crash/output artifacts remain in each run directory and in ACU's normal `%LOCALAPPDATA%\ACU\logs\` and `%LOCALAPPDATA%\ACU\crashes\` directories.

For repeatable commands, isolation details and measurement definitions, see [bench/README.md](../../bench/README.md). Specification and follow-up: [issue #8](https://github.com/stanley50z/ahk-computer-use/issues/8).
