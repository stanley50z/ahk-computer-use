# Optimize for short scripts, not for input injection atomicity

The founding principle asked that a scripted click land even while the user moves the mouse. AutoHotkey normally submits one SendInput batch, but at the time of this decision another AutoHotkey script held the mouse hook, forcing mouse input to fall back to SendEvent. Suspending that script would disrupt the user's hotkeys; adding our own hook would not remove the other script's hook. We chose short scripts over an atomicity guarantee because what the user perceives is how long the desktop is occupied, not the injection mode. The historical jiggle test measured about 99 percent hits in both modes with the cursor moving 60 to 380 times a second; that is evidence for this decision, not a guarantee for another environment.

## Consequences

- The prelude removes default injected mouse delays. The skill favors short scripts with observable waits instead of fixed sleeps; opt-in paced input helpers use deliberate press and movement durations.
- ACU has no persistent desktop-control session or take-back-control button. The launcher enforces a time limit on each script. Handling interruption of a running launcher is separate from that architectural choice.
- The jiggle experiment lives in `experiments/jiggle/`. Retain measured results as historical evidence and distinguish them from current validation; documentation must not claim an unmeasured hit rate.
