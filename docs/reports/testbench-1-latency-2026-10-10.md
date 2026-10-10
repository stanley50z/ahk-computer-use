# Testbench 1 latency analysis and deadline removal

The 240-second value was an overall benchmark-worker safety default, not an ACU limitation or a measured requirement of the Calculator task. The user rejected it. It has now been removed from `bench/start.py`, `bench/run.py`, and the capture loop—not raised or made an implicit fallback. Future actors run until completion, failure, or explicit cancellation through `bench/stop.py`.

Manual cancellation, owned-process cleanup, ACU's per-script watchdog, observer waits, and backend request/startup timeouts remain separate protections. The three archived trials all completed below 240 seconds, so the old cap did not cause their recorded latency. Their original launch records and results are preserved.

This analysis replays the three saved traces. It does not rerun a desktop task or claim a runtime performance fix. The existing runs are a deterministic attribution baseline; verifying a speedup would require a later authorized benchmark.

## Main finding

**The 51.14-second ACU result is mostly an inefficient cold-agent interaction loop, not a 51-second AHK calculation.** The calculation itself was one CLI call lasting 4.41 seconds, of which the launcher measured 3.989 seconds. The agent consumed ten model responses before it finished.

| Recorded category | Pi + ACU | Pi + CUA | Codex + native |
| --- | ---: | ---: | ---: |
| Total actor wall time | 51.141 s | 127.985 s | 225.481 s |
| Model response durations | 43.071 s | 66.437 s | Not exposed |
| Tool busy time | 6.788 s | 60.018 s | 101.739 s |
| Wall minus the above measured categories | 1.282 s | 1.531 s | 123.741 s, model + orchestration + startup |
| Model requests | 10 | 15 | 35 |
| Result available by the end of this tool call | 41.638 s | 109.571 s | 217.973 s |
| Remaining time after that call | 9.503 s | 18.414 s | 7.508 s |

The result-availability times are **upper bounds from tool completion timestamps**, not instrumented instants of UI repaint. They exclude the parent's later independent verification/cleanup, as does actor wall time. Native residual time is not authoritative model latency. Its turn-only residual excluding tools is 121.649 seconds; the difference is about 2.092 seconds of startup/turn framing.

## ACU: where the 51 seconds went

About **84.2%** of wall time is accounted for by model responses, **13.3%** by tools, and **2.5%** by startup/orchestration/receipt overhead.

| Model response | What it requested next | Model time | Wait until first visible model delta |
| --- | --- | ---: | ---: |
| 1 | Read the ACU skill | 2.447 s | 1.779 s |
| 2 | Read scripting guidance | 5.222 s | 4.601 s |
| 3 | Write launch script | 6.489 s | 2.195 s |
| 4 | Run launch script | 4.106 s | 3.554 s |
| 5 | Read tree guidance | 2.716 s | 2.062 s |
| 6 | Run tree inspection | 3.383 s | 2.701 s |
| 7 | Write calculation script | 6.709 s | 3.409 s |
| 8 | Run calculation script | 2.594 s | 1.813 s |
| 9 | Write result evidence | 5.237 s | 2.785 s |
| 10 | Produce final answer | 4.168 s | 2.081 s |
| **Total** | | **43.071 s** | **26.979 s** |

After the first visible deltas, the responses took another **16.092 seconds**. First-visible-delta wait includes provider/network/queueing/prefill/buffering/hidden reasoning; the records do not separate those causes. It is not pure network delay or exact provider-side time-to-first-token.

The tools were quick except the intentional action chain:

| CLI call | Outer tool duration | Launcher's measured duration |
| --- | ---: | ---: |
| Launch/discover new Calculator and write ownership | 1.362 s | 1.139 s |
| Dump the tree | 1.007 s | 0.602 s |
| Invoke 27 buttons and read result | 4.408 s | 3.989 s |

