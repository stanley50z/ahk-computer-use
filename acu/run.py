"""ACU launcher: run one AutoHotkey v2 script with captured output, a deadline and verified shutdown.

Usage: python acu/run.py SCRIPT.ahk [--timeout SECONDS] [-- ARG ...]

Arguments after -- are passed to the script and arrive in its A_Args. Prints the script's stdout and stderr followed by one "[acu] ..." trailer line, then exits with the
script's exit code, 124 when the shared validation/execution budget expires, or 130 on Ctrl+C.
On timeout or interruption the script is first asked to close (WM_CLOSE to its main window, which
runs its exit handlers) and killed if it is still running one second later. Shutdown is verified
before returning or raising. Force-killing the launcher bypasses this cleanup.

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

# Modules a run does not always need are imported where they are used: the CLI starts once per action chain.
import ctypes
import os
import subprocess
import sys
import time
from contextlib import contextmanager
from ctypes import wintypes
from dataclasses import dataclass
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


def install_console_handlers() -> None:
    """Give both CLI entry points the same Ctrl+Break cancellation behavior as Ctrl+C."""
    if sys.platform == "win32":
        import signal

        signal.signal(signal.SIGBREAK, signal.default_int_handler)


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


@contextmanager
def defer_console_interrupts():
    """Delay console cancellation until the caller has registered ownership of a new process."""
    import signal
    import threading

    if threading.current_thread() is not threading.main_thread():
        yield
        return
    interrupted = False

    def defer(_number, _frame):
        nonlocal interrupted
        interrupted = True

    signals = [signal.SIGINT]
    if sys.platform == "win32":
        signals.append(signal.SIGBREAK)
    previous = {number: signal.getsignal(number) for number in signals}
    try:
        for number, handler in previous.items():
            if handler != signal.SIG_IGN:
                signal.signal(number, defer)
        yield
    finally:
        for number, handler in previous.items():
            signal.signal(number, handler)
        if interrupted:
            raise KeyboardInterrupt


def shell_execute(exe: Path, params: str) -> wintypes.HANDLE:
    """Start exe through ShellExecuteEx, the one way Windows starts a UI Access program, and return its process handle."""
    SEE_MASK_NOCLOSEPROCESS, SEE_MASK_NOASYNC, SEE_MASK_FLAG_NO_UI, SW_SHOWNORMAL = 0x40, 0x100, 0x400, 1
    shell32 = ctypes.WinDLL("shell32", use_last_error=True)
    shell32.ShellExecuteExW.argtypes = [ctypes.POINTER(ShellExecuteInfo)]
    info = ShellExecuteInfo(cbSize=ctypes.sizeof(ShellExecuteInfo), fMask=SEE_MASK_NOCLOSEPROCESS | SEE_MASK_NOASYNC | SEE_MASK_FLAG_NO_UI, lpFile=str(exe), lpParameters=params, nShow=SW_SHOWNORMAL)
    if not shell32.ShellExecuteExW(ctypes.byref(info)):
        raise OSError(ctypes.get_last_error(), f"could not start {exe}")
    return info.hProcess


def report_shutdown_failure(script: Path, output: str, timeout: float, started: float) -> None:
    """Persist and announce a failed shutdown before waiting with ownership retained."""
    import traceback

    message = "[acu] shutdown failed; retaining ownership until the process exits"
    print(message, file=sys.stderr, flush=True)
    output += "\n" + message + "\n" + traceback.format_exc()
    duration_ms = round((time.monotonic() - started) * 1000)
    try:
        report = record(script, Run(output, "error", 1, duration_ms, message), timeout)
    except OSError as diagnostic_error:
        print(f"[acu] could not persist shutdown failure: {diagnostic_error}", file=sys.stderr, flush=True)
    else:
        print(f"[acu] shutdown failure report: {report}", file=sys.stderr, flush=True)


def validate(script: Path, args: Sequence[str], timeout: float) -> subprocess.CompletedProcess[bytes]:
    """Own the validator from creation through bounded communication and verified cleanup."""
    command = [str(plain_ahk_exe()), "/ErrorStdOut=UTF-8", "/validate", "/include", str(PRELUDE), str(script), *args]
    started = time.monotonic()
    process = None
    output = b""
    try:
        try:
            try:
                with defer_console_interrupts():
                    process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                output, _ = process.communicate(timeout=max(0, started + timeout - time.monotonic()))
            finally:
                if process is not None:
                    with defer_console_interrupts():
                        try:
                            if process.poll() is None:
                                process.kill()
                            process.wait()
                        except Exception:
                            try:
                                report_shutdown_failure(script, output.decode("utf-8", errors="replace"), timeout, started)
                            finally:
                                while True:
                                    try:
                                        process.wait()
                                        break
                                    except OSError:
                                        # Already reported; retry only to verify exit, never to resume work.
                                        time.sleep(0.05)
                            raise
        except subprocess.TimeoutExpired as failure:
            # The validator has exited; drain its pipe so the timeout report keeps all diagnostics.
            failure.stdout, _ = process.communicate()
            raise
        return subprocess.CompletedProcess(command, process.returncode, output)
    finally:
        if process is not None and process.stdout is not None:
            process.stdout.close()


def wait_for_exit(process: wintypes.HANDLE, timeout: float) -> bool:
    """Poll the owned process in short waits so Python can handle keyboard interrupts."""
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    deadline = time.monotonic() + max(0, timeout)
    while True:
        milliseconds = min(50, max(0, int((deadline - time.monotonic()) * 1000)))
        status = kernel32.WaitForSingleObject(process, milliseconds)
        if status == 0:  # WAIT_OBJECT_0
            return True
        if status != 258:  # WAIT_TIMEOUT
            raise ctypes.WinError(ctypes.get_last_error())
        if time.monotonic() >= deadline:
            return False


def stop_script(process: wintypes.HANDLE) -> str:
    """Close the owned script, escalating to a verified kill even if graceful cleanup raises."""
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetProcessId.argtypes = [wintypes.HANDLE]
    kernel32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
    try:
        if wait_for_exit(process, 0):
            return "exited"
        request_close(kernel32.GetProcessId(process))
        if wait_for_exit(process, CLOSE_GRACE_SECONDS):
            return "closed on request"
    finally:
        if not wait_for_exit(process, 0):
            if not kernel32.TerminateProcess(process, TIMEOUT_EXIT_CODE):
                raise ctypes.WinError(ctypes.get_last_error())
            if not wait_for_exit(process, 5):
                raise RuntimeError("AutoHotkey did not exit after termination")
    return "killed"


def run_script(script: Path, timeout: float, args: Sequence[str] = ()) -> Run:
    """Run within one validation/execution budget; reap the script before returning or raising."""
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

    started = time.monotonic()
    deadline = started + timeout
    try:
        loaded = validate(script, args, max(0, deadline - time.monotonic()))
    except subprocess.TimeoutExpired as failure:
        output = (failure.stdout or b"").decode("utf-8", errors="replace")
        duration_ms = round((time.monotonic() - started) * 1000)
        return Run(output, "timeout", TIMEOUT_EXIT_CODE, duration_ms, f"[acu] timeout {timeout:g}s: validation")
    except KeyboardInterrupt:
        duration_ms = round((time.monotonic() - started) * 1000)
        return Run("", "error", 130, duration_ms, f"[acu] interrupted during validation {duration_ms}ms")
    output = loaded.stdout.decode("utf-8", errors="replace")
    if loaded.returncode != 0:
        duration_ms = round((time.monotonic() - started) * 1000)
        return Run(output, "error", loaded.returncode, duration_ms, f"[acu] exit {loaded.returncode} {duration_ms}ms")

    if time.monotonic() >= deadline:
        duration_ms = round((time.monotonic() - started) * 1000)
        return Run(output, "timeout", TIMEOUT_EXIT_CODE, duration_ms, f"[acu] timeout {timeout:g}s: validation")

    import tempfile

    fd, out_path = tempfile.mkstemp(prefix="acu-", suffix=".out")
    os.close(fd)
    timed_out = interrupted = False
    try:
        params = subprocess.list2cmdline(["/ErrorStdOut=UTF-8", "/include", str(PRELUDE), str(script), OUTPUT_ARG + out_path, HOME_ARG + str(acu_home()), *args])
        process = None
        try:
            try:
                with defer_console_interrupts():
                    process = shell_execute(ahk_exe(), params)
                timed_out = not wait_for_exit(process, deadline - time.monotonic())
            except KeyboardInterrupt:
                interrupted = True
            finally:
                if process is not None:
                    # A second interrupt must not abandon a script during shutdown.
                    while True:
                        try:
                            ending = stop_script(process)
                            break
                        except KeyboardInterrupt:
                            interrupted = True
                        except Exception:
                            # A failed stop is not permission to hand the desktop to another script.
                            try:
                                snapshot = output + Path(out_path).read_text(encoding="utf-8", errors="replace")
                                report_shutdown_failure(script, snapshot, timeout, started)
                            finally:
                                # Even an unsuccessful wait cannot prove exit. Keep the handle and lease;
                                # defer further console interrupts until the OS confirms the process ended.
                                with defer_console_interrupts():
                                    while kernel32.WaitForSingleObject(process, 1000) != 0:
                                        time.sleep(0.05)
                            raise
            exit_code = wintypes.DWORD()
            if process is not None and not kernel32.GetExitCodeProcess(process, ctypes.byref(exit_code)):
                raise ctypes.WinError(ctypes.get_last_error())
        finally:
            if process is not None:
                kernel32.CloseHandle(process)
        output += Path(out_path).read_text(encoding="utf-8", errors="replace")
    finally:
        os.unlink(out_path)

    duration_ms = round((time.monotonic() - started) * 1000)
    if interrupted:
        return Run(output, "error", 130, duration_ms, f"[acu] interrupted {duration_ms}ms")
    if timed_out:
        return Run(output, "timeout", TIMEOUT_EXIT_CODE, duration_ms, f"[acu] timeout {timeout:g}s: {ending}")
    if exit_code.value == 0:
        return Run(output, "ok", 0, duration_ms, f"[acu] ok {duration_ms}ms")
    return Run(output, "error", exit_code.value, duration_ms, f"[acu] exit {exit_code.value} {duration_ms}ms")


def record(script: Path, run: Run, timeout: float) -> Path | None:
    """Append the run log; return the failure report's path so CLI callers can expose it."""
    import hashlib
    import json
    from datetime import datetime

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
    import argparse

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

    install_console_handlers()
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
