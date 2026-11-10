"""A finished trial folder's outcome: its verdict with named reasons, plus what aggregation reads from it.

read_outcome(run_dir) is the only place the verdict and the cleanup rule are written. The controller records
summary.json's `passed` and `cleanup_passed` from it, stop.py checks cleanup with it, and aggregate.py builds its
rows from it. It reads the records the controller writes during a trial, never the verdict fields it later
records, so archived Illustrator summaries without the common check fields read the same as new ones.
"""

import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


# Why a trial failed, in the order the checks run. A trial passes when it has no reason.
class Reason(StrEnum):
    WORKER_FAILURE = 'worker_failure'  # The controller raised; crash.txt holds the stack.
    ACTOR_INCOMPLETE = 'actor_incomplete'  # Nonzero exit, failed capture, or no successful final response.
    UNEXPECTED_PROVIDER_FAILURE = 'unexpected_provider_failure'  # failure.json: an unrecovered provider error.
    ISOLATION = 'isolation'
    TASK = 'task'
    CONDUCT = 'conduct'
    INFRASTRUCTURE_FAILURE = 'infrastructure_failure'  # infrastructure-failure.json: maintainer export/collection.
    CLEANUP = 'cleanup'  # Owned resources not released, or the saved cursor scheme not restored.


# What read_outcome returns: callers use passed and reasons for the verdict, the rest for summaries and aggregation.
@dataclass(frozen=True)
class Outcome:
    reasons: tuple[Reason, ...]
    finished: bool  # finished.json says the worker finished; it does not imply cleanup passed.
    # Cleanup failed for a reason other than a recorded infrastructure failure, whose cleanup deliberately
    # preserves the unexported drawing. Reports list it as a safeguard violation.
    cleanup_violation: bool
    unexpected_failure: dict | None
    infrastructure_failure: dict | None
    summary: dict | None  # The recorded summary.json with its scenario detail; None if it was never written.
    output_image: Path | None  # The scenario's recorded maintainer output, where it has one.
    statistics: dict | None  # The comparison metrics row; None when metrics.json is missing or unusable.
    metric_error: str | None

    # The verdict: a trial passes only when no check failed.
    @property
    def passed(self) -> bool:
        return not self.reasons

    # summary.json's cleanup_passed: cleanup was verified and the controller did not fail around it.
    @property
    def cleanup_passed(self) -> bool:
        return Reason.CLEANUP not in self.reasons and Reason.WORKER_FAILURE not in self.reasons


# A missing record means its check did not pass; a malformed one raises.
def _record(path: Path) -> dict | None:
    return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else None


# A check record passes only when it exists and says passed: true; null or a missing field fails.
def _passed(record: dict | None) -> bool:
    return record is not None and record.get('passed') is True


# Read a trial folder, finished or not; absent records become reasons and only malformed JSON raises.
def read_outcome(run_dir: Path) -> Outcome:
    summary = _record(run_dir / 'summary.json')
    finished = _record(run_dir / 'finished.json') or {}
    cleanup = _record(run_dir / 'cleanup.json') or {}
    unexpected_failure = _record(run_dir / 'failure.json')
    infrastructure_failure = _record(run_dir / 'infrastructure-failure.json')
    actor = (summary or {}).get('metrics') or {}
    cursor_restored = cleanup.get('cursor_scheme_restored') is True
    checks = {
        Reason.WORKER_FAILURE: not (run_dir / 'crash.txt').is_file(),
        Reason.ACTOR_INCOMPLETE: (summary is not None and summary.get('exit_code') == 0
                                  and actor.get('agent_completed') is True and _passed(actor.get('capture'))),
        Reason.UNEXPECTED_PROVIDER_FAILURE: unexpected_failure is None,
        Reason.ISOLATION: _passed(_record(run_dir / 'isolation.json')),
        Reason.TASK: _passed(_record(run_dir / 'verification.json')),
        Reason.CONDUCT: _passed(_record(run_dir / 'conduct.json')),
        Reason.INFRASTRUCTURE_FAILURE: infrastructure_failure is None,
        Reason.CLEANUP: cleanup.get('passed') is True and cursor_restored,
    }
    reasons = tuple(reason for reason, passed in checks.items() if not passed)
    statistics, metric_error = _statistics(run_dir / 'metrics.json', (summary or {}).get('quality'))
    output = (summary or {}).get('output_image')
    return Outcome(
        reasons=reasons, finished=finished.get('worker_finished') is True,
        cleanup_violation=not checks[Reason.CLEANUP] and not (infrastructure_failure and cursor_restored),
        unexpected_failure=unexpected_failure, infrastructure_failure=infrastructure_failure, summary=summary,
        output_image=Path(output).resolve() if output else None, statistics=statistics, metric_error=metric_error)


# A failed trial may lack usable metrics; keep the data-loss reason instead of raising.
def _statistics(path: Path, quality: dict | None) -> tuple[dict | None, str | None]:
    if not path.is_file():
        return None, 'failed before extracted metrics were recorded'
    try:
        return comparison_statistics(json.loads(path.read_text(encoding='utf-8'))['benchmark'], quality), None
    except (json.JSONDecodeError, OSError, KeyError) as error:
        return None, str(error)


# Flatten only comparison metrics; descriptive code share remains an observation, never a success criterion.
def comparison_statistics(benchmark: dict, quality: dict | None) -> dict:
    tokens = benchmark.get('api_tokens') or {}
    code = benchmark.get('code_tokens', {})
    calls = benchmark.get('computer_use', {})
    complete = benchmark.get('token_counts_complete') is True
    result = {'total_api_tokens': tokens.get('total') if complete else None}
    for key in ('input_uncached', 'cache_read', 'cache_write', 'output_including_reasoning', 'reasoning_subset'):
        result[key] = tokens.get(key) if complete else None
    result['computer_use_code_tokens_estimate'] = code.get('estimated_tokens') if not code.get('review_required') else None
    result['code_share_percent_estimate'] = code.get('output_share_percent_estimate') if complete and not code.get('review_required') else None
    attributable = calls.get('attribution_complete') is True
    timed = attributable and calls.get('durations_complete') is True
    result['computer_use_call_count'] = calls.get('call_count') if attributable else None
    result['computer_use_busy_s'] = calls.get('busy_seconds') if timed else None
    result['computer_use_sum_call_s'] = calls.get('sum_call_seconds') if timed else None
    for key in ('foreground_iou', 'boundary_mean_manhattan_px', 'boundary_p95_manhattan_px'):
        result[key] = (quality or {}).get(key)
    return result
