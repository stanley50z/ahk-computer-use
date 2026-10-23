# ACU design session, 2026-10-08

Historical record of ACU's opening brainstorm, not current setup instructions or a work queue. Environment facts, vendor interfaces, source revisions and repository state below describe 2026-10-08. The original proposals and open questions are preserved.

For current behavior, use the root `README.md`, `CONTEXT.md` and `docs/adr/`. In particular:

- [ADR-0001](../adr/0001-scripts-not-a-server.md) records the CLI-only interface, with read-only snippet and history commands added by [ADR-0010](../adr/0010-reusable-snippets.md).
- [ADR-0002](../adr/0002-short-scripts-over-injection-atomicity.md) records the jiggle-test result; the experiment is no longer an unperformed prerequisite.
- [ADR-0008](../adr/0008-ui-access-build-started-through-shellexecute.md) makes UI Access the execution route and replaces the proposed output-pipe route. The direct `cmd` launch workaround below is historical, not the supported ACU invocation.
- [ADR-0009](../adr/0009-persistent-desktop-state-and-english-input.md) supersedes cursor/foreground restoration, takeover comparison and restore opt-outs. Desktop state stays in place.

The UIA binding, tree dump, ADRs and root glossary discussed as future work below now exist. Remaining items in the original open-questions list are historical questions, not claims that today's checkout lacks those capabilities.

Participants: the repository owner and one agent session. No code was written during this session. The only files added were research notes and this record.

## 1. What ACU is

ACU gives an AI agent the ability to operate this Windows machine: look at the screen, click, type, and drive application windows. The agent supplies the intelligence. ACU supplies the hands.

The owner set three principles at the start of the session, quoted in substance:

1. Be as minimal as possible, for the codebase, for the user, and for the AI agent.
2. AutoHotkey v2 is the core. Every computer-use action should be attempted through AHK scripts.
3. Because AHK scripts are fast and deterministic, ACU should not need a "recover or cancel from ACU control" button. If the user moves the mouse while the agent is writing a script, the script should still click accurately, because the click is scripted rather than hand-aimed. The owner flagged this third principle as the one needing research.

Principle 3 drove most of the session. The short verdict is that it holds for a single injected action, holds in weakened form for a short script, and does not hold across an agent's whole turn. Section 4 has the detail.

## 2. How the session was run

Three research notes were produced and live beside this one:

| Note | Scope | Author |
| --- | --- | --- |
| `docs/research/ahk-input-injection.md` | AHK input internals, the atomicity question, coordinates and DPI, launcher behavior | This session, from the AHK source tree plus two probe scripts |
| `docs/research/cua-survey.md` | `trycua/cua` architecture, Windows input routes, sizes, what to borrow or skip | Background agent, static inspection only |
| `docs/research/computer-use-landscape.md` | Anthropic and OpenAI tool contracts, UFO, OmniParser, terminator, Windows-MCP, Agent-S, bytebot, PyAutoGUI, xdotool, and seven AutoHotkey MCP projects | Background agent, web research with bounded fetches |

Primary sources used, in order of weight:

- The AutoHotkey source tree at `~/github repo ref/AutoHotkey`, commit `47eabd41`, branch `alpha`. This is the authority on what AHK actually does.
- A shallow clone of `trycua/cua` at `~/github repo ref/cua`, commit `48cc491`, about 508 MB on disk. The owner asked to keep this checkout.
- The AutoHotkey v2 documentation and Microsoft's Win32 documentation.
- Two read-only probe scripts run on this machine. They printed facts and exited. Both were deleted afterwards.

### Environment facts measured on this machine

| Fact | Value |
| --- | --- |
| AutoHotkey | 2.0.22, 64-bit, running without administrator rights |
| Primary display | 3840x2160 at 192 DPI (200%) |
| Second display | 2560x1440 at 192 DPI (200%), offset to the right at y=117 |
| Thread DPI awareness | System aware, not per-monitor |
| `A_SendMode` default | Input |
| `A_CoordModeMouse` default | Client |
| Named mutexes `AHK Keybd` and `AHK Mouse` | Both exist |
| Owner of those mutexes | `C:\Users\13982\Documents\ahk script\master.ahk`, pid 13920 |

The mutex result is the single most consequential measurement of the session. Section 4 explains it.

