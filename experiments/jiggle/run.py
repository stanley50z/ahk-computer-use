"""Jiggle test: how often does an ACU click land while something else keeps moving the cursor?

Usage: python experiments/jiggle/run.py [--clicks 200]

Starts target.ahk, a window with a 24x24 button, and jiggler.ahk, which moves the cursor to a random point
on the primary monitor about every millisecond. Then fires one `Click x, y` at the button per launcher
process and reports hits, launcher failures, timing, and whether another AutoHotkey script held the mouse
hook at the time, which makes AutoHotkey fall back from SendInput to SendEvent.

Takes about a minute and the whole desktop. Run it twice, with the hook-holding script running and
stopped, and record both results in README.md. Not part of the pytest suite.
"""

import argparse
import ctypes
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from ctypes import wintypes
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO))
from acu.run import ahk_exe, request_close  # noqa: E402

TARGET_TITLE = "ACU jiggle target"
ERROR_ALREADY_EXISTS = 183

user32 = ctypes.windll.user32
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
user32.FindWindowW.restype = ctypes.c_void_p
user32.FindWindowW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p]
user32.FindWindowExW.restype = ctypes.c_void_p
user32.FindWindowExW.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_wchar_p]
user32.GetWindowRect.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.RECT)]
kernel32.CreateMutexW.restype = ctypes.c_void_p
kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
kernel32.CloseHandle.argtypes = [ctypes.c_void_p]


def another_ahk_holds_mouse_hook() -> bool:
    """The check AutoHotkey itself makes before using SendInput: does the mutex its mouse hook creates exist?"""
    handle = kernel32.CreateMutexW(None, False, "AHK Mouse")
    exists = ctypes.get_last_error() == ERROR_ALREADY_EXISTS
    kernel32.CloseHandle(handle)
    return exists


def start_ahk(script: Path, env: dict[str, str]) -> subprocess.Popen:
    return subprocess.Popen(
        [str(ahk_exe()), str(script)],
        env={**os.environ, **env},
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def wait_for_window(title: str) -> int:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        hwnd = user32.FindWindowW(None, title)
        if hwnd and user32.IsWindowVisible(hwnd):
            return hwnd
        time.sleep(0.05)
    raise SystemExit(f"window {title!r} never appeared")


def button_center(window: int) -> tuple[int, int]:
    button = user32.FindWindowExW(window, None, "Button", None)
    rect = wintypes.RECT()
    user32.GetWindowRect(button, ctypes.byref(rect))
    return (rect.left + rect.right) // 2, (rect.top + rect.bottom) // 2


def read_int(path: Path) -> int | None:
    return int(path.read_text()) if path.is_file() else None


def main() -> None:
    parser = argparse.ArgumentParser(description="Measure the ACU click hit rate under continuous cursor movement.")
    parser.add_argument("--clicks", type=int, default=200)
    args = parser.parse_args()

    workdir = Path(tempfile.mkdtemp(prefix="acu-jiggle-"))
    count_file = workdir / "hits.txt"
    moves_file = workdir / "moves.txt"
    target = start_ahk(HERE / "target.ahk", {"ACU_JIGGLE_COUNT_FILE": str(count_file)})
    jiggler = None
    try:
        x, y = button_center(wait_for_window(TARGET_TITLE))
        hook_held = another_ahk_holds_mouse_hook()
        jiggler = start_ahk(HERE / "jiggler.ahk", {"ACU_JIGGLE_MOVES_FILE": str(moves_file), "ACU_JIGGLE_SECONDS": "300"})
        time.sleep(0.5)

        click_env = {**os.environ, "ACU_JIGGLE_X": str(x), "ACU_JIGGLE_Y": str(y), "ACU_HOME": str(workdir / "ACU")}
        command = [sys.executable, str(REPO / "acu" / "run.py"), str(HERE / "click.ahk"), "--timeout", "10"]
        script_ms: list[int] = []
        launcher_ms: list[int] = []
        failures: list[str] = []
        started = time.monotonic()
        for _ in range(args.clicks):
            t0 = time.monotonic()
            result = subprocess.run(command, env=click_env, capture_output=True, text=True, encoding="utf-8")
            launcher_ms.append(round((time.monotonic() - t0) * 1000))
            trailer = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else ""
            if result.returncode != 0:
                failures.append(trailer)
            elif match := re.search(r"ok (\d+)ms", trailer):
                script_ms.append(int(match.group(1)))
        jiggling_seconds = time.monotonic() - started

        request_close(jiggler.pid)
        jiggler.wait(timeout=5)
        time.sleep(0.2)
        hits = read_int(count_file) or 0
        moves = read_int(moves_file)
    finally:
        for proc in (jiggler, target):
            if proc is not None and proc.poll() is None:
                proc.kill()

    report = {
        "clicks": args.clicks,
        "hits": hits,
        "hit_rate": hits / args.clicks,
        "launcher_failures": failures,
        "another_ahk_held_mouse_hook": hook_held,
        "send_mode_in_effect": "SendEvent" if hook_held else "SendInput",
        "jiggler_moves_per_second": round(moves / jiggling_seconds) if moves else None,
        "script_ms_mean": round(sum(script_ms) / len(script_ms)) if script_ms else None,
        "script_ms_max": max(script_ms) if script_ms else None,
        "launcher_ms_mean": round(sum(launcher_ms) / len(launcher_ms)),
        "target": [x, y],
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
