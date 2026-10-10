# Testbench 1, round 2: four configurations

Fresh sequential trials of all four arms on 2026-10-10, 15:58 to 16:10 UTC, after the ACU changes from the [round 1 latency analysis](testbench-1-latency-2026-10-10.md) and the new task-time measurement. Source: working tree after `dd5014d` (uncommitted). Scenario v3, same hash in every arm:

```text
976d8b3a978a2954173dd4a7da084a0ef205ee415f340e91be3d9242344373d2
```

**All four passed the task, the isolation audit, and recorded cleanup.** The independent observer read each owned Calculator window:

```text
128 + 465 × 12387 ÷ 138473 − 12343
= -12,173.403768243628721844691744961
```

The GPT arms used GPT-6.1 (`gpt-6.1-sol`) at low reasoning. The new `claude-acu` arm used Claude Code 2.1.295 with Haiku 5.5 (`claude-haiku-5-5`) at high effort, the one agreed exception, because Claude Code runs only Claude models. No parent coaching, retry, or implementation change happened during the timed runs. The classifier fix described under Limits was made while the CUA worker ran; it does not touch the actor.

## Measurements

Task time is the primary measurement: from the actor's session start, when it holds the skill, to the end of its last computer-use call. Writing `result.json` and the final answer are outside it.

| Measurement | Pi + ACU | Claude Code + ACU | Pi + CUA | Codex + native |
| --- | ---: | ---: | ---: | ---: |
| Task / isolation / cleanup | Pass | Pass | Pass | Pass |
| **Task time** | **32.90 s** | **95.47 s** | **133.64 s** | **227.08 s** |
| Relative to ACU | 1.00× | 2.90× | 4.06× | 6.90× |
| Wall time, secondary | 56.57 s | 112.28 s | 156.54 s | 240.83 s |
| Model response time | 43.645 s | 71.487 s, receipt-based | 90.887 s | Not exposed |
| Tool busy time | 4.641 s | 37.546 s | 64.247 s | 105.854 s |
| Model responses | 7 | 14 | 16 | Not counted by exec |
| Harness tool calls | 6 | 13 | 17 | 35 |
| Computer-use calls | 3 | 10 | 7 | 32 |
| Uncached input tokens | 8,617 | 28 | 40,067 | 55,809 |
| Cached input tokens | 28,416 | 278,883 read, 31,784 written | 342,912 | 1,803,264 |
| Output tokens, including reasoning | 995 | 15,196 | 1,529 | 3,034 |
| Reasoning subset | 0 | 9,260 | 22 | Not exposed |
| **Total tokens** | **38,028** | **325,891** | **384,508** | **1,862,107** |

Round 1 task times, replayed with the same definition, were ACU 40.62 s, CUA 112.62 s, and native 216.65 s. ACU is the only arm that changed between rounds. Its task time fell by 7.7 s and its responses from 10 to 7, on one sample each; CUA and native moved the other way by similar amounts without any change, which is the noise floor to keep in mind.

Pi's ACU wall time includes 7.76 s before `agent_start` this round, against about 1 s in round 1. That is harness startup, outside task time. Native uncached input is aggregate input minus cached input. Claude Code's model time is the receipt interval from its request status event to `message_stop`; its own `duration_api_ms` was 71.441 s, which agrees.

## What each configuration did

### Pi + ACU: three scripts, no sleeps

| Response | Requested next | Model time | Tool time |
| --- | --- | ---: | ---: |
| 1 | Read the skill | 5.406 s | 0.003 s |
| 2 | Write and run the launch script in one shell call | 8.618 s | 2.504 s |
| 3 | Write and run the calculation script in one shell call | 7.544 s | 1.215 s |
| 4 | Screenshot of the owned window | 6.373 s | 0.827 s |
| 5 | Read the PNG | 3.505 s | 0.089 s |
| 6 | Write result evidence | 7.663 s | 0.002 s |
| 7 | Final answer | 4.536 s | |

The launch script followed the skill's example: `AcuLaunch("calc.exe", "Calculator")`, ownership written from inside the script, and every button printed through `FindElements`, so no separate tree turn. The calculation script invoked the 27 buttons by AutomationId with no sleeps at all and read the display back in the same run: 1,214 ms in the launcher. The actor then chose to screenshot the window, which counts as computer use and ends the task at 40.66 s. The three turns after it, reading the image, writing `result.json`, and answering, are the part the new definition excludes.

The actor reported no hiccups and called semantic activation fast and reliable. Its task time is now four model responses plus 4.5 s of tools. The floor for this task is three responses.

### Claude Code + ACU: correct, with a self-inflicted detour

Haiku 5.5 used `AcuLaunch` and the one-shell-call write-and-run pattern from the first script. Three things cost it time:

