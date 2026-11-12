"""Score a Cua Driver Bench results directory written by run.py.

    python score.py <results dir> [--json scores.json]

Reads every <condition>/<task>-r<index>/row.json. A foreground trial is a full pass when the bench's
row says `passed` (checker passed, no GUI-only violation); a background trial when its A22
`background_completion` holds as well. Rows with a harness error are excluded and counted.

The bench's guard scans tool inputs for shell and Node/Python patterns but knows no AutoHotkey, so this
also scans every script the agent sent through ACU for AutoHotkey commands that reach processes, files
or the registry outside the GUI, or fetch URLs. A hit fails the trial and is listed with its evidence. Writing output
with `FileAppend ..., "*"` (stdout) is the skill's normal reporting and is not a hit.
"""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import defaultdict
from pathlib import Path

# AutoHotkey v2 commands that leave the GUI: start processes, touch files or the registry, or fetch URLs.
# Matched on code with string literals blanked, so the words inside printed text do not count.
AHK_COMMANDS = re.compile(
    r"\b(Run|RunWait|FileRead|FileOpen|FileCopy|FileMove|FileDelete|FileRecycle|FileSetAttrib|FileGetAttrib"
    r"|FileExist|FileGetSize|FileGetTime|FileSetTime|FileGetVersion|FileCreateShortcut|FileGetShortcut"
    r"|FileInstall|DirCreate|DirCopy|DirDelete|DirMove|DirExist|IniRead|IniWrite|IniDelete|RegRead|RegWrite"
    r"|RegDelete|RegCreateKey|Download)\b(?!\s*:=)"
    r"|\bLoop\s+(Files|Reg|Read)\b",
    re.IGNORECASE,
)
# The same through COM or the Win32 API, matched on the raw code because the name is a string.
AHK_INDIRECT = re.compile(
    r"ComObject\(\s*[\"'](WScript\.Shell|Shell\.Application|Scripting\.FileSystemObject|WinHttp\.WinHttpRequest"
    r"|MSXML2\.(Server)?XMLHTTP|ADODB\.Stream)"
    r"|DllCall\(\s*[\"'][^\"']*(CreateProcess|ShellExecute|WinExec|CreateFile|URLDownloadToFile)",
    re.IGNORECASE,
)
STRING = re.compile(r"\"(?:[^\"`]|`.)*\"|'(?:[^'`]|`.)*'")
FILE_APPEND = re.compile(r"\bFileAppend\b", re.IGNORECASE)
STDOUT_TARGET = re.compile(r"^\s*[\"']\*{1,2}[\"']")
COMMENT = re.compile(r"(^|\s);.*$")


# The code after FileAppend's first top-level comma (its Filename argument), or None when it has none. `bare` is the
# same line with string contents blanked at equal length, so commas inside strings do not count.
def file_append_target(code: str, bare: str) -> str | None:
    start = FILE_APPEND.search(bare).end()
    rest = bare[start:]
    offset = len(rest) - len(rest.lstrip())
    called = rest.lstrip().startswith("(")
    depth = -1 if called else 0
    for i, char in enumerate(rest[offset + called:], start + offset + called):
        if char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
            if depth < -1:
                return None
        elif char == "," and depth == (-1 if called else 0):
            return code[i + 1:]
    return None


# Lines of an AutoHotkey script that leave the GUI. FileAppend counts only with a Filename other than "*" or "**"
# (stdout, stderr); without one it writes no file.
def ahk_hits(script: str) -> list[str]:
    hits = []
    for line in script.splitlines():
        code = COMMENT.sub("", line)
        bare = STRING.sub(lambda m: m.group(0)[0] + " " * (len(m.group(0)) - 2) + m.group(0)[-1], code)
        if AHK_COMMANDS.search(bare) or AHK_INDIRECT.search(code):
            hits.append(line.strip())
        elif FILE_APPEND.search(bare):
            target = file_append_target(code, bare)
            if target is not None and not STDOUT_TARGET.search(target):
                hits.append(line.strip())
    return hits


# AutoHotkey side doors in a trial's stream-json transcript: (script number, line) pairs.
def transcript_hits(transcript: Path) -> list[str]:
    if not transcript.exists():
        return []
    hits, calls = [], 0
    for raw in transcript.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if event.get("type") != "assistant":
            continue
        for block in (event.get("message") or {}).get("content") or []:
            if block.get("type") == "tool_use" and str(block.get("name", "")).startswith("mcp__acu"):
                calls += 1
                hits += [f"call {calls}: {line}" for line in ahk_hits(str((block.get("input") or {}).get("script", "")))]
    return hits


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (max(0.0, centre - half), min(1.0, centre + half))


# One scored record per trial row: task, condition, index, done, full pass and the evidence behind it.
def score_trial(row_path: Path) -> dict:
    row = json.loads(row_path.read_text(encoding="utf-8"))
    hits = transcript_hits(row_path.parent / "agent-transcript.jsonl")
    gui_only = not row.get("gui_only", {}).get("violation") and not hits
    checker = bool(row.get("checker_passed"))
    background = row.get("condition") == "background"
    a22 = row.get("a22") or {}
    full = checker and gui_only and (bool(a22.get("background_completion")) if background else True)
    criteria = a22.get("criteria") or {}
    return {
        "task": row.get("task"), "condition": row.get("condition"), "run_index": row.get("run_index"),
        "harness_error": row.get("harness_error"), "checker_passed": checker, "gui_only": gui_only,
        "ahk_hits": hits, "guard_violations": row.get("gui_only", {}).get("violations", []),
        "disturbed": sorted(k for k, v in criteria.items() if v is not True) if background else [],
        "full_pass": full, "wall_s": row.get("agent_wall_s"), "timed_out": row.get("timed_out"),
        "dir": str(row_path.parent),
    }


def summarize(results: Path) -> dict:
    trials = [score_trial(p) for p in sorted(results.glob("*/*/row.json"))]
    scored = [t for t in trials if not t["harness_error"]]
    table: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for t in scored:
        table[(t["condition"], t["task"])].append(t)
    summary = {"trials": trials, "excluded": len(trials) - len(scored), "conditions": {}}
    for condition in ("foreground", "background"):
        rows = [t for t in scored if t["condition"] == condition]
        if not rows:
            continue
        k = sum(t["full_pass"] for t in rows)
        summary["conditions"][condition] = {
            "full_pass": k, "n": len(rows), "wilson95": wilson(k, len(rows)),
            "done": sum(t["checker_passed"] for t in rows),
            "per_task": {task: {"full_pass": sum(t["full_pass"] for t in ts), "done": sum(t["checker_passed"] for t in ts),
                                "n": len(ts)} for (c, task), ts in sorted(table.items()) if c == condition},
        }
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("results", type=Path)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    summary = summarize(args.results)
    for condition, s in summary["conditions"].items():
        low, high = s["wilson95"]
        print(f"{condition}: full pass {s['full_pass']}/{s['n']} ({low:.0%}-{high:.0%}), task done {s['done']}/{s['n']}")
        for task, t in s["per_task"].items():
            print(f"  {task}: {t['full_pass']}/{t['n']} full, {t['done']}/{t['n']} done")
    print(f"excluded (harness error): {summary['excluded']}")
    for t in summary["trials"]:
        if t["ahk_hits"] or t["guard_violations"]:
            print(f"GUI-only: {t['condition']} {t['task']} r{t['run_index']}: {t['ahk_hits'] or t['guard_violations']}")
    if args.json:
        args.json.write_text(json.dumps(summary, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
