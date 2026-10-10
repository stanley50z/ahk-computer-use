# ACU

ACU lets an AI agent operate this Windows desktop through AutoHotkey v2 scripts. The agent supplies the intelligence; ACU supplies the hands, the eyes, and the manual.

## Language

### Parts

**Agent**:
The AI session that writes and runs scripts. It reads output and images; it never touches the mouse itself.
_Avoid_: model, assistant, bot

**User**:
The person whose desktop ACU operates, who may touch the mouse at any moment.
_Avoid_: owner, operator, human

**Harness**:
A coding-agent product that hosts the agent and loads the skill: Claude Code, Pi, Codex, OpenCode.
_Avoid_: client, IDE, agent

**Skill**:
The document a harness loads that teaches the agent the tool interface, the loop, and when to load capability guidance.
_Avoid_: prompt, manual, instructions

**Capability**:
A discoverable ACU entry containing guidance, a parameter contract, and optionally a maintained script. Instructions-only capabilities guide the agent's own script; runnable capabilities have an implementation ACU can execute.
_Avoid_: skill (reserved for the harness-loaded document), plugin, macro

**Prelude**:
The code ACU places ahead of every script so that coordinates, DPI, errors, restore, and the accessibility tree are already taken care of.
_Avoid_: header, bootstrap, runtime

**Launcher**:
The program that runs one script under the prelude, captures its output, enforces its time limit, and records the run.
_Avoid_: runner, wrapper, executor

**UI Access**:
The Windows privilege a script runs with, which lets it see and drive elevated windows without being elevated itself. The UAC consent prompt is outside it.
_Avoid_: elevation, admin mode, run as administrator

### A script's life

**Script**:
One AutoHotkey v2 file, supplied by the agent or maintained by ACU, for one action chain run through the launcher. Script variables and its AHK process do not persist between executions; effects on applications can.
_Avoid_: tool call, command, action, macro

**Action chain**:
The sequence of desktop steps one script performs when the agent can predict the states in between: press a button, wait for its dialog, act inside it.
_Avoid_: task, workflow, step

**Loop**:
Look, act, check. The agent repeats it until the user's postcondition is observed, never until a script merely exits.

**Trailer**:
The launcher's last output line, its verdict on the run: ok, exit with a code, or timeout.
_Avoid_: summary, status line, footer

**Entry state**:
The foreground window and cursor position as they were when a script started.

**Restore**:
Putting the entry state back when a script ends, on success, on error, and on timeout alike.
_Avoid_: cleanup, reset

**Takeover**:
The user intervening while a script runs, recognized by the cursor not being where ACU left it. A takeover cancels restore.
_Avoid_: interruption, interference, conflict

**Keep-foreground**:
A script's declaration that its purpose is to leave an application showing, so restore puts back only the cursor.

### Finding things on screen

**Perception ladder**:
The order in which the agent locates something to act on: by element name or id, then by element bounds, then by screenshot coordinates.
_Avoid_: fallback chain, strategy

**Tree**:
The structure of elements a window publishes through UI Automation; the same tree a screen reader reads.
_Avoid_: DOM, UI tree, accessibility API

**Element**:
One node of the tree, with a type, usually a name, sometimes an id and a value, and screen bounds.
_Avoid_: node, widget, item

**Control**:
An element the agent can operate: it supports an action such as invoke, toggle, value, select, or expand.
_Avoid_: button (unless it is one), component

**Classic control**:
A Win32 child window with a class name and number, the pre-tree way applications exposed buttons and fields. Most modern applications have none.

**Control view**:
The tree with purely structural elements left out. Paths number this view.

**Path**:
The comma-separated route of child indexes from a window to an element in the control view, used when an element has no name or id.
_Avoid_: selector, locator, XPath

**Dump**:
The listing of a window's tree that the agent reads before acting: one line per element, bounded by depth and element count.
_Avoid_: snapshot, inspection

**Source rectangle**:
The screen area a screenshot was taken from, as an origin and a size, printed with every capture.

**Scale**:
Screen pixels per screenshot pixel, printed with every capture so an image point converts to a screen point.
_Avoid_: zoom factor, ratio

### Measuring

**Jiggle test**:
The experiment that measures how often a scripted click lands while something keeps moving the cursor. It settled the question of injection atomicity with a number.