## 3. The landscape, in one page

Nobody has built what the owner described, but every piece of it exists somewhere.

The two vendor contracts both put the agent outside the executor. Anthropic's current computer use entry is `computer_toolset_20260801`, which exposes 17 member tools including `screenshot`, `zoom`, the click family, `scroll`, `type`, `key`, `hold_key`, and `wait`. Coordinates are in the pixel space of the screenshot the client returns, and the client is responsible for scaling them back to the real display. OpenAI's structured computer tool has nine action types. Neither vendor dictates how input reaches the operating system.

Among the implementations, input atomicity is rarer than expected:

| Project | How a coordinate click is delivered |
| --- | --- |
| AutoHotkey, SendMode Input | One `SendInput` array holding move, down, and up |
| cua-driver, synthesized mouse route | One `SendInput` array holding move, down, and up |
| mediar-ai/terminator | Three separate `SendInput` calls |
| PyAutoGUI on Windows | `SetCursorPos`, then a separate `mouse_event` with button-only flags |
| xdotool on X11 | A move command, then a separate click command |

So AHK already matches the best-engineered competitor on this specific point, and beats the libraries most agent projects depend on. That finding is the technical justification for the whole project.

On prior art in the AutoHotkey space, seven projects were examined. The closest small one, `spyoungtech/ahk-mcp`, is 380 lines but pins AutoHotkey v1 and has no visible license. `Xeo786/AutohotkeyV2_MCPServer` is a development and debugging server under GPL-3.0. `TrueCrimeDev/ahk-mcp` is a substantial development suite whose standout feature is returning AHK selector snippets verified against the live accessibility tree, with read-only UI Automation tools. `sandraschi/autohotkey-mcp` manages a scriptlet depot and has a visible activity display with an emergency stop. `claude-did-this/MCPControl` is a multi-provider TypeScript server with AutoHotkey v2 as one option. None is a minimal AHK v2 executor with a precise claim about input atomicity and a test behind it. That is the open slot ACU fills.

From `trycua/cua`, the useful conclusion is about scope. Its driver is roughly 307,000 lines, with about 33,000 in the Windows adapter alone, and it maintains parallel delivery routes: UI Automation pattern calls, posted window messages, synthetic pen injection, and foreground `SendInput`. Worth borrowing: coordinates always expressed in screenshot space with the scale returned, a result contract that separates refusal from delivery from verified effect, and `zoom` implemented as a region screenshot. Worth avoiding: its Python agent acknowledges model safety checks automatically and after execution, and its user-facing Cancel button only appends a line to the chat without stopping the running task. Its "multiplayer, each with your own cursor" feature is drawn overlays plus per-window input leases, not independent operating system input devices.

## 4. Principle 3, resolved

### The strong guarantee, and what it rests on

In the default send mode, `Click x, y` compiles to a single `SendInput` call carrying move, button down, and button up. The relevant code path is `PerformMouseCommon`, which allocates one array of at most ten events and flushes it once through `SendEventArray` (`source/keyboard_mouse.cpp:1977-2031`, `:2718-2745`). Microsoft documents the guarantee that makes this matter: events in one `SendInput` array are inserted serially and "are not interspersed with other keyboard or mouse input events inserted either by the user (with the keyboard or mouse) or by calls to keybd_event, mouse_event, or other calls to SendInput".

AHK adds a second layer of protection that survives even when the first is lost. The button down and button up events reuse the move's absolute coordinates and its `MOUSEEVENTF_ABSOLUTE` flag (`source/keyboard_mouse.cpp:2329-2341`). The source comment records the reason: this "has been shown to significantly improve reliability in cases where the user is moving the mouse during the MouseClick/Drag commands" (`:2131-2140`). Every event re-aims at the target, so a physical move that slips between events is corrected by the next one.

The AHK documentation also notes that physical input during a `SendInput` is buffered and delivered afterwards rather than discarded. The user's keystrokes are not lost, just deferred.

### Why this machine does not get the strong guarantee

A low-level mouse hook forces Windows to route every mouse event, injected or physical, through the hook owner's thread and wait for its verdict before queuing. That destroys the atomicity of a `SendInput` batch. AHK's author tested this and left the finding in a comment: with a mouse hook present, "I could physically move the mouse cursor a little between each of sendinput's mouse clicks" (`source/keyboard_mouse.cpp:2725-2740`). AHK therefore removes its own hooks for the duration of each `SendInput` call and restores them afterwards.

