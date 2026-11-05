# Record the user's actions as steps of tree and screenshot captures

An agent that knows how a user worked an app can choose a working action chain or snippet instead of rediscovering one. The tray recorder (`acu recorder`, `acu/recorder.ahk`) saves what the user does and how the window's tree changed. `acu recording` prints a recording as a timeline. A recording only adds evidence. It does not create or change snippets.

## Decisions

- **Resident AutoHotkey, outside the launcher.** The recorder runs as a long-lived tray script under the UI Access build. It includes `UIA.ahk`, `AcuTree` and `AcuScreenshot` directly, so a capture costs no process start and its dump lines match `tree.ahk` exactly. The launcher's 300-second limit and desktop lease would not fit a recording. The recorder does not use the prelude, which redirects output for a single run.
- **Raw Input, not a hook.** As in `bench/input_recorder.py`, a hidden window receives `WM_INPUT` with `RIDEV_INPUTSINK`. Any low-level hook would make ACU's `SendInput` fall back to `SendEvent` while the recorder runs. Raw Input does not distinguish injected input, and recordings accept that.
- **Steps end on quiet input.** UI Automation reads take time and the app needs time to react, so the state between two fast actions cannot be captured reliably. A capture waits until input has been quiet for 600 ms after a click, scroll or hotkey and 1,200 ms after other keys. Actions inside that window share a step. Movement is ignored, and a capture waits while a mouse button is held.
- **Targets are dump lines.** An action's target is the element's dump line with its control-view path, computed by walking up to the top-level window. The same element is then findable in the tree files without a second identity scheme. The line is read when the input is processed, possibly after a capture, so its value and state flags can be late, while its path, type, name and id are not.
- **The handler only queues.** UI Automation calls pump messages, and AutoHotkey does not re-enter a message handler that is still running, so a slow `WM_INPUT` handler would lose events. The handler copies events into a queue, and one 50 ms timer processes them and captures steps. A button whose release was lost is closed as a click when `GetAsyncKeyState` shows it up.
- **The tray is not the task.** A timer remembers the last foreground window outside the taskbar, the overflow flyout and the recorder's own process, and captures use it when the user is on the tray. Clicks on those windows never end a step by themselves, and the trailing ones are dropped at Stop. A step records the focused element only when the captured window has the foreground.

## Consequences

- Fast users get fewer, larger steps. Each step's actions stay in order, with their times.
- Only the foreground window's tree is saved. Separate popup windows show up as action targets and in screenshots.
- Typed text is reconstructed from keys in the foreground window's layout. IME composition is not reconstructed, and the next tree's value is the authority. Password fields store only the length.
- Recordings are unpruned user data under `ACU_HOME`, with full document text, as tree dumps already are.
