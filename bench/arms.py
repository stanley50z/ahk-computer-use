"""One table owns harness, skill, runtime and computer-use route facts for every arm."""
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

from bench.common import ROOT
from bench.harnesses import pi, claude, codex


# Syntax-aware attribution reads these facts after identifying executable code.
@dataclass(frozen=True)
class ComputerUseRoute:
    executable: str | None = None
    subcommand: str | None = None
    excluded_subcommands: tuple[str, ...] = ()
    script_argument: int | None = None
    javascript_namespace: str | None = None


ACU_ROUTE = ComputerUseRoute(executable='acu', subcommand='run', script_argument=2)
CUA_ROUTE = ComputerUseRoute(executable='cua-driver', excluded_subcommands=('--help', '--version', 'describe'))
NATIVE_ROUTE = ComputerUseRoute(javascript_namespace='sky')


# Arm facts are shared by profile preparation, measurement, auditing and aggregation.
@dataclass(frozen=True)
class Arm:
    id: str
    harness: ModuleType
    skill_name: str
    runtime: str
    route: ComputerUseRoute
    uses_cua_daemon: bool = False
    native: bool = False

    # Resolve installed skills when preparing a profile, without probing at import time.
    def skill_path(self):
        if self.native:
            return pi.native_skill()
        return ROOT / 'acu' if self.skill_name == 'acu' else Path.home() / '.agents/skills' / self.skill_name


ARM_TABLE = {arm.id: arm for arm in (
    Arm('pi-acu', pi, 'acu', 'ACU', ACU_ROUTE),
    Arm('pi-cua', pi, 'cua-driver', 'CUA', CUA_ROUTE, uses_cua_daemon=True),
    Arm('pi-computer-use', pi, 'computer-use', 'Codex computer use', NATIVE_ROUTE, native=True),
    Arm('claude-acu', claude, 'acu', 'ACU', ACU_ROUTE),
    Arm('claude-cua', claude, 'cua-driver', 'CUA', CUA_ROUTE, uses_cua_daemon=True),
    Arm('codex-computer-use', codex, 'computer-use', 'Codex computer use', NATIVE_ROUTE, native=True),
)}
ARMS = tuple(key for key, arm in ARM_TABLE.items() if arm.harness.live)


# Shared callers select model and reasoning from the arm's harness adapter.
def arm_model(arm):
    host = ARM_TABLE[arm].harness
    return host.model, host.reasoning


# Only CUA arms restart the shared daemon before and after their trial.
def uses_cua_daemon(arm):
    return ARM_TABLE[arm].uses_cua_daemon
