# Five-configuration benchmark integration

Specification: [issue #15](https://github.com/stanley50z/ahk-computer-use/issues/15).

## New comparison matrix

The user replaced GPT-6.1 with **GPT-6 Astra at low reasoning** and requested comparisons within a fixed harness/model rather than comparing Pi with a separate Codex actor:

| Arm | Harness / model | Desktop runtime |
| --- | --- | --- |
| `pi-acu` | Pi / `openai/gpt-6-astra`, low | ACU |
| `pi-cua` | Pi / `openai/gpt-6-astra`, low | CUA driver |
| `pi-computer-use` | Pi / `openai/gpt-6-astra`, low | Installed Codex native computer-use runtime |
| `claude-acu` | Claude Code / `claude-opus-5-5`, low effort | ACU |
| `claude-cua` | Claude Code / `claude-opus-5-5`, low effort | CUA driver |

Both Calculator and Adobe Illustrator Pen and Export use this matrix. The standalone `codex-computer-use` arm is retired for new launches; its saved events remain analysable. Historical GPT-6.1/Opus trial data and prompt/skill fingerprints are unchanged, not relabeled as Astra results.

Task prompts, input assets, continuous timing, no parent coaching, failure retention, isolated actor sessions and post-run owned-resource cleanup remain unchanged. The existing scenario/file rename work in the checkout was preserved.

## Does native computer use work in Pi?

**Yes, with explicit host compatibility support.** Pi successfully used the vendor `node_repl` MCP tools and `@oai/sky` to open Calculator, enter the expression and observe the independently verified result. No vendor source/skill was changed; the actor remained Pi + GPT-6 Astra/low.

Two fresh failed integration attempts identified necessary differences from the former Codex host:

1. **`spawn EPERM`** when the standalone node runtime started its desktop helper through the Codex sandbox launcher. The executable's own `--help` documents `--disable-sandbox`. The benchmark passes this supported option to match the former native Codex profile's explicit full-access mode. It applies only to the run-local native server, not global settings.
2. **MCP form elicitation unavailable.** Native app-use approval requires form elicitation; Pi's built-in MCP client does not implement it. `bench/native_mcp.py` advertises form support and answers only recognized low-risk computer-use app approvals for the selected scenario's exact allowlist, using the user's standing authorization. Unknown apps, URL forms, missing or non-low risk classifications, audio/high-risk and unrelated requests are declined. Approval also requires app-only parameters and the vendor's empty object form schema; extra form fields or unknown request shape fail closed. Tool requests/results otherwise pass unchanged to the installed server. The adapter is not a custom desktop-helper protocol and never directly controls the desktop.

The native profile enables only Pi's built-in MCP extension, one isolated `node_repl` server and its four tools. `sky` is the only trusted service; browser backends are disabled. The standard four file/shell tools and vendor computer-use skill are explicit. The adapter's subprocesses are owned jobs, and native state/config resides in the run-local home. Incremental Pi tool declarations and actual model/reasoning/skill evidence are audited.

The adapter logs every decision to `native-approvals.jsonl`. In the successful Calculator check, all accepted approvals named exactly `Microsoft.WindowsCalculator_8wekyb3d8bbwe!App`. Because Pi does not supply Codex's native turn metadata/persistent approval context, the SDK requested approval repeatedly; those round trips and their latency are included in task time. This is a documented integration difference, not a claim of byte-identical hosting behavior or zero adapter overhead.

## Live Calculator checks

These are fresh integration checks, **one successful task attempt per profile** in the initial matrix, not a repeated performance study. The native row retains an unresolved conduct flag and is not an unconditional overall pass. A later native rerun after stricter permission checks is recorded separately below.

| Arm | Task time | Computer-use calls | Arithmetic | Isolation | Conduct | Cleanup |
| --- | ---: | ---: | --- | --- | --- | --- |
| Pi + Astra + ACU | 22.71 s | 2 | Correct | Pass | Pass | Pass |
| Pi + Astra + CUA | 129.19 s | 8 | Correct | Pass | Pass | Pass |
| Pi + Astra + native computer use | 52.46 s | 5 | Correct | Pass | Extra window flagged | Pass |
| Claude Code + Opus + ACU | 27.65 s | 1 | Correct | Pass | Pass | Pass |
| Claude Code + Opus + CUA | 209.94 s | 9 | Correct | Pass | Pass | Pass |

All five produced `4,676.0458862027102809497692132297`, observed independently in a newly opened Calculator window. Both CUA checks ended without active named CLI sessions; the shared daemon remains available.

The native conduct audit flagged HWND `7739512`, PID `62832`, class `WinUIDesktopWin32WindowClass`. A read-only identity check found Photos.exe displaying `kimi-k3-vs-gpt-5.6-sol-cost.png`. The native actor's requests did not establish why that window appeared. The original conduct failure is retained, not waived or attributed without evidence; the unrelated Photos window was left alone. The successful calculation establishes host/runtime compatibility, not a clean overall conduct verdict for that attempt.

### Trial directories

Under `C:\Users\13982\ahk-computer-use\.pi\bench\`:

- Initial native spawn failure: `20261011T191606Z-calculator-pi-computer-use-1d9215`.
- Native elicitation failure: `20261011T191828Z-calculator-pi-computer-use-f2478d`.
- Successful native calculation: `20261011T192302Z-calculator-pi-computer-use-1ebf89`.
- Claude + CUA: `20261011T192429Z-calculator-claude-cua-3ed496`.
- Pi + ACU: `20261011T192857Z-calculator-pi-acu-f064af`.
- Pi + CUA: `20261011T192955Z-calculator-pi-cua-692ce6`.
- Claude + ACU: `20261011T193236Z-calculator-claude-acu-6d1a75`.
- Strict-approval native rerun: `20261011T194207Z-calculator-pi-computer-use-8a2179`.

Failed attempts are preserved separately, not used as task-completion measurements or silently retried in the same session.

### Strict-approval rerun and Calculator popup finding

After review tightened the approval boundary, a fresh native Pi rerun again entered the correct expression and result (47.50 s of task activity, 59.38 s wall time). The recorded real form has an explicit low-risk classification, app-only parameters and empty object schema; the stricter adapter accepted only the Calculator app.

This time the automatic observer found both main-frame HWND33165728 (`ApplicationFrameWindow`, PID8044) and popup HWND21434504 (`Xaml_WindowedPopupClass`, PID46536). Both matched the broad Calculator process probe, so verification and cleanup refused the ambiguous pair. The original trial is **not an automatic pass**.

Using original/current class and PID evidence, recovery bound only the new main frame, independently verified the correct arithmetic through the normal display checker, closed that frame, and verified the popup vanished and no new Calculator windows remained. Original failed records are preserved; `verification-recovery.json` and `cleanup-recovery.json` document recovery. This existing observer defect is tracked separately in [issue #16](https://github.com/stanley50z/ahk-computer-use/issues/16); no ambiguous-window relaxation was added to this profile change.

## Validation and limits

- Offline preparation succeeded for **all five profiles on both scenarios**; each scenario has the same actor prompt hash across its five arms. No credentials are copied during offline preparation.
- **59 focused quiet tests passed, one desktop check deselected.** They cover all five profiles for both scenarios, isolated native MCP configuration, both Claude skills, both CUA daemon lifecycles, incremental tool declarations, persistent REPL timing, cross-scenario permission rejection, sensitive/unknown form rejection, and child-process ownership.
- Review tightened missing-risk/unknown-form rejection and added both-scenario, cross-scenario and client-disconnect coverage. Late requests after client EOF are cancelled without approval; malformed non-JSON MCP output remains an explicit protocol failure with a crash report, not a silent pass-through.
- The new native runtime supports real app input through Pi, rather than only MCP discovery. Claude + CUA is also proven by a real task.
- **No five-arm Illustrator trial round has been run under Astra.** The earlier four-arm GPT-6.1 results are still historical. A new matched Illustrator experiment must use fresh runs and the current five-profile matrix.
- An adapter approval is permission to operate the scenario app, not permission to modify unrelated apps, settings, files or credentials. The benchmark still has configuration/prompt isolation, not an OS security sandbox; transcript/conduct review remains necessary.

## Debugging and cleanup evidence

Persistent integration evidence: `C:\Users\13982\ahk-computer-use\.pi\five-arm\`.

- `native-discovery/discovery.log`: Pi connected to the installed native server and discovered its four tools.
- `red-*.log`, `green-*.log`, `focused-tests.log`: focused regression evidence.
- `profiles-8f1738c5/profiles.json`: both scenarios' five isolated profiles.
- `results.json` / `results.log`: observed task/audit/cleanup outcomes.
- `check-extra-window.log`: Photos window identity, without acting on it.
- `sessions-final.json`: no active task CUA session remains.

Each trial preserves raw events, persisted transcript, model/skill/config hashes, metrics, isolation/conduct/verification, capture/worker state and cleanup records. Native app approvals are in the run directory's `native-approvals.jsonl`; adapter failures persist `native-approvals.crash.txt`. Native sandbox launch evidence for the first attempt is under its `agent-home/.sandbox/`.

All eight trial workers finished and owned actor process trees were stopped. The initial seven completed ordinary cleanup; the last required the documented popup recovery. Final Calculator cleanup and cursor-scheme restoration are verified, private credential copies were removed, and the active benchmark lock is released. No new server port or external service was installed. ACU retains its usual `%LOCALAPPDATA%\ACU\logs\runs.jsonl` and `%LOCALAPPDATA%\ACU\crashes\` paths.
