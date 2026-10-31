"""The only scenario-name dispatch: register an adapter factory for each supported task."""
from functools import partial
from typing import Callable

from bench.calculator import CalculatorScenario
from bench.scenario import Scenario
from bench.tb3 import TASKS, TB3Scenario


# Defer Pillow until after CLI runtime preflight selects the project's installed dependencies.
def illustrator_scenario() -> Scenario:
    from bench.illustrator_pen_tool import IllustratorScenario
    return IllustratorScenario()


SCENARIOS: dict[str, Callable[[], Scenario]] = {
    'calculator': CalculatorScenario,
    'illustrator-pen-tool': illustrator_scenario,
    **{name: partial(TB3Scenario, name) for name in TASKS},
}


# A new instance keeps collection state local to one attempt, including failed attempts.
def get_scenario(name: str) -> Scenario:
    if name not in SCENARIOS:
        raise ValueError(f'unknown scenario: {name}')
    return SCENARIOS[name]()
