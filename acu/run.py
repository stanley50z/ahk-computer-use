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
import re
import subprocess
import sys
import time
from contextlib import contextmanager
from ctypes import wintypes
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO, Literal, Protocol, Sequence

HERE = Path(__file__).resolve().parent
PRELUDE = HERE / "prelude.ahk"
DEFAULT_AHK = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "AutoHotkey" / "v2" / "AutoHotkey64_UIA.exe"
TIMEOUT_EXIT_CODE = 124
CLOSE_GRACE_SECONDS = 1.0
WM_CLOSE = 0x0010
OUTPUT_ARG = "--acu-out="  # the prelude strips these leading arguments: the output file to redirect into, and ACU_HOME
HOME_ARG = "--acu-home="

Outcome = Literal["ok", "error", "timeout"]
SNIPPET_MARKER = re.compile(r"^\[acu:snippets\] ([^\\/\r\n:]+\.exe)\r?$(?:\n)?", re.MULTILINE | re.IGNORECASE)


def is_app_process(name: str) -> bool:
    """Exclude store-app frame hosts from both run records and legacy history attribution."""
    return name.casefold() != "applicationframehost.exe"


@dataclass
class Run:
    """What one script run produced: its merged output, how it ended, and the trailer line to print."""

    output: str
    outcome: Outcome
    exit_code: int
    duration_ms: int
    phase: Literal["validation", "execution"] = "execution"
    timeout_s: float = 30
    ending: str = ""
    interrupted: bool = False
    app: str | None = field(init=False)

    def __post_init__(self) -> None:
        """Capture one distinct app before discovery expands output; absent/ambiguous markers stay unknown."""
        names = {match[1].casefold(): match[1] for match in SNIPPET_MARKER.finditer(self.output)
                 if is_app_process(match[1])}
        self.app = next(iter(names.values())) if len(names) == 1 else None

    @property
    def trailer(self) -> str:
        """Derive the unchanged text/JSON verdict in one place from execution facts."""
        if self.interrupted:
            phase = " during validation" if self.phase == "validation" else ""
            return f"[acu] interrupted{phase} {self.duration_ms}ms"
        if self.outcome == "timeout":
            ending = "validation" if self.phase == "validation" else self.ending
            return f"[acu] timeout {self.timeout_s:g}s: {ending}"
        if self.outcome == "ok":
            return f"[acu] ok {self.duration_ms}ms"
        return f"[acu] exit {self.exit_code} {self.duration_ms}ms"


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
        report = record(script, Run(output, "error", 1, duration_ms), timeout)
    except OSError as diagnostic_error:
        print(f"[acu] could not persist shutdown failure: {diagnostic_error}", file=sys.stderr, flush=True)
    else:
        print(f"[acu] shutdown failure report: {report}", file=sys.stderr, flush=True)


class ValidationProcess(Protocol):
    """Pipe-based validator owned until wait completes and stdout is closed."""

    stdout: BinaryIO | None
    returncode: int | None

    def communicate(self, timeout: float | None = None) -> tuple[bytes, bytes | None]: ...
    def poll(self) -> int | None: ...
    def kill(self) -> None: ...
    def wait(self) -> int: ...


class ScriptProcess(Protocol):
    """A UI Access process; close releases its handle only after verified exit."""

    def wait(self, timeout: float) -> bool: ...
    def request_close(self) -> None: ...
    def kill(self) -> None: ...
    def exit_code(self) -> int: ...
    def close(self) -> None: ...


class ProcessAdapter(Protocol):
    """Create owned validation/script processes; callers defer interrupts across these calls."""

    def start_validation(self, command: Sequence[str]) -> ValidationProcess: ...
    def start_script(self, exe: Path, arguments: Sequence[str]) -> ScriptProcess: ...


class Win32ScriptProcess:
    """Adapt a ShellExecute process handle to the launcher's lifecycle operations."""

    def __init__(self, exe: Path, arguments: Sequence[str]):
        self.kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self.kernel32.GetProcessId.argtypes = [wintypes.HANDLE]
        self.kernel32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
        self.kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        self.kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        # Configure the adapter before creation so no setup failure can orphan a new process.
        self.handle = shell_execute(exe, subprocess.list2cmdline(arguments))

    def wait(self, timeout: float) -> bool:
        return wait_for_exit(self.handle, timeout)

    def request_close(self) -> None:
        request_close(self.kernel32.GetProcessId(self.handle))

    def kill(self) -> None:
        if not self.kernel32.TerminateProcess(self.handle, TIMEOUT_EXIT_CODE):
            raise ctypes.WinError(ctypes.get_last_error())

    def exit_code(self) -> int:
        code = wintypes.DWORD()
        if not self.kernel32.GetExitCodeProcess(self.handle, ctypes.byref(code)):
            raise ctypes.WinError(ctypes.get_last_error())
        return code.value

    def close(self) -> None:
        self.kernel32.CloseHandle(self.handle)


class Win32ProcessAdapter:
    """Use a pipe for the plain validator and ShellExecute for signed UI Access execution."""

    def start_validation(self, command: Sequence[str]) -> ValidationProcess:
        return subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    def start_script(self, exe: Path, arguments: Sequence[str]) -> ScriptProcess:
        return Win32ScriptProcess(exe, arguments)


