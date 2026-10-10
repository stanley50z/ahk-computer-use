"""Shared script-first operations used by both transports."""

import ctypes
import json
import math
import tempfile
from contextlib import contextmanager
from pathlib import Path

from jsonschema import ValidationError, validate

from . import run as launcher

HERE = Path(__file__).resolve().parent


def discover(query: str = "", limit: int = 10) -> dict:
    """Return compact summaries so agents load only the relevant capability."""
    if not 1 <= limit <= 50:
        raise ValueError("limit must be between 1 and 50")
    words = query.casefold().split()
    matches = []
    for item in json.loads((HERE / "capabilities.json").read_text(encoding="utf-8")):
        haystack = (item["id"] + " " + item["description"]).casefold()
        if all(word in haystack for word in words):
            matches.append({key: item[key] for key in ("id", "description", "runnable", "engine")})
    return {"capabilities": matches[:limit], "total": len(matches)}


def describe(id: str) -> dict:
    """Load bundled instructions and parameter contracts for one exact capability ID."""
    for item in json.loads((HERE / "capabilities.json").read_text(encoding="utf-8")):
        if item["id"] == id:
            filename = item.pop("instructions_file")
            return {**item, "instructions": (HERE / filename).read_text(encoding="utf-8")}
    raise ValueError(f"unknown capability: {id}")


def _parameters(id: str, parameters: dict) -> None:
    """Validate maintained script arguments against its disclosed contract before execution."""
    try:
        validate(parameters, describe(id)["parameters"])
    except ValidationError as error:
        raise ValueError(error.message) from error


@contextmanager
def _desktop_lease():
    """Reject overlapping ACU tool executions; Windows releases the mutex if its owner dies."""
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    kernel32.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint]
    kernel32.ReleaseMutex.argtypes = [ctypes.c_void_p]
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = kernel32.CreateMutexW(None, False, "Local\\ACU-script-execution")
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    acquired = False
    try:
        status = kernel32.WaitForSingleObject(handle, 0)
        if status == 258:
            raise ValueError("busy: another ACU tool execution owns the desktop; inspect before retrying")
        if status not in (0, 128):  # WAIT_OBJECT_0 or WAIT_ABANDONED
            raise ctypes.WinError(ctypes.get_last_error())
        acquired = True
        yield
    finally:
        if acquired:
            kernel32.ReleaseMutex(handle)
        kernel32.CloseHandle(handle)


def _launch(script: Path, timeout: float, args: list[str]) -> dict:
    """Use the existing launcher and return execution facts, never a claim of verified effect."""
    if not math.isfinite(timeout) or not 0 < timeout <= 300:
        raise ValueError("timeout must be finite and between 0 (exclusive) and 300 seconds")
    if not script.is_file():
        raise ValueError(f"script not found: {script}")
    if any(not isinstance(arg, str) or "\0" in arg for arg in args):
        raise ValueError("script args must be strings without NUL characters")
    with _desktop_lease():
        try:
            result = launcher.run_script(script, timeout, args)
        except SystemExit as error:  # The old launcher reports a missing AHK installation this way.
            raise ValueError(str(error)) from error
        response = {
            "engine": "ahk", "outcome": result.outcome, "exit_code": result.exit_code,
            "output": result.output, "trailer": result.trailer, "duration_ms": result.duration_ms,
            "artifacts": {"run_log": str(launcher.acu_home() / "logs" / "runs.jsonl")},
        }
        try:
            report = launcher.record(script, result, timeout)
        except OSError as error:
            response["log_error"] = str(error)  # Logging cannot replace the script's outcome.
        else:
            if report:
                response["artifacts"]["crash_report"] = str(report)
        return response


