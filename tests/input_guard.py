"""Holds each desktop test until nobody has touched the keyboard or mouse for 5 seconds, so a test never takes over
input the user is still giving. conftest.py runs it before every desktop-marked test; nothing else uses it."""

import ctypes
import subprocess
import time
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from acu.run import plain_ahk_exe

QUIET_MS = 5000
POLL_S = 0.2  # How soon input during the wait brings up the notice.
NOTICE_TITLE = "ACU desktop test waiting"
NOTICE_SCRIPT = Path(__file__).resolve().parent / "scripts" / "input_guard_notice.ahk"


class Notice(Protocol):
    def close(self) -> None: ...


# Returns once QUIET_MS have passed since the last keyboard or mouse input. Ticks are milliseconds on Windows' 32-bit
# tick clock, which wraps. A wait prints one report line. Input that arrives during the wait, as opposed to input from
# before it such as a previous test's, also shows the notice, which closes when the wait ends however it ends.
def wait_for_quiet_input(now: Callable[[], int], last_input: Callable[[], int], sleep: Callable[[float], None],
                         show_notice: Callable[[], Notice], report: Callable[[str], None]) -> None:
    first = last_input()
    idle = (now() - first) % 2**32
    if idle >= QUIET_MS:
        return
    report(f"Waiting for {QUIET_MS // 1000} s without keyboard or mouse input before a desktop test "
           f"(the last input was {idle} ms ago).")
    notice = None
    try:
        while idle < QUIET_MS:
            sleep(min(POLL_S, (QUIET_MS - idle) / 1000))
            latest = last_input()
            idle = (now() - latest) % 2**32
            if latest != first and notice is None:
                notice = show_notice()
    finally:
        if notice is not None:
            notice.close()


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]


# The tick of the last keyboard or mouse input in this session, injected input included.
def last_input_tick() -> int:
    info = LASTINPUTINFO(ctypes.sizeof(LASTINPUTINFO))
    if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
        raise ctypes.WinError()
    return info.dwTime


# The current tick on the same clock as last_input_tick.
def tick_now() -> int:
    ctypes.windll.kernel32.GetTickCount.restype = ctypes.c_uint
    return ctypes.windll.kernel32.GetTickCount()


class NoticeWindow:
    """The pop-up asking the user to leave the keyboard and mouse alone, run by the plain AutoHotkey build."""

    def __init__(self):
        self.process = subprocess.Popen([str(plain_ahk_exe()), str(NOTICE_SCRIPT), NOTICE_TITLE])

    def close(self) -> None:
        self.process.kill()
        self.process.wait()


# Shows the notice without taking focus; wait_for_quiet_input closes it.
def show_notice() -> NoticeWindow:
    return NoticeWindow()


# Waits for quiet input with the real clock and pop-up, reporting on the terminal past pytest's output capture.
def before_desktop_test(config) -> None:
    capture = config.pluginmanager.getplugin("capturemanager")
    terminal = config.pluginmanager.getplugin("terminalreporter")

    def report(line: str) -> None:
        with capture.global_and_fixture_disabled():
            terminal.write_line(line)
    wait_for_quiet_input(tick_now, last_input_tick, time.sleep, show_notice, report)
