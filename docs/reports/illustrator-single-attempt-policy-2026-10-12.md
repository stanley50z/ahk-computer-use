# Illustrator benchmark: neutral skill and one PNG attempt

> Historical v0.4 policy, preserved for its original trials. The one-attempt/actor-export, five-trial and token-trimming rules below are superseded. Use the [current benchmark guide](../../bench/README.md) for v0.11 drawing-only actors, maintainer export, three scheduled trials per configuration and all-successes/no-trimming averages. See the [report index](README.md) for evidence availability.

Specification: [issue #19](https://github.com/stanley50z/ahk-computer-use/issues/19).

## Decisions implemented offline

The benchmark tests Pen-tool use and export, not report writing or repeated visual optimization.

- **One actor deliverable:** `Cloud9-Recreated.png`. No actor `result.json`, other report, or saved editable AI is required. The blank AI remains an input.
- **One drawing attempt:** no full redraw, restarting completed sections or repeated refinement passes. Correcting accidental input or retrying an action that did not register is allowed. Export the first completed attempt even if imperfect.
- **Post-run quality observations:** unaligned foreground IoU and boundary error remain recorded, with no numeric shape pass threshold or scoring target in the actor prompt. Required PNG/export properties are still checked.
- **Simple report:** output image, extracted metrics, safeguard violations and one completion outcome. Existing internal logs remain debugging evidence, not additional actor obligations or competing headline verdicts.
- **Code share is descriptive**, not a goal, success criterion or trimming key. Inclusive host-call timing remains accepted and labeled; no fine-grained runtime instrumentation was added.
- **Exactly five attempts per configuration**, successful or failed, with no replacement trials. A complete round contains 25 attempts across the existing five configurations.
- **No benchmark-specific ACU prompt/skill guidance.** Illustrator/Pen workflows, geometry tips and menu recipes were removed from `acu/SKILL.md`; only general input, focus, popup and sparse professional-application UI-tree guidance remains. `AGENTS.md` records the permanent neutrality rule.

The task is now `Adobe Illustrator Pen and Export v0.4 (single attempt)`. Plans record the PNG-only deliverable, the five-attempt rule, the policy stamp `benchmark-neutral-v1`, and prompt/skill fingerprints. The starter/reference image bytes remain unchanged.

## Exact aggregation rule

| Successful attempts out of five | What is averaged |
| --- | --- |
| 5 | Sort by total API tokens, drop lowest/highest, average every metric over the same middle three |
| 4 | All four successes; no trimming |
| 3 | All three successes; no trimming |
| 2 | Both successes; no trimming |
| 1 | The one success; no trimming |
| 0 | No aggregate, not zero values |

Failures never enter any mean. They remain in the report with their available metrics, images and safeguard flags. Equal-token ties use persisted trial start order, not a reordered manifest. Missing metric values remain unknown; averages never silently switch to a different subset for one metric. Five successes with an unknown total-token sorting key cannot be trimmed, so the aggregate is withheld with a reason.

`bench/aggregate.py` is an offline extractor. A maintainer-authored round manifest lists all 25 run directories and explicit `safeguard_violations` arrays from session review. That bookkeeping JSON is not written by the benchmark actor. Pen-only and single-attempt compliance are reviewed from the full session; an image alone cannot establish those facts. The extractor rejects nonmatching profiles and historical tuned protocols, and never starts or replaces a trial. See [the benchmark guide](../../bench/README.md) for its input and command.

## PNG-only grading

`bench/illustrator_pen_export.py::verify_outputs` reads the output PNG directly. It ignores unsolicited report files, including malformed JSON, and does not require saved AI or vector-inspection evidence. Missing, corrupt or incorrectly exported images report ordinary completion problems rather than causing a report-parser crash. Drawing-quality measurements do not decide success.

The benchmark controller no longer runs saved-AI inspection for actor submissions. That inspection helper remains only for maintainer regression fixtures that check input geometry; it is not an actor task requirement.

A valid but crude blue rectangle is covered by a regression test: completion succeeds while the quality score stays poor. This makes the distinction between export completion and drawing quality explicit.

## No workaround for Codex computer use

No runtime/vendor changes or actor assistance were added. The actor must encounter its tool's actual capabilities and limitations.

[Issue #14](https://github.com/stanley50z/ahk-computer-use/issues/14) is a separate post-run cleanup defect: after a CUA attempt, Illustrator's ownerless Color Picker prevented the maintainer observer from reactivating the main frame. Recognizing and cancelling a verified task-created dialog after the actor stops is cleanup, not solving the task. This preparation change does not fix or exercise that issue, and does not compensate for Codex computer-use drawing failures.

## Historical data

Previous sessions, images, manifests, metrics and verdicts were not rewritten. Earlier ACU trials included application-specific skill guidance and repeated refinement; those runs remain development evidence, **not a neutral v0.4 baseline**. The previous 28% elapsed-time improvement is also historical, not a claim under the new token/call-time policy.

The next meaningful comparison requires new sessions under the neutral skill and v0.4 prompt. Do not retroactively call an earlier malformed-manifest trial a new-protocol pass, or mix its profile hashes with the new cohort.

## Validation and current pause

**90 focused quiet tests passed; one desktop integration test was intentionally deselected.** Coverage includes:

- no Illustrator/Pen-specific recipes in the skill;
- PNG-only prompt/preparation and unchanged input asset hashes;
- missing/corrupt PNGs and ignored unsolicited malformed JSON;
- quality observation without a shape threshold;
- five-attempt trimming, every failure count, tie order, unknown metrics and one retained cohort for all means;
- public aggregation CLI across all five configurations, failed/corrupt metric handling, profile mismatch and historical-protocol rejection.

All five profiles were prepared offline with matching prompt hashes and the new policy stamp. A copy of the previous real Pi+ACU PNG was inspected under the new image-reader interface without an actor JSON or saved AI. Its quality score was unchanged. This was an artifact-reader regression, **not a new actor trial or a retroactive method verdict**.

No Illustrator session, desktop action, new model actor, test server or localhost port was started. Read-only review sessions did not use the desktop. The **full 25-attempt run remains paused until the user announces PC availability**. The changed live controller/desktop path has not been exercised under v0.4; that validation is deliberately deferred.

## Files and debugging evidence

- Task prompt: `bench/scenarios/illustrator-pen-export.md`.
- Neutral skill: `acu/SKILL.md`; neutrality rule: `AGENTS.md`.
- Image checker/controller: `bench/illustrator_pen_export.py`, `bench/run.py`.
- Aggregation: `bench/aggregate.py`.
- Tests: `tests/test_skill.py`, `tests/test_bench_illustrator_pen_export.py`, `tests/test_bench_aggregate.py`.
- Persistent offline evidence: `C:\Users\13982\ahk-computer-use\.pi\pen-export-single-pass\` (`red-*.log`, `green-*.log`, `focused-checks.log`, `profile-check.log`, `real-image-check.log`, review findings/dispositions).
- Aggregation errors persist a traceback beside the supplied manifest as `*.aggregate-crash.txt`.
- Future live runs retain their normal `.pi/bench/<run-id>/` session, image, metric and crash records. ACU runtime logs/crashes remain under `%LOCALAPPDATA%\ACU\logs\runs.jsonl` and `%LOCALAPPDATA%\ACU\crashes\`.

Changes are uncommitted. The existing unrelated scenario-renaming and prior configuration work in the checkout was preserved.
