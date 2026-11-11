"""Run the bench's `launch/windows_session.py` with its fixed screen positions on a chosen display.

The bench places BenchLab, the witness and "User activity" windows and the pointer park point at fixed
physical coordinates on the primary display. This runs the unmodified launcher with those four positions
moved by the chosen display's desktop origin, and with the launcher made per-monitor DPI aware so the
pointer park uses the same physical coordinates as BenchLab and the sentinel (on the bench's own 100%
VM both are no-ops). run.py calls it:

    python session.py --bench <macos_bench> [--display \\\\.\\DISPLAY2] -- <windows_session.py arguments>
"""

from __future__ import annotations

import argparse
import ctypes
import importlib.util
import sys
from pathlib import Path

ctypes.windll.shcore.SetProcessDpiAwareness(2)
sys.path.insert(0, str(Path(__file__).resolve().parent))
from display import mode  # noqa: E402


def shifted(frame: tuple[int, ...], dx: int, dy: int) -> tuple[int, ...]:
    return (frame[0] + dx, frame[1] + dy, *frame[2:])


def main() -> int:
    split = sys.argv.index("--")
    parser = argparse.ArgumentParser()
    parser.add_argument("--bench", type=Path, required=True)
    parser.add_argument("--display")
    args = parser.parse_args(sys.argv[1:split])
    spec = importlib.util.spec_from_file_location("windows_session", args.bench / "launch" / "windows_session.py")
    session = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(session)
    if args.display:
        m = mode(args.display)
        dx, dy = m.dmPositionX, m.dmPositionY
        session.LAB_FRAME = shifted(session.LAB_FRAME, dx, dy)
        session.WITNESS_FRAME = shifted(session.WITNESS_FRAME, dx, dy)
        session.v2.USER_WINDOW_FRAME = shifted(session.v2.USER_WINDOW_FRAME, dx, dy)
        session.v2.PARK_POINT = shifted(session.v2.PARK_POINT, dx, dy)
    return session.main(sys.argv[split + 1:])


if __name__ == "__main__":
    sys.exit(main())