def execute(code: str | None = None, file: str | None = None, engine: str = "ahk",
            timeout: float = 30, args: list[str] | None = None) -> dict:
    """Run agent-written code or an existing script; inline files are managed and removed by ACU."""
    if engine != "ahk":
        raise ValueError(f"unsupported engine: {engine}; available: ahk")
    if (code is None) == (file is None):
        raise ValueError("provide exactly one of code or file")
    if not math.isfinite(timeout) or not 0 < timeout <= 300:
        raise ValueError("timeout must be finite and between 0 (exclusive) and 300 seconds")
    if file is not None:
        return _launch(Path(file).expanduser().resolve(), timeout, args or [])
    if not code or not code.strip() or "\0" in code:
        raise ValueError("code must be non-empty and contain no NUL characters")
    temporary = launcher.acu_home() / "tmp"
    temporary.mkdir(parents=True, exist_ok=True)
    directory = tempfile.TemporaryDirectory(prefix="script-", dir=temporary)
    script = Path(directory.name) / "action.ahk"
    result = None
    try:
        script.write_text(code, encoding="utf-8")
        result = _launch(script, timeout, args or [])
    finally:
        try:
            directory.cleanup()
        except OSError as cleanup_error:
            if result is None:
                raise  # No execution facts to preserve; report the chained tool failure.
            result["cleanup_error"] = str(cleanup_error)
            result["artifacts"]["leftover_script"] = str(script)
    return result


def run(id: str, parameters: dict | None = None, timeout: float = 30) -> dict:
    """Run a bundled implementation by ID; instruction-only capabilities fail explicitly."""
    capability = describe(id)
    if not capability["runnable"]:
        raise ValueError(f"{id} provides instructions only; draft an action chain and use execute")
    supplied = {} if parameters is None else parameters
    _parameters(id, supplied)
    if id == "windows.list":
        return _launch(HERE / "windows.ahk", timeout, [])
    if id == "uia.tree":
        return tree(**supplied, timeout=timeout)
    if id == "screen.capture":
        return screenshot(**supplied, timeout=timeout)
    raise ValueError(f"no maintained implementation for {id}")


def tree(target: str, find: str = "", type: str = "", depth: int = 25,
         max: int = 300, timeout: float = 30) -> dict:
    """Inspect a window through the maintained tree script, passing arguments literally."""
    if not target.strip():
        raise ValueError("target must be non-empty")
    _parameters("uia.tree", {"target": target, "find": find, "type": type, "depth": depth, "max": max})
    args = [target, "--depth", str(depth), "--max", str(max)]
    if find:
        args += ["--find", find]
    if type:
        args += ["--type", type]
    return _launch(HERE / "tree.ahk", timeout, args)


def screenshot(mode: str = "fullscreen", target: str | None = None, monitor: int = 1,
               rect: list[int] | None = None, out: str | None = None, max: int = 1280,
               timeout: float = 30) -> dict:
    """Capture with the maintained script and disclose saved path and coordinate mapping."""
    _parameters("screen.capture", {"mode": mode, "target": target, "monitor": monitor,
                                   "rect": rect, "out": out, "max": max})
    if mode == "app":
        if not target or not target.strip() or rect is not None:
            raise ValueError("app mode requires a non-empty target and no rect")
        args = [mode, target]
    elif mode == "custom":
        if rect is None or rect[2] <= rect[0] or rect[3] <= rect[1] or target is not None:
            raise ValueError("custom mode requires a positive rectangle and no target")
        args = [mode, *map(str, rect)]
    else:
        if target is not None or rect is not None:
            raise ValueError("fullscreen mode accepts neither target nor rect")
        args = [mode, str(monitor)]
    args += ["--max", str(max)]
    if out is not None:
        if not out.strip():
            raise ValueError("out must be non-empty")
        args += ["--out", str(Path(out).expanduser().resolve())]
    result = _launch(HERE / "screenshot.ahk", timeout, args)
    if result["outcome"] == "ok":
        metadata = {}
        for line in result["output"].splitlines():
            key, separator, value = line.partition("=")
            if separator and key in ("saved", "image", "source", "scale"):
                metadata[key] = value
        if set(metadata) != {"saved", "image", "source", "scale"}:
            raise ValueError("screenshot script returned incomplete metadata")
        result["screenshot"] = metadata
    return result