The file reads and writes took roughly milliseconds each; **asking the model to request them in separate turns** cost seconds. The three CLI calls contribute about 1.05 seconds beyond their launcher measurements, including shell/console startup, logging and receipt overhead. Those are not the main bottleneck.

The calculation tool call did not start until **37.230 seconds** into the run. The correct displayed result was returned by **41.638 seconds**, but writing `result.json` and generating a final answer consumed almost another ten seconds. There is avoidable orchestration both before the actual input and after the result is known.

The action script also requests 27 sleeps of 90 ms plus a final 300 ms: **2.73 seconds of nominal fixed sleep requests**. Actual sleep time can differ because of timer granularity. This is a secondary opportunity, not an explanation of 50 seconds. Replace blind waits only with reliable observed-state waits; do not trade correctness for an unchecked burst of input.

### What should change next

Implemented on 2026-10-10 after this analysis, in the working tree: the guides moved into the skill, the skill now asks for write-and-run in one shell call and for folding the first look into the launch script, the prelude gained `AcuLaunch` and `AcuWaitUntil`, and the bench measures task time up to the last computer-use call. Item 4 below was judged bench-specific and left out. None of this has been measured in a new trial yet.

Keep the file-only `acu run` interface. Optimize how the calling agent uses it:

1. **Reduce mandatory guide-reading turns.** The skill currently requires a separate scripting-guide read, and the actor later reads the tree guide separately. Common short instructions can live in the main skill; independent references can be read in one response when needed. Avoid removing safety/targeting guidance just to shorten the prompt.
2. **Avoid separate model turns just to run a file it has just written.** A permitted sequential tool chain can write then execute a script without another model response. Dependent write/run calls must not be dispatched in parallel. This is a calling-workflow change, not an inline-code ACU operation.
3. **Combine launch with needed observation where predictable.** Collect the necessary controls/state in the launch script instead of an extra standalone inspection turn when that can be done safely through the provided UIA class. Do not nest another leased `acu run` inside an active run.
4. **Write result evidence from the action chain's observed facts.** Ownership already follows this pattern in the launch script. Doing the same for result evidence avoids the separate 5.237-second model response; preserve verification and ownership records rather than dropping them.
5. **Then examine the fixed sleeps.** Their nominal ceiling is only a few seconds in this sample; shaving them cannot address the much larger model-round-trip cost.

As an accounting counterfactual—not a measured speedup—erasing the four observed responses for separate launch execution, separate tree-guidance reading, separate calculation execution, and separate result-file writing would remove 14.653 seconds from this trace. Combined responses still require generation and may have different latency, so that is not a promise of a 36.49-second future run. More substantial improvement needs fewer cold-agent setup turns and/or lower response latency, not just a faster Windows executor.

This benchmark intentionally starts a fresh actor that must load its own instructions and write new scripts. It measures cold-agent task completion, not only `acu run` performance or a warm conversation with remembered selectors. Neither registry commands nor MCP are needed to address these findings.

## CUA: repeated runtime work plus extra setup

CUA spent **66.437 seconds in 15 model responses** and **60.018 seconds in tools**. It also waited **44.811 seconds in total before first visible model deltas**; the remaining response time was 21.626 seconds.

Major tool costs:

- Doctor/window enumeration: **4.173 s**.
- Successful launch: **5.242 s**.
- Open Navigation helper: **2.710 s**.
- Scientific-mode selection plus 27 arithmetic inputs in the helper: **45.200 s**.

That last helper refreshes state after every click and selects a fresh snapshot-bound token. It sends an initial state request, then **28 click/state pairs** (one mode selection and 27 arithmetic buttons), plus writes detailed action evidence. That is an amortized **1.61 seconds per click/state pair**, including the initial capture and evidence I/O rather than separately timing them. This is much more repeated runtime work than ACU's single 27-button chain. The saved trace does not separately time subprocess startup, daemon IPC, semantic invocation, and state refresh inside each pair; blaming any single layer would be speculative.

