# Calculator, round 3: in-script looking, Opus 5.5 on the Claude arm

Fresh sequential trials of all four arms on 2026-10-10, 20:40 to 20:48 UTC, after two changes since [round 2](testbench-1-round-2-2026-10-10.md): `AcuTree` and `AcuScreenshot` became prelude functions callable from inside a script, with `acu run tree.ahk` resolving without a path, and the Claude arm moved from Haiku 5.5 at high effort to Opus 5.5 at low effort. Scenario v3, same hash as before. Source: working tree, uncommitted.

**All four passed the task, the isolation audit, and recorded cleanup**, each showing `-12,173.403768243628721844691744961`.

## Measurements

| Measurement | Pi + ACU | Claude Code + ACU | Pi + CUA | Codex + native |
| --- | ---: | ---: | ---: | ---: |
| Model | GPT-6.1 low | Opus 5.5 low | GPT-6.1 low | GPT-6.1 low |
| **Task time** | **19.54 s** | **22.31 s** | **99.84 s** | **206.25 s** |
| Relative to Pi + ACU | 1.00× | 1.14× | 5.11× | 10.56× |
| Wall time | 33.76 s | 31.14 s | 115.03 s | 215.89 s |
| Model response time | 26.537 s | 18.036 s, receipt-based | 56.720 s | Not exposed |
| Tool busy time | 5.459 s | 12.498 s | 56.972 s | 103.322 s |
| Model responses | 6 | 5 | 12 | Not counted by exec |
| Harness tool calls | 5 | 4 | 13 | 35 |
| Computer-use calls | 2 | 2 | 6 | 31 |
| Uncached input tokens | 10,570 | 10 | 45,208 | 30,257 |
| Cached input tokens | 28,032 | 41,171 read, 12,754 written | 266,752 | 1,035,520 |
| Output tokens, including reasoning | 822 | 1,632 | 1,346 | 3,793 |
| Reasoning subset | 0 | 0 | 22 | Not exposed |
| **Total tokens** | **39,424** | **55,567** | **313,306** | **1,069,570** |

Task time runs from session start to the end of the last computer-use call. One sample per arm.

## ACU across the three rounds

| Round | Change tested | Task time | To result | Responses | Computer-use calls |
| --- | --- | ---: | ---: | ---: | ---: |
| 1 | Baseline skill | 40.62 s | 40.62 s | 10 | 3 |
| 2 and repeats, median | Guides inlined, write-and-run in one call, AcuLaunch, no sleeps | 31.94 s | 25.98 s | 7 | 3 |
| 3 | AcuTree and AcuScreenshot inside the script | 19.54 s | 19.54 s | 6 | 2 |

Round 3's calculation script pressed Clear and the 27 buttons, then called `AcuTree(target)` for the final state and `AcuScreenshot({app: target}, …)` for the picture, all in one 2.55 s run. The standalone screenshot call that ended every round 2 trial is gone, and with it the model response that requested it. Two things made up the 12.4 s drop from the round 2 median: the removed turn, about 7 s of model and tool time, and faster responses this evening, 4.4 s each against 6.1 s in round 2. The structural part is the removed turn; the rest is provider latency and will move around.

Ten responses to the result became three: read the skill, launch, calculate. That is the floor for this task under the current skill.

## What each configuration did

### Pi + ACU

Read the skill, then `launch.ahk`: `AcuLaunch`, ownership JSON assembled and written from inside the script, every button listed through `FindElements`. Then `calculate.ahk`: Clear, 27 invokes by AutomationId with no waits, `AcuTree(target)` printed, `AcuScreenshot` saved to the workspace. Task time ended there at 20.6 s. The actor then read the image, wrote `result.json`, and answered. No hiccups reported.

### Claude Code + ACU, Opus 5.5 at low effort

Five responses, the fewest of any ACU trial. Its launch script called `AcuLaunch` and then `AcuTree` twice, once for Text elements to read the mode header and once for anything named Toggle, so it confirmed Scientific mode without a separate turn. Its calculation script mapped each character of the expression to a button name, pressed Clear and the 27 buttons by name, slept 200 ms, and read the display and expression. It wrote ownership and result through the shell in the same calls, never touching the file tool. Zero reasoning tokens. Its feedback: the single-file manual was enough and the launch-plus-inspect example meant two action runs with no guessing; it would have liked a digit-to-button-name table and a mode check, both Calculator knowledge rather than skill material.

The first launch call took 8.70 s of tool time against 2.8 s for the Pi actor's, but ACU's launcher measured 1,187 ms for it, including Calculator start-up and the two dumps. The other 7.5 s sat in Claude Code's Bash tool on its first use, outside ACU; the second call showed 3.35 s against 1,259 ms measured, so that overhead shrinks but does not vanish.

### Pi + CUA

Twelve responses. The ended label `calc-v3` was rejected a third time in three rounds; the actor then used `calc-buttons-b7f333`, which the parent ended after cleanup with no sessions remaining. Its helper ran the 27 click-and-refresh pairs in 45.1 s. Feedback unchanged: reliable, documentation bloated, expression text misleading.

### Codex + native

Thirty-five calls, accessibility null again, one screenshot-coordinate click per model turn through a `clickButton` helper. Faster than round 2 by 21 s with 800k fewer tokens, consistent with fewer or smaller screenshots being returned; the structure was identical.

## Cleanup

All four workers closed only their claimed window after identity binding, found no remaining new Calculator windows, reloaded the cursor scheme, deleted their credential copy, and released the lock. Independent inspection after the last run: none of the eight worker and actor PIDs alive, no credential copy present, no `active.lock`. Owned windows: 4071720, 5905230, 4262080, and the native window bound by the observer.

## Evidence

Local, gitignored: [combined JSON](../../.pi/bench/testbench-1-20261010-2040.json), [CSV](../../.pi/bench/testbench-1-20261010-2040.csv), and the four run directories `20261010T204023Z-pi-acu-ef19a9`, `20261010T204109Z-claude-acu-eceea5`, `20261010T204208Z-pi-cua-b7f333`, `20261010T204430Z-codex-computer-use-ec515f` under `.pi/bench/`, each with `metrics-replayed.json`. Specification: [issue #8](https://github.com/stanley50z/ahk-computer-use/issues/8).
