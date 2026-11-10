"""A finished trial folder's outcome, read from the records the controller writes; no desktop work."""
import json
from pathlib import Path

import pytest

from bench.outcome import Reason, read_outcome


# Write one JSON record into a trial folder, creating the folder.
def write(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding='utf-8')


# The records a passing trial leaves behind; tests override one record at a time.
def finished_trial(folder: Path, *, summary=None, **records) -> Path:
    passing = {
        'isolation.json': {'passed': True, 'problems': []},
        'verification.json': {'passed': True},
        'conduct.json': {'passed': True, 'problems': []},
        'cleanup.json': {'passed': True, 'cursor_scheme_restored': True},
        'metrics.json': {'benchmark': {'token_counts_complete': True, 'api_tokens': {'total': 120},
                                       'computer_use': {'call_count': 2, 'attribution_complete': True}}},
    }
    passing.update({name.replace('_', '-') + '.json': value for name, value in records.items()})
    for name, value in passing.items():
        if value is not None:
            write(folder / name, value)
    recorded = {'arm': 'pi-acu', 'exit_code': 0, 'passed': True,
                'metrics': {'agent_completed': True, 'capture': {'passed': True}}}
    if summary is not False:
        write(folder / 'summary.json', {**recorded, **(summary or {})})
    write(folder / 'finished.json', {'worker_finished': True, 'cleanup': passing['cleanup.json']})
    return folder


def test_a_trial_that_passed_every_check_passes(tmp_path):
    outcome = read_outcome(finished_trial(tmp_path))
    assert outcome.passed is True
    assert outcome.reasons == ()
    assert outcome.cleanup_passed is True
    assert outcome.finished is True
    assert outcome.cleanup_violation is False


@pytest.mark.parametrize('failed, reason', [
    ({'summary': {'exit_code': 1}}, Reason.ACTOR_INCOMPLETE),
    ({'summary': {'exit_code': 3221225786}}, Reason.ACTOR_INCOMPLETE),  # STATUS_CONTROL_C_EXIT
    ({'summary': {'metrics': {'agent_completed': False, 'capture': {'passed': True}}}}, Reason.ACTOR_INCOMPLETE),
    ({'summary': {'metrics': {'agent_completed': True, 'capture': {'passed': False}}}}, Reason.ACTOR_INCOMPLETE),
    ({'summary': False}, Reason.ACTOR_INCOMPLETE),
    ({'failure': {'kind': 'unexpected_provider_failure', 'errors': ['503']}}, Reason.UNEXPECTED_PROVIDER_FAILURE),
    ({'isolation': {'passed': False, 'problems': ['extra skill loaded']}}, Reason.ISOLATION),
    ({'isolation': None}, Reason.ISOLATION),
    ({'verification': {'passed': False}}, Reason.TASK),
    ({'verification': {'passed': None}}, Reason.TASK),
    ({'verification': None}, Reason.TASK),
    ({'conduct': {'passed': False, 'problems': ['guarded files changed']}}, Reason.CONDUCT),
    ({'conduct': None}, Reason.CONDUCT),
    ({'infrastructure_failure': {'kind': 'maintainer_export_failure'}}, Reason.INFRASTRUCTURE_FAILURE),
    ({'cleanup': {'passed': False, 'cursor_scheme_restored': True}}, Reason.CLEANUP),
    ({'cleanup': {'passed': True, 'cursor_scheme_restored': False}}, Reason.CLEANUP),
    ({'cleanup': {'passed': True}}, Reason.CLEANUP),
    ({'cleanup': None}, Reason.CLEANUP),
], ids=lambda value: str(value)[:60])
def test_each_failed_check_names_its_reason(tmp_path, failed, reason):
    outcome = read_outcome(finished_trial(tmp_path, **failed))
    assert outcome.passed is False
    assert outcome.reasons == (reason,)


def test_a_controller_crash_fails_the_trial_and_its_cleanup(tmp_path):
    folder = finished_trial(tmp_path)
    (folder / 'crash.txt').write_text('Traceback: cleanup check raised', encoding='utf-8')
    outcome = read_outcome(folder)
    assert outcome.reasons == (Reason.WORKER_FAILURE,)
    assert outcome.cleanup_passed is False, 'summary.json has always recorded a crashed trial as cleanup failed'
    assert outcome.cleanup_violation is False


