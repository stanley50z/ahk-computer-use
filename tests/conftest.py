"""Shared helpers for ACU tests. Every test runs a real AutoHotkey script through the real launcher."""

import ctypes
import os
import subprocess
import sys
import time
from ctypes import wintypes
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
LAUNCHER = REPO / "acu" / "run.py"
SCRIPTS = Path(__file__).resolve().parent / "scripts"

sys.path.insert(0, str(REPO))
from acu.run import ahk_exe  # noqa: E402

user32 = ctypes.windll.user32
# Per-monitor-v2 awareness so cursor and window coordinates read here match what the prelude sees.
user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
user32.GetForegroundWindow.restype = ctypes.c_void_p
user32.FindWindowW.restype = ctypes.c_void_p
user32.FindWindowW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p]
user32.IsWindowVisible.argtypes = [ctypes.c_void_p]
dwmapi = ctypes.windll.dwmapi
dwmapi.DwmGetWindowAttribute.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_uint]


@pytest.fixture(autouse=True)
def acu_home(tmp_path, monkeypatch):
    """Point the launcher's logs at a temp dir so tests never write to %LOCALAPPDATA%\\ACU."""
    home = tmp_path / "ACU"
    monkeypatch.setenv("ACU_HOME", str(home))
    return home


def run_launcher(script, *args, timeout=60):
    """Run any script through acu/run.py and return the CompletedProcess."""
    return subprocess.run(
        [sys.executable, str(LAUNCHER), str(script), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=timeout,
    )


def run_acu(script_name, *args, timeout=60):
    """Run tests/scripts/<script_name> through acu/run.py and return the CompletedProcess."""
    return run_launcher(SCRIPTS / script_name, *args, timeout=timeout)


def reported(stdout, key):
    """Value of the `key=value` line a script printed."""
    for line in stdout.splitlines():
        if line.startswith(key + "="):
            return line[len(key) + 1 :]
    raise AssertionError(f"no {key}= line in output:\n{stdout}")


def wait_until(condition, seconds, what):
    """Poll until condition() is true; fail with `what` if it is not within the deadline."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if condition():
            return
        time.sleep(0.05)
    raise AssertionError(what)


def foreground():
    """Handle of the current foreground window, read directly from Windows."""
    return user32.GetForegroundWindow()


def cursor():
    """Current cursor position in physical screen pixels."""
    point = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(point))
    return point.x, point.y


def set_cursor(x, y):
    """Park the cursor the way a user leaving the mouse somewhere would."""
    user32.SetCursorPos(x, y)


def monitor_rects():
    """Each attached monitor's rectangle as (x, y, width, height) in physical pixels, in enumeration order."""

    class MonitorInfo(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT), ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]

    rects = []
    callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(wintypes.RECT), ctypes.c_void_p)

    def visit(monitor, _dc, _rect, _data):
        info = MonitorInfo(cbSize=ctypes.sizeof(MonitorInfo))
        user32.GetMonitorInfoW(ctypes.c_void_p(monitor), ctypes.byref(info))
        r = info.rcMonitor
        rects.append((r.left, r.top, r.right - r.left, r.bottom - r.top))
        return True

    user32.EnumDisplayMonitors(None, None, callback_type(visit), None)
    return rects


def visible_frame(hwnd):
    """A window's visible frame as (x, y, width, height), excluding the invisible resize border."""
    rect = wintypes.RECT()
    dwmapi.DwmGetWindowAttribute(hwnd, 9, ctypes.byref(rect), ctypes.sizeof(rect))
    return rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top


@pytest.fixture
def open_window():
    """Factory that starts helper_window.ahk as a stand-in for a user's application and returns its hwnd.

    Every window it opened is killed when the test ends.
    """
    procs = []

    def start(title, x, y, backcolor=""):
        env = {**os.environ, "ACU_TEST_TITLE": title, "ACU_TEST_X": str(x), "ACU_TEST_Y": str(y), "ACU_TEST_BACKCOLOR": backcolor}
        procs.append(
            subprocess.Popen(
                [str(ahk_exe()), str(SCRIPTS / "helper_window.ahk")],
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        )
        wait_until(lambda: user32.FindWindowW(None, title), 5, f"helper window {title!r} never appeared")
        hwnd = user32.FindWindowW(None, title)
        wait_until(lambda: user32.IsWindowVisible(hwnd), 5, f"helper window {title!r} never became visible")
        return hwnd

    yield start

    for proc in procs:
        proc.kill()
        proc.wait()