The existing `calc-v3` session was already ended. Its rejected launch cost a 3.304-second model response and a 0.261-second tool call before a new label was selected. A run-specific lifecycle label from the outset would avoid that particular detour.

CUA wrote ownership in a separate model response, then requested state to a file and separately read it, then generated a general-purpose helper in a 9.121-second response. Its main calculation helper began at **64.371 seconds**. The result was returned by **109.571 seconds**, followed by **18.414 seconds** for a screenshot, reading it, result evidence, and a final answer.

Useful next targets are less setup/evidence chatter, an initially unique session label, and profiling the click/state pair before changing runtime policy. Do not bypass snapshot-token freshness or silently delete postcondition checks.

## Native: 27 model-mediated input cycles

Native used **35 model requests** and **34 harness calls**, including 32 `node_repl.js` cells. Accessibility was null, so it performed one screenshot-bound pointer click followed by a fresh state capture per arithmetic button, as its skill directs.

- First click call began at **41.408 s**.
- Equals/last refresh returned at **217.973 s**.
- That input segment took **176.565 s**.
- The 27 click-plus-refresh calls consumed **89.858 s**, median **3.326 s** each.
- The gaps between those calls consumed another **86.707 s**, about **3.335 s per gap** across 26 gaps. Those gaps include model requests/orchestration, not application input.

A read-only state/screenshot call took **3.384 seconds**, very similar to the click-plus-refresh median. An earlier ownership plus accessibility-state call took **3.161 seconds**. By contrast, the final Node filesystem-only evidence cell took **0.011 seconds**. The evidence points to the **state-fetch/capture/helper path**, not a universal three-second `node_repl` cost or necessarily a slow click. These traces cannot separate capture, UIA, serialization, helper IPC and internal settling waits.

Two costs compound: about 3.3 seconds of runtime work per input and about 3.3 seconds between inputs. Twenty-seven buttons therefore dominate the elapsed time. The selected native skill requires fresh observation and separate state-derived actions; the comparison is also measuring that workflow policy. Do not propose batching stale coordinates or skipping required observation as an equivalent safe native trial.

The best next investigation is why the native state-fetch path takes about three seconds and why accessibility is unavailable here. That would need focused source/profiling work or a separately authorized runtime probe, not an assumption based on this trace alone. Exact model-response timing remains unavailable in Codex exec; its 121.649-second model-plus-orchestration residual is only an estimate.

## Validation and reproducible artifacts

- `uv run pytest tests/test_bench*.py -q`: **19 focused quiet checks passed**.
- Regression coverage verifies no overall deadline is advertised, a real stand-in process can finish beyond 240 accelerated measured seconds, explicit cancellation retains evidence and stops owned processes, and descendants cannot outlive the owned process tree unnoticed.
- No new actor/desktop run was performed, and the ACU/CUA/native skills or runtime implementations were not changed for speed.

Offline trace replay (no desktop action):

```text
python .pi/artifacts/testbench-1-analysis/analyze_timelines.py
```

Adding `--assert-acu-under-seconds 50` gives a deterministic red baseline on this recorded 51.141-second sample. It is an analysis check, not a new benchmark time limit. A future captured comparison can be supplied with `--comparison`.

Persistent local artifacts:

- [Timeline analysis](../../.pi/artifacts/testbench-1-analysis/timeline-analysis.json), [readable trace](../../.pi/artifacts/testbench-1-analysis/timeline-analysis.log), [slow-baseline check](../../.pi/artifacts/testbench-1-analysis/latency-baseline.log).
- [Deadline RED](../../.pi/artifacts/testbench-1-analysis/deadline-red.log), [GREEN](../../.pi/artifacts/testbench-1-analysis/deadline-green.log), [focused bench checks](../../.pi/artifacts/testbench-1-analysis/bench-checks.log).
- [Original complete comparison](testbench-1-2026-10-10.md) and its linked raw runs.

The original application screenshots, stdout, model receipts, and run metrics remain unchanged. No performance prediction above is presented as a validated runtime improvement.