- Its launch script called `FileDelete` on a file that did not exist, which throws in AutoHotkey, so the script died after printing the window identity and before writing ownership. It recovered by writing `ownership.json` with the file tool before any click.
- It decided to switch the already-Scientific window to Standard mode through the navigation pane, entered the expression, saw a left-to-right result, recognised that precedence was wrong, switched back to Scientific, and entered the expression again. Seven of its ten computer-use calls were tree dumps or mode changes.
- It used fixed sleeps (150 ms per button plus 500 ms, and 600 to 800 ms around mode changes) rather than `AcuWaitUntil`, and ran `tree.ahk` seven times instead of folding the look into the launch script.

Its responses started fast, about 0.8 s to first visible output, but it produced 15,196 output tokens of which 9,260 were reasoning at high effort. The actor's feedback: the skill and tree output were clear; it asked for notes that Calculator's Standard mode ignores precedence, that `CalculatorExpression` is offscreen with zero bounds and readable only by name, and that `FileDelete` throws on a missing file. The first is task knowledge, not skill material. The `CalculatorExpression` note is already covered by the skill's screen-reader-text paragraph. The `FileDelete` point is a fair one-line addition.

### Pi + CUA: same shape as round 1

Sixteen responses. The first `list_windows` call used the ended label `calc-v3` and was rejected, the same hiccup as round 1; the actor then used `calc-v3-run1602`. Its helper `operate.py` ran 27 snapshot-bound clicks with a state refresh after each in 50.26 s, about 1.86 s per pair. The actor said the snapshot-bound activation was reliable, the documentation bloated, and the accessibility expression text misleading. The parent ended `calc-v3-run1602` after cleanup, outside timing, and `list_sessions` then returned none. The shared daemon was not stopped.

### Codex + native: 27 model-mediated clicks again

Thirty-five tool calls. Accessibility was null again, so the actor defined a `clickButton` helper that clicks a screenshot coordinate and refreshes the capture, then called it once per button from a separate model turn: 3.33 s of runtime per click and about the same again between clicks. It reported that an initial screenshot was forwarded as text. Task time ended at the equals click; the `result.json` write came 7.1 s later through Node's filesystem API.

## Repeat ACU trials, 17:03 to 17:05 UTC

Three more `pi-acu` trials, authorized after round 2 to size the gain, with no further ACU change:

| Trial | Outcome | Task time | Responses | Total tokens |
| --- | --- | ---: | ---: | ---: |
| `20261010T170307Z-pi-acu-152395` | Blocked: the launch script ended with `restore skipped: cursor moved by someone else`, the actor stopped as the skill requires | 13.04 s, no calculation | 4 | 16,867 |
| `20261010T170347Z-pi-acu-b71dcb` | Pass | 31.94 s | 7 | 38,137 |
| `20261010T170450Z-pi-acu-361d88` | Pass | 27.27 s | 7 | 38,125 |

The blocked trial is the same signal as round 1's first attempt, where the user confirmed concurrent mouse use; whether the cursor moved this time is not established by the bench, which only records that the cursor was not where the prelude left it. Its window was closed by cleanup; it is excluded from timing.

The three completed trials after the changes, round 2 plus these two, took 32.90, 31.94, and 27.27 s: median 31.94 s against round 1's 40.62 s. All three had the same seven-response shape: skill, launch script with ownership and button list, 27-button chain, screenshot, read image, write result, final answer. The task time ends at the screenshot each time, which the actor chose to take because the accessibility expression reads `Minus (`. Ending at the calculation instead would give 25.7, 26.0, and 21.7 s. Per-response model time was 3.6 to 8.6 s with 2.4 to 4.5 s before the first visible token, which is where the remaining spread between trials comes from.

### Findings across all ACU trials

Per-turn replay of every completed ACU trial, before and after the changes (`.pi/artifacts/testbench-1-analysis/acu-trials-comparison.log`, produced by `compare_acu_trials.py` beside it):

| Trial | Responses | To result | Task time | Model time | Model per response | Calc chain | Tokens |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Old skill, `run.py`, v2 | 8 | 33.74 s | 33.74 s | 34.67 s | 4.33 s | 5.01 s | 45,063 |
| CLI-only rerun, v3 | 13 | 43.32 s | 51.02 s | 59.73 s | 4.59 s | 4.38 s | 80,162 |
| Round 1 | 10 | 40.62 s | 40.62 s | 43.07 s | 4.31 s | 4.41 s | 52,784 |
| Round 2 | 7 | 25.70 s | 32.90 s | 43.64 s | 6.24 s | 1.21 s | 38,028 |
| Repeat 2 | 7 | 25.98 s | 31.94 s | 43.09 s | 6.16 s | 1.31 s | 38,137 |
| Repeat 3 | 7 | 21.67 s | 27.27 s | 40.39 s | 5.77 s | 1.41 s | 38,125 |

"To result" is session start to the end of the calculation call, the moment the correct display existed.

