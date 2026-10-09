"""ACU launcher: run one AutoHotkey v2 script under the ACU prelude with captured output and a hard timeout.

Usage: python acu/run.py SCRIPT.ahk [--timeout SECONDS] [-- ARG ...]

Arguments after -- are passed to the script and arrive in its A_Args. Prints the script's stdout and stderr followed by one "[acu] ..." trailer line, then exits with the
script's exit code, or 124 when the watchdog fired. At the timeout the script is first asked to close
(WM_CLOSE to its main window, which runs the prelude's exit handler) and killed if it is still running
one second later.

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
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal, Sequence

HERE = Path(__file__).resolve().parent
PRELUDE = HERE / "prelude.ahk"
DEFAULT_AHK = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "AutoHotkey" / "v2" / "AutoHotkey64.exe"
TIMEOUT_EXIT_CODE = 124
CLOSE_GRACE_SECONDS = 1.0
WM_CLOSE = 0x0010

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
    """Path to AutoHotkey64.exe, overridable with the ACU_AHK environment variable."""
    path = Path(os.environ.get("ACU_AHK") or DEFAULT_AHK)
    if not path.is_file():
        raise SystemExit(f"[acu] AutoHotkey not found at {path}; set ACU_AHK to the v2 AutoHotkey64.exe")
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


def run_script(script: Path, timeout: float, args: Sequence[str] = ()) -> Run:
    """Run the script under the prelude with the watchdog and return what happened.

    Waits for the AutoHotkey process itself, not for end-of-file on its output: a program the script
    launches inherits the pipe and would otherwise hold the launcher open until that program closed.
    """
    command = [str(ahk_exe()), "/ErrorStdOut=UTF-8", "/include", str(PRELUDE), str(script), *args]
    started = time.monotonic()
    proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    chunks: list[bytes] = []

    def drain() -> None:
        while chunk := os.read(proc.stdout.fileno(), 65536):
            chunks.append(chunk)

    reader = threading.Thread(target=drain, daemon=True)
    reader.start()

    timed_out = False
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        request_close(proc.pid)
        try:
            proc.wait(timeout=CLOSE_GRACE_SECONDS)
            ending = "closed on request"
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            ending = "killed"
    reader.join(0.2)  # everything the script wrote is already in the pipe; an inherited handle may keep it open

    duration_ms = round((time.monotonic() - started) * 1000)
    output = b"".join(chunks).decode("utf-8", errors="replace")
    if timed_out:
        return Run(output, "timeout", TIMEOUT_EXIT_CODE, duration_ms, f"[acu] timeout {timeout:g}s: {ending}")
    if proc.returncode == 0:
        return Run(output, "ok", 0, duration_ms, f"[acu] ok {duration_ms}ms")
    return Run(output, "error", proc.returncode, duration_ms, f"[acu] exit {proc.returncode} {duration_ms}ms")


def record(script: Path, run: Run, timeout: float) -> None:
    """Append the run to logs/runs.jsonl and, unless it ended cleanly, write a crash report with its output."""
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
