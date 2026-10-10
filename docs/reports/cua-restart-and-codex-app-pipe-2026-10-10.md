# Fairness follow-up: CUA daemon restart and the Codex app-pipe trial

Two bench changes and one experiment on 2026-10-10 evening, after the question whether the CUA and native arms were set up fairly. Working tree, uncommitted.

## CUA: the daemon is restarted before every CUA trial

Every fresh CUA actor named its first session after the scenario, `calc-v3`, and the shared `cua-driver` daemon remembers ended labels, so each trial after the first paid a rejected call: 3.7 s, 7.0 s, and 11.2 s in the three rounds. By the user's decision the bench worker now runs `cua-driver stop` and `cua-driver autostart kick` before a CUA trial, outside actor timing, waits for `status` to report running and `list_sessions` to be empty, and records `daemon-restart.json`. A manual run of the sequence took 1.3 s to stop and under a second to return. The rule "never stop a shared service" in `bench/README.md` is narrowed to every service other than this one. A stand-in driver covers the sequence in the quiet tests. No CUA trial has run under the new rule yet.

## Codex: the app is current, and the app pipe does not change the result

The "Codex desktop app" on this machine is the Microsoft Store package `OpenAI.Codex`, whose executable and display name are ChatGPT; its Codex integration owns the computer-use pipe the bench had been avoiding. ACU drove the check: it opened the Store on Updates and downloads, pressed "Check for updates", and read the list. The OpenAI app appeared under "Recent updates, modified yesterday" at version 26.1007.2314.0 with no update offered, so there was nothing to upgrade. Updates offered for unrelated apps were left alone. Scripts: `.pi/artifacts/codex-upgrade/`.

ACU then started the app (`shell:AppsFolder\OpenAI.Codex_2p2nqsd0c76g0!App`). The app rewrote `~/.codex/config.toml` with a fresh pipe GUID and build 26.1007.21434, and the pipe appeared. The bench gained `--native-transport app-pipe`, which keeps the user's pipe settings instead of forcing the SDK helper and refuses to start unless the pipe is open.

Trial `20261010T223812Z-codex-computer-use-app-pipe-5504da`: the actor requested accessibility with `include_text: true` and received null, exactly as through the SDK helper in all three rounds. It fell back to one screenshot-coordinate click per turn and reached the correct result in a task time of 202.4 s against 206.3 s in round 3, with 1,060,709 tokens. The transport is not the cause of the missing accessibility; the native helper returns none for Calculator either way. The actor also reported that its first helper definition through `eval` was rejected by the runtime and that it redefined the function directly.

## A bench defect the trial exposed

The automatic verifier refused to bind the actor's window: the pre-trial probe had listed handle 6555840 as an existing window. It was a hidden ApplicationFrameHost shell, and the frame host reused it for the new Calculator; no Calculator existed before the trial and the actor opened exactly one. The old rule protected every pre-existing handle, hidden or not, so the run was recorded as failed and its window left open by design. The parent read the display independently (correct), closed only that window after the identity checks, reloaded the cursor scheme, and re-probed: `cleanup-reconciliation.json` and `summary-reconciled.json` sit beside the unchanged automatic `summary.json`.

Fix: `probe.ahk` now lists visible windows as `window=` and hidden ones as `hiddenwindow=`, and only visible pre-existing handles are protected. A regression test covers a reused hidden shell. The rule still refuses any visible pre-existing window and any window whose process changed.

## An ACU finding on the side

`AcuTree` on the ChatGPT window four seconds after launch failed with COM error 0x80131505 from `ElementFromHandle` with a cache request; the same dump succeeded a few seconds later. An Electron window exists before its UI Automation provider is ready. A short retry inside `AcuTree` would hide that from agents; not applied.

## State

Quiet suite green. No CUA trial under the restart rule, and no further native trial, has been run; both are ready. The ChatGPT app window was closed; the process stays resident in the tray as the app normally does.