It cannot remove another process's hook. What it can do is notice one. AHK processes that install hooks create named mutexes `AHK Keybd` and `AHK Mouse` (`source/hook.cpp:27-28`), and `SystemHasAnotherKeybdHook` and `SystemHasAnotherMouseHook` detect them by attempting creation and checking for `ERROR_ALREADY_EXISTS` (`:4059-4090`). When another AHK process owns a hook, send mode downgrades to SendEvent, on the reasoning that a non-atomic `SendInput` keeps its drawbacks and loses its only advantage (`source/keyboard_mouse.cpp:197-212`, `:1991-1994`).

The probe found both mutexes present, held by `master.ahk`. So on this machine, as configured today, ACU clicks already run in SendEvent mode: three `mouse_event` calls with `SetMouseDelay` between them, default 10 ms. The absolute coordinates still re-aim each event, so a moving hand is still corrected. A physical button press inside that window is not.

Two further limits apply regardless of hooks. AHK cannot detect low-level hooks in non-AutoHotkey programs, so a keyboard remapper, recording tool, or peripheral utility can weaken `SendInput` invisibly. And `SendInput` is subject to User Interface Privilege Isolation: injection into a higher-integrity window fails, and Microsoft documents that neither the return value nor `GetLastError` reveals that cause.

### The decision

The owner's position, which settles it: speed matters more than atomicity, because what the user perceives is not the injection mode but how long the desktop is occupied.

That reframes the problem correctly. A `SendInput` batch and three `mouse_event` calls with no delay differ by well under a millisecond. A script containing `Sleep 2000` occupies the desktop for two seconds. The second is what a person notices. So the rules worth enforcing are about script duration, not injection mode.

Accordingly: set `SetMouseDelay -1` in the prelude to collapse the SendEvent gap, prefer `WinWait` with a short timeout over fixed sleeps, and give the launcher a hard watchdog. Do not suspend the user's other AHK scripts to reclaim atomicity. That trick is real, AHK documents sending `WM_COMMAND 65404` to another script and says hooks are removed when justified by the change, but it would silently disable the owner's hotkeys for the duration of every step, and `#SuspendExempt` hotkeys would defeat it anyway. It stays recorded as a measured option, not a default.

## 5. Target windows, foreground, and restore

### What AHK already provides

AHK has had the target-application concept since the beginning. Every window function accepts WinTitle criteria: a title substring, `ahk_exe`, `ahk_class`, `ahk_pid`, or `ahk_id` with a window handle. The handle is unambiguous and is what ACU should use, returned by whichever step enumerated the windows.

`WinActivate` is more robust than it looks. The documentation states that it makes six attempts over 60 ms, then sends `{Alt 2}` as a workaround for operating system foreground restrictions, then makes a seventh attempt. It restores a minimized window before activating it. It still cannot activate across the secure desktop or onto a UAC prompt, and the docs record a hang when running over Remote Desktop with the client minimized.

### The script as the unit of work

The owner's model, adopted: one script is one logical action chain. Click a button, wait for the popup it raises, click a button inside the popup, finish. The agent writes that as a single script whenever it can predict the intermediate states, either from an accessibility tree dump or from having seen the dialog before. When it cannot predict them, it falls back to screenshot, short script, screenshot. The skill file should present both as normal.

This is where AHK is genuinely better than a tool-call-per-action protocol. A chain that would be four round trips through a model becomes one script that runs in 200 ms.

### Restore, and the one point of pushback

The owner asked for restore at the end of the script rather than after each action, and that is the right unit. Restoring the previous foreground window immediately after each click would close any menu the click opened.

The pushback, accepted into the design, is about a condition rather than timing. Restore should be conditional, not unconditional:

1. Restore only if the user did not physically intervene during the script. If they touched the mouse or keyboard, they have taken over, and pulling focus back to where they were beforehand is the interruption the design is trying to avoid.
2. Restore only if the foreground still belongs to the target process. A popup from the same application counts as ours and may be restored over. An unrelated window that appeared should be left alone.
3. Run restore on the error path and on watchdog termination too, through the prelude's exit handler, so a failed script never strands the cursor.

