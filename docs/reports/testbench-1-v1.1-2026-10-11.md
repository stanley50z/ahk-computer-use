# Testbench 1 on scenario v1.1: the task alone, with a conduct audit

First run of the minimal prompt, 2026-10-11 03:02 to 03:09 UTC, source `5315008` plus the window-diff fix below. The actors received exactly:

```text
Open a new Windows Calculator window and calculate:

98765 * 432 / 1234 * 56 / 789 + 6543 - 4321

When done, write result.json in the workspace with these fields: observed_result (the displayed text), observed_expression, input_method, and hiccups (an array of concrete problems encountered).
```

Prompt hash `8db66cf472f7…`. No safeguard sentence: nothing about input routes, skill reading, ownership, other windows, or leaving the window open. The bench finds the actor's window by observation and audits conduct afterwards.

**All four passed the task, the isolation audit, the conduct audit, and cleanup.** Every display read `4,676.0458862027102809497692132297`.

## Measurements

| Measurement | Pi + ACU | Claude Code + ACU | Pi + CUA | Codex + native |
| --- | ---: | ---: | ---: | ---: |
| Model | GPT-6.1 low | Opus 5.5 low | GPT-6.1 low | GPT-6.1 low |
| Input route | Keyboard, then Invoke after a typing error | Keyboard, `SendText` | UIA Invoke by token | Keyboard, `press_key` |
| **Task time** | **44.13 s** | **16.38 s** | **103.51 s** | **54.09 s** |
| Wall time | 62.28 s | 26.73 s | 113.30 s | 59.37 s |
| Model response time | 45.509 s | 13.011 s, receipt-based | 37.542 s | Not exposed |
| Tool busy time | 11.315 s | 12.604 s | 74.506 s | 19.866 s |
| Model responses | 11 | 4 | 9 | Not counted by exec |
| Computer-use calls | 6 | 1 | 6 | 6 |
| **Total tokens** | **78,367** | **37,088** | **156,993** | **230,247** |
| Conduct | Pass | Pass | Pass | Pass |

One sample per arm; a different prompt and expression from every earlier round, so no row compares directly with them.

## What changed when the prompt said nothing

**Three of four actors typed.** With no instruction either way, the keyboard became the default for everyone except CUA, whose skill ranks snapshot-bound accessibility actions first and whose actor followed it. Under the earlier prompts the same models had pressed buttons every time; the restriction, and later the sentence listing routes, had been steering them.

**Claude Code + ACU: one computer-use call, 16.4 s.** Its single script launched Calculator with `AcuLaunch`, activated it, sent Escape, typed the expression with `SendText`, waited with `AcuWaitUntil` for the expression to show `=`, and printed display and expression. Four model responses, no reasoning tokens, one hiccup noted about screen-reader text. It then deleted its script, which the prompt no longer forbids; the transcript still holds it.

**Pi + ACU: the AutoHotkey `Send` trap, 44.1 s.** It typed the expression with `Send`, where `+` means Shift and `^` means Control, so `+6543` became `^543` and Calculator showed −4,321. The actor saw the wrong expression in the readback, recovered with a second script that cleared and invoked each button by id, hit a missing `clearButton` (Scientific mode names it `clearEntryButton` once an entry exists), switched to Escape, and finished: eleven responses. The skill says to use `SendText` for literal text and `Send` for keys; the actor did not follow it. It also reported that its first `AcuTree` right after `AcuLaunch` returned only the window frame and a second dump was needed: Calculator's content tree was not populated the instant the window appeared. The `UIA_E_TIMEOUT` retry does not cover that case, because the call succeeds with a near-empty tree.

**Codex + native: 54.1 s, its best by far.** Keyboard again, now all 31 keys in one cell at 8.0 s instead of one per cell; without the result-file ceremony the whole run took 8 tool calls and 230k tokens. Accessibility was null again; it read the result from the screenshot.

**Pi + CUA: unchanged in shape, 103.5 s**, 27 click-and-refresh pairs in a helper, result read from accessibility text. The daemon restart ran before the trial for the first time (`daemon-restart.json`, passed); the actor's label `calc-task` was accepted first time.

## The conduct audit's first run

Guarded files unchanged in all four trials: no actor touched the skill, the launcher, the bench, or its installed skill directory. No write or edit tool call left the workspace. The heuristic command scan flagged one item, the native actor's PowerShell path in a `Get-Content` read, which is noise.

The window check fired on CUA and native with the same handle, 66054, owned by `explorer.exe`. That window has existed all day and toggles its own visibility; the first version of the diff compared visible sets only, so a background window that became visible during a trial counted as new. Fixed: a handle listed visible or hidden in the before probe is pre-existing. The two `conduct.json` files were recomputed from their saved probes and carry a note; the fingerprints are now saved per run as `fingerprint-before.json` and `fingerprint-after.json` so file checks can be replayed too.

## Candidate ACU changes, applied in `319a1cd`

- Skill: `Send` treats `+ ^ ! #` as modifiers; text goes through `SendText`. Now stated in bold with the exact Calculator example.
- `AcuLaunch` waits until the window's tree stops growing before returning, and reports the count as `elements`.

