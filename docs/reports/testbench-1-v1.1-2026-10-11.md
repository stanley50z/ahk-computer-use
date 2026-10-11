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

## Candidate ACU changes, not applied

- Skill: say outright that `Send` treats `+ ^ ! #` as modifiers and that an expression or any literal text goes through `SendText`. The rule is there; it needs to be impossible to miss.
- `AcuTree`, or `AcuLaunch`: wait until the window's tree has more than its frame before returning, bounded like the existing retry.

## Cleanup

Each worker closed only the observed new Calculator after identity binding, reloaded the cursor scheme, deleted its credential copy, and released the lock. Independent inspection: no worker or actor PID alive, no credential copy, no lock. CUA sessions empty after the trial.

## Evidence

Local, gitignored: [combined JSON](../../.pi/bench/testbench-1-20261011-0302.json) and run directories `20261011T030240Z-pi-acu-0d5ed1`, `20261011T030356Z-claude-acu-cf8477`, `20261011T030502Z-pi-cua-a69cf0`, `20261011T030711Z-codex-computer-use-560ffa` under `.pi/bench/`, each with `prompt.txt`, `conduct.json`, `verification.json`, and `metrics-replayed.json`. Specification: [issue #8](https://github.com/stanley50z/ahk-computer-use/issues/8).
