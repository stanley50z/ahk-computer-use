# GUI-360 feasibility for ACU

## Bottom line

GUI-360 is broad **within Windows Microsoft Office**, not a comprehensive Windows-desktop benchmark. It covers Word, Excel and PowerPoint, with unusually rich recorded observations and actions. Its published evaluation measures offline grounding, screen parsing and next-action prediction. It is not a ready-to-run, closed-loop ACU task suite. Templates and goals can seed live ACU scenarios, but those scenarios need local setup/reset procedures and independent outcome checks. [1–4]

Research was read-only except for this report: public metadata, documentation, source and three small JSONL trajectories; no image archives, repositories, browser sessions or desktop applications were downloaded/launched. Dataset revision inspected: `1c46362efaae836c601004e77b98a1aba89a530f`.

## Verified coverage and counts

The paper reports **1,225,177 action-step samples** across the full corpus, including failed runs. This is not 1.2 million independent tasks. The card reports the following successful-trajectory subset; the HF file listing independently agrees with the train/test trajectory counts. The paper describes an 80/20 trajectory split shared across evaluation tasks. [1–3]

| Measure | Train | Bench/test |
|---|---:|---:|
| Successful trajectories | 13,750 | 3,439 |
| Recorded steps | 105,368 | 26,284 |
| Grounding steps | 79,487 | 19,780 |
| Screen-parsing / action-prediction steps, each | 105,368 | 26,284 |
| Images, as reported | 210,736 | 52,568 |
| UI elements | 17,668,694 | 4,324,617 |

Thus there are **17,189 successful trajectories**, 131,652 successful steps and 263,304 reported images. These are paper/card totals, not an independent count of image-archive members. Raw samples reference more screenshot variants than the table's two images per step, so do not assume these totals enumerate every shipped PNG. Test trajectories comprise Word 1,409, Excel 1,087 and PowerPoint 943. [1–3,5]

Collection used **15 Windows 11 VMs**, four CPU cores each, with GPT-4o followed by GPT-4.1 retries of failures. No macOS/Linux/mobile task coverage is claimed for this release. Application coverage does not establish coverage of browsers, Explorer, installers, creative software, arbitrary dialogs or long cross-application workflows. The paper's platform is compatible with ACU's Windows focus; exact Office build, language, display configuration and reproducible VM image remain unverified. [2]

## What is actually shipped

- HF contains `train/data`, `test/data`, `fail/data` JSONL trajectories; screenshot archives; four processed SFT datasets; and **135 template files** under `templates/excel`, `templates/word`, `templates/powerpoint`. The real directory is plural `templates`, unlike the card's illustrative `template`. [1,3]
- Raw annotations contain goal, template filename, execution/step IDs, completion judgments, screenshots, accessibility/UI control metadata, observation, thought, action and status. These are recorded execution data, not executable task specifications with reset and assertion functions. [1,5]
- The linked code provides offline evaluators, model adapters, prompts, conversion scripts and dependencies. The documented CLI reads a local test dataset and calls a model; grounding scores point-in-box, parsing scores control matching, and action prediction compares function/arguments/status. Model inference may use a network API: “offline” describes the recorded environment, not a requirement to disconnect the network. [4,6]
- The paper describes TrajAgent environment preparation/reset and links the UFO collection framework. The inspected GUI-360 repository tree does **not** supply a turnkey Windows VM, Office installation/licenses, task-specific live reset scripts or live document-outcome evaluators. A separate collection framework link is not proof that the released task set can be replayed unchanged. [1,2,4,7]

### Real samples and schema wrinkles

All three were read from **test** JSONL files, not README examples. [5]

| Execution ID | Actual request | Template | Steps |
|---|---|---|---:|
| `excel_1_116` | Ensure the ribbon is always shown in the Excel application. | `adult_sexual_behaviors.xlsx` | 2 |
| `word_1_1` | Add an arrow to the document by navigating to the 'Insert' tab, selecting 'Shapes', and choosing an arrow style. | `template2.docx` | 5 |
| `ppt_1_113` | Draw a speech bubble on Slide 1 in the PowerPoint presentation. | `template6.pptx` | 6 |

Excel step 1 is a GUI `click` with `args={"button":"left","double":false,"x":1010.0,"y":172.0}`, rectangle `[1000,162,1020,182]`, and separate desktop coordinates `(1002,164)`. Its actual field is **`control_test`**, not the card's `control_text`. Step 2 has an empty function, `action_type="API"`, no rectangle and `status="OVERALL_FINISH"`; the judgment says the setting was already selected. It is therefore a useful observation/termination smoke case, not proof of changing the setting. [5]