## Three repeats per ACU arm after the fixes, 03:58 to 04:03 UTC

| Trial | Route | Task time | Responses | Computer-use calls | Tokens | Hiccups |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| pi-acu 3894c7 | `SendText`, Invoke on Equals | 15.90 s | 6 | 2 | 37,843 | none |
| pi-acu a28397 | `SendText` with `=` | 16.68 s | 6 | 2 | 37,743 | none |
| pi-acu 15801e | `SendText`, Invoke on Equals | 15.02 s | 6 | 2 | 37,945 | none |
| claude-acu 10a667 | Invoke by AutomationId | 17.54 s | 4 | 1 | 37,583 | none |
| claude-acu aa0890 | Clear, `SendText` with `=` | 19.54 s | 5 | 2 | 51,656 | its own wait predicate threw after typing; a read-only script recovered |
| claude-acu 5499af | Invoke by name, `AcuWaitUntil` per press | 16.18 s | 4 | 1 | 36,765 | none |

**Pi + ACU: median 15.90 s, range 15.02 to 16.68 s, six responses every time.** All three used `SendText`; none repeated the `Send` mistake that cost the first v1.1 trial 28 s. `AcuLaunch` reported `elements=76` in each launch, and each actor's first dump saw the full control set, so the empty-frame detour is gone too. The three trials differ by less than two seconds, and that spread is model latency: the two scripts took 2.7 to 3.0 s of tool time in every trial.

**Claude Code + ACU: median 17.54 s, range 16.18 to 19.54 s.** Two of three chose Invoke this time and one typed; the model alternates freely between the two routes with no instruction either way. The one hiccup was the actor's own AutoHotkey bug, an `InStr` with an empty needle inside its wait predicate, which it diagnosed from the error and recovered from in one extra call. Its first shell call still carries 4 to 8 s of Claude Code tool start-up that ACU's launcher does not see.

## Three repeats for the other two arms, 04:07 to 04:18 UTC

The same balance for CUA and native, so every arm has four v1.1 trials. All six passed task, isolation, conduct and cleanup; the daemon restart ran before each CUA trial and no stale label was hit.

| Trial | Route | Task time | Responses | Computer-use calls | Tokens |
| --- | --- | ---: | ---: | ---: | ---: |
| pi-cua 644e0f | Invoke by token, helper | 88.28 s | 9 | 5 | 208,774 |
| pi-cua 256092 | Invoke by token, helper | 106.43 s | 11 | 7 | 283,289 |
| pi-cua 4dd675 | Invoke by token, helper | 107.75 s | 11 | 7 | 200,747 |
| codex 2482dc | Keyboard, one cell | 52.45 s | n/a | 7 | 364,572 |
| codex 89d1d6 | Keyboard, one cell | 60.34 s | n/a | 8 | 427,832 |
| codex 21847a | Keyboard, one cell | 48.02 s | n/a | 6 | 229,711 |

CUA's helper, the 27 click-and-refresh pairs, took 53.8, 57.5 and 69.6 s of its three runs; every CUA actor reported the `Minus (` accessibility wording and checked a screenshot. Every native actor typed all keys in one cell of about 8 s and reported null accessibility.

## Scenario v1.1, four trials per arm

| Arm | Trials | Median task time | Range | Median tokens | Route chosen |
| --- | ---: | ---: | --- | ---: | --- |
| Pi + ACU | 4 | 16.29 s | 15.02 to 44.13 s | 37,894 | typed (1 of 4 recovered from a `Send` mistake, before the fix) |
| Claude Code + ACU | 4 | 16.96 s | 16.18 to 19.54 s | 37,336 | typed 2, invoked 2 |
| Codex + native | 4 | 53.27 s | 48.02 to 60.34 s | 297,410 | typed, one cell |
| Pi + CUA | 4 | 104.97 s | 88.28 to 107.75 s | 204,761 | invoked by token |

All sixteen trials passed every check. The ACU arms are the fastest by a factor of three over native and six over CUA, and use a fifth to an eighth of the tokens. The spread within each arm is now small relative to the gaps between arms. Combined record: `.pi/bench/testbench-1-v1.1-all-20261011.json`.

## Cleanup

Each worker closed only the observed new Calculator after identity binding, reloaded the cursor scheme, deleted its credential copy, and released the lock. Independent inspection: no worker or actor PID alive, no credential copy, no lock. CUA sessions empty after the trial.

## Evidence

Local, gitignored: [combined JSON](../../.pi/bench/testbench-1-20261011-0302.json) and run directories `20261011T030240Z-pi-acu-0d5ed1`, `20261011T030356Z-claude-acu-cf8477`, `20261011T030502Z-pi-cua-a69cf0`, `20261011T030711Z-codex-computer-use-560ffa` under `.pi/bench/`, each with `prompt.txt`, `conduct.json`, `verification.json`, and `metrics-replayed.json`. Specification: [issue #8](https://github.com/stanley50z/ahk-computer-use/issues/8).
