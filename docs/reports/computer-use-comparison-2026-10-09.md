# Calculator comparison: ACU, CUA and native Computer Use

All three isolated actors used **GPT-6.1 (`gpt-6.1-sol`) at low reasoning** and completed the same arithmetic through Calculator UI buttons:

```text
128 + 465 × 12387 ÷ 138473 − 12343
= -12,173.403768243628721844691744961
```

The user's clarified requirement accepts pointer clicks and semantic UI button activation. Keyboard/text input, direct field-value injection, clipboard input and calculating outside the application remain excluded. The previous ACU run satisfies this intended rule; its original stricter-policy verdict and source audit remain preserved.

**Task success is separate from desktop cleanup.** The user reported an invisible cursor after the comparison. Recovery succeeded with user confirmation, but the earlier automated cleanup verdict had checked windows/processes, not actual cursor visibility. This is a real cleanup failure, not a clean overall completion claim.

## Results from the completed task trials

| | Pi + ACU | Pi + CUA | Codex + native Computer Use |
| --- | ---: | ---: | ---: |
| Calculator result independently verified | Yes | Yes | Yes |
| Only corresponding skill/runtime in the valid run | Yes | Yes | Yes |
| UI method | Semantic button activation | Snapshot-bound UIA Invoke | Screenshot-coordinate button clicks |
| **Wall time** | **43.61 s** | **111.61 s** | **234.25 s** |
| Model response time, measured | 34.668 s | 56.809 s | Not exposed by exec stream |
| Model + orchestration time, estimated from residual | 34.834 s | 57.013 s | 125.950 s |
| Tool busy time, union of intervals | 7.659 s | 53.456 s | 106.016 s |
| Model requests | 8 | 14 | 36 |
| Harness tool calls | 7 | 15 | 35 |
| Uncached input tokens | 15,709 | 34,250 | 58,210 |
| Cached input tokens | 28,288 | 286,720 | 1,801,600 |
| Output tokens, including reasoning | 1,066 | 1,420 | 3,941 |
| Reasoning subset, already included in output | 0 | 18 | 22 |
| **Total tokens** | **45,063** | **322,390** | **1,863,751** |
| Effective output / measured model-response second | 30.75 tok/s | 25.00 tok/s | Unknown |
| Output / estimated non-tool second | 30.60 tok/s | 24.91 tok/s | 31.29 tok/s |
| Output / wall second | 24.45 tok/s | 12.72 tok/s | 16.82 tok/s |
| Illustrative wall at 100 effective output tok/s | 19.60 s | 69.00 s | 147.71 s, estimated |

This is one pilot completion per arm, not a statistical ranking. ACU used the recorded v2 prompt and was reassessed under the clarified intent; CUA/native used v3. The arithmetic/input goal is now accepted across all three, but exact prompt hashes differ. Starting Calculator was already in Scientific mode in the successful runs; no mode-change challenge was established.

Token totals sum API usage across requests, including repeatedly cached context. They are not unique prompt tokens, final context length, or uncached billing volume. Native model requests were counted from distinct cumulative usage records in its rollout, not from tool count.

### Interpreting time normalization

The primary comparison is observed wall time. On this pilot, CUA took about 2.56× ACU's time; native took about 5.37×. Most of the extra time was not explained by a dramatically different measured output rate: tool work and extra model round trips both increased.

The 100 tok/s illustration uses `wall − model-response seconds + output / 100`. This scales full-response latency, including queueing/prefill, and is not pure decoding-rate normalization. For native, model duration is unavailable; residual agent time minus the union of tool intervals substitutes **model plus orchestration time**, explicitly an estimate. Do not present its estimated 31.29 tok/s as provider-measured decoding throughput. Pi's alternative first-delta-preserving estimates remain in the run metrics.

## What happened in each arm

### ACU

The updated discovery guidance was followed: snapshot existing handles, launch, find a new matching title, retain its handle/PID. One action-chain script activated the number/operator buttons and read back the result.

Its argument-less UIA `.Click()` used semantic Invoke, not pointer movement. That library fact has not changed; the user clarified that it is an acceptable UI action for this test. Original automated and physical-policy-audited verdicts remain preserved beside the user-intent reassessment.

### CUA

The fresh agent loaded only `cua-driver` and its runtime/Windows references. It discovered the app through the driver, used the returned target and snapshot-bound element tokens, and ran a Python helper that refreshed state after each of 27 clicks. Every input was the driver's `click` operation; no keyboard/value-injection action appeared.

The driver reported accessibility Invoke routes. Individual effects were labelled `unverifiable`, so the agent read the display after each action rather than treating an action response as task proof. The final independent tree/screenshot check matched. The helper batched the controller loop into one shell call, but its 27 action/observation pairs still incurred runtime overhead. More extensive skill/schema material and additional model requests contributed to repeated cached context.

The agent reported no task hiccups. Its named CLI lifecycle `calc-v3` was subsequently explicitly ended; no shared daemon was stopped.

### Native Codex

The first attempt was **invalid setup**, not a fair tool trial:

- The configured app-owned native pipe did not exist.
- `skip_host_skill_discovery` did not remove the advertised host/builtin/project skills in the actual CLI transcript.
- The agent stopped before opening Calculator. The bench also mishandled PowerShell's UTF-8 BOM in its blocked-result JSON.

