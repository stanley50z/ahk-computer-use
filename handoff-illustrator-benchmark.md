# Historical handoff: Illustrator benchmark before the v0.5 rerun

This handoff is archived context. The state and next steps below describe the period before the completed v0.5 rerun and the subsequent v0.6 prompt/reference revision, not the current checkout.

For current behavior, read `bench/README.md`, `bench/scenarios/illustrator-pen-export.md`, and [issue #21](https://github.com/stanley50z/ahk-computer-use/issues/21). The desktop maximization/Color Picker check passed before the [completed v0.5 round](docs/reports/illustrator-pen-export-v05-round-2026-10-12.md). v0.6 is implemented and validated offline; another benchmark round requires a fresh user request. Historical outcomes remain unchanged.

## State at the original handoff

- Checkout: `main`, committed and pushed at `0878fa5dbb01b58e4735a3bb992b9b1fe8e96c17` — `feat: Simplify Illustrator trials and harden desktop cleanup`. Local/upstream revisions matched and the worktree was clean before this handoff was written.
- **Desktop work is paused until the user announces PC availability.** Do not start Illustrator, desktop integration tests, or another benchmark round automatically. The user stopped the previous round for lack of time; subsequent changes were offline only.
- The current protocol is **v0.5 with three trials per configuration and all-successes averaging**. Read `bench/README.md`, `bench/scenarios/illustrator-pen-export.md`, and `bench/aggregate.py::TRIAL_POLICY` for the authoritative rules and fixed model/runtime profiles. Do not revive the older five-trial or single-drawing-attempt rules.
- No benchmark actor or test server was left running. Final resource verification for the completed round is linked below. Shared services and unrelated applications were preserved.
- No commit/push is requested for this new handoff file. The previous commit is complete; do not wait for or repair its background Wiki job.

## What the user was addressing

The user wanted the benchmark to measure drawing/export rather than setup and bookkeeping. Their questions led to changes in initial window setup, calibration, drawing restrictions, provider-failure classification, trial count, and Color Picker cleanup. Implementation details are in commit `0878fa5` and the current benchmark guide, not repeated here.

The latest scope and superseding decisions are tracked in:

- [Issue #20: v0.5 scope](https://github.com/stanley50z/ahk-computer-use/issues/20), including the three-trial follow-up.
- [Issue #14: ownerless Color Picker cleanup](https://github.com/stanley50z/ahk-computer-use/issues/14).
- `.pi/benchmark-v05/spec.md` describes the earlier stage of the work; its five-trial wording is superseded by `.pi/three-trials-picker/spec.md` and the current issue #20 body.
- [Issue #19](https://github.com/stanley50z/ahk-computer-use/issues/19) contains the older single-attempt specification and a superseding comment. Its original body is historical, not the current drawing policy.

## Next work, in priority order

### 1. Validate the desktop changes when availability is announced

The window normalization and ownerless Color Picker fix are implemented but **not live-validated**. The marked integration test is:

`tests/test_bench_illustrator_pen_export.py::test_illustrator_pen_export_real_illustrator_preparation_and_owned_document_cleanup`

It now checks initial maximization, explicit maintainer-only calibration, the actual ownerless picker, protected-handle refusal, and owned-resource teardown. Read the test and `tests/conftest.py` for the existing desktop gate before running it. Use a focused check, not the entire desktop suite. Keep #14/#20 open until the outstanding live behavior is verified.

Relevant implementation:

- `bench/illustrator/window.ahk`
- `bench/illustrator/dismiss-dialogs.ahk`
- `bench/illustrator_pen_export.py`
- `tests/scripts/illustrator_color_picker.jsx`

**Do not overclaim the window fix:** it addresses missing initial maximization. The cause of later resizing into the upper-left quarter remains unconfirmed. No vendor/runtime patch or mid-attempt window repair was added.

### 2. Resolve export filename/path bookkeeping

**This is still unimplemented.** The user identified filename/destination handling as something the testbench should supply. Removing the blank calibration export stops normal setup from exporting into `grading/`, but does not automate the destination/name. The current prompt still requires `Cloud9-Recreated.png` and suffix renaming.

Do not claim this problem was solved, or quietly add a mid-trial helper. Agree on how the testbench owns naming/destination while preserving the intended export interaction before implementing that change.

### 3. Keep other findings separate

- Scratch files were temporary input scripts, screenshots/crops, and CLI-response JSON, not actor deliverables. The user asked what they were; **the scratch-write policy was not changed**. Its route-dependent enforcement remains a comparison limitation documented in the completed-round report.
- Runtime/API discovery and wrapper construction were discussed, but no interface or skill changes were authorized in that exchange.
- Metric attribution limitations remain tracked in [issue #18](https://github.com/stanley50z/ahk-computer-use/issues/18). Do not silently turn incomplete ledgers into complete timing/code-share claims.
- A new benchmark round, if requested, must use fresh directories and the current protocol. Do not reuse the previous round's launch helpers/schedule.

## Validation and review evidence

Latest offline validation and policy replay:

- `.pi/three-trials-picker/commit-checks.log` — fresh checks immediately before committing; desktop test intentionally excluded.
- `.pi/three-trials-picker/real-policy-check.log` — real assets/profile preparation and archived metrics used only as regression input, with original bytes preserved.
- `.pi/three-trials-picker/spec-review.md`
- `.pi/three-trials-picker/standards-review.md`
- `.pi/three-trials-picker/review-dispositions.md` — findings resolved before commit.
- `.pi/three-trials-picker/fixture-source.md` — source references for Illustrator's real Color Picker fixture API.

Earlier v0.5 checks and review dispositions are in `.pi/benchmark-v05/`. In particular, `real-evidence-check.log` verifies classification of both recorded provider failures without rerunning actors. The regression suite also covers provider-error persistence through malformed transcript and cleanup failures.

## Historical round: preserve, do not rerun or regrade

Report: `docs/reports/illustrator-pen-export-neutral-round-2026-10-12.md`.

Evidence root: `.pi/rounds/illustrator-pen-export-20261012T014917Z/`.

Useful entry points:

- `freeze.json`, `round-closed.json`, `aggregate.json`
- `review-01.json` through `review-05.json`, `review-dispositions.json`, `metric-review.json`
- `all-outputs.png`, `final-cleanup.json`, `scratch-cleanup.json`
- `attempts/<slot>/` for original sessions, metrics, images, logs and failures

That round used v0.4 and the old aggregation policy. The user's final-slot interruption is recorded explicitly, without invented launch/session/usage data. Its report contains all outcomes and qualifications; do not duplicate or reinterpret its counts using v0.5 rules. Frozen benchmark source is under its `source/` directory. Historical helper scripts that import today's aggregator are not a supported way to regenerate old five-trial results.

The older root `handoff-testbench-2.md` is historical context, not this handoff's current plan.

## Safety and debugging reminders

Read project `AGENTS.md` and `bench/README.md` before further work. Preserve pre-existing documents/windows and original evidence. Maintainer cleanup may cancel an independently attributed task dialog, but must never advance or repair actor work. ACU skills must stay benchmark-neutral.

Persistent debugging locations are documented in `bench/README.md`: per-run `worker.log`, observer logs, `failure.json`, and crash reports; desktop fixture evidence under `.pi/illustrator-pen-export-validation/native-check-*/`; ACU runtime history under `%LOCALAPPDATA%/ACU/logs/` and crash reports under `%LOCALAPPDATA%/ACU/crashes/`.

## Suggested skills

- **acu** — load before any authorized desktop validation; use the project skill for maintainer desktop work. Benchmark actors still use their assigned runtime through the isolated controller.
- **diagnosing-bugs** — for live reproduction of remaining resizing behavior or a failed cleanup regression; do not substitute speculation for a reproduction.
- **tdd** — before further implementation; use the existing public preparation, analysis, aggregation and cleanup seams.
- **code-review** — after substantive changes; distinguish scope findings from standards findings and retain review dispositions.
- **unslop** — apply to user-facing explanations and reports.
- **commit** — only when asked to commit the next changes; include the appropriate visible non-secret files and verify the final remote state.