def test_recorded_verdict_fields_are_not_inputs(tmp_path):
    # summary.json's passed and cleanup_passed are what the controller recorded from an earlier reading.
    stale = read_outcome(finished_trial(tmp_path / 'stale', summary={'passed': False, 'cleanup_passed': False}))
    assert stale.passed is True
    contradicted = read_outcome(finished_trial(tmp_path / 'contradicted', summary={'task_passed': True},
                                               verification={'passed': False}))
    assert contradicted.reasons == (Reason.TASK,)


def test_every_failed_check_is_named_in_order(tmp_path):
    folder = finished_trial(tmp_path, summary={'exit_code': 1}, conduct={'passed': False, 'problems': ['x']},
                            cleanup={'passed': False, 'cursor_scheme_restored': True})
    (folder / 'crash.txt').write_text('Traceback', encoding='utf-8')
    assert read_outcome(folder).reasons == (Reason.WORKER_FAILURE, Reason.ACTOR_INCOMPLETE, Reason.CONDUCT, Reason.CLEANUP)


# Archived Illustrator summaries lack the common check fields; new ones keep them next to the Illustrator detail.
ILLUSTRATOR_DETAIL = {'scenario': 'illustrator-pen-tool', 'drawing_passed': True, 'infrastructure_failure': None,
                      'safeguard_violations': [], 'problems': [], 'quality': {'foreground_iou': 0.96}}
COMMON_CHECKS = {'isolation_passed': True, 'task_passed': True, 'conduct_passed': True, 'conduct_problems': []}


@pytest.mark.parametrize('shape', [ILLUSTRATOR_DETAIL, {**ILLUSTRATOR_DETAIL, **COMMON_CHECKS}], ids=['archived', 'new'])
def test_both_illustrator_summary_shapes_read_the_same(tmp_path, shape):
    assert read_outcome(finished_trial(tmp_path / 'pass', summary=shape)).passed is True
    failed = read_outcome(finished_trial(tmp_path / 'conduct', summary=shape, conduct={'passed': False, 'problems': ['x']}))
    assert failed.reasons == (Reason.CONDUCT,)


def test_an_infrastructure_failure_explains_its_cleanup_failure(tmp_path):
    failure = {'kind': 'maintainer_export_failure', 'errors': ['renderer failed twice']}
    preserved = read_outcome(finished_trial(tmp_path / 'preserved', infrastructure_failure=failure,
                                            cleanup={'passed': False, 'cursor_scheme_restored': True}))
    assert preserved.reasons == (Reason.INFRASTRUCTURE_FAILURE, Reason.CLEANUP)
    assert preserved.infrastructure_failure == failure
    assert preserved.cleanup_violation is False
    unrestored = read_outcome(finished_trial(tmp_path / 'unrestored', infrastructure_failure=failure,
                                             cleanup={'passed': False, 'error': 'cursor restore raised'}))
    assert unrestored.cleanup_violation is True, 'an unrestored cursor is never explained by the export'
    unexplained = read_outcome(finished_trial(tmp_path / 'unexplained', cleanup={'passed': False, 'cursor_scheme_restored': True}))
    assert unexplained.cleanup_violation is True


def test_unfinished_worker_is_reported(tmp_path):
    folder = finished_trial(tmp_path)
    (folder / 'finished.json').unlink()
    assert read_outcome(folder).finished is False


def test_metrics_row_and_output_image_come_from_the_trial(tmp_path):
    image = tmp_path / 'grading/Cloud9-Recreated.png'
    outcome = read_outcome(finished_trial(tmp_path, summary={**ILLUSTRATOR_DETAIL, 'output_image': str(image)}))
    assert outcome.output_image == image.resolve()
    assert outcome.metric_error is None
    assert outcome.statistics['total_api_tokens'] == 120
    assert outcome.statistics['computer_use_call_count'] == 2
    assert outcome.statistics['computer_use_busy_s'] is None, 'durations were not marked complete'
    assert outcome.statistics['foreground_iou'] == 0.96
    assert read_outcome(finished_trial(tmp_path / 'calculator')).output_image is None


@pytest.mark.parametrize('metrics, error', [(None, 'failed before extracted metrics were recorded'),
                                            ({'tokens': {}}, "'benchmark'")])
def test_missing_or_unusable_metrics_keep_their_reason(tmp_path, metrics, error):
    outcome = read_outcome(finished_trial(tmp_path, metrics=metrics))
    assert outcome.statistics is None and outcome.metric_error == error
    (tmp_path / 'metrics.json').write_text('{interrupted metrics', encoding='utf-8')
    assert read_outcome(tmp_path).metric_error.startswith('Expecting property name')
