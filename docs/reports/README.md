# Benchmark reports and investigations

These are dated records of particular code, prompts, model configurations and benchmark policies. Their results and evidence are historical, not instructions for running today's checkout. Words such as "current", "latest" and "next" inside an old report refer to that report's snapshot.

## Latest report

[Combined Illustrator, TB3.1–TB3.4 and TB4 results](https://stanley50z.github.io/ahk-computer-use/reports/latest/) covers the 5 November 2026 round (75 trials, original final-output comparisons, and side-by-side video playback) and, in its own tab, TB4: ACU on Cua Driver Bench, 12 November 2026 (90 trials). The [20–21 October report](https://stanley50z.github.io/ahk-computer-use/reports/2026-10-22/) remains at its dated address. The public copy uses silent videos up to 720p; full-resolution clips and audio remain local.

The stable `reports/latest/` link points to the newest published report. GitHub Pages serves only the reviewed static bundle on the dedicated `gh-pages` branch, not this repository's `main` checkout. Local paths, raw sessions, logs and work documents are excluded from the public bundle.

## Current instructions

- [ACU installation, usage and debugging](../../README.md)
- [Benchmark scenarios, profiles, measurement and cleanup](../../bench/README.md)
- [Current Illustrator actor task](../../bench/scenarios/illustrator-pen-tool.md)
- [Domain terms](../../CONTEXT.md) and [architectural decisions](../adr/)
- [Project agent instructions and desktop approval](../../AGENTS.md)

Current Illustrator actors draw and leave the document open; maintainers export it unchanged. Current rounds use three scheduled trials per selected configuration and retain every reviewed success in averages, without token-based trimming. Old actor-export, single-attempt, five-trial or trimming specifications below remain evidence of earlier policies, not active requirements. ACU leaves desktop state in place; old restoration/keep-foreground/takeover and per-run-approval descriptions are superseded by the current instructions.

## Reports to start with

- [TB4: ACU on Cua Driver Bench, 2026-11-12](cua-driver-bench-acu-2026-11-11.html): all ten Windows tasks of Cua Driver Bench v2, 90 trials, next to the other drivers' published runs. The file name keeps the date of the first run.
- [Illustrator v0.11 round, 2026-10-20](illustrator-pen-export-v011-round-2026-10-20.html): all 15 scheduled slots, reviewed outcomes and comparison images.
- [Illustrator input/runtime audit, 2026-10-20](illustrator-shift-c-and-runtime-audit-2026-10-20.html) and [three-failure investigation](illustrator-three-failures-investigation-2026-10-20.html).
- [GUI-360 feasibility](gui-360-feasibility.html): source inspection and limitations behind the TB3 Office scenarios, not a current TB3 results report.
- [Historical four-trial turn-by-turn report](testbench-2-four-trials-turn-by-turn-2026-10-11.html): curated command/output evidence for the earlier four-configuration, actor-export task. Its timings and policies are not today's ranking or execution rules.
- [Original ACU progress snapshot](acu-progress-2026-10-08.html): implementation history before the current CLI and desktop-state policy.

Other dated files in this directory remain available as historical records. File names using Testbench 1/TB2 refer to Calculator/Adobe Illustrator Pen Tool (formerly Pen and Export); current CLI identifiers are in the benchmark guide.

## Public and local evidence

Raw native agent session archives stay local. Curated historical reports, including the turn-by-turn report, may retain selected commands, tool outputs, assistant task messages and comparison images. This is not a requirement to publish every trial's output collection.

Paths under `.pi/`, absolute `C:/...` paths, `file:///` links and local recording paths refer to private/local artifacts and may be unavailable in another checkout. They are provenance pointers, not promised public downloads. Do not bulk-publish raw sessions or logs to make those links work. Original results and evidence are not silently rewritten to match newer policies.
