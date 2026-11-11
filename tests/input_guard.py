"""Holds each desktop test until nobody has touched the keyboard or mouse for 5 seconds, so a test never takes over
input the user is still giving. conftest.py starts the listener for a --desktop session and runs the wait before every
desktop-marked test; nothing else uses it."""

import ctypes
import subprocess
import threading
import time
from collections.abc import Callable
from ctypes import wintypes
from pathlib import Path
from typing import Protocol

from acu.run import plain_ahk_exe

QUIET_MS = 5000
POLL_S = 0.2  # How soon input during the wait brings up the notice.
NOTICE_TITLE = "ACU desktop test waiting"
NOTICE_SCRIPT = Path(__file__).resolve().parent / "scripts" / "input_guard_notice.ahk"
WM_DESTROY, WM_CLOSE, WM_INPUT = 0x0002, 0x0010, 0x00FF
RIDEV_INPUTSINK = 0x100
LISTENER_CLASS = "AcuTestInputGuard"


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


# The current tick of Windows' millisecond clock.
def tick_now() -> int:
    ctypes.windll.kernel32.GetTickCount.restype = ctypes.c_uint
    return ctypes.windll.kernel32.GetTickCount()


# The Raw Input registrations InputListener makes: the mouse (usage page 1, usage 2) and the keyboard (usage 6),
# delivered to hwnd whichever window has the focus. Game controllers and other HID devices are left out: a keyboard
# that also exposes a controller interface streams controller reports even when nobody touches it.
def keyboard_and_mouse(hwnd: int) -> list[tuple[int, int, int, int]]:
    return [(1, 2, RIDEV_INPUTSINK, hwnd), (1, 6, RIDEV_INPUTSINK, hwnd)]


user32 = ctypes.WinDLL("user32", use_last_error=True)
LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
user32.DefWindowProcW.restype = LRESULT
user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.CreateWindowExW.restype = wintypes.HWND
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]


class RAWINPUTDEVICE(ctypes.Structure):
    _fields_ = [("usUsagePage", wintypes.USHORT), ("usUsage", wintypes.USHORT), ("dwFlags", wintypes.DWORD),
                ("hwndTarget", wintypes.HWND)]


class WNDCLASSW(ctypes.Structure):
    _fields_ = [("style", wintypes.UINT), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int),
                ("hInstance", wintypes.HINSTANCE), ("hIcon", wintypes.HICON), ("hCursor", wintypes.HANDLE),
                ("hbrBackground", wintypes.HBRUSH), ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR)]


class InputListener:
    """The tick of the last keyboard or mouse event, injected events included, heard through Raw Input on a hidden window
    in its own thread, without an input hook. Raw Input reports nothing from before the listener starts, so the start
    counts as an event: the first desktop test of a session waits until 5 seconds after it."""

    def __init__(self, now: Callable[[], int] = tick_now):
        self.now = now
        self.last = now()
        self.hwnd = None

    def last_input(self) -> int:
        return self.last

    # Every WM_INPUT is a key, a button, a move or a wheel step, since only the keyboard and mouse are registered.
    def on_message(self, message: int) -> None:
        if message == WM_INPUT:
            self.last = self.now()

    # Starts listening and returns once the devices are registered; a failed registration raises here.
    def start(self) -> None:
        ready, failure = threading.Event(), []
        self.thread = threading.Thread(target=self._listen, args=(ready, failure), name="input guard", daemon=True)
        self.thread.start()
        ready.wait()
        if failure:
            raise failure[0]

    def stop(self) -> None:
        user32.PostMessageW(self.hwnd, WM_CLOSE, 0, 0)
        self.thread.join()

    def _listen(self, ready: threading.Event, failure: list[BaseException]) -> None:
        def procedure(hwnd, message, wparam, lparam):
            self.on_message(message)
            if message == WM_DESTROY:
                user32.PostQuitMessage(0)
            return user32.DefWindowProcW(hwnd, message, wparam, lparam)
        try:
            self.procedure = WNDPROC(procedure)  # Kept alive for as long as the window can call it.
            instance = ctypes.windll.kernel32.GetModuleHandleW(None)
            window_class = WNDCLASSW(lpfnWndProc=self.procedure, hInstance=instance, lpszClassName=LISTENER_CLASS)
            if not user32.RegisterClassW(ctypes.byref(window_class)):
                raise ctypes.WinError(ctypes.get_last_error())
            self.hwnd = user32.CreateWindowExW(0, LISTENER_CLASS, LISTENER_CLASS, 0, 0, 0, 0, 0, None, None, instance, None)
            if not self.hwnd:
                raise ctypes.WinError(ctypes.get_last_error())
            devices = (RAWINPUTDEVICE * 2)(*(RAWINPUTDEVICE(*device) for device in keyboard_and_mouse(self.hwnd)))
            if not user32.RegisterRawInputDevices(devices, 2, ctypes.sizeof(RAWINPUTDEVICE)):
                raise ctypes.WinError(ctypes.get_last_error())
        except BaseException as error:
            failure.append(error)
            ready.set()
            return
        ready.set()
        message = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
            user32.DispatchMessageW(ctypes.byref(message))


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


listener: InputListener | None = None


# Starts the session's listener; conftest.py calls it when --desktop is given and stop_listening when pytest ends.
def start_listening() -> None:
    global listener
    listener = InputListener()
    listener.start()


def stop_listening() -> None:
    global listener
    listener.stop()
    listener = None


# Waits for quiet keyboard and mouse input with the real clock and pop-up, reporting on the terminal past pytest's
# output capture.
def before_desktop_test(config) -> None:
    capture = config.pluginmanager.getplugin("capturemanager")
    terminal = config.pluginmanager.getplugin("terminalreporter")

    def report(line: str) -> None:
        with capture.global_and_fixture_disabled():
            terminal.write_line(line)
            terminal.flush()  # Shown now, even when pytest's output goes to a pipe.
    wait_for_quiet_input(tick_now, listener.last_input, time.sleep, show_notice, report)