def validate(script: Path, args: Sequence[str], timeout: float,
             process_adapter: ProcessAdapter) -> subprocess.CompletedProcess[bytes]:
    """Own the validator from creation through bounded communication and verified cleanup."""
    command = [str(plain_ahk_exe()), "/ErrorStdOut=UTF-8", "/validate", "/include", str(PRELUDE), str(script), *args]
    started = time.monotonic()
    process = None
    output = b""
    try:
        try:
            try:
                with defer_console_interrupts():
                    process = process_adapter.start_validation(command)
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


def stop_script(process: ScriptProcess) -> str:
    """Close the owned script, escalating to a verified kill even if graceful cleanup raises."""
    try:
        if process.wait(0):
            return "exited"
        process.request_close()
        if process.wait(CLOSE_GRACE_SECONDS):
            return "closed on request"
    finally:
        if not process.wait(0):
            process.kill()
            if not process.wait(5):
                raise RuntimeError("AutoHotkey did not exit after termination")
    return "killed"


def run_script(script: Path, timeout: float, args: Sequence[str] = (), *,
               process_adapter: ProcessAdapter | None = None) -> Run:
    """Run within one validation/execution budget; reap the script before returning or raising."""
    adapter = Win32ProcessAdapter() if process_adapter is None else process_adapter

    started = time.monotonic()
    deadline = started + timeout
    try:
        loaded = validate(script, args, max(0, deadline - time.monotonic()), adapter)
    except subprocess.TimeoutExpired as failure:
        output = (failure.stdout or b"").decode("utf-8", errors="replace")
        duration_ms = round((time.monotonic() - started) * 1000)
        return Run(output, "timeout", TIMEOUT_EXIT_CODE, duration_ms, phase="validation", timeout_s=timeout)
    except KeyboardInterrupt:
        duration_ms = round((time.monotonic() - started) * 1000)
        return Run("", "error", 130, duration_ms, phase="validation", interrupted=True)
    output = loaded.stdout.decode("utf-8", errors="replace")
    if loaded.returncode != 0:
        duration_ms = round((time.monotonic() - started) * 1000)
        return Run(output, "error", loaded.returncode, duration_ms, phase="validation")

    if time.monotonic() >= deadline:
        duration_ms = round((time.monotonic() - started) * 1000)
        return Run(output, "timeout", TIMEOUT_EXIT_CODE, duration_ms, phase="validation", timeout_s=timeout)

    import tempfile

    fd, out_path = tempfile.mkstemp(prefix="acu-", suffix=".out")
    os.close(fd)
    timed_out = interrupted = False
    try:
        arguments = ["/ErrorStdOut=UTF-8", "/include", str(PRELUDE), str(script), OUTPUT_ARG + out_path, HOME_ARG + str(acu_home()), *args]
        process = None
        try:
            try:
                with defer_console_interrupts():
                    process = adapter.start_script(ahk_exe(), arguments)
                timed_out = not process.wait(deadline - time.monotonic())
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
                                    while True:
                                        try:
                                            if process.wait(1):
                                                break
                                        except OSError:
                                            pass  # Already reported; only a successful wait proves exit.
                                        time.sleep(0.05)
                            raise
            exit_code = process.exit_code() if process is not None else 0
        finally:
            if process is not None:
                process.close()
        output += Path(out_path).read_text(encoding="utf-8", errors="replace")
    finally:
        os.unlink(out_path)

    duration_ms = round((time.monotonic() - started) * 1000)
    if interrupted:
        return Run(output, "error", 130, duration_ms, interrupted=True)
    if timed_out:
        return Run(output, "timeout", TIMEOUT_EXIT_CODE, duration_ms, timeout_s=timeout, ending=ending)
    if exit_code == 0:
        return Run(output, "ok", 0, duration_ms)
    return Run(output, "error", exit_code, duration_ms)


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
        "app": run.app,
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
    """Format the shared run operation as output followed by the low-level trailer."""
    import argparse
    from .tool import LOW_LEVEL_OPTIONS, run_operation, split_script_args

    launcher_args, script_args = split_script_args(sys.argv[1:] if argv is None else argv)

    parser = argparse.ArgumentParser(
        description="Run an AutoHotkey v2 script under the ACU prelude.",
        epilog="Arguments after -- are passed to the script and arrive in its A_Args.",
    )
    parser.add_argument("script", help="path to the .ahk script")
    parser.add_argument("--timeout", type=float, default=30, help="seconds before the watchdog stops the script")
    args = parser.parse_args(launcher_args)
    try:
        completed = run_operation(args.script, args.timeout, script_args, options=LOW_LEVEL_OPTIONS)
    except ValueError as error:
        parser.error(str(error))
    run = completed.run

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    text = run.output
    if text and not text.endswith("\n"):
        text += "\n"
    sys.stdout.write(text + run.trailer + "\n")
    sys.stdout.flush()

    if completed.log_error is not None:
        print(f"[acu] log failed: {completed.log_error}", file=sys.stderr)
    return run.exit_code


if __name__ == "__main__":
    # Direct file invocation must use the same package module as the installed CLI.
    sys.path.insert(0, str(HERE.parent))
    from acu.run import main as package_main

    sys.exit(package_main())
