"""ACU launcher: run one AutoHotkey v2 script under the ACU prelude with captured output and a hard timeout.

Usage: python acu/run.py SCRIPT.ahk [--timeout SECONDS] [-- ARG ...]

Arguments after -- are passed to the script and arrive in its A_Args. Prints the script's stdout and stderr followed by one "[acu] ..." trailer line, then exits with the
script's exit code, or 124 when the watchdog fired. At the timeout the script is first asked to close
(WM_CLOSE to its main window, which runs the prelude's exit handler) and killed if it is still running
one second later.

Scripts run under AutoHotkey's signed UI Access build, so they can see and drive elevated windows
without being elevated themselves. Windows only starts a UI Access program through ShellExecute, which
gives it no standard output and not the launcher's environment either. So the launcher passes an output
file and its ACU_HOME as the script's first arguments, which the prelude consumes: it redirects stdout and
stderr into the file and sets ACU_HOME. Anything else a script needs goes in the arguments after --.
Load-time errors and warnings happen before the prelude runs, so the script is first loaded without
running (/validate) under the plain build, with a pipe.

Every run appends a JSON line to <ACU_HOME>/logs/runs.jsonl. Runs that end in an error or a timeout
also write a crash report with the full output to <ACU_HOME>/crashes/. ACU_HOME defaults to
%LOCALAPPDATA%\\ACU. Script text is never logged; only its SHA-256.
"""

import argparse
import ctypes
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from ctypes import wintypes
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal, Sequence

HERE = Path(__file__).resolve().parent
PRELUDE = HERE / "prelude.ahk"
DEFAULT_AHK = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "AutoHotkey" / "v2" / "AutoHotkey64_UIA.exe"
TIMEOUT_EXIT_CODE = 124
CLOSE_GRACE_SECONDS = 1.0
WM_CLOSE = 0x0010
OUTPUT_ARG = "--acu-out="  # the prelude strips these leading arguments: the output file to redirect into, and ACU_HOME
HOME_ARG = "--acu-home="

Outcome = Literal["ok", "error", "timeout"]


@dataclass
class Run:
    """What one script run produced: its merged output, how it ended, and the trailer line to print."""

    output: str
    outcome: Outcome
    exit_code: int
    duration_ms: int
    trailer: str


def ahk_exe() -> Path:
    """The AutoHotkey build scripts run under: the signed UI Access build, overridable with the ACU_AHK environment variable."""
    path = Path(os.environ.get("ACU_AHK") or DEFAULT_AHK)
    if not path.is_file():
        raise SystemExit(f"[acu] AutoHotkey not found at {path}; install AutoHotkey v2 with its UI Access option, or set ACU_AHK")
    return path


def plain_ahk_exe() -> Path:
    """The same AutoHotkey build without UI Access, for anything that needs a pipe: validating a script, and the tests' stand-in windows."""
    exe = ahk_exe()
    path = exe.with_name(exe.name.replace("_UIA", ""))
    if not path.is_file():
        raise SystemExit(f"[acu] AutoHotkey not found at {path}, expected beside {exe.name}")
    return path


def acu_home() -> Path:
    """Root directory for logs and crash reports: ACU_HOME, else %LOCALAPPDATA%\\ACU."""
    return Path(os.environ.get("ACU_HOME") or Path(os.environ["LOCALAPPDATA"]) / "ACU")


def request_close(pid: int) -> None:
    """Post WM_CLOSE to every AutoHotkey main window owned by pid, so the script's OnExit handlers run."""
    user32 = ctypes.windll.user32
    callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    user32.EnumWindows.argtypes = [callback_type, ctypes.c_void_p]
    user32.GetWindowThreadProcessId.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
    user32.GetClassNameW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int]
    user32.PostMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p]

    def visit(hwnd, _):
        owner = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == pid:
            class_name = ctypes.create_unicode_buffer(64)
            user32.GetClassNameW(hwnd, class_name, 64)
            if class_name.value == "AutoHotkey":
                user32.PostMessageW(hwnd, WM_CLOSE, None, None)
        return True

    user32.EnumWindows(callback_type(visit), None)


class ShellExecuteInfo(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD), ("fMask", wintypes.ULONG), ("hwnd", wintypes.HWND), ("lpVerb", wintypes.LPCWSTR),
        ("lpFile", wintypes.LPCWSTR), ("lpParameters", wintypes.LPCWSTR), ("lpDirectory", wintypes.LPCWSTR), ("nShow", ctypes.c_int),
        ("hInstApp", wintypes.HINSTANCE), ("lpIDList", ctypes.c_void_p), ("lpClass", wintypes.LPCWSTR), ("hkeyClass", wintypes.HKEY),
        ("dwHotKey", wintypes.DWORD), ("hIcon", wintypes.HANDLE), ("hProcess", wintypes.HANDLE),
    ]


def shell_execute(exe: Path, params: str) -> wintypes.HANDLE:
    """Start exe through ShellExecuteEx, the one way Windows starts a UI Access program, and return its process handle."""
    SEE_MASK_NOCLOSEPROCESS, SEE_MASK_NOASYNC, SEE_MASK_FLAG_NO_UI, SW_SHOWNORMAL = 0x40, 0x100, 0x400, 1
    shell32 = ctypes.WinDLL("shell32", use_last_error=True)
    shell32.ShellExecuteExW.argtypes = [ctypes.POINTER(ShellExecuteInfo)]
    info = ShellExecuteInfo(cbSize=ctypes.sizeof(ShellExecuteInfo), fMask=SEE_MASK_NOCLOSEPROCESS | SEE_MASK_NOASYNC | SEE_MASK_FLAG_NO_UI, lpFile=str(exe), lpParameters=params, nShow=SW_SHOWNORMAL)
    if not shell32.ShellExecuteExW(ctypes.byref(info)):
        raise OSError(ctypes.get_last_error(), f"could not start {exe}")
    return info.hProcess


