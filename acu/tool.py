"""Run an existing AHK script file through the CLI under the launcher protections."""

import ctypes
import math
import re
from contextlib import contextmanager
from pathlib import Path

from . import run as launcher
from .settings import snippets_enabled
from .snippets import format_snippets, list_snippets, snippets_root

HERE = Path(__file__).resolve().parent
BUNDLED_SCRIPTS = ("tree.ahk", "screenshot.ahk")


def resolve_script(script: str) -> Path:
    """The script to run: the caller's path, or a bundled script named without a directory, so an agent need not know where ACU lives."""
    path = Path(script).expanduser()
    if path.name in BUNDLED_SCRIPTS and str(path.parent) == "." and not path.is_file():
        return HERE / path.name
    return path.resolve()


@contextmanager
def _desktop_lease():
    """Reject overlapping CLI runs; Windows releases the mutex if its owner dies."""
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


def _expand_snippet_markers(output: str, working_folder: Path) -> str:
    """Replace AHK discovery lines using the same store and format as explicit listing."""
    marker = re.compile(r"^\[acu:snippets\] ([^\\/\r\n:]+\.exe)\r?$(?:\n)?", re.MULTILINE | re.IGNORECASE)
    if not marker.search(output):
        return output
    enabled = snippets_enabled(working_folder)

    def expand(match: re.Match[str]) -> str:
        if not enabled:
            return ""
        root = snippets_root()
        if not root.is_dir():
            return ""
        folder = next((path for path in root.iterdir()
                       if path.is_dir() and path.name.casefold() == match[1].casefold()), None)
        if folder is None:
            return ""
        return format_snippets(folder, list_snippets(folder)) + "\n"

    return marker.sub(expand, output)


def run(script: str, timeout: float = 30, args: list[str] | None = None) -> dict:
    """Run an existing AHK script under the launcher; preserve the caller's file and expose execution facts."""
    if not script.strip():
        raise ValueError("script path must be non-empty")
    if not math.isfinite(timeout) or not 0 < timeout <= 300:
        raise ValueError("timeout must be finite and between 0 (exclusive) and 300 seconds")
    path = resolve_script(script)
    if not path.is_file():
        raise ValueError(f"script not found: {path}")
    arguments = [] if args is None else args
    if any(not isinstance(arg, str) or "\0" in arg for arg in arguments):
        raise ValueError("script args must be strings without NUL characters")
    with _desktop_lease():
        try:
            result = launcher.run_script(path, timeout, arguments)
        except SystemExit as error:  # The low-level launcher reports a missing installation this way.
            raise ValueError(str(error)) from error
        result.output = _expand_snippet_markers(result.output, Path.cwd())
        response = {
            "engine": "ahk", "outcome": result.outcome, "exit_code": result.exit_code,
            "output": result.output, "trailer": result.trailer, "duration_ms": result.duration_ms,
            "artifacts": {"run_log": str(launcher.acu_home() / "logs" / "runs.jsonl")},
        }
        try:
            report = launcher.record(path, result, timeout)
        except OSError as error:
            response["log_error"] = str(error)  # Logging cannot replace the script's outcome.
        else:
            if report:
                response["artifacts"]["crash_report"] = str(report)
        return response
