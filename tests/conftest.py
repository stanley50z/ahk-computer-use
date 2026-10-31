"""Shared ACU test helpers; desktop-marked checks run real AutoHotkey scripts."""

import ctypes
import json
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
from acu.run import plain_ahk_exe  # noqa: E402

user32 = ctypes.windll.user32
# Per-monitor-v2 awareness so cursor and window coordinates read here match what the prelude sees.
user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
user32.GetForegroundWindow.restype = ctypes.c_void_p
user32.FindWindowW.restype = ctypes.c_void_p
user32.FindWindowW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p]
user32.IsWindowVisible.argtypes = [ctypes.c_void_p]
dwmapi = ctypes.windll.dwmapi
dwmapi.DwmGetWindowAttribute.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_uint]


# Registers explicit permission to execute the desktop integration tests.
def pytest_addoption(parser):
    parser.addoption("--desktop", action="store_true", help="include desktop integration tests (may take over mouse and focus)")


# Keep desktop tests out of normal runs, even when their files are selected explicitly.
def pytest_collection_modifyitems(config, items):
    if config.getoption("--desktop"):
        return
    excluded = [item for item in items if item.get_closest_marker("desktop")]
    items[:] = [item for item in items if not item.get_closest_marker("desktop")]
    config.hook.pytest_deselected(items=excluded)


CLOUD9_REFERENCE = REPO / "bench/assets/illustrator-pen-tool/Cloud9-Reference.png"
# For tests about the real Cloud9 reference's pixels or hash, which checkouts build with bench/build_reference.py.
needs_cloud9_reference = pytest.mark.skipif(
    not CLOUD9_REFERENCE.is_file(), reason="Cloud9-Reference.png not built; see bench/build_reference.py")


@pytest.fixture(autouse=True)
def illustrator_reference(tmp_path, monkeypatch):
    """Without the locally built Cloud9 reference, bench preparation uses a blue block with the same bounds."""
    if CLOUD9_REFERENCE.is_file():
        return
    from PIL import Image, ImageDraw

    import bench.illustrator_pen_tool

    stand_in = tmp_path / "Cloud9-Reference.png"
    image = Image.new("RGB", (800, 800), "white")
    ImageDraw.Draw(image).rectangle((143, 206, 692, 584), fill=(0, 174, 239))
    image.save(stand_in, dpi=(72, 72))
    monkeypatch.setattr(bench.illustrator_pen_tool, "ILLUSTRATOR_REFERENCE", stand_in)


@pytest.fixture(autouse=True)
def acu_home(tmp_path, monkeypatch):
    """Point the launcher's logs at a temp dir so tests never write to %LOCALAPPDATA%\\ACU."""
    home = tmp_path / "ACU"
    monkeypatch.setenv("ACU_HOME", str(home))
    return home


@pytest.fixture
def process_adapter(tmp_path, monkeypatch):
    """Keep fake launcher processes independent of the machine's AutoHotkey installation."""
    from fake_process import FakeProcessAdapter

    for name in ("AutoHotkey64_UIA.exe", "AutoHotkey64.exe"):
        (tmp_path / name).touch()
    monkeypatch.setenv("ACU_AHK", str(tmp_path / "AutoHotkey64_UIA.exe"))
    return FakeProcessAdapter()


def run_launcher(script, *args, timeout=60):
    """Run any script through acu/run.py and return the CompletedProcess."""
    return subprocess.run(
        [sys.executable, str(LAUNCHER), str(script), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=timeout,
    )


def run_cli(script, *, timeout=5, args=()):
    """Run the public CLI in a subprocess and retain its JSON facts for desktop checks."""
    result = subprocess.run(
        [sys.executable, "-m", "acu", "run", str(script), "--timeout", str(timeout), "--", *args],
        cwd=REPO, capture_output=True, text=True, encoding="utf-8", timeout=timeout + 10,
    )
    facts = json.loads(result.stdout)
    assert result.returncode == facts.get("exit_code"), result.stdout + result.stderr
    return facts


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


def monitor_dpis():
    """Each attached monitor's effective DPI, in the same order as monitor_rects()."""
    dpis = []
    callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(wintypes.RECT), ctypes.c_void_p)

    def visit(monitor, _dc, _rect, _data):
        x, y = wintypes.UINT(), wintypes.UINT()
        ctypes.windll.shcore.GetDpiForMonitor(ctypes.c_void_p(monitor), 0, ctypes.byref(x), ctypes.byref(y))
        dpis.append(x.value)
        return True

    user32.EnumDisplayMonitors(None, None, callback_type(visit), None)
    return dpis


def system_dpi():
    """The DPI an application that is not per-monitor aware draws at."""
    return user32.GetDpiForSystem()


def visible_frame(hwnd):
    """A window's visible frame as (x, y, width, height), excluding the invisible resize border."""
    rect = wintypes.RECT()
    dwmapi.DwmGetWindowAttribute(hwnd, 9, ctypes.byref(rect), ctypes.sizeof(rect))
    return rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top


@pytest.fixture
def open_window():
    """Factory that starts a stand-in for a user's application window and returns its hwnd.

    Runs tests/scripts/helper_window.ahk unless `script` names another fixture script; extra keyword
    arguments become environment variables for it. Every window it opened is killed when the test ends.
    Uses the plain build: these stand in for a user's ordinary applications, and a UI Access program
    cannot be started with Popen anyway.
    """
    procs = []

    def start(title, x, y, backcolor="", script="helper_window.ahk", **extra_env):
        env = {**os.environ, "ACU_TEST_TITLE": title, "ACU_TEST_X": str(x), "ACU_TEST_Y": str(y), "ACU_TEST_BACKCOLOR": backcolor, **extra_env}
        procs.append(
            subprocess.Popen(
                [str(plain_ahk_exe()), str(SCRIPTS / script)],
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
