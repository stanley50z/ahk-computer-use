"""Run the bench's `launch/windows_session.py` with its fixed screen positions on a chosen display.

The bench places BenchLab, the witness and "User activity" windows, the pointer park point and the
multi-app tasks' windows at fixed physical coordinates on the primary display. This runs the unmodified
launcher with those positions moved by the chosen display's desktop origin, and with the launcher made
per-monitor DPI aware so the pointer park uses the same physical coordinates as BenchLab and the sentinel
(on the bench's own 100% VM both are no-ops).

It also keeps the user's own Chrome open: CDB-G04's cleanup stops every `chrome.exe` of the desktop session
by name, and here it stops only the Chrome running on the task workspace's profile. run.py calls it:

    python session.py --bench <macos_bench> [--display \\\\.\\DISPLAY2] -- <windows_session.py arguments>
"""

from __future__ import annotations

import argparse
import ctypes
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import psutil

sys.path.insert(0, str(Path(__file__).resolve().parent))
from display import mode  # noqa: E402

# The bench checkout of the latest session, so abort.py can find the task workspaces after the run ended.
LAST_BENCH = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "cdb-bench" / "last-bench.txt"


def shifted(frame: tuple[int, ...], dx: int, dy: int) -> tuple[int, ...]:
    return (frame[0] + dx, frame[1] + dy, *frame[2:])


# Give every multi-app task (the bench's windows/cdb.py module) its window bounds moved by (dx, dy).
def move_task_windows(cdb, dx: int, dy: int) -> None:
    init = cdb.CdbTask.__init__

    def __init__(self, *args, **kwargs):
        init(self, *args, **kwargs)
        for app in self.descriptor["apps"]:
            bounds = (app.get("window") or {}).get("bounds")
            if bounds:
                bounds["x"] += dx
                bounds["y"] += dy

    cdb.CdbTask.__init__ = __init__


# Chrome processes whose command line names the task workspace (its --user-data-dir lives there).
def task_chrome(workspace: Path) -> list[int]:
    root = str(workspace).lower()
    return [p.pid for p in psutil.process_iter(["name", "cmdline"])
            if (p.info["name"] or "").lower() == "chrome.exe"
            and any(root in arg.lower().replace("/", "\\") for arg in p.info["cmdline"] or [])]


# Make the bench's cleanup stop the task's Chrome by its profile instead of every chrome.exe by name. The
# trial's own Chrome is also stopped through its process tree by CdbTask.stop_apps.
def spare_users_chrome(cdb) -> None:
    names = cdb.process_names
    cdb.process_names = lambda descriptor: names(descriptor) - {"chrome.exe"}
    clear = cdb.CdbTask.clear_leftovers

    def clear_leftovers(self):
        clear(self)
        if "chrome.exe" in names(self.descriptor):
            for pid in task_chrome(self.workspace):
                subprocess.run(["taskkill", "/T", "/F", "/PID", str(pid)], capture_output=True)

    cdb.CdbTask.clear_leftovers = clear_leftovers


def main() -> int:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
    split = sys.argv.index("--")
    parser = argparse.ArgumentParser()
    parser.add_argument("--bench", type=Path, required=True)
    parser.add_argument("--display")
    args = parser.parse_args(sys.argv[1:split])
    LAST_BENCH.parent.mkdir(parents=True, exist_ok=True)
    LAST_BENCH.write_text(str(args.bench.resolve()), encoding="utf-8")
    spec = importlib.util.spec_from_file_location("windows_session", args.bench / "launch" / "windows_session.py")
    session = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(session)
    import cdb  # the bench's windows/cdb.py, on the path the launcher just set up

    spare_users_chrome(cdb)
    if args.display:
        m = mode(args.display)
        dx, dy = m.dmPositionX, m.dmPositionY
        session.LAB_FRAME = shifted(session.LAB_FRAME, dx, dy)
        session.WITNESS_FRAME = shifted(session.WITNESS_FRAME, dx, dy)
        session.v2.USER_WINDOW_FRAME = shifted(session.v2.USER_WINDOW_FRAME, dx, dy)
        session.v2.PARK_POINT = shifted(session.v2.PARK_POINT, dx, dy)
        move_task_windows(cdb, dx, dy)
    return session.main(sys.argv[split + 1:])


if __name__ == "__main__":
    sys.exit(main())
