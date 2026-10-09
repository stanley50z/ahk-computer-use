# AutoHotkey v2 input injection: can a scripted click survive the user moving the mouse?

Research notes for ACU, 2026-10-08. Primary sources: the AutoHotkey source tree (commit 47eabd41, `~/github repo ref/AutoHotkey`), the AutoHotkey v2 docs, Microsoft's Win32 docs, and two read-only probe scripts run on this machine (AutoHotkey 2.0.22, Windows 11).

## Question

ACU's third principle says the agent's AHK script should land its click even if the human nudges the mouse while the script runs, so that no "take back control" feature is needed. Is that true, and under what conditions?

## Short answer

Mostly yes, with three caveats that matter in practice.

- A single `Click x, y` in AHK's default SendMode Input is one `SendInput()` call carrying move, down, and up. Windows inserts that batch serially and does not interleave physical mouse or keyboard events with it. The user's hand cannot get between the move and the click.
- Even when AHK falls back to SendEvent, each of the three events carries the absolute target coordinates. A physical move that slips in between is overridden by the next event. The failure case is a physical button press in a window of roughly 20 ms, not a move.
- The guarantee is lost when another process has a low-level mouse hook. On this machine `master.ahk` holds both hooks, so AHK already runs ACU-style clicks in SendEvent mode here. See "When the guarantee breaks".

The practical conclusion: the atomic unit is one script invocation, and it should contain one short action. Between invocations the human and the agent share one cursor and one keyboard focus. Nothing persistent runs, so there is nothing to cancel. The only safety net worth building is a hard timeout in the launcher.

## How AHK sends a click