PowerPoint includes `wheel_mouse_input` with `wheel_dist=-3` and a `drag` using `start_x/start_y/end_x/end_y`, plus separate desktop coordinates. Word uses clicks. Published normalized evaluation tools instead use `coordinate` and `start_coordinate/end_coordinate`; they also include Office API functions such as `set_cell_value`, `select_text` and `set_background_color`. The card reports 81% GUI / 19% API actions, but the empty terminal “API” record demonstrates why this is not automatically 19% meaningful API calls. [1,5,8]

An adapter must distinguish screenshot-local from desktop coordinates, normalize arguments and map terminal statuses explicitly. Blind coordinate replay on the current machine is invalid. Office API actions are not ordinary mouse/keyboard operations; either exclude them from a GUI-only score or declare a separate hybrid track. [5,8]

**Evaluator caveat:** the inspected visual action-prediction loader skips `drag` and actions with empty rectangles, maps `OVERALL_FINISH` to `FINISH`, and maps raw `FINISH` to `CONTINUE`. It builds history from prior recorded thoughts. Consequently its evaluated sample count can be smaller than the card's action-prediction step count. For these samples, it generates IDs such as `excel_in_app_excel_1_116_1`; the Excel terminal row is filtered out. Pin and audit the code revision before reproducing a published score. [6]

## Download and license

Current listed file sizes total **573,834,286,171 bytes (573.83 GB decimal)**. This was calculated from HF `siblings[].size`, not downloaded. Breakdown: train 41.29 GB, test 10.08 GB, fail 449.95 GB, processed data 72.48 GB, templates 27.17 MB. The API's `usedStorage=721,407,757,941` is a different repository-storage figure and should not be presented as the current checkout download size. [3]

The test screenshot archive alone is **6,296,922,916 bytes (6.30 GB)**; train screenshots are 26.40 GB. Test JSONL metadata contributes another ~3.78 GB. Individual annotations are small enough to fetch selectively (the three inspected files total ~1.69 MB), but no individually addressable test PNGs appear in the file listing: screenshot extraction from a compressed tar may still require a substantial download. Expanded disk requirements were not measured. [3,5]

The HF card declares **MIT**, but no `LICENSE` file appears in the dataset listing despite the card linking one. The code repository has a concrete MIT license, copyright 2025 MJ. This does not grant Windows/Office licenses or independently resolve rights in third-party template content. [1,3,9]

## Proposed small ACU pilot — not implemented

1. **Start with a three-task feasibility check**, using the IDs above and only their annotations/templates. Validate template availability, installed Office version and task preconditions before any desktop run. Use disposable copies in an isolated user/VM and preserve existing documents. Excel's setting may affect user preferences; record and restore it.
2. **Keep two experiments separate.** For offline model evaluation, request a small image bundle or explicitly approve the test archive download, then select ~30 held-out steps stratified by application. Use only clean screenshots plus each task's permitted inputs. Report grounding and next-action agreement separately; this tests model decisions, not ACU input delivery or recovery.
3. **For live ACU**, reconstruct the initial state, provide the original goal, and let the agent observe/act through ACU rather than replaying gold coordinates. Assert final state independently: ribbon setting, an arrow shape in the Word document, a speech-bubble/callout on slide 1. The Word/PPT assertions should inspect saved artifacts, not merely trust the actor's completion message. A synthetic substitute document is acceptable for a smoke test but must be labeled an adapted task, not the original benchmark.
4. For an initial ACU-only pilot, propose three scheduled reset trials per task (nine attempts), using the existing Pi + ACU profile. Do not replace failed slots. Keep the existing no-overall-actor-deadline policy; per-script watchdogs and explicit cancellation remain available. Report task success and setup/reset/infrastructure failures separately, then the existing API token breakdown, computer-use code share and computer-use call duration. Elapsed wall time is diagnostic, not a ranking metric. This is a proposal, not authorization to launch trials or change the existing benchmark protocol.

### Fit with the existing ACU bench

Local inspection found reusable fresh-session profiles, skill/prompt hashing, event capture, usage attribution and owned-process cleanup in `bench/run.py`, `bench/processes.py` and `bench/efficiency.py`. However, `SCENARIOS` currently accepts only `calculator` and `illustrator-pen-export`; preparation, application approval, verification and cleanup contain application-specific branches. `bench/aggregate.py` also validates the Illustrator protocol specifically. Dropping a new Markdown prompt into `bench/scenarios/` is therefore insufficient. [10]

