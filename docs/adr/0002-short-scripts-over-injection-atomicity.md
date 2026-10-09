# Optimize for short scripts, not for input injection atomicity

The founding principle asked that a scripted click land even while the user moves the mouse. AutoHotkey delivers that through one atomic SendInput batch, but on this machine another AutoHotkey script holds the mouse hook, which downgrades every send to SendEvent, and recovering the batch would mean suspending the user's hotkeys on every step or installing a hook of our own. We decided not to, because what the user perceives is how long the desktop is occupied, not the injection mode: the jiggle test measured about 99 percent hits in both modes with the cursor moving 60 to 380 times a second.

## Consequences

- The prelude removes injected mouse delays, the skill demands short scripts with observable waits instead of sleeps, and the launcher's time limit is the only stop.
- There is no cancel or take-back-control feature, because nothing persists between scripts for it to stop.
- Measured numbers live in the README; a README must not claim a hit rate that was not measured.
