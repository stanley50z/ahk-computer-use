"""Stop a Cua Driver Bench run now and put the machine back.

    python abort.py [--bench <cua checkout>/libs/cua-driver-bench/automated-eval/macos_bench]

It stops, with their whole process trees:
- every run.py and session.py of this folder, which takes the trial's agent, ACU, BenchLab, the sentinel and
  the task apps with it;
- the script that started one of them, when that is a non-interactive shell or Python script, so a loop
  can't start the next trial;
- any process still running on a multi-app task workspace (LibreOffice hands its document to a separate
  soffice.bin, and the task Chrome runs its own browser process).

It then deletes the task workspaces and restores the display layout display.py saved (display.STATE). It is safe to run when nothing is running. The bench
path comes from the running session.py command lines, then from the last session (session.LAST_BENCH),
then from --bench.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import psutil

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import display  # noqa: E402
from session import LAST_BENCH  # noqa: E402

SCRIPTS = {str(HERE / "run.py").lower(), str(HERE / "session.py").lower()}
SHELLS = {"pwsh.exe", "powershell.exe", "cmd.exe", "bash.exe", "python.exe", "pythonw.exe"}
# Arguments that mark a shell or Python process as running a script rather than an interactive prompt.
SCRIPT_FLAGS = {"-command", "-c", "-file", "/c", "-encodedcommand"}


def cmdline(proc: psutil.Process) -> list[str]:
    try:
        return proc.cmdline()
    except psutil.Error:
        return []


def is_bench_script(args: list[str]) -> bool:
    return any(a.lower().replace("/", "\\") in SCRIPTS for a in args)


# A non-interactive shell or interpreter: it was given a script or a command, so it may loop over trials.
def runs_a_script(proc: psutil.Process) -> bool:
    try:
        name = proc.name().lower()
    except psutil.Error:
        return False
    args = [a.lower() for a in cmdline(proc)[1:]]
    return name in SHELLS and any(a in SCRIPT_FLAGS or a.endswith((".ps1", ".py", ".cmd", ".bat")) for a in args)


# The bench's run.py and session.py processes, plus each one's parent when that parent runs a script.
def bench_processes() -> tuple[list[psutil.Process], list[str]]:
    found, benches = [], []
    for proc in psutil.process_iter():
        args = cmdline(proc)
        if not is_bench_script(args):
            continue
        found.append(proc)
        if "--bench" in args[:-1]:
            benches.append(args[args.index("--bench") + 1])
        parent = proc.parent()
        if parent is not None and not is_bench_script(cmdline(parent)) and runs_a_script(parent):
            found.append(parent)
    return found, benches


# The multi-app tasks' workspace folders, from the bench checkout's Windows launch descriptors.
def workspaces(bench: Path) -> list[Path]:
    home = os.environ.get("USERPROFILE") or str(Path.home())
    roots = []
    for descriptor in (bench.parents[1] / "taskpack" / "tasks").glob("*/*/platform/launch.windows.json"):
        root = json.loads(descriptor.read_text(encoding="utf-8")).get("workspace_root")
        if root:
            roots.append(Path(root.replace("${USERPROFILE}", home)))
    return roots


def kill_tree(pid: int) -> None:
    subprocess.run(["taskkill", "/T", "/F", "/PID", str(pid)], capture_output=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bench", type=Path)
    args = parser.parse_args()
    procs, benches = bench_processes()
    # Parents first, so a loop can't start another trial while its child is being stopped.
    for proc in sorted(procs, key=lambda p: not runs_a_script(p) or is_bench_script(cmdline(p))):
        print(f"stopping {proc.pid} {' '.join(cmdline(proc))[:160]}")
        kill_tree(proc.pid)

    bench = Path(benches[0]) if benches else args.bench
    if bench is None and LAST_BENCH.exists():
        bench = Path(LAST_BENCH.read_text(encoding="utf-8").strip())
    for root in workspaces(bench) if bench else []:
        key = str(root).lower()
        for proc in psutil.process_iter():
            if any(key in a.lower().replace("/", "\\") for a in cmdline(proc)):
                print(f"stopping {proc.pid} {proc.name()} (on {root})")
                kill_tree(proc.pid)
        if root.exists():
            shutil.rmtree(root, ignore_errors=True)
            print(f"deleted {root}" if not root.exists() else f"could not delete all of {root}")
    if bench is None:
        print("bench path unknown: task workspaces not checked (pass --bench)")

    if display.STATE.exists():
        print("restored the display layout" if display.restore() else f"display layout differs; kept {display.STATE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
