# Handoff: Testbench 2 and the ACU follow-up

Historical handoff retained for preparation provenance. Its remaining-work and per-run approval notes are superseded by `docs/reports/testbench-2-first-run-2026-10-11.md`, `bench/README.md`, and the current project `AGENTS.md`. TB2 is now runnable; the first matched comparison measured a 28.0% median task-time reduction with higher median shape IoU. Numeric shape pass thresholds remain uncalibrated.

## Current state

The conversation began with designing an Illustrator Pen-tool benchmark, produced starter assets, then addressed ACU friction found during exploration. The implementation and assets were committed and pushed to `origin/main` in `e9d33fd54f1aceb4752f23f488790cc02994a62a` (`feat: Preserve desktop state and prepare English input`). Local/upstream revisions matched and the working tree was clean before creating this handoff. This handoff itself is not committed.

The likely next task is to finish Testbench 2's design and implementation. A runnable scenario, final actor prompt, scoring thresholds, and benchmark trials have not been completed. Follow the pointers below rather than reconstructing decisions from early proposals in the conversation.

## Read for the next task

| Need | Authoritative pointer |
| --- | --- |
| Testbench 2 scope and confirmed user decisions | [Issue #10](https://github.com/stanley50z/ahk-computer-use/issues/10) |
| The two files to give the actor, and verified starter contents | `bench/assets/testbench-2/README.md` |
| Official package locations, guidelines, asset fingerprints, framing/color mismatches, and grading proposals | `docs/reports/testbench-2-source-inspection-2026-10-11.md` |
| Existing benchmark profiles, isolation, continuous task-time definition, approval requirements, and cleanup | `bench/README.md`; inspect `bench/run.py` before extending the runner |
| Current ACU usage | `acu/SKILL.md` and `README.md` |
| Replacement of restoration policy and English-input behavior | `docs/adr/0009-persistent-desktop-state-and-english-input.md` |
| ACU fixes, review dispositions, focused validation, and evidence locations | `docs/reports/acu-illustrator-retro-2026-10-11.md`; [issue #11](https://github.com/stanley50z/ahk-computer-use/issues/11) |

Keep the source-inspection report and official vectors/guidelines in maintainer context. Actor handoff is the prepared starter and separate raster reference; provenance is not actor input. The latest starter decision replaced the earlier embedded/locked-reference proposal. Timing and appearance-setting decisions are recorded in issue #10 and the source report.

## Continue carefully

1. Read issue #10 and the starter README, then identify the remaining prompt, grading, and runner decisions. The source report's grading section is a proposal, not an approved numeric pass threshold.
2. Resolve any decisions that affect what the actor must do before implementing the scenario. Do not assume the official raster/vector variants share framing or export settings; the source report documents their differences.
3. Use the current ACU skill for desktop work. Some archived preparation scripts under `.pi/testbench-2-design/` call the removed `AcuKeepForeground()` API; treat them as historical evidence, not current recipes.
4. Get fresh approval for any desktop integration checks or benchmark trials. Previous approval covered this session's focused disposable-window checks only. The user needed the computer during validation; coordinate idle desktop time and distinguish interruptions from product failures.
5. Read the source report's final cleanup note before touching pre-existing Illustrator documents. Re-inspect current window state rather than relying on old handles or discarding unsaved work. The latest cleanup found no task fixture windows/processes left; no temporary server was started.

Use the project's `uv` environment for checks. Exact focused commands and results are in the ACU follow-up report; do not rerun the full desktop suite as a routine gate. Runtime logs/crash-report paths are documented in `README.md`; local validation evidence is under `.pi/logs/acu-illustrator-fixes/`, and asset-preparation evidence under `.pi/testbench-2-design/`.

The application-dependent investigations in [#12](https://github.com/stanley50z/ahk-computer-use/issues/12) and [#13](https://github.com/stanley50z/ahk-computer-use/issues/13) are deferred. They are not requirements to expand while finishing the benchmark. Benchmark cleanup and vendored `acu/lib/UIA.ahk` were preserved; read the repository's constraints before changing either.

The commit hook owns background Wiki publication. Finish project commit/push verification without waiting for or repairing that job.

## Suggested skills

- **acu**: load before any explicitly authorized desktop inspection or Illustrator action.
- **tdd**: load before implementing the scenario, checker, or runner changes; test the agreed public behavior with focused checks.
- **writing-for-agents**: use when drafting the actor prompt/skill instructions or editing steering documents.
- **domain-modeling**: use if changing architectural decisions or terminology; current vocabulary lives in `CONTEXT.md`.
- **code-review**: review completed changes against the originating issue and a pinned comparison point.
- **commit**: use when the user requests the next commit.
- **unslop**: apply to user-facing writing.