That attempt took 28.53 s and 163,442 tokens, recorded separately and excluded from the comparison table. Its raw failure and parsing traceback are retained.

The corrected native run used explicit per-skill exclusions and the shipped SDK's own Windows helper transport through `@oai/sky`. It did not manually launch a helper executable, implement a custom protocol, install another tool, change global discovery links or alter security settings. Browser support and other trusted services remained disabled. Actual persisted context confirmed GPT-6.1/low and only the computer-use skill declaration.

The actor encountered null accessibility data, recovered with screenshot-coordinate input, activated its owned window after an occluded first capture, and refreshed screenshots between inputs. It also reported cumbersome image handling/initial serialized image output. This generated many tool/model round trips and substantial repeated cached input. It finished within the 240-second cap, but only by about six seconds.

This is the Codex CLI with the native SDK-owned helper, not a live Codex Desktop app-owned-pipe session. In particular, lifecycle/cleanup behavior may differ from the Desktop app.

## Cursor cleanup incident

After completion the user could not see the cursor. Windows still reported `CURSOR_SHOWING` with cursor handle 65539, which demonstrates why that flag alone is insufficient evidence of visible rendering.

The recovery reloaded the **saved Windows cursor scheme** using `SystemParametersInfoW(SPI_SETCURSORS)` and set the current arrow. No saved pointer settings were changed, no unrelated process was killed, and the user confirmed the cursor was back. Log: `.pi/bench/cursor-recovery.log`.

The exact backend cause is not conclusively isolated. Abrupt native-helper shutdown is a candidate, but no new desktop reproduction was performed. Do not attribute it definitively to CUA or native Computer Use solely from the report timing.

The bench now reloads the configured cursor scheme after owned controller/window cleanup, checks the OS showing flag, requires cursor-restoration evidence before acknowledging cleanup, and prevents a cleanup exception from leaving an overall-pass summary. Quiet contract regression coverage passed. The emergency recovery was tested with user confirmation; the new automatic integration has **not** had another live benchmark run. Further desktop trials should validate cleanup first, not resume a routine suite.

## Validation and ownership

- Corresponding-only skills were audited from actual sessions in all valid runs; no parent coaching or tool implementation changes occurred during their timed action loops.
- The independent observer read the actual display and captured a PNG outside actor timing.
- Owned Calculator windows were closed, worker/actor processes were verified exited, and owned Windows job descendants were stopped.
- Temporary credential copies were deleted and the controller lock released. Existing unrelated applications and shared services were preserved.
- Actor JSON now accepts the UTF-8 BOM that PowerShell may emit; original actor files remain untouched.
- Seventeen focused quiet bench checks passed. No full desktop suite or additional live trial was run after the cursor report.

## Evidence

Local, gitignored data:

- [Comparison JSON](../../.pi/bench/calculator-comparison-v3.json) and [CSV](../../.pi/bench/calculator-comparison-v3.csv).
- ACU: [summary](../../.pi/bench/20261009T232142Z-pi-acu-fixed-d764a9/summary.json), [policy reassessment](../../.pi/bench/20261009T232142Z-pi-acu-fixed-d764a9/policy-v3-reassessment.json), [screenshot](../../.pi/bench/20261009T232142Z-pi-acu-fixed-d764a9/calculator-result.png).
- CUA: [summary](../../.pi/bench/20261009T233638Z-pi-cua-0e5a8f/summary.json), [button helper](../../.pi/bench/20261009T233638Z-pi-cua-0e5a8f/workspace/buttons.py), [verification](../../.pi/bench/20261009T233638Z-pi-cua-0e5a8f/verification.json), [screenshot](../../.pi/bench/20261009T233638Z-pi-cua-0e5a8f/calculator-result.png).
- Native: [summary](../../.pi/bench/20261009T234504Z-codex-computer-use-isolated-7b418b/summary.json), [action audit](../../.pi/bench/20261009T234504Z-codex-computer-use-isolated-7b418b/native-action-audit.json), [timing audit](../../.pi/bench/20261009T234504Z-codex-computer-use-isolated-7b418b/native-timing-audit.json), [verification](../../.pi/bench/20261009T234504Z-codex-computer-use-isolated-7b418b/verification.json), [screenshot](../../.pi/bench/20261009T234504Z-codex-computer-use-isolated-7b418b/calculator-result.png).
- Excluded native setup: [summary](../../.pi/bench/20261009T233909Z-codex-computer-use-5af6eb/summary.json), [isolation failure](../../.pi/bench/20261009T233909Z-codex-computer-use-5af6eb/isolation.json), [traceback](../../.pi/bench/20261009T233909Z-codex-computer-use-5af6eb/crash.txt).
- [Cursor incident record](../../.pi/bench/cursor-incident.json), [recovery log](../../.pi/bench/cursor-recovery.log), [CUA lifecycle cleanup](../../.pi/bench/cua-session-cleanup.log).

Specification and remaining instrumentation/cleanup questions: [issue #8](https://github.com/stanley50z/ahk-computer-use/issues/8). Run setup and definitions: [bench/README.md](../../bench/README.md). Artifacts may contain screen content or account metadata; do not publish raw transcripts without review.
