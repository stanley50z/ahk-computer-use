# Illustrator v0.8: drawing-only protocol validation

Implemented the user-confirmed [issue #23](https://github.com/stanley50z/ahk-computer-use/issues/23) protocol. No new benchmark round, commit or push was performed. Historical v0.7 trials and verdicts are unchanged.

## Actor task

The actor recreates the reference with the Pen tool, using genuine Bézier curves and direction handles for its curved portions. Many short straight-line segments may not approximate those curves. Fill remains #00AEEF; all Illustrator interaction uses the assigned runtime. The actor stops with the finished drawing open. No export, save, report or output filename is requested.

Five configurations, three scheduled trials each, all-successes/no-replacement aggregation, assets, recovery/measurement rules, allowed off-app geometry analysis and neutral skills remain unchanged. `acu/` and vendor runtimes have no changes.

## Maintainer export and failures

After actor conduct is audited, cleanup inspects and exports the independently owned live drawing as-is, outside actor measurements. It verifies an 800 × 800 opaque-white, non-interlaced PNG with approximately 72-ppi metadata before closing. Lossless PNG encoding preserves RGBA pixels; no shape, fill, curve, artboard or image-size repair occurs.

Ordinary export failures receive at most two attempts. Integrity/data refusals stop immediately; cleanup never repeats an already-refused collection. `maintainer_export_failure` and pre-export `maintainer_collection_failure` are infrastructure records, not invented actor conduct. Unexported drawings remain open on failure. Unknown native fill representations stay unknown until rendered evidence is available. Hidden/off-artboard references are not final drawing content.

Native control-point inspection rejects all-straight geometry, including flat coincident-anchor loops. Full-session review still must reject faceting in mixed paths: one genuine curved segment does not prove every reference curve was correctly constructed. No arbitrary anchor-count, curve-ratio or numeric quality threshold was added.

## Validation

- **109 focused quiet tests passed**, with the desktop test explicitly deselected there.
- **The focused real Illustrator integration test passed separately.** It creates a substantial Pen-tool Bézier handle, leaves the document unsaved, exercises protected ownerless-picker handling, retains hidden/off-artboard references, deliberately redirects the first export destination, verifies retry and the final PNG, and checks owned-document cleanup.
- Final PNG: 800 × 800, opaque, non-interlaced, pHYs density approximately 72.009 ppi (integer PNG density representation of 72 ppi).
- Final fixture source document was closed. Pre-existing documents and the borrowed Illustrator application were preserved. No benchmark lock, private credential copy, new fixed port or temporary server remained.
- Two independent review axes found error-path defects; focused RED/GREEN regressions cover their fixes. Original review reports and dispositions are retained. The manual `prepare-export.ahk` tool is documented as retained, not run by trials/tests.
- The first live check exported correctly but its test teardown attempted duplicate cleanup; that failure remains in `live-validation.log`. Teardown was corrected and subsequent live checks passed. No original failed evidence was rewritten.

## Resize diagnosis

The first v0.7 actor explicitly executed `WinRestore(t)` followed by `WinMove(0,0,1600,1000,t)`. The recording first shows the reduced footprint at 02:19.667, matching the recorded tool bracket. The actor's stated rationale is only "Resizing the canvas window"; coordinate convenience is an inference. No ACU/DPI fix or forced-maximization rule was added. See the [exact resize report](illustrator-window-resize-v07-2026-10-13.md).

## Persistent evidence

[Validation JSON](file:///C:/Users/13982/ahk-computer-use/.pi/benchmark-v08/final-validation.json) · [Quiet checks](file:///C:/Users/13982/ahk-computer-use/.pi/benchmark-v08/final-focused-checks.log) · [Real desktop check](file:///C:/Users/13982/ahk-computer-use/.pi/benchmark-v08/hidden-reference-green.log) · [Review dispositions](file:///C:/Users/13982/ahk-computer-use/.pi/benchmark-v08/review-dispositions.md)

Native fixture: `C:/Users/13982/ahk-computer-use/.pi/illustrator-pen-export-validation/native-check-7569f87f/`. It retains `drawing-verification.json`, `export.json`, `illustrator-cleanup.json`, generated JSX/result JSON with native stacks, `observer-*.log`, and `export-attempt-1-crash.txt` for the deliberate failed destination. Other RED/GREEN logs and complete failure output remain under `C:/Users/13982/ahk-computer-use/.pi/benchmark-v08/`; controller failures persist per-run `crash.txt` and `infrastructure-failure.json`.
