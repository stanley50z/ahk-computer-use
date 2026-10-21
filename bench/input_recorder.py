"""Record mouse buttons, wheel and keys system-wide through Windows Raw Input, without installing an input hook.

Usage: python bench/input_recorder.py <log.jsonl> <stop-file>
The bench starts it before the actor and creates <stop-file> when the actor ends. A low-level hook would make
ACU fall back from SendInput to SendEvent, so this uses RIDEV_INPUTSINK on a hidden window instead. Each line
holds the event, the cursor position read when it was processed, and the top-level window under that point.
Raw Input cannot tell who sent an event: the desktop must be left to the actor during a trial.
"""

import ctypes
import json
import sys
import time
import traceback
from ctypes import wintypes
from pathlib import Path

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
WM_INPUT, WM_TIMER, WM_DESTROY = 0x00FF, 0x0113, 0x0002
RIDEV_INPUTSINK, RID_INPUT, RIM_TYPEMOUSE, RIM_TYPEKEYBOARD = 0x100, 0x10000003, 0, 1
MOUSE_BUTTONS = {0x0001: ('left', 'down'), 0x0002: ('left', 'up'), 0x0004: ('right', 'down'), 0x0008: ('right', 'up'),
                 0x0010: ('middle', 'down'), 0x0020: ('middle', 'up')}
RI_MOUSE_WHEEL, RI_MOUSE_HWHEEL, RI_KEY_BREAK = 0x0400, 0x0800, 0x01
LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)


class RAWINPUTDEVICE(ctypes.Structure):
    _fields_ = [('usUsagePage', wintypes.USHORT), ('usUsage', wintypes.USHORT), ('dwFlags', wintypes.DWORD), ('hwndTarget', wintypes.HWND)]


class RAWINPUTHEADER(ctypes.Structure):
    _fields_ = [('dwType', wintypes.DWORD), ('dwSize', wintypes.DWORD), ('hDevice', wintypes.HANDLE), ('wParam', wintypes.WPARAM)]


class RAWMOUSE(ctypes.Structure):
    # usButtonFlags/usButtonData share a ULONG union, so Windows pads two bytes after usFlags.
    _fields_ = [('usFlags', wintypes.USHORT), ('_padding', wintypes.USHORT), ('usButtonFlags', wintypes.USHORT), ('usButtonData', wintypes.USHORT),
                ('ulRawButtons', wintypes.ULONG), ('lLastX', wintypes.LONG), ('lLastY', wintypes.LONG), ('ulExtraInformation', wintypes.ULONG)]


class RAWKEYBOARD(ctypes.Structure):
    _fields_ = [('MakeCode', wintypes.USHORT), ('Flags', wintypes.USHORT), ('Reserved', wintypes.USHORT), ('VKey', wintypes.USHORT),
                ('Message', wintypes.UINT), ('ExtraInformation', wintypes.ULONG)]


class RAWINPUTDATA(ctypes.Union):
    _fields_ = [('mouse', RAWMOUSE), ('keyboard', RAWKEYBOARD)]


class RAWINPUT(ctypes.Structure):
    _fields_ = [('header', RAWINPUTHEADER), ('data', RAWINPUTDATA)]


class WNDCLASSW(ctypes.Structure):
    _fields_ = [('style', wintypes.UINT), ('lpfnWndProc', WNDPROC), ('cbClsExtra', ctypes.c_int), ('cbWndExtra', ctypes.c_int),
                ('hInstance', wintypes.HINSTANCE), ('hIcon', wintypes.HICON), ('hCursor', wintypes.HANDLE), ('hbrBackground', wintypes.HBRUSH),
                ('lpszMenuName', wintypes.LPCWSTR), ('lpszClassName', wintypes.LPCWSTR)]


user32.DefWindowProcW.restype = LRESULT
user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.WindowFromPoint.restype = wintypes.HWND
user32.WindowFromPoint.argtypes = [wintypes.POINT]
user32.GetAncestor.restype = wintypes.HWND
user32.GetForegroundWindow.restype = wintypes.HWND
user32.CreateWindowExW.restype = wintypes.HWND


