"""Offline aggregation of three attempts per configuration; never launches or retries a trial."""

import argparse
import hashlib
import json
import math
import statistics
import sys
import traceback
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bench.common import TRIAL_POLICY, actor_path
from bench.run import WINDOW_AUDIT_POLICY
from bench.arms import ARMS, ARM_TABLE


SCENARIO = 'illustrator-pen-tool'
SCENARIO_VERSION = 'Adobe Illustrator Pen Tool v0.11'
# Rounds recorded before the Pen Tool rename keep their original names; the actor prompt and protocol are unchanged.
LEGACY_NAMES = {'illustrator-pen-export': SCENARIO, 'Adobe Illustrator Pen and Export v0.11': SCENARIO_VERSION}


# Average every successful trial over one shared cohort; no token sorting or trimming.
def aggregate_configuration(attempts):
    count = TRIAL_POLICY['attempts_per_configuration']
    if len(attempts) != count:
        raise ValueError('exactly three attempts are required for each configuration')
    if len({attempt['id'] for attempt in attempts}) != count:
        raise ValueError('attempt IDs must be unique')
    if any(type(attempt['passed']) is not bool for attempt in attempts):
        raise ValueError('each attempt needs a reviewed boolean outcome')
    successful = [attempt for attempt in attempts if attempt['passed']]
    result = {'attempts': count, 'successes': len(successful), 'failures': count-len(successful),
              'failed_ids': [attempt['id'] for attempt in attempts if not attempt['passed']],
              'unexpected_failure_ids': [attempt['id'] for attempt in attempts if not attempt['passed'] and attempt.get('unexpected_failure')],
              'infrastructure_failure_ids': [attempt['id'] for attempt in attempts if attempt.get('infrastructure_failure')],
              'retained_ids': [], 'sample_size': 0, 'averages': None, 'missing_metrics': []}
    if not successful:
        result['reason'] = 'no successful attempts'
        return result
    result['retained_ids'] = [attempt['id'] for attempt in successful]
    result['sample_size'] = len(successful)
    result['averages'] = {}
    for key in sorted({key for attempt in successful for key in attempt['statistics']}):
        values = [attempt['statistics'].get(key) for attempt in successful]
        if any(value is None for value in values):
            result['averages'][key] = None
            result['missing_metrics'].append(key)
        else:
            if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) for value in values):
                raise ValueError(f'{key} must contain finite numbers or explicit unknowns')
            result['averages'][key] = statistics.mean(values)
    return result


# Flatten only comparison metrics; descriptive code share remains an observation, never a success criterion.
def comparison_statistics(benchmark, quality):
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


