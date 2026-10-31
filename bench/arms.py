"""One table owns harness, skill, runtime and computer-use route facts for every arm."""
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

from bench.common import ROOT
from bench.harnesses import pi, claude, codex


# Arm facts are shared by profile preparation, measurement, auditing and aggregation.
@dataclass(frozen=True)
class Arm:
    id: str
    harness: ModuleType
    skill_name: str
    runtime: str
    computer_use_pattern: str
    uses_cua_daemon: bool = False
    native: bool = False

    # Resolve installed skills when preparing a profile, without probing at import time.
    def skill_path(self):
        if self.native:
            return pi.native_skill()
        return ROOT / 'acu' if self.skill_name == 'acu' else Path.home() / '.agents/skills' / self.skill_name


ARM_TABLE = {arm.id: arm for arm in (
    Arm('pi-acu', pi, 'acu', 'ACU', r'\bacu run\b'),
    Arm('pi-cua', pi, 'cua-driver', 'CUA', r'cua-driver', uses_cua_daemon=True),
    Arm('pi-computer-use', pi, 'computer-use', 'Codex computer use', r'\bsky\.', native=True),
    Arm('claude-acu', claude, 'acu', 'ACU', r'\bacu run\b'),
    Arm('claude-cua', claude, 'cua-driver', 'CUA', r'cua-driver', uses_cua_daemon=True),
    Arm('codex-computer-use', codex, 'computer-use', 'Codex computer use', r'\bsky\.', native=True),
)}
ARMS = tuple(key for key, arm in ARM_TABLE.items() if arm.harness.live)


# Shared callers select model and reasoning from the arm's harness adapter.
def arm_model(arm):
    host = ARM_TABLE[arm].harness
    return host.model, host.reasoning


# Only CUA arms restart the shared daemon before and after their trial.
def uses_cua_daemon(arm):
    return ARM_TABLE[arm].uses_cua_daemon
