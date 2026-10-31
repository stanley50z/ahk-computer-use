"""Scenario contract driven by the controller; adapters never import the controller."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from bench.tool_calls import ToolCall


# The independent observer is shared by all arms and can be replaced for offline lifecycle checks.
class Observer(Protocol):
    def __call__(self, run_dir: Path, script: Path, *args, suffix: str = '', timeout: int = 15) -> str: ...


# Per-attempt facts shared with the adapter, including whether collection may inspect an actor result.
@dataclass
class Trial:
    plan: dict
    observer: Observer
    before: str
    actor_started: bool = False

    @property
    def run_dir(self) -> Path:
        return Path(self.plan['run_dir'])


# Register a fresh adapter per attempt. Optional hooks mean no work for scenarios without that resource.
class Scenario(ABC):
    application: str
    prepares_desktop = True
    verify_before_audit = False
    group_process_windows = False
    fail_outside_writes = False
    cursor_verification = 'Saved Windows scheme reloaded and OS showing flag checked; not pixel-level proof.'

    def validate_assets(self):
        pass

    def prepare_files(self, plan):
        pass

    @abstractmethod
    def approved_apps(self) -> list[str]:
        """Executables the native desktop bridge may launch for this scenario."""

    def prepare_desktop(self, trial: Trial):
        pass

    def start_recorder(self, run_dir: Path):
        return None

    def stop_recorder(self, run_dir: Path, recorder):
        pass

    def guarded_roots(self, plan) -> list[Path]:
        return []

    def audit(self, trial: Trial, conduct):
        pass

    @abstractmethod
    def collect_and_grade(self, trial: Trial, tools: list[ToolCall]) -> dict:
        """Return verification; the controller persists it at this scenario's audit boundary."""

    @abstractmethod
    def cleanup(self, trial: Trial) -> dict:
        """Release only owned resources; the controller always restores the cursor afterward."""

    def check_cleanup(self, cleanup):
        pass

    def summarize(self, summary, plan, verification, conduct, isolation):
        pass

    # Final cleanup contributes to the verdict after run_trial's finally block has completed.
    def finalize_summary(self, summary, cleanup, *, failed=False):
        passed = not failed and cleanup.get('passed') is True and cleanup.get('cursor_scheme_restored') is True
        summary['cleanup_passed'] = passed
        if not passed:
            summary['passed'] = False