def validate(script: Path, args: Sequence[str]) -> subprocess.CompletedProcess[bytes]:
    """Load the script without running it, under the plain build with a pipe, so syntax errors and load-time warnings are captured."""
    command = [str(plain_ahk_exe()), "/ErrorStdOut=UTF-8", "/validate", "/include", str(PRELUDE), str(script), *args]
    return subprocess.run(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)


def run_script(script: Path, timeout: float, args: Sequence[str] = ()) -> Run:
    """Run the script under the prelude with the watchdog and return what happened."""
    kernel32 = ctypes.windll.kernel32
    kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel32.GetProcessId.argtypes = [wintypes.HANDLE]
    kernel32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    WAIT_OBJECT_0 = 0

    started = time.monotonic()
    loaded = validate(script, args)
    output = loaded.stdout.decode("utf-8", errors="replace")
    if loaded.returncode != 0:
        duration_ms = round((time.monotonic() - started) * 1000)
        return Run(output, "error", loaded.returncode, duration_ms, f"[acu] exit {loaded.returncode} {duration_ms}ms")

    fd, out_path = tempfile.mkstemp(prefix="acu-", suffix=".out")
    os.close(fd)
    params = subprocess.list2cmdline(["/ErrorStdOut=UTF-8", "/include", str(PRELUDE), str(script), OUTPUT_ARG + out_path, HOME_ARG + str(acu_home()), *args])
    process = shell_execute(ahk_exe(), params)
    try:
        timed_out = kernel32.WaitForSingleObject(process, int(timeout * 1000)) != WAIT_OBJECT_0
        if timed_out:
            request_close(kernel32.GetProcessId(process))
            if kernel32.WaitForSingleObject(process, int(CLOSE_GRACE_SECONDS * 1000)) == WAIT_OBJECT_0:
                ending = "closed on request"
            else:
                kernel32.TerminateProcess(process, TIMEOUT_EXIT_CODE)
                kernel32.WaitForSingleObject(process, 5000)
                ending = "killed"
        exit_code = wintypes.DWORD()
        kernel32.GetExitCodeProcess(process, ctypes.byref(exit_code))
    finally:
        kernel32.CloseHandle(process)
    output += Path(out_path).read_text(encoding="utf-8", errors="replace")
    os.unlink(out_path)

    duration_ms = round((time.monotonic() - started) * 1000)
    if timed_out:
        return Run(output, "timeout", TIMEOUT_EXIT_CODE, duration_ms, f"[acu] timeout {timeout:g}s: {ending}")
    if exit_code.value == 0:
        return Run(output, "ok", 0, duration_ms, f"[acu] ok {duration_ms}ms")
    return Run(output, "error", exit_code.value, duration_ms, f"[acu] exit {exit_code.value} {duration_ms}ms")


def record(script: Path, run: Run, timeout: float) -> Path | None:
    """Append the run log; return the failure report's path so CLI/MCP callers can expose it."""
    home = acu_home()
    stamp = datetime.now().astimezone()
    digest = hashlib.sha256(script.read_bytes()).hexdigest()
    entry: dict[str, object] = {
        "ts": stamp.isoformat(timespec="milliseconds"),
        "script": str(script),
        "sha256": digest,
        "outcome": run.outcome,
        "exit_code": run.exit_code,
        "duration_ms": run.duration_ms,
        "timeout_s": timeout,
    }
    report = None
    if run.outcome != "ok":
        crashes = home / "crashes"
        crashes.mkdir(parents=True, exist_ok=True)
        report = crashes / f"{stamp.strftime('%Y%m%d-%H%M%S-%f')}-{digest[:8]}.json"
        report.write_text(json.dumps({**entry, "output": run.output}, indent=2), encoding="utf-8")
        entry["crash_report"] = str(report)
    logs = home / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    with (logs / "runs.jsonl").open("a", encoding="utf-8") as log:
        log.write(json.dumps(entry) + "\n")
    return report


def main(argv: Sequence[str] | None = None) -> int:
    # Split at the first -- by hand: everything after it belongs to the script, whatever argparse version runs.
    launcher_args = list(sys.argv[1:] if argv is None else argv)
    script_args: list[str] = []
    if "--" in launcher_args:
        split = launcher_args.index("--")
        launcher_args, script_args = launcher_args[:split], launcher_args[split + 1 :]

    parser = argparse.ArgumentParser(
        description="Run an AutoHotkey v2 script under the ACU prelude.",
        epilog="Arguments after -- are passed to the script and arrive in its A_Args.",
    )
    parser.add_argument("script", type=Path, help="path to the .ahk script")
    parser.add_argument("--timeout", type=float, default=30, help="seconds before the watchdog stops the script")
    args = parser.parse_args(launcher_args)
    script = args.script.resolve()
    if not script.is_file():
        parser.error(f"script not found: {script}")

    run = run_script(script, args.timeout, script_args)

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    text = run.output
    if text and not text.endswith("\n"):
        text += "\n"
    sys.stdout.write(text + run.trailer + "\n")
    sys.stdout.flush()

    # After the output, and never allowed to replace the script's exit code: a lost log line is reported, not fatal.
    try:
        record(script, run, args.timeout)
    except OSError as failure:
        print(f"[acu] log failed: {failure}", file=sys.stderr)
    return run.exit_code


if __name__ == "__main__":
    sys.exit(main())
