"""Show, switch and restore a display's resolution, scaling and primary role for a Cua Driver Bench run.

The bench's Windows windows are placed in physical pixels and assume a 1920 x 1080 primary at 100%:

    python display.py show
    python display.py set \\\\.\\DISPLAY2 1920 1080 --scale 100 --primary
    python display.py restore

The state file defaults to %LOCALAPPDATA%\\cdb-bench\\display-state.json, where abort.py also looks. `set` saves every display's mode, position, scaling and primary role to the state file (it refuses to
overwrite an existing one, so a second `set` cannot lose the original), then applies the new mode and
scaling. `--primary` also makes the display the primary at desktop origin (0, 0) and moves the others by
the same offset, so the arrangement stays as it was. `restore` puts the saved layout back. Scaling goes
through the DisplayConfig DPI calls that Windows' own Settings page uses; they are undocumented, so `set`
reads the scaling back and reports it.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import sys
from ctypes import wintypes as w
from pathlib import Path

STATE = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "cdb-bench" / "display-state.json"

ctypes.windll.shcore.SetProcessDpiAwareness(2)
user32 = ctypes.windll.user32
SCALES = (100, 125, 150, 175, 200, 225, 250, 300, 350, 400, 450, 500)
PRIMARY_DEVICE = 0x4
QDC_ONLY_ACTIVE_PATHS, MODE_SOURCE = 2, 1
# SDC_APPLY | SDC_USE_SUPPLIED_DISPLAY_CONFIG | SDC_SAVE_TO_DATABASE | SDC_ALLOW_CHANGES
SDC_APPLY_LAYOUT = 0x80 | 0x20 | 0x200 | 0x400


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
    _fields_ = [("sourceAdapterId", LUID), ("sourceId", ctypes.c_uint32), ("sourceModeInfoIdx", ctypes.c_uint32),
                ("_rest", ctypes.c_byte * 56)]


class SOURCE_MODE(ctypes.Structure):  # DISPLAYCONFIG_SOURCE_MODE: the desktop size and position of a display
    _fields_ = [("width", ctypes.c_uint32), ("height", ctypes.c_uint32), ("pixelFormat", ctypes.c_uint32),
                ("x", ctypes.c_int32), ("y", ctypes.c_int32)]


class MODE(ctypes.Structure):  # DISPLAYCONFIG_MODE_INFO; `source` is valid when infoType is MODE_SOURCE
    _fields_ = [("infoType", ctypes.c_uint32), ("id", ctypes.c_uint32), ("adapterId", LUID),
                ("source", SOURCE_MODE), ("_rest", ctypes.c_byte * 28)]


# The current mode and desktop position of one display, e.g. \\.\DISPLAY2.
def mode(name: str) -> DEVMODE:
    m = DEVMODE()
    m.dmSize = ctypes.sizeof(DEVMODE)
    if not user32.EnumDisplaySettingsW(name, -1, ctypes.byref(m)):
        raise SystemExit(f"no display {name}")
    return m


# The attached displays as (name, is primary).
def attached() -> list[tuple[str, bool]]:
    class DD(ctypes.Structure):
        _fields_ = [("cb", w.DWORD), ("DeviceName", w.WCHAR * 32), ("DeviceString", w.WCHAR * 128),
                    ("StateFlags", w.DWORD), ("DeviceID", w.WCHAR * 128), ("DeviceKey", w.WCHAR * 128)]
    found, i = [], 0
    while True:
        d = DD()
        d.cb = ctypes.sizeof(d)
        if not user32.EnumDisplayDevicesW(None, i, ctypes.byref(d), 0):
            return found
        i += 1
        if d.StateFlags & 1:
            found.append((d.DeviceName, bool(d.StateFlags & PRIMARY_DEVICE)))


def displays() -> list[str]:
    return [name for name, _ in attached()]


# The active DisplayConfig paths and modes, as Windows' Settings page reads them.
def query() -> tuple[ctypes.Array, ctypes.Array]:
    paths, modes = ctypes.c_uint32(), ctypes.c_uint32()
    user32.GetDisplayConfigBufferSizes(QDC_ONLY_ACTIVE_PATHS, ctypes.byref(paths), ctypes.byref(modes))
    path_buf, mode_buf = (PATH * paths.value)(), (MODE * modes.value)()
    if user32.QueryDisplayConfig(QDC_ONLY_ACTIVE_PATHS, ctypes.byref(paths), path_buf, ctypes.byref(modes),
                                 mode_buf, None):
        raise SystemExit("QueryDisplayConfig failed")
    return path_buf, mode_buf


# The GDI name (\\.\DISPLAY2) of a path's source.
def gdi_name(path: PATH) -> str:
    q = SOURCE_NAME()
    q.header = HEADER(1, ctypes.sizeof(SOURCE_NAME), path.sourceAdapterId, path.sourceId)
    return "" if user32.DisplayConfigGetDeviceInfo(ctypes.byref(q)) else q.viewGdiDeviceName


# The DisplayConfig source (adapter, id) that shows display NAME.
def source(name: str) -> tuple[LUID, int]:
    for p in query()[0]:
        if gdi_name(p) == name:
            return p.sourceAdapterId, p.sourceId
    raise SystemExit(f"no DisplayConfig source for {name}")


# Give each named display a desktop size and position in one SetDisplayConfig call, which changes nothing
# if it fails. The display at (0, 0) is the primary. Displays not named keep their mode.
def apply_layout(targets: dict[str, tuple[int, int, int, int]]) -> None:
    path_buf, mode_buf = query()
    for p in path_buf:
        name = gdi_name(p)
        if name in targets:
            m = mode_buf[p.sourceModeInfoIdx]
            if m.infoType != MODE_SOURCE:
                raise SystemExit(f"no source mode for {name}")
            m.source.width, m.source.height, m.source.x, m.source.y = targets[name]
    result = user32.SetDisplayConfig(len(path_buf), path_buf, len(mode_buf), mode_buf, SDC_APPLY_LAYOUT)
    if result:
        raise SystemExit(f"SetDisplayConfig returned {result}")


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


# Desktop positions that make TARGET the primary at (0, 0): every display moves by the same offset.
def primary_positions(layout: list[dict], target: str) -> dict[str, tuple[int, int]]:
    tx, ty = next(d["position"] for d in layout if d["display"] == target)
    return {d["display"]: (d["position"][0] - tx, d["position"][1] - ty) for d in layout}


def describe(name: str, primary: bool) -> dict:
    m = mode(name)
    current, recommended, _ = scale(name)
    return {"display": name, "width": m.dmPelsWidth, "height": m.dmPelsHeight, "frequency": m.dmDisplayFrequency,
            "position": [m.dmPositionX, m.dmPositionY], "scale": current, "recommended_scale": recommended,
            "primary": primary}


def layout() -> list[dict]:
    return [describe(name, primary) for name, primary in attached()]


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("show")
    s = sub.add_parser("set")
    s.add_argument("display")
    s.add_argument("width", type=int)
    s.add_argument("height", type=int)
    s.add_argument("--scale", type=int, default=100)
    s.add_argument("--primary", action="store_true")
    s.add_argument("--save", type=Path, default=STATE)
    r = sub.add_parser("restore")
    r.add_argument("state", type=Path, nargs="?", default=STATE)
    args = parser.parse_args()
    if args.command == "show":
        for d in layout():
            print(json.dumps(d))
    elif args.command == "set":
        if args.save.exists():
            raise SystemExit(f"{args.save} exists: restore it first, or remove it if it is stale")
        if args.display not in displays():
            raise SystemExit(f"no display {args.display}")
        saved = layout()
        args.save.parent.mkdir(parents=True, exist_ok=True)
        args.save.write_text(json.dumps({"displays": saved}), encoding="utf-8")
        positions = primary_positions(saved, args.display) if args.primary else {
            d["display"]: tuple(d["position"]) for d in saved}
        targets = {d["display"]: (d["width"], d["height"], *positions[d["display"]]) for d in saved}
        targets[args.display] = (args.width, args.height, *positions[args.display])
        try:
            apply_layout(targets)
            set_scale(args.display, args.scale)
        except SystemExit:
            restore(args.save)
            raise
        for d in layout():
            print(json.dumps(d))
    else:
        restore(args.state)


# Put back the layout saved in STATE and delete the file once every display matches it. Returns whether it did.
def restore(state: Path = STATE) -> bool:
    saved = json.loads(state.read_text(encoding="utf-8"))["displays"]
    apply_layout({d["display"]: (d["width"], d["height"], *d["position"]) for d in saved})
    for d in saved:
        set_scale(d["display"], d["scale"])
    now = layout()
    for d in now:
        print(json.dumps(d))
    keys = ("display", "width", "height", "position", "scale", "primary")
    if [{k: d[k] for k in keys} for d in now] != [{k: d[k] for k in keys} for d in saved]:
        return False
    state.unlink()
    return True


if __name__ == "__main__":
    sys.exit(main())
