"""User recordings from the tray recorder (acu/recorder.ahk): start it, and read one back as a timeline.

A recording folder holds steps.jsonl, one JSON object per step, with NNN-tree.txt and NNN.png beside it. Step 0 is
the state when recording started. Every later step lists the user's actions since the previous capture and the state
after them. summarize() prints each step's actions with their target element's dump line, then how the window's tree
changed since the last capture of the same window, so an agent can see what an action did without diffing files.
"""

import ctypes
import difflib
import json
import subprocess
from pathlib import Path

from . import run as launcher

RECORDER = Path(__file__).resolve().parent / "recorder.ahk"
MAX_CHANGES = 40  # changed tree lines printed per step; the rest are counted and left in the tree files


def recordings_root() -> Path:
    return launcher.acu_home() / "recordings"


def start_recorder() -> str:
    """Start the tray app under the UI Access build; a second start leaves the running one alone."""
    exe = launcher.ahk_exe()
    params = subprocess.list2cmdline([str(RECORDER), f"{launcher.HOME_ARG}{launcher.acu_home()}"])
    ctypes.windll.kernel32.CloseHandle(launcher.shell_execute(exe, params))
    return f"ACU recorder is in the notification area; click its icon to start or stop recording.\nRecordings: {recordings_root()}"


def latest_recording(root: Path) -> Path:
    folders = sorted(path for path in root.glob("*") if (path / "steps.jsonl").is_file())
    if not folders:
        raise ValueError(f"no recordings in {root}")
    return folders[-1]


def tree_lines(path: Path) -> list[str]:
    """Element lines of a dump, without its window= header and elements=/truncated= footer."""
    lines = path.read_text(encoding="utf-8").splitlines()
    return [line for line in lines if line and not line.startswith(("window=", "elements=", "truncated="))]


def tree_changes(before: list[str], after: list[str]) -> list[str]:
    """Removed (-) and added (+) element lines. Lines compare without their path, so an element inserted above
    others does not show every later sibling as changed; the printed lines keep their paths."""
    def unpathed(line: str) -> str:
        return line.split(" ", 1)[1] if " " in line else line

    matcher = difflib.SequenceMatcher(None, [unpathed(line) for line in before], [unpathed(line) for line in after], autojunk=False)
    changes = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag != "equal":
            changes += [f"- {line}" for line in before[i1:i2]] + [f"+ {line}" for line in after[j1:j2]]
    return changes


def describe_target(target: dict | None) -> str:
    if not target:
        return ""
    window = target.get("window", {})
    where = f' in "{window.get("title", "")}" {window.get("exe", "")}'.rstrip()
    if "error" in target:
        return f" (target unknown: {target['error']}){where}"
    return f" on {target['line']}{where}"


def describe_action(action: dict) -> str:
    kind = action.get("kind")
    target = describe_target(action.get("target"))
    if kind == "click":
        count = {1: "click", 2: "double-click"}.get(action.get("count", 1), f"{action.get('count')}x click")
        return f"{action['button']} {count} at {action['x']},{action['y']}{target}"
    if kind == "drag":
        return (f"{action['button']} drag {action['from'][0]},{action['from'][1]} to {action['to'][0]},{action['to'][1]}{target}"
                f"\n         dropped{describe_target(action.get('drop'))}")
    if kind == "scroll":
        notches = action["delta"] / 120
        return f"scroll {action['axis']} {notches:+g} notches at {action['x']},{action['y']}{target}"
    if kind == "type":
        text = f"{action['length']} masked characters" if action.get("masked") else json.dumps(action.get("text", ""), ensure_ascii=False)
        erased = f" after erasing {action['backspaces']} characters" if action.get("backspaces") else ""
        return f"type {text}{erased} into{target.removeprefix(' on')}"
    if kind in ("key", "hotkey"):
        count = f" x{action['count']}" if action.get("count", 1) > 1 else ""
        return f"{kind} {action['keys']}{count}{', focus' + target.removeprefix(' on') if target else ''}"
    return json.dumps(action, ensure_ascii=False)


def summarize(folder: str | None = None) -> str:
    path = Path(folder) if folder else latest_recording(recordings_root())
    steps_file = path / "steps.jsonl"
    if not steps_file.is_file():
        raise ValueError(f"not a recording (no steps.jsonl): {path}")
    steps = [json.loads(line) for line in steps_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    final = bool(steps and steps[-1].get("final"))
    out = [f"Recording {path}",
           f"{len(steps)} steps{'' if final else ', no final step (still recording, or the recorder stopped unexpectedly)'}."
           " Each step lists the user's actions since the previous capture, then the state after them.", ""]
    trees: dict[int, tuple[int, list[str]]] = {}  # hwnd -> (step, element lines) of its latest captured tree
    previous_window = None
    for step in steps:
        window = step.get("window") or {}
        title = f'"{window.get("title", "")}" {window.get("exe", "")} (hwnd {window.get("hwnd")})' if window else "no window"
        same = previous_window is not None and window.get("hwnd") == previous_window
        out.append(f"Step {step['step']} at {step['ms'] / 1000:.1f}s{' (final)' if step.get('final') else ''}, window {'unchanged' if same else title}")
        for action in step.get("actions", []):
            out.append(f"  {action['ms'] / 1000:6.1f}s {describe_action(action)}")
        if step["step"] and not step.get("actions"):
            out.append("  no actions")
        if step.get("focus") and "line" in step["focus"]:
            out.append(f"  focus after: {step['focus']['line']}")
        files = [f"tree {step['tree']}" if "tree" in step else f"tree failed: {step.get('tree_error')}"]
        shot = step.get("screenshot")
        if shot:
            x, y, w, h = shot["source"]
            files.append(f"screenshot {shot['file']} (source {x},{y} {w}x{h}, scale {shot['scale']:g})")
        else:
            files.append(f"screenshot failed: {step.get('screenshot_error')}")
        out.append("  " + ", ".join(files))
        if step.get("input_during_capture"):
            out.append("  input arrived during this capture; its tree or screenshot may already show part of the next step")
        if "tree" in step:
            lines = tree_lines(path / step["tree"])
            hwnd = window.get("hwnd")
            if hwnd in trees:
                base_step, base_lines = trees[hwnd]
                changes = tree_changes(base_lines, lines)
                if not changes:
                    out.append(f"  tree unchanged since step {base_step}")
                else:
                    out.append(f"  tree changes since step {base_step} ({len(changes)} lines):")
                    out += [f"    {line}" for line in changes[:MAX_CHANGES]]
                    if len(changes) > MAX_CHANGES:
                        out.append(f"    ... {len(changes) - MAX_CHANGES} more; compare {base_step:03}-tree.txt with {step['tree']}")
            else:
                out.append(f"  first capture of this window: {len(lines)} elements")
            trees[hwnd] = (step["step"], lines)
        previous_window = window.get("hwnd")
        out.append("")
    return "\n".join(out).rstrip() + "\n"