Default mode is SendInput. `A_SendMode` reported `Input` in the probe, and the SendMode docs call Input the default. (https://www.autohotkey.com/docs/v2/lib/SendMode.htm)

`Click`, `MouseClick`, `MouseMove`, and `MouseClickDrag` all go through `PerformMouseCommon`, which allocates one `INPUT` array of at most 10 events, resolves the send mode, lets `MouseClick` fill the array, then flushes it with one call. (`source/keyboard_mouse.cpp:1977-2031`)

`SendEventArray` is the flush. In Input mode it is a single `SendInput(sEventCount, sEventSI, sizeof(INPUT))`. (`source/keyboard_mouse.cpp:2718-2745`)

`MouseMove` in Input mode is instantaneous regardless of the speed argument: `if (aSpeed == 0 || sSendMode == SM_INPUT)` emits one absolute move event. (`source/keyboard_mouse.cpp:2355-2420`)

The down and up events reuse the move's `MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE` flags and coordinates: `MouseEvent(event_flags | event_down, event_data, aX, aY)` and the matching `event_up` call. (`source/keyboard_mouse.cpp:2329-2341`) The source comment explains why: "Since the mouse was just moved to an explicitly specified set of coordinates, use those coordinates with subsequent clicks. This has been shown to significantly improve reliability in cases where the user is moving the mouse during the MouseClick/Drag commands." (`source/keyboard_mouse.cpp:2131-2140`)

AHK removes its own low-level hooks for the duration of the `SendInput` call. The comment records the empirical reason: with a mouse hook present "I could physically move the mouse cursor a little between each of sendinput's mouse clicks. But removing the mouse-hook during SendInputs solves all that." (`source/keyboard_mouse.cpp:2725-2740`)

## What Windows guarantees

"The SendInput function inserts the events in the INPUT structures serially into the keyboard or mouse input stream. These events are not interspersed with other keyboard or mouse input events inserted either by the user (with the keyboard or mouse) or by calls to keybd_event, mouse_event, or other calls to SendInput." (https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-sendinput)

Two more lines from the same page matter for ACU:

- "This function is subject to UIPI. Applications are permitted to inject input only into applications that are at an equal or lesser integrity level." The failure is silent: "neither GetLastError nor the return value will indicate the failure was caused by UIPI blocking."
- "This function does not reset the keyboard's current state. Any keys that are already pressed when the function is called might interfere with the events that this function generates."

The AHK docs add that SendInput buffers physical input during the send and delivers it afterwards, which is why they prefer it over BlockInput: "unlike BlockInput, SendInput/Play does not discard what the user types during the send; instead, such keystrokes are buffered and sent afterward." (https://www.autohotkey.com/docs/v2/lib/Send.htm)

## When the guarantee breaks

### Another AutoHotkey script has a hook

`PerformMouseCommon` checks `SystemHasAnotherMouseHook()` and switches to SendEvent when it returns true. (`source/keyboard_mouse.cpp:1991-1994`) Keyboard sends do the same with `SystemHasAnotherKeybdHook()`. (`source/keyboard_mouse.cpp:197-212`)

Detection is a named mutex, `"AHK Keybd"` and `"AHK Mouse"`, created by whichever AHK process installs a hook. `CreateMutex` returning `ERROR_ALREADY_EXISTS` means another AHK instance owns one. (`source/hook.cpp:27-28`, `source/hook.cpp:4059-4090`)

The probe reproduced that check on this machine:

```
Mutex 'AHK Keybd': EXISTS
Mutex 'AHK Mouse': EXISTS
Running AHK script: C:\Users\13982\Documents\ahk script\master.ahk - AutoHotkey v2.0.22 (pid 13920)
```

So on this machine every ACU click would already run in SendEvent mode: three `mouse_event` calls with `SetMouseDelay` (default 10 ms) between them. (`source/keyboard_mouse.cpp:2496-2504`, https://www.autohotkey.com/docs/v2/lib/SetMouseDelay.htm) The per-event absolute coordinates still re-aim each event, so a physical move in that window is corrected by the next event. A physical button press in that window is not.

Anyone who uses AutoHotkey for hotkeys is in this situation, so ACU should be designed for SendEvent fallback, not just for the SendInput ideal. `SetMouseDelay -1` in the prelude shrinks the window to back-to-back calls.

### A non-AHK process has a low-level hook

AHK cannot see hooks from other programs. The docs are explicit: "since SendInput is unable to detect a low-level hook in programs other than AutoHotkey v1.0.43+, it will not revert in these cases, making it less reliable than the other modes." (https://www.autohotkey.com/docs/v2/lib/SendMode.htm) Combined with the source comment above, an external mouse hook (a remapper such as kanata with its LLHOOK backend, some gaming or RGB software, screen recorders) means physical moves can land between the batch's events while AHK still believes it is atomic. The absolute-coordinate events remain the fallback defense.

### Between invocations

Everything above covers one `Click`. Between two script runs, or during `Sleep`, `WinWait`, or `KeyWait` inside a script, the human's input flows normally. If they click another window, keyboard focus moves, and the next `Send` types into the wrong place. The mitigation is structural: short scripts, and `WinActivate` plus `WinWaitActive` before any `Send` that cares about focus. `ControlSend` and `ControlClick` sidestep focus entirely for windows that accept posted messages, but many modern apps (Chromium, Electron, UWP) ignore them, so they are an optimization, not the default.

### Held buttons and modifiers

SendInput does not reset key state. A human holding Shift turns the agent's click into a shift-click. A human holding the left button turns the agent's move into a drag. AHK's `Send` compensates for modifier keys it knows about, but nothing compensates for a held mouse button. Rare, and acceptable.

### Elevated windows

ACU runs as a normal user. Clicks on an elevated window, a UAC prompt, or an admin-level installer are dropped silently because of UIPI. The AHK FAQ's recommended workaround is the UI Access build, which is already installed here as `C:\Program Files\AutoHotkey\v2\AutoHotkey64_UIA.exe` and requires only that AutoHotkey lives under Program Files. (https://www.autohotkey.com/docs/v2/FAQ.htm#uac) Running as administrator is the other option and has the side effect that everything the script launches is elevated too.

## Coordinates and DPI

Two traps, both confirmed by the probe.

CoordMode defaults to Client in v2: "By default, coordinates are relative to the active window's client area." (https://www.autohotkey.com/docs/v2/lib/CoordMode.htm) The probe read the cursor as `565,1117` in Client mode and `871,1289` in Screen mode at the same instant. Every ACU script must start with `CoordMode "Mouse", "Screen"` and `CoordMode "Pixel", "Screen"`, or the agent's screenshot coordinates will land relative to whatever window happens to be active.

AutoHotkey v2.0 "has not been marked as per-monitor DPI-aware", so on mixed-DPI setups "system functions such as MoveWindow and GetWindowRect automatically scale the coordinates", and the docs' workaround is `DllCall("SetThreadDpiAwarenessContext", "ptr", -4, "ptr")` before touching external windows. (https://www.autohotkey.com/docs/v2/misc/DPIScaling.htm) The probe reported thread awareness 1 (system). This machine has both monitors at 200% (3840x2160 primary, 2560x1440 secondary, both DPI 192), so geometry is uniform here, but a 100% external monitor would break the screenshot-to-click mapping. The prelude should set per-monitor-v2 awareness unconditionally.

`MouseMove` converts to SendInput's 0..65535 absolute space using the primary monitor size (`GetSystemMetrics(SM_CXSCREEN)`), without `MOUSEEVENTF_VIRTUALDESK`. Coordinates on the secondary monitor therefore become values above 65535 or below 0. (`source/keyboard_mouse.cpp:2400-2410`) This has worked for secondary monitors in practice for years, but it is worth including a second-monitor click in the regression tests.

## BlockInput is not the answer

`BlockInput "On"` and the `Send`/`Mouse` modes "might have no effect if UAC is enabled or the script has not been run as administrator." Only the `MouseMove` mode works unprivileged, because it is implemented in AHK's own mouse hook and only suppresses cursor movement, not clicks. The docs themselves steer users to SendInput instead. (https://www.autohotkey.com/docs/v2/lib/BlockInput.htm) `BlockInput "MouseMove"` around a click is a possible opt-in for the SendEvent-fallback case, nothing more.

## Launching AHK from an agent: stdout is a trap

A GUI-subsystem process launched straight from Git Bash (which is what Claude Code's Bash tool uses on Windows) receives no usable standard output handle. `FileAppend(text, "*")` then throws, AHK shows an error dialog titled with the script name, and the launching shell hangs until the process is killed. Observed three times before the cause was found.

Two launch routes that work:

- `cmd //c "C:\PROGRA~1\AutoHotkey\v2\AutoHotkey64.exe /ErrorStdOut C:\path\script.ahk"` from Git Bash (short path avoids the quoting mess).
- A .NET `Process` with `RedirectStandardOutput`, which also gives a hard timeout and a kill. Prototype used for the probes:

```powershell
param([string]$Script, [int]$TimeoutMs = 15000)
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = "C:\Program Files\AutoHotkey\v2\AutoHotkey64.exe"
$psi.Arguments = "/ErrorStdOut `"$Script`""
$psi.UseShellExecute = $false
$psi.RedirectStandardOutput = $true
$psi.RedirectStandardError = $true
$proc = [System.Diagnostics.Process]::Start($psi)
$out = $proc.StandardOutput.ReadToEndAsync()
if (-not $proc.WaitForExit($TimeoutMs)) { Stop-Process -Id $proc.Id -Force }
Write-Output $out.Result
```

Independent of the launcher, every ACU script needs an `OnError` handler that prints and exits, so a runtime error never becomes a modal dialog. The `/include` command-line switch can inject such a prelude before the agent's script without the agent writing boilerplate. (https://www.autohotkey.com/docs/v2/Scripts.htm#cmd) `/ErrorStdOut` covers only load-time syntax errors. (same page)

## Proposed experiment before committing to the design

A jiggle test, run on this machine with `master.ahk` both running and stopped:

1. Script A shows a small AHK Gui with a 24x24 button that counts clicks.
2. Script B moves the physical cursor to a random screen point every 1 ms in SendEvent mode for 30 seconds.
3. ACU-style script C issues 200 `Click x, y` on the button through the launcher, one process per click.

Expected: hit rate near 100% in both conditions, because of the absolute-coordinate events. If the SendEvent-fallback condition drops hits, add `SetMouseDelay -1` and retest, then `BlockInput "MouseMove"` and retest. This is the test that turns principle 3 from a belief into a number.

## Sources

- AutoHotkey source, commit 47eabd41: `source/keyboard_mouse.cpp` (SendKeys 180-215, PerformMouseCommon 1977-2031, MouseClick 2116-2300, MouseMove 2355-2420, MouseEvent 2496-2504, SendEventArray 2718-2790), `source/hook.cpp` (27-28, 4059-4090).
- https://www.autohotkey.com/docs/v2/lib/SendMode.htm
- https://www.autohotkey.com/docs/v2/lib/Send.htm
- https://www.autohotkey.com/docs/v2/lib/BlockInput.htm
- https://www.autohotkey.com/docs/v2/lib/CoordMode.htm
- https://www.autohotkey.com/docs/v2/lib/ControlClick.htm
- https://www.autohotkey.com/docs/v2/misc/DPIScaling.htm
- https://www.autohotkey.com/docs/v2/FAQ.htm#uac
- https://www.autohotkey.com/docs/v2/Scripts.htm#cmd
- https://www.autohotkey.com/docs/v2/lib/FileOpen.htm (stdin and stdout via `"*"`)
- https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-sendinput
- Probe scripts: `acu_probe.ahk`, `acu_probe2.ahk` (temporary, deleted after this note), output quoted above.
