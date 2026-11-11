"""Run an existing AHK script file through the CLI under the launcher protections."""

import math
import re
from contextlib import nullcontext
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from . import run as launcher
from .settings import snippets_enabled
from .snippets import find_app_folder, format_snippets, list_snippets, snippets_root

HERE = Path(__file__).resolve().parent
BUNDLED_SCRIPTS = ("tree.ahk", "screenshot.ahk")


def resolve_script(script: str, cwd: str | None = None) -> Path:
    """Resolve a caller's path or bare bundled name; history supplies the captured cwd."""
    path = Path(script).expanduser()
    candidate = Path(cwd) / path if cwd else path
    if path.name in BUNDLED_SCRIPTS and str(path.parent) == "." and not candidate.is_file():
        return HERE / path.name
    return candidate.resolve()


def _expand_snippet_markers(output: str, working_folder: Path) -> str:
    """Replace AHK discovery lines using the same store and format as explicit listing."""
    marker = launcher.SNIPPET_MARKER
    if not marker.search(output):
        return output
    try:
        enabled = snippets_enabled(working_folder)
    except ValueError as error:
        message = " ".join(str(error).splitlines())
        return marker.sub(lambda match: f"[acu] {message}\n", output)

    def expand(match: re.Match[str]) -> str:
        if not enabled:
            return ""
        try:
            folder = find_app_folder(snippets_root(), match[1])
            if folder is None:
                return ""
            return format_snippets(folder, list_snippets(folder)) + "\n"
        except OSError as error:  # The script already acted; report the store problem beside its result.
            return f"[acu] cannot list snippets: {error}\n"

    return marker.sub(expand, output)


@dataclass(frozen=True)
class RunOptions:
    """Intentional entrypoint differences, independent of output formatting.

    acu run takes the desktop lease, bounds timeout to (0, 300], and expands
    snippet markers. The low-level command disables all three. Both resolve
    local/bundled scripts, capture app attribution, and record completed runs.
    """

    lease: bool = True
    bounded_timeout: bool = True
    expand_markers: bool = True


CLI_OPTIONS = RunOptions()
LOW_LEVEL_OPTIONS = RunOptions(lease=False, bounded_timeout=False, expand_markers=False)


@dataclass
class RunResult:
    """A completed operation, including diagnostics that cannot replace its outcome."""

    run: launcher.Run
    run_log: Path
    crash_report: Path | None = None
    log_error: str | None = None


def split_script_args(arguments: Sequence[str]) -> tuple[list[str], list[str]]:
    """Split only the first --; the remainder belongs literally to the script."""
    values = list(arguments)
    if "--" not in values:
        return values, []
    boundary = values.index("--")
    return values[:boundary], values[boundary + 1:]


def run_operation(script: str, timeout: float = 30, args: Sequence[str] = (), *,
                  options: RunOptions = CLI_OPTIONS,
                  process_adapter: launcher.ProcessAdapter) -> RunResult:
    """Own resolution, console cancellation, optional lease, execution, discovery and recording.

    The adapter supplies every Windows contact; each entry point passes the real one unless a test passes a fake.
    """
    if not script.strip():
        raise ValueError("script path must be non-empty")
    if options.bounded_timeout and (not math.isfinite(timeout) or not 0 < timeout <= 300):
        raise ValueError("timeout must be finite and between 0 (exclusive) and 300 seconds")
    path = resolve_script(script)
    if not path.is_file():
        raise ValueError(f"script not found: {path}")
    if any(not isinstance(arg, str) or "\0" in arg for arg in args):
        raise ValueError("script args must be strings without NUL characters")
    launcher.install_console_handlers()
    with process_adapter.desktop_lease() if options.lease else nullcontext():
        result = launcher.run_script(path, timeout, args, process_adapter)
        if options.expand_markers:
            result.output = _expand_snippet_markers(result.output, Path.cwd())
        response = RunResult(result, launcher.acu_home() / "logs" / "runs.jsonl")
        try:
            response.crash_report = launcher.record(path, result, timeout)
        except OSError as error:
            response.log_error = str(error)
        return response


def run(script: str, timeout: float = 30, args: list[str] | None = None, *,
        process_adapter: launcher.ProcessAdapter) -> dict:
    """Format the shared operation's result for the JSON CLI."""
    try:
        completed = run_operation(script, timeout, [] if args is None else args, process_adapter=process_adapter)
    except SystemExit as error:
        raise ValueError(str(error)) from error
    result = completed.run
    response = {
        "engine": "ahk", "outcome": result.outcome, "exit_code": result.exit_code,
        "output": result.output, "trailer": result.trailer, "duration_ms": result.duration_ms,
        "artifacts": {"run_log": str(completed.run_log)},
    }
    if completed.crash_report:
        response["artifacts"]["crash_report"] = str(completed.crash_report)
    if completed.log_error is not None:
        response["log_error"] = completed.log_error
    return response
