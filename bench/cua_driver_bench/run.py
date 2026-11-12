r"""Run Cua Driver Bench's Windows tasks against ACU, one trial at a time, resuming where it stopped.

    python run.py --bench "<cua checkout>/libs/cua-driver-bench/automated-eval/macos_bench" \
        --python "<Python 3.12 with wxPython>" --out "<results dir>" \
        [--tasks MB-09 ...] [--conditions foreground background] [--runs 5] [--model claude-sonnet-5-5] \
        [--display \\.\DISPLAY2] [--tool-exe "Cua Spaces.exe" ...]

Without --tasks it runs every Bench v2 task the manifest lists for Windows, in manifest order; each task
runs in the conditions the manifest lists for it, with run indexes 0 to runs-1 (the bench's seeds). A trial
lands in <out>/<condition>/<task>-r<index>/ with the bench's row.json, the agent transcript and the
adapter log. --display runs the trials on that display instead of the primary (session.py moves the
bench's fixed window positions there; display.py switches it to the 1920 x 1080 at 100% the bench
assumes). A trial with a row.json and no harness error is skipped on the next start; a harness error
is retried up to --retries times with the same seed. --tool-exe is passed to the launcher: a shell whose
parent is one of those executables does not fail the GUI-only guard (use it for background apps of this
machine that start shells by themselves, never for the tool under test).

Progress goes to <out>/run.log. Create <out>/STOP to stop after the current trial.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

AGENT = Path(__file__).resolve().with_name("agent.py")
SESSION = Path(__file__).resolve().with_name("session.py")


# The (task, conditions) pairs of the bench's manifest that run on Windows, in schedule order.
def manifest_tasks(bench: Path) -> list[tuple[str, list[str]]]:
    manifest = json.loads((bench.parents[1] / "taskpack" / "v2-taskset.json").read_text(encoding="utf-8"))
    return [(t["id"], t["conditions"]) for t in manifest["tasks"] if "windows" in t["os"]]


def schedule(bench: Path, tasks: list[str] | None, conditions: list[str], runs: int) -> list[tuple[str, str, int]]:
    chosen = [(t, c) for t, c in manifest_tasks(bench) if not tasks or t in tasks]
    missing = set(tasks or []) - {t for t, _ in chosen}
    if missing:
        raise SystemExit(f"not Windows tasks of the manifest: {sorted(missing)}")
    return [(task, condition, index) for index in range(runs) for condition in conditions
            for task, allowed in chosen if condition in allowed]


def finished(trial: Path) -> bool:
    row = trial / "row.json"
    if not row.exists():
        return False
    return not json.loads(row.read_text(encoding="utf-8")).get("harness_error")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bench", type=Path, required=True)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--tasks", nargs="*")
    parser.add_argument("--conditions", nargs="*", default=["foreground", "background"])
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--model", default="claude-sonnet-5-5")
    parser.add_argument("--timeout", default="360")
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--tool-exe", action="append", default=[])
    parser.add_argument("--display")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    log = (args.out / "run.log").open("a", encoding="utf-8", buffering=1)
    plan = schedule(args.bench.resolve(), args.tasks, args.conditions, args.runs)
    log.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} plan {len(plan)} trials, model {args.model}\n")
    for task, condition, index in plan:
        if (args.out / "STOP").exists():
            log.write(f"{time.strftime('%H:%M:%S')} STOP file found, stopping\n")
            return 0
        trial = args.out / condition / f"{task}-r{index}"
        for attempt in range(args.retries + 1):
            if finished(trial):
                break
            command = [
                str(args.python), str(SESSION), "--bench", str(args.bench),
                *(["--display", args.display] if args.display else []), "--",
                "--task", task, "--run-index", str(index), "--condition", condition, "--out", str(trial),
                "--label", "acu", "--timeout", args.timeout,
                *[part for exe in args.tool_exe for part in ("--tool-exe", exe)],
                "--", sys.executable, str(AGENT), "--model", args.model,
            ]
            started = time.monotonic()
            done = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
            summary = done.stdout.strip().splitlines()[-1:] or [done.stderr.strip()[-400:]]
            log.write(f"{time.strftime('%H:%M:%S')} {condition} {task} r{index} try {attempt + 1} "
                      f"{round(time.monotonic() - started)}s exit {done.returncode}: {summary[0]}\n")
    log.write(f"{time.strftime('%H:%M:%S')} done\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