1. **Time to the result fell by about 15 s, from 40.6 s to a median of 25.7 s.** The latency analysis had predicted 14.65 s from removing the four separable turns. The mechanism is confirmed: three responses reach the result instead of six to eight, every time.
2. **Total model time per run did not change**: 43.1 s before, 43.6, 43.1 and 40.4 s after. The remaining responses are heavier, 6.1 s each instead of 4.3 s, because each writes a whole script and runs it, and because the actor now spends four responses after the result. Fewer, heavier turns; the saving is entirely waiting that used to sit in front of the result.
3. **A new tail appeared.** All three post-change actors took a screenshot after the calculation and read it; the round 1 actor did not. The skill's new sentence that names are screen-reader text, met with Calculator's `Minus (`, appears to prompt a visual check. It costs about 6 s of task time and two responses, the largest remaining lever that is not provider latency. A skill line saying that tree text is sufficient evidence for a text result would remove it; not applied.
4. **The calculation chain dropped from 4.4 to 5.0 s to 1.2 to 1.4 s** with zero `Sleep` calls in every post-change script and a correct result each time. The launch call grew from 1.4 s to 1.7 to 3.3 s because it now waits for the window and lists 48 buttons; the spread is Calculator start-up.
5. **Behaviour is now near-deterministic.** Seven responses in all three trials, near-identical scripts, and 38,028, 38,137 and 38,125 total tokens. Round 1 used 52,784.
6. **The floor is provider latency.** First visible output arrives 2.4 to 4.5 s into each response, about half of model time. With three responses to the result, the floor is roughly 15 to 18 s; the trials sit at 22 to 26 s.
7. **The blocked repeat was real mouse use.** The observer's cursor readings were 2601,2133 before the actor, 1694,1627 after it, and 2682,2141 at cleanup binding. In every passed trial the cursor stayed on the same pixel throughout. The takeover rule fired correctly. Two of eight ACU trials so far were blocked this way, both with physical movement; it is a shared-desktop hazard, not a defect.
8. **Pi start-up varies.** `agent_start` came at 1.0 s in most trials but 7.8 and 8.1 s in two, each the first trial after a pause. It inflates wall time only.

## Cleanup

Each worker closed only its claimed window after binding the independently observed identity, found no remaining new Calculator windows, reloaded the saved cursor scheme and checked the OS showing flag, deleted its temporary credential copy, and released the controller lock. Independent process inspection after the last run found none of the eight worker and actor PIDs alive, and the same check after the three repeat trials found their six PIDs gone, no credential copy in any `agent-home`, and no `active.lock`. Owned windows: 4587684, 3479880, 7476424, 7541960. The cursor check remains an OS flag, not pixel-level proof.

## Limits

- One sample per arm; not a statistical ranking. Cache and latency conditions differ between arms and rounds.
- The live summaries of the first three arms were computed by a classifier that missed `acu run` after a heredoc, because a word boundary does not exist after a JSON-escaped newline. The fix, matching on raw argument text, landed while the CUA worker ran, so only the native run used it live. Each run directory has `metrics-replayed.json` from `python bench/run.py analyse` with the fixed classifier; the table uses those. The only task time that changed is Claude Code's: its live `summary.json` says 85.98 s because the last calculation call had been missed.
- Claude Code's safe mode disables CLAUDE.md, skills, hooks, and plugins by flag; the stream lists tools, MCP servers, and skills, which were audited, but not memory files.
- The Pi ACU actor's screenshot was its own choice; without it the task would have ended at the calculation call at 33.46 s.

## Evidence

Local, gitignored; may contain desktop and account metadata.

- [Combined JSON](../../.pi/bench/testbench-1-20261010-1558.json), [CSV](../../.pi/bench/testbench-1-20261010-1558.csv).
- Pi + ACU: [run](../../.pi/bench/20261010T155836Z-pi-acu-b28bbb/summary.json), scripts in `workspace/`, [screenshot](../../.pi/bench/20261010T155836Z-pi-acu-b28bbb/calculator-result.png).
- Claude Code + ACU: [run](../../.pi/bench/20261010T155949Z-claude-acu-b63f31/summary.json), [isolation](../../.pi/bench/20261010T155949Z-claude-acu-b63f31/isolation.json), scripts in `workspace/scripts/`, transcript under `agent-home/projects/`.
- Pi + CUA: [run](../../.pi/bench/20261010T160215Z-pi-cua-e09054/summary.json), [helper](../../.pi/bench/20261010T160215Z-pi-cua-e09054/workspace/operate.py), [lifecycle release](../../.pi/bench/20261010T160215Z-pi-cua-e09054/lifecycle-cleanup.json).
- Codex + native: [run](../../.pi/bench/20261010T160528Z-codex-computer-use-d2a669/summary.json), [isolation](../../.pi/bench/20261010T160528Z-codex-computer-use-d2a669/isolation.json).

Specification and running log: [issue #8](https://github.com/stanley50z/ahk-computer-use/issues/8).