The case where this is wrong is a script that deliberately leaves transient UI open for its successor, such as an open menu. No opt-out flag is being built yet. The skill rule "end every script at a stable state" covers it, and a flag can be added when a real task needs one.

### A correction to condition 1

During verification for this record, the mechanism proposed earlier in the session turned out to be qualified in a way that matters.

`A_TimeIdlePhysical` does not unconditionally ignore injected input. The documentation states that it "ignores artificial keystrokes and/or mouse clicks whenever the corresponding hook (keyboard or mouse) is installed", and that "if neither hook is installed, this variable is equivalent to A_TimeIdle". `A_TimeIdle` is reset by the script's own injected input, so without a hook the variable cannot distinguish the user from ACU itself.

Making it work requires ACU to install its own keyboard and mouse hooks, which has a side effect worth weighing. ACU's own sends stay atomic, because AHK removes its own hooks during `SendInput`. But ACU's hooks would create the `AHK Keybd` and `AHK Mouse` mutexes, which downgrades `SendInput` for every other AutoHotkey script on the machine while ACU runs, including `master.ahk`.

The hook-free alternative is to infer takeover from observable state: remember where ACU last placed the cursor and which window it activated, then compare against actual cursor position and foreground window before restoring. A user who moved the mouse and left it elsewhere is detected. A user who moved it and returned it is not, which is an acceptable miss, because restoring to the same place is harmless.

Provisional decision: start hook-free with the position-and-foreground comparison, because it costs nothing and has no effect on other scripts. Add `InstallMouseHook` behind a setting only if real use shows the comparison missing cases that matter. This supersedes the earlier statement in this session that `A_TimeIdlePhysical` could be read directly.

## 6. Perception: coordinates, controls, and the accessibility tree

### Why pure coordinates are not enough

The owner's instinct, that programmatic detection of a button beats relying on a model's vision, is correct and was the most design-changing point of the session.

AHK's built-in control functions do exactly that for one class of application. Classic Win32 controls are child windows with ClassNN identifiers such as `Button1` and `Edit2`, and AHK can enumerate them, read their text, click them without moving the pointer through `ControlClick`, choose menu items by label, and set edit fields directly. This still covers file dialogs, parts of Explorer, installers, and many utilities.

It fails on everything modern, because those applications draw their own interface inside a single blank window. Chromium and Electron, WinUI and UWP, WPF, Qt, and Office expose no child controls for their buttons. To the classic API they have none.

### What the accessibility tree is, and what UIA-v2 is

These are two different layers, and the distinction answers the owner's closing question.

The accessibility tree is a Windows platform feature. Applications publish a tree of elements, each carrying a name, a control type, state, screen bounds, and supported actions such as Invoke, Toggle, or SetValue. The operating system interface to that tree is UI Automation, a COM API shipped since Windows 7. This is the same tree a screen reader reads, and the same one Microsoft's Accessibility Insights displays. Every serious agent project in this space reads it: cua-driver, Windows-MCP, terminator, and Microsoft's UFO.

UIA-v2 is a wrapper, nothing more. It is a single AutoHotkey v2 file, 7,946 lines, pure AHK with no compiled component, that calls the same `IUIAutomation` COM interfaces and negotiates the interface version available on the host. It is MIT licensed, has 491 stars, and was last pushed on 2026-04-23. It does not decide what appears in the tree; the application does. Its purpose is to let an AHK script query that tree in a few lines rather than hundreds of raw `DllCall` invocations. It also ships a browser helper for Chrome, Edge, and Firefox, and sets a flag that asks Chromium to enable its accessibility tree, which Chromium otherwise leaves off until a client connects.

Using it keeps principle 2 intact. The work is still done by an AHK script; the script just reaches a Windows API that AHK has no built-in binding for.

Known limits, all shared with every other UI Automation consumer: icon-only buttons frequently publish no accessible name, canvas-drawn interfaces and games publish nothing, Chromium's first query after enabling accessibility can be slow, and large trees need a budget, which is why cua caps its walk at 250 elements and depth 25. A successful Invoke is also not proof the application acted, so state should be read back.

### The adopted ladder

The agent should try, in order:

