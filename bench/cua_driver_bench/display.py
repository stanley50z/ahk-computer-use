"""Show, switch and restore one display's resolution and scaling for a Cua Driver Bench run.

The bench's Windows windows are placed in physical pixels and assume a 1920 x 1080 display at 100%:

    python display.py show
    python display.py set \\\\.\\DISPLAY2 1920 1080 --scale 100 --save display-state.json
    python display.py restore display-state.json

`set` saves the display's current mode, position and scaling to the state file (it refuses to overwrite
an existing one, so a second `set` cannot lose the original), then applies the new mode and scaling.
`restore` puts the saved values back. Scaling goes through the DisplayConfig DPI calls that Windows'
own Settings page uses; they are undocumented, so `set` reads the scaling back and reports it.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import sys
from ctypes import wintypes as w
from pathlib import Path

ctypes.windll.shcore.SetProcessDpiAwareness(2)
user32 = ctypes.windll.user32
SCALES = (100, 125, 150, 175, 200, 225, 250, 300, 350, 400, 450, 500)
DM_POSITION, DM_PELSWIDTH, DM_PELSHEIGHT, DM_DISPLAYFREQUENCY = 0x20, 0x80000, 0x100000, 0x400000
CDS_UPDATEREGISTRY = 0x1


class DEVMODE(ctypes.Structure):
    _fields_ = [("dmDeviceName", w.WCHAR * 32), ("dmSpecVersion", w.WORD), ("dmDriverVersion", w.WORD),
                ("dmSize", w.WORD), ("dmDriverExtra", w.WORD), ("dmFields", w.DWORD), ("dmPositionX", w.LONG),
                ("dmPositionY", w.LONG), ("dmDisplayOrientation", w.DWORD), ("dmDisplayFixedOutput", w.DWORD),
                ("dmColor", w.SHORT), ("dmDuplex", w.SHORT), ("dmYResolution", w.SHORT), ("dmTTOption", w.SHORT),
                ("dmCollate", w.SHORT), ("dmFormName", w.WCHAR * 32), ("dmLogPixels", w.WORD),
                ("dmBitsPerPel", w.DWORD), ("dmPelsWidth", w.DWORD), ("dmPelsHeight", w.DWORD),
                ("dmDisplayFlags", w.DWORD), ("dmDisplayFrequency", w.DWORD), ("_rest", w.DWORD * 8)]


class LUID(ctypes.Structure):
    _fields_ = [("LowPart", w.DWORD), ("HighPart", w.LONG)]


class HEADER(ctypes.Structure):
    _fields_ = [("type", ctypes.c_int32), ("size", ctypes.c_uint32), ("adapterId", LUID), ("id", ctypes.c_uint32)]


class SOURCE_NAME(ctypes.Structure):
    _fields_ = [("header", HEADER), ("viewGdiDeviceName", w.WCHAR * 32)]


class DPI_GET(ctypes.Structure):
    _fields_ = [("header", HEADER), ("minScaleRel", ctypes.c_int32), ("curScaleRel", ctypes.c_int32),
                ("maxScaleRel", ctypes.c_int32)]


class DPI_SET(ctypes.Structure):
    _fields_ = [("header", HEADER), ("scaleRel", ctypes.c_int32)]


class PATH(ctypes.Structure):  # DISPLAYCONFIG_PATH_INFO; only the source part is read
    _fields_ = [("sourceAdapterId", LUID), ("sourceId", ctypes.c_uint32), ("_rest", ctypes.c_byte * 60)]


# The current mode and desktop position of one display, e.g. \\.\DISPLAY2.
def mode(name: str) -> DEVMODE:
    m = DEVMODE()
    m.dmSize = ctypes.sizeof(DEVMODE)
    if not user32.EnumDisplaySettingsW(name, -1, ctypes.byref(m)):
        raise SystemExit(f"no display {name}")
    return m


def displays() -> list[str]:
    class DD(ctypes.Structure):
        _fields_ = [("cb", w.DWORD), ("DeviceName", w.WCHAR * 32), ("DeviceString", w.WCHAR * 128),
                    ("StateFlags", w.DWORD), ("DeviceID", w.WCHAR * 128), ("DeviceKey", w.WCHAR * 128)]
    names, i = [], 0
    while True:
        d = DD()
        d.cb = ctypes.sizeof(d)
        if not user32.EnumDisplayDevicesW(None, i, ctypes.byref(d), 0):
            return names
        i += 1
        if d.StateFlags & 1:
            names.append(d.DeviceName)


# The DisplayConfig source (adapter, id) that shows display NAME.
def source(name: str) -> tuple[LUID, int]:
    paths, modes = ctypes.c_uint32(), ctypes.c_uint32()
    user32.GetDisplayConfigBufferSizes(2, ctypes.byref(paths), ctypes.byref(modes))
    path_buf = (PATH * paths.value)()
    mode_buf = (ctypes.c_byte * (64 * modes.value))()
    if user32.QueryDisplayConfig(2, ctypes.byref(paths), path_buf, ctypes.byref(modes), mode_buf, None):
        raise SystemExit("QueryDisplayConfig failed")
    for p in path_buf[: paths.value]:
        q = SOURCE_NAME()
        q.header = HEADER(1, ctypes.sizeof(SOURCE_NAME), p.sourceAdapterId, p.sourceId)
        if not user32.DisplayConfigGetDeviceInfo(ctypes.byref(q)) and q.viewGdiDeviceName == name:
            return p.sourceAdapterId, p.sourceId
    raise SystemExit(f"no DisplayConfig source for {name}")


# (current scale %, recommended scale %, allowed scales) of display NAME.
def scale(name: str) -> tuple[int, int, list[int]]:
    adapter, sid = source(name)
    q = DPI_GET()
    q.header = HEADER(-3, ctypes.sizeof(DPI_GET), adapter, sid)
    if user32.DisplayConfigGetDeviceInfo(ctypes.byref(q)):
        raise SystemExit("reading the scale failed")
    rec = -q.minScaleRel
    allowed = [SCALES[i] for i in range(rec + q.minScaleRel, min(rec + q.maxScaleRel, len(SCALES) - 1) + 1)]
    return SCALES[rec + q.curScaleRel], SCALES[rec], allowed


def set_scale(name: str, percent: int) -> None:
    _, recommended, _ = scale(name)
    adapter, sid = source(name)
    q = DPI_SET()
    q.header = HEADER(-4, ctypes.sizeof(DPI_SET), adapter, sid)
    q.scaleRel = SCALES.index(percent) - SCALES.index(recommended)
    if user32.DisplayConfigSetDeviceInfo(ctypes.byref(q)):
        raise SystemExit(f"setting {name} to {percent}% failed")


def apply_mode(name: str, width: int, height: int, position: tuple[int, int] | None = None,
               frequency: int | None = None) -> None:
    m = mode(name)
    m.dmPelsWidth, m.dmPelsHeight, m.dmFields = width, height, DM_PELSWIDTH | DM_PELSHEIGHT
    if position is not None:
        (m.dmPositionX, m.dmPositionY), m.dmFields = position, m.dmFields | DM_POSITION
    if frequency is not None:
        m.dmDisplayFrequency, m.dmFields = frequency, m.dmFields | DM_DISPLAYFREQUENCY
    result = user32.ChangeDisplaySettingsExW(name, ctypes.byref(m), None, CDS_UPDATEREGISTRY, None)
    if result != 0:
        raise SystemExit(f"ChangeDisplaySettingsEx({name}) returned {result}")


def describe(name: str) -> dict:
    m = mode(name)
    current, recommended, _ = scale(name)
    return {"display": name, "width": m.dmPelsWidth, "height": m.dmPelsHeight, "frequency": m.dmDisplayFrequency,
            "position": [m.dmPositionX, m.dmPositionY], "scale": current, "recommended_scale": recommended}


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("show")
    s = sub.add_parser("set")
    s.add_argument("display")
    s.add_argument("width", type=int)
    s.add_argument("height", type=int)
    s.add_argument("--scale", type=int, default=100)
    s.add_argument("--save", type=Path, required=True)
    r = sub.add_parser("restore")
    r.add_argument("state", type=Path)
    args = parser.parse_args()
    if args.command == "show":
        for name in displays():
            print(json.dumps(describe(name)))
    elif args.command == "set":
        if args.save.exists():
            raise SystemExit(f"{args.save} exists: restore it first, or remove it if it is stale")
        args.save.write_text(json.dumps(describe(args.display)), encoding="utf-8")
        apply_mode(args.display, args.width, args.height)
        set_scale(args.display, args.scale)
        print(json.dumps(describe(args.display)))
    else:
        saved = json.loads(args.state.read_text(encoding="utf-8"))
        apply_mode(saved["display"], saved["width"], saved["height"], tuple(saved["position"]), saved["frequency"])
        set_scale(saved["display"], saved["scale"])
        now = describe(saved["display"])
        print(json.dumps(now))
        if (now["width"], now["height"], now["scale"]) == (saved["width"], saved["height"], saved["scale"]):
            args.state.unlink()


if __name__ == "__main__":
    sys.exit(main())