The smallest implementation would add one GUI-360 task manifest plus Office-specific preparation, verification and cleanup, then connect those operations to the existing controller. Only extract shared scenario operations where this addition actually needs them; a general benchmark framework is unnecessary. Freeze the dataset revision, execution ID, original/adapted goal, template hash, Office build, initial-state recipe, actor profile and verifier version in each plan. Keep gold trajectories/evaluation fields outside actor-readable context and review shell/script history for prohibited Office API or direct document-editing shortcuts. Existing prompt isolation is not an OS security boundary. Do not put task-specific solutions into `acu/`. [10]

Use `.pi/bench/<run-id>/` for transcripts, screenshots, output documents, `verification.json`, `cleanup.json`, `worker.log` and `crash.txt` with tracebacks, following existing conventions. ACU's normal launcher logs remain `%LOCALAPPDATA%\\ACU\\logs\\runs.jsonl`, with crash reports under `%LOCALAPPDATA%\\ACU\\crashes\\`. Reports belong in `docs/reports/`. Add a GUI-360-specific task/attempt summary rather than passing new tasks through the Illustrator-only round validator. [10]

### Evaluation leakage and remaining gaps

- This report exposes three **test** goals and gold actions. Treat them as development smoke cases now; choose a fresh, sealed subset for a later headline score.
- Grounding legitimately supplies the recorded current thought, which often names the answer target. Do not compare this score to full-goal planning success. For action prediction, hide the current gold thought/action, completion judgment and future steps. The upstream protocol supplies prior thoughts; report that privileged history explicitly. [1,6]
- Use the declared train/test trajectory split, not random steps. Near-identical templates, requests or screens may span splits; template-disjointness and duplicate removal were not established. Audit those before claiming generalization. Unknown pretraining exposure to this public dataset also limits clean comparisons. [2]
- Labels come from automated collection and LLM-driven validation, not universal human verification. Manually inspect the pilot's success criteria; exact next-action matching can penalize a different valid route. [2,4]
- No live benchmark was run. Exact environment reproducibility, complete template-to-task mapping, archive contents and runnable compatibility of the published evaluator remain untested.

## Primary sources

1. [HF dataset card (raw)](https://huggingface.co/datasets/vyokky/GUI-360/raw/main/README.md)
2. [Original paper, v1; especially §§3–4 and Appendix D](https://arxiv.org/html/2511.04307v1)
3. [HF metadata with file sizes](https://huggingface.co/api/datasets/vyokky/GUI-360?blobs=true), [file tree](https://huggingface.co/datasets/vyokky/GUI-360/tree/main), [test archive metadata](https://huggingface.co/api/datasets/vyokky/GUI-360/tree/main/test)
4. [Official evaluation/setup README](https://github.com/2020-qqtcg/GUI-360/blob/main/README.md)
5. Actual annotations: [Excel](https://huggingface.co/datasets/vyokky/GUI-360/resolve/main/test/data/excel/in_app/success/excel_1_116.jsonl), [Word](https://huggingface.co/datasets/vyokky/GUI-360/resolve/main/test/data/word/in_app/success/word_1_1.jsonl), [PowerPoint](https://huggingface.co/datasets/vyokky/GUI-360/resolve/main/test/data/ppt/in_app/success/ppt_1_113.jsonl)
6. [Action-prediction evaluator source](https://github.com/2020-qqtcg/GUI-360/blob/main/evaluator/action_prediction.py), [tool evaluation documentation](https://github.com/2020-qqtcg/GUI-360/blob/main/eval_func/README.md)
7. [Official repository tree API](https://api.github.com/repos/2020-qqtcg/GUI-360/git/trees/main?recursive=1); collection framework linked by card: [Microsoft UFO](https://github.com/microsoft/UFO)
8. [Actual normalized tool definitions](https://github.com/2020-qqtcg/GUI-360/blob/main/evaluator/tool_definitions.py)
9. [Code license](https://github.com/2020-qqtcg/GUI-360/blob/main/LICENSE)
10. Local authoritative sources: `bench/README.md`; `bench/run.py` (`SCENARIOS`, `prepare`, `run_trial`); `bench/start.py`; `bench/aggregate.py`; `acu/SKILL.md`.