# Load a maintainer-authored manifest after session review; no JSON is requested from the actor.
def aggregate_round(manifest_path):
    from bench.illustrator_pen_tool import EXPORT_POLICY

    manifest_path = Path(manifest_path).resolve()
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    groups, identities, attempts = {}, {}, []
    seen = set()
    for entry in manifest['attempts']:
        run = (manifest_path.parent / entry['run_dir']).resolve()
        if run in seen:
            raise ValueError('run directories must be unique')
        seen.add(run)
        violations = entry['safeguard_violations']
        if not isinstance(violations, list) or not all(isinstance(item, str) for item in violations):
            raise ValueError('each reviewed attempt needs an explicit safeguard_violations array')
        plan = json.loads((run / 'plan.json').read_text(encoding='utf-8'))
        finished = json.loads((run / 'finished.json').read_text(encoding='utf-8'))
        if finished.get('worker_finished') is not True:
            raise ValueError(f'attempt has not finished: {run}')
        scenario = LEGACY_NAMES.get(plan['scenario'], plan['scenario'])
        version = LEGACY_NAMES.get(plan.get('scenario_version'), plan.get('scenario_version'))
        if scenario != SCENARIO or plan['arm'] not in ARMS:
            raise ValueError('this round must contain the five Illustrator configurations')
        if version != SCENARIO_VERSION or plan.get('skill_guidance_policy') != 'benchmark-neutral-v1':
            raise ValueError('round requires the neutral v0.11 simple drawing-and-appearance baseline; historical protocols are not eligible')
        host = ARM_TABLE[plan['arm']].harness
        host.validate_plan(plan, aggregate=True)
        if plan.get('window_audit_policy') != WINDOW_AUDIT_POLICY:
            raise ValueError('round requires the diagnostic-only window audit policy')
        if plan.get('export_policy') != EXPORT_POLICY or plan.get('actor_deliverables') != []:
            raise ValueError('round requires matched maintainer export policy and no actor file deliverables')
        if plan.get('recovery_policy') != host.recovery_policy:
            raise ValueError('round requires the normal within-session recovery policy')
        if plan.get('trial_policy') != TRIAL_POLICY:
            raise ValueError('round requires the three-attempt all-successes trial policy')
        workspace = Path(plan['workspace']).resolve()
        if workspace != (run / 'workspace').resolve():
            raise ValueError('prepared workspace does not belong to this attempt')
        template = (run / 'prompt-template.txt').read_text(encoding='utf-8')
        prompt = (run / 'prompt.txt').read_text(encoding='utf-8')
        if hashlib.sha256(template.encode('utf-8')).hexdigest() != plan['prompt_template_sha256']:
            raise ValueError('unmatched frozen prompt template fingerprint')
        if (hashlib.sha256(prompt.encode('utf-8')).hexdigest() != plan['prompt_sha256']
                or prompt != template.replace('<WORKSPACE>', actor_path(workspace))):
            raise ValueError('rendered prompt does not match its frozen template and workspace')
        identity = {key: plan[key] for key in ('model', 'reasoning', 'scenario', 'scenario_version', 'prompt_template_sha256', 'skill_sha256', 'assets', 'measurement_policy', 'skill_guidance_policy', 'trial_policy', 'recovery_policy', 'export_policy', 'window_audit_policy')}
        identity.update(scenario=scenario, scenario_version=version, provider=plan.get('provider'))
        attempt_record = json.loads((run / 'run-attempt.json').read_text(encoding='utf-8'))
        started_at = datetime.fromisoformat(attempt_record['started_at'])
        if started_at.tzinfo is None:
            raise ValueError('attempt order needs a persisted timezone-aware started_at timestamp')
        if plan['arm'] in identities and identities[plan['arm']] != identity:
            raise ValueError(f'unmatched model/prompt/skill/assets/policy in {plan["arm"]}')
        identities[plan['arm']] = identity
        summary_path = run / 'summary.json'
        summary = json.loads(summary_path.read_text(encoding='utf-8')) if summary_path.is_file() else None
        failure_path = run / 'failure.json'
        unexpected_failure = json.loads(failure_path.read_text(encoding='utf-8')) if failure_path.is_file() else (summary or {}).get('unexpected_failure')
        cleanup = finished.get('cleanup', {})
        infrastructure_path = run / 'infrastructure-failure.json'
        infrastructure_failure = json.loads(infrastructure_path.read_text(encoding='utf-8')) if infrastructure_path.is_file() else (summary or {}).get('infrastructure_failure')
        violations = list(violations) + ((summary or {}).get('safeguard_violations') or [])
        if (cleanup.get('passed') is not True and not infrastructure_failure) or cleanup.get('cursor_scheme_restored') is not True:
            violations.append('cleanup failed or is unverified')
        violations = list(dict.fromkeys(violations))
        passed = (summary is not None and summary.get('passed') is True and summary.get('drawing_passed') is True
                  and not violations and not unexpected_failure and not infrastructure_failure)
        output = (summary or {}).get('output_image')
        image = Path(output).resolve() if output else None
        if image is not None and image != (run / EXPORT_POLICY['output']).resolve():
            raise ValueError('recorded image must be this run\'s canonical maintainer output')
        if passed and (not (run / 'events.jsonl').is_file() or image is None or not image.is_file()):
            raise ValueError(f'successful attempt is missing session history or its output image: {run}')
        statistics_row, metric_error = None, None
        metrics_path = run / 'metrics.json'
        if metrics_path.is_file():
            try:
                metrics = json.loads(metrics_path.read_text(encoding='utf-8'))
                statistics_row = comparison_statistics(metrics['benchmark'], (summary or {}).get('quality'))
            except (json.JSONDecodeError, OSError, KeyError) as error:
                if passed:
                    raise ValueError(f'successful attempt has unusable extracted metrics: {run}') from error
                metric_error = str(error)  # Failed attempts never enter the averages; retain the data-loss reason.
        elif passed:
            raise ValueError(f'successful attempt is missing extracted metrics: {run}')
        else:
            metric_error = 'failed before extracted metrics were recorded'
        row = {'id': str(run), 'started_at': started_at, 'passed': passed, 'statistics': statistics_row,
               'safeguard_violations': violations, 'unexpected_failure': unexpected_failure,
               'infrastructure_failure': infrastructure_failure}
        groups.setdefault(plan['arm'], []).append(row)
        attempts.append({'run_dir': str(run), 'arm': plan['arm'], 'passed': passed,
                         'output_image': str(image) if image is not None and image.is_file() else None,
                         'statistics': statistics_row, 'metric_error': metric_error, 'safeguard_violations': violations,
                         'unexpected_failure': unexpected_failure, 'infrastructure_failure': infrastructure_failure,
                         'drawing_passed': (summary or {}).get('drawing_passed'),
                         'recovered_provider_errors': (summary or {}).get('recovered_provider_errors', [])})
    if set(groups) != set(ARMS):
        raise ValueError('a full round requires all five configurations, with three attempts each')
    if len({identity['prompt_template_sha256'] for identity in identities.values()}) != 1 or len({json.dumps(identity['assets'], sort_keys=True) for identity in identities.values()}) != 1:
        raise ValueError('unmatched prompts/assets between configurations')
    for attempts_in_group in groups.values():
        if len({attempt['started_at'] for attempt in attempts_in_group}) != len(attempts_in_group):
            raise ValueError('ambiguous persisted trial order')
        attempts_in_group.sort(key=lambda attempt: attempt['started_at'])
    for host in {ARM_TABLE[arm].harness for arm in ARMS}:
        if len({(identity['model'], identity['reasoning']) for arm, identity in identities.items() if ARM_TABLE[arm].harness is host}) != 1:
            raise ValueError('unmatched model/reasoning within a harness comparison')
    if len({identity['measurement_policy'] for identity in identities.values()}) != 1:
        raise ValueError('unmatched measurement policies between configurations')
    return {'policy': 'three-attempts-all-successes-v1', 'attempts': attempts,
            'configurations': {arm: aggregate_configuration(groups[arm]) for arm in ARMS}}


# The offline CLI prints a report without modifying run evidence; failures persist a stack trace beside the manifest.
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(aggregate_round(args.manifest), ensure_ascii=False, indent=2))
    except Exception:
        args.manifest.with_suffix('.aggregate-crash.txt').write_text(traceback.format_exc(), encoding='utf-8')
        raise


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