1. Find the element by control type and name, then act semantically through Invoke or SetValue. No pointer movement, often no foreground change.
2. Find the element, take its bounds, and click the center. Physical input, but aimed programmatically rather than visually.
3. Screenshot, and let the model supply coordinates.

`ImageSearch` is a deterministic fallback for nameless icon buttons, brittle against scaling and theme changes, and worth having for the cases where the tree is empty.

A naming trap to document: `AutoHotkey64_UIA.exe` has nothing to do with UI Automation. It is the UIAccess build, which exists to inject input into elevated windows.

## 7. Proposed architecture

No server in the first version. The agent already knows AutoHotkey v2, already has a shell, and already writes files. ACU can therefore be four small pieces rather than a daemon.

| Piece | Job | Notes |
| --- | --- | --- |
| Prelude | Injected ahead of the agent's script with AHK's `/include` switch, so the agent writes no boilerplate | `CoordMode` set to Screen for mouse and pixel, per-monitor-v2 DPI awareness, `SetMouseDelay -1`, an `OnError` handler that prints and exits, no tray icon, save foreground window and cursor on entry, conditional restore on exit including error and timeout paths |
| Launcher | Runs a script with output captured and a hard timeout | Not optional, see the stdout trap below |
| Screenshot script | Full screen or a region, PNG out, prints image size and the scale factor used | A region argument gives Anthropic-style `zoom` for free |
| Skill file | Tells the agent the loop, the perception ladder, and the script-shape rules | The main lever on agent behavior, and the cheapest thing to iterate on |

### The stdout trap

Worth recording because it cost three hangs during this session before the cause was clear. AutoHotkey is a GUI-subsystem executable. Launched directly from Git Bash, which is what this harness uses for shell commands on Windows, it receives no usable standard output handle. `FileAppend(text, "*")` then throws, AutoHotkey displays a modal error dialog, and the calling shell blocks until the process is killed.

Two launch routes work. From Git Bash, `cmd //c` with a short path such as `C:\PROGRA~1\AutoHotkey\v2\AutoHotkey64.exe` avoids both the handle problem and the quoting problem. Better, a .NET `Process` with redirected output also provides the timeout and the kill in the same place, which is why the launcher exists as its own piece. Independently of the launcher, every script needs the prelude's `OnError` handler, because `/ErrorStdOut` covers only load-time syntax errors, not runtime ones.

### Logging

Per the owner's standing requirement for persistent debugging artifacts: a JSON-lines run log under `%LOCALAPPDATA%\ACU\logs\` and crash reports with stack traces under `%LOCALAPPDATA%\ACU\crashes\`. AutoHotkey cannot produce native crash dumps, so a persisted error report with the script hash, the exception message, and the line number takes their place. Script text and screenshots should be opt-in or retention-limited, since both can contain secrets.

## 8. Decisions made in this session

