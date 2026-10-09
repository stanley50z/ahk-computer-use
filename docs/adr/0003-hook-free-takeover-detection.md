# Detect takeover by comparing cursor and foreground, without a hook

At the end of a script the prelude restores the entry state, but only when the user did not take over. AutoHotkey's physical-idle timer only distinguishes the user's input from ours when our own keyboard and mouse hooks are installed, and any AutoHotkey hook downgrades SendInput for every other AutoHotkey script on the machine. So the prelude shadows the mouse functions to remember where it placed the cursor and which processes it clicked, and compares that record with reality at exit.

## Consequences

- A user who moves the mouse and puts it back exactly is not detected; restoring to the same place is harmless.
- Keyboard-only takeover and clicks written inside `Send` are not detected. Accepted until real use shows it matters, at which point a hook behind a setting is the next step.
- A script whose purpose is to leave a window showing declares keep-foreground instead of fighting restore.