def main(log_path, stop_path):
    user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))  # physical pixels, like ACU and the window audit
    output = open(log_path, 'a', encoding='utf-8', buffering=1)

    def record(event):
        point = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(point))
        root = user32.GetAncestor(user32.WindowFromPoint(point), 2)  # GA_ROOT
        event.update(t=round(time.time(), 4), x=point.x, y=point.y, window=root or 0, foreground=user32.GetForegroundWindow() or 0)
        output.write(json.dumps(event) + '\n')

    received = {'raw': 0}

    def procedure(hwnd, message, wparam, lparam):
        if message == WM_INPUT:
            received['raw'] += 1
            size = wintypes.UINT(0)
            user32.GetRawInputData(ctypes.c_void_p(lparam), RID_INPUT, None, ctypes.byref(size), ctypes.sizeof(RAWINPUTHEADER))
            buffer = ctypes.create_string_buffer(size.value)
            user32.GetRawInputData(ctypes.c_void_p(lparam), RID_INPUT, buffer, ctypes.byref(size), ctypes.sizeof(RAWINPUTHEADER))
            raw = ctypes.cast(buffer, ctypes.POINTER(RAWINPUT)).contents
            device = 'none' if not raw.header.hDevice else 'device'
            if raw.header.dwType == RIM_TYPEMOUSE:
                flags = raw.data.mouse.usButtonFlags
                for bit, (button, action) in MOUSE_BUTTONS.items():
                    if flags & bit:
                        record({'kind': 'mouse', 'button': button, 'action': action, 'source': device})
                for bit, name in ((RI_MOUSE_WHEEL, 'wheel'), (RI_MOUSE_HWHEEL, 'hwheel')):
                    if flags & bit:
                        record({'kind': name, 'delta': ctypes.c_short(raw.data.mouse.usButtonData).value, 'source': device})
            elif raw.header.dwType == RIM_TYPEKEYBOARD:
                key = raw.data.keyboard
                record({'kind': 'key', 'vk': key.VKey, 'scan': key.MakeCode, 'action': 'up' if key.Flags & RI_KEY_BREAK else 'down',
                        'extended': bool(key.Flags & 0x02), 'source': device})
        elif message == WM_TIMER and Path(stop_path).exists():
            user32.DestroyWindow(hwnd)
        elif message == WM_DESTROY:
            user32.PostQuitMessage(0)
        return user32.DefWindowProcW(hwnd, message, wparam, lparam)

    callback = WNDPROC(procedure)
    instance = kernel32.GetModuleHandleW(None)
    window_class = WNDCLASSW(lpfnWndProc=callback, hInstance=instance, lpszClassName='AcuBenchInputRecorder')
    user32.RegisterClassW(ctypes.byref(window_class))
    hwnd = user32.CreateWindowExW(0, 'AcuBenchInputRecorder', 'ACU bench input recorder', 0, 0, 0, 0, 0, None, None, instance, None)
    devices = (RAWINPUTDEVICE * 2)(RAWINPUTDEVICE(1, 2, RIDEV_INPUTSINK, hwnd), RAWINPUTDEVICE(1, 6, RIDEV_INPUTSINK, hwnd))
    if not user32.RegisterRawInputDevices(devices, 2, ctypes.sizeof(RAWINPUTDEVICE)):
        raise ctypes.WinError()
    user32.SetTimer(hwnd, 1, 100, None)
    output.write(json.dumps({'kind': 'started', 't': round(time.time(), 4)}) + '\n')
    message = wintypes.MSG()
    while user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
        user32.TranslateMessage(ctypes.byref(message))
        user32.DispatchMessageW(ctypes.byref(message))
    output.write(json.dumps({'kind': 'stopped', 't': round(time.time(), 4), 'raw_messages': received['raw']}) + '\n')
    output.close()


if __name__ == '__main__':
    try:
        main(sys.argv[1], sys.argv[2])
    except Exception:
        Path(sys.argv[1]).with_suffix('.crash.txt').write_text(traceback.format_exc(), encoding='utf-8')
        raise