| # | Decision | Reasoning | Status |
| --- | --- | --- | --- |
| 1 | Keep the `trycua/cua` checkout at `~/github repo ref/cua` | Owner's call. It is the best available reference for Windows input routing | Settled by owner |
| 2 | No "cancel ACU control" feature in the first version | Nothing persists between scripts, so there is nothing to cancel. The launcher's watchdog is the stop path | Provisional, rests on decision 3 |
| 3 | Optimize for short scripts, not for injection atomicity | Owner's call. Perceived interruption tracks desktop occupancy, not send mode. A batch and three no-delay calls differ by under a millisecond | Settled by owner |
| 4 | `SetMouseDelay -1` in the prelude | Collapses the SendEvent fallback window, which is the mode this machine actually uses | Agent proposal, uncontested |
| 5 | Do not suspend the user's other AHK scripts to regain atomicity | Would disable the owner's hotkeys on every step, and `#SuspendExempt` hotkeys defeat it. Recorded as a measurable option | Agent proposal, uncontested |
| 6 | One script equals one logical action chain | Owner's model. Collapses what would be several model round trips into one fast script | Settled by owner |
| 7 | Activate the target window by handle, verify with `WinWaitActive`, and report activation failure rather than clicking blind | Owner delegated the choice. Shrinks the shared-desktop problem to the length of one step | Agent decision, delegated |
| 8 | Restore foreground and cursor at end of script, conditionally | Owner asked for end-of-script. Conditions prevent fighting a user who has taken over, and prevent stealing focus from an unrelated window | Owner's unit, agent's conditions |
| 9 | Detect takeover by comparing cursor position and foreground window, not by `A_TimeIdlePhysical` | The variable only ignores injected input when a hook is installed, and installing one degrades every other AHK script's `SendInput` | Agent decision, supersedes an earlier claim this session |
| 10 | Prelude sets per-monitor-v2 DPI awareness and screen coordinate mode | AHK v2 is not per-monitor aware by default, and `CoordMode` defaults to Client, which would silently reinterpret every coordinate | Owner accepted, agent detail |
| 11 | Perception ladder: named element then Invoke, element bounds then click, screenshot then coordinates | Owner's instinct that programmatic targeting beats model vision, confirmed against how every comparable project works | Settled jointly |
| 12 | Add UIA-v2 as the accessibility tree binding, in milestone 2 | Single pure-AHK file, MIT, keeps AHK as the core. Deferred so milestone 1 proves the launcher, prelude, and click first | Agent proposal, owner informed |
| 13 | No server in the first version. Prelude, launcher, screenshot script, skill file | Principle 1. The agent already has a shell and a file writer. MCP only if a non-CLI client needs it | Agent proposal, uncontested |
| 14 | Watchdog default 30 s, recommended `WinWait` default 2 s | Round numbers, deliberately revisable once real scripts exist | Agent decision, weakly held |
| 15 | Persistent logs and crash reports under `%LOCALAPPDATA%\ACU\` | Owner's standing requirement for debugging artifacts | Settled by standing policy |

## 9. What was still open at the session's end

Ordered roughly by what blocks what.

1. **The jiggle test, not yet authorized.** The experiment that turns principle 3 from a belief into a number: a script clicks a small test button 200 times through the launcher while a second script moves the physical cursor continuously, run once with `master.ahk` active and once with it stopped. It takes over the desktop for about a minute, so it needs the owner's go-ahead and a moment when the machine is free. Until it runs, the README should not state a hit rate.
2. **Takeover detection, needs a prototype.** Confirm that comparing cursor position and foreground window catches the cases that matter, and measure what installing a mouse hook would actually cost if the comparison proves too weak.
3. **Agent interface.** Shell-invoked scripts first, as in decision 13. Whether an MCP server follows depends on whether a non-CLI client matters to the owner. Not urgent.
4. **Elevated windows.** `AutoHotkey64_UIA.exe` is already installed under Program Files and would let ACU drive elevated windows without running as administrator. Making it the default launcher target is attractive but changes the install story, so it is deferred to a decision of its own.
5. **Tree dump format and budget.** How to serialize the accessibility tree for an agent cheaply: which properties, what depth and element caps, and how to name elements stably enough that the agent can refer back to one.
6. **Mixed-DPI verification.** Both displays here run at 200%, so the DPI code path is untested against a 100% monitor. Needed before claiming multi-monitor support.
7. **Second-monitor click regression test.** AHK normalizes mouse coordinates against the primary display's metrics without `MOUSEEVENTF_VIRTUALDESK` (`source/keyboard_mouse.cpp:2400-2410`), so coordinates on the second display fall outside the nominal 0 to 65535 range. This has worked in practice for years, but ACU should have a test that pins it.
8. **ADRs and a glossary.** Per this repository's conventions, the settled decisions above belong in `docs/adr/` as individual records, and the recurring terms, prelude, launcher, step, turn, element token, takeover, belong in a root `CONTEXT.md`.
9. **License review before copying code.** UIA-v2 is MIT and safe to vendor with attribution. The cua driver workspace is MIT, but other parts of that monorepo carry different terms, so file-level checks are required if any code is copied rather than ideas adapted.

## 10. Repository state at the end of this session

Added by this session, all uncommitted:

- `docs/research/ahk-input-injection.md`
- `docs/research/cua-survey.md`
- `docs/research/computer-use-landscape.md`
- `docs/design/acu-brainstorm-2026-10-08.md`, this file

Also uncommitted, and predating this session: small OpenWiki-related edits to `AGENTS.md` and `CLAUDE.md`, left untouched deliberately.

No source code exists yet. Nothing was installed. The probe scripts were deleted after use.
