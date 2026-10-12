"""Offline aggregation of five attempts per configuration; never launches or retries a trial."""

import argparse
import json
import math
import statistics
import sys
import traceback
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


# Trim by total API tokens only when all five succeed; otherwise average every success without trimming.
def aggregate_configuration(attempts):
    if len(attempts) != 5:
        raise ValueError('exactly five attempts are required for each configuration')
    if len({attempt['id'] for attempt in attempts}) != 5:
        raise ValueError('attempt IDs must be unique')
    if any(type(attempt['passed']) is not bool for attempt in attempts):
        raise ValueError('each attempt needs a reviewed boolean outcome')
    successful = [attempt for attempt in attempts if attempt['passed']]
    result = {'attempts': 5, 'successes': len(successful), 'failures': 5-len(successful),
              'failed_ids': [attempt['id'] for attempt in attempts if not attempt['passed']],
              'trimmed_ids': [], 'retained_ids': [], 'sample_size': 0, 'averages': None, 'missing_metrics': []}
    if not successful:
        result['reason'] = 'no successful attempts'
        return result
    if len(successful) == 5:
        totals = [attempt['statistics'].get('total_api_tokens') for attempt in successful]
        if any(value is None for value in totals):
            result['reason'] = 'cannot trim: a successful attempt has unknown total API tokens'
            return result
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) for value in totals):
            raise ValueError('total API tokens must be finite numbers')
        # Python's stable sort preserves the original trial order for ties, independent of other metrics.
        ordered = sorted(successful, key=lambda attempt: attempt['statistics']['total_api_tokens'])
        result['trimmed_ids'] = [ordered[0]['id'], ordered[-1]['id']]
        successful = ordered[1:-1]
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
    from bench.run import ARMS

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
        if plan['scenario'] != 'illustrator-pen-export' or plan['arm'] not in ARMS:
            raise ValueError('this round must contain the five Illustrator configurations')
        if plan.get('scenario_version') != 'Adobe Illustrator Pen and Export v0.4 (single attempt)' or plan.get('skill_guidance_policy') != 'benchmark-neutral-v1':
            raise ValueError('round requires the neutral single-attempt v0.4 baseline; historical tuned runs are not eligible')
        identity = {key: plan[key] for key in ('model', 'reasoning', 'scenario', 'scenario_version', 'prompt_sha256', 'skill_sha256', 'assets', 'measurement_policy', 'skill_guidance_policy')}
        attempt_record = json.loads((run / 'run-attempt.json').read_text(encoding='utf-8'))
        started_at = datetime.fromisoformat(attempt_record['started_at'])
        if started_at.tzinfo is None:
            raise ValueError('attempt order needs a persisted timezone-aware started_at timestamp')
        if plan['arm'] in identities and identities[plan['arm']] != identity:
            raise ValueError(f'unmatched model/prompt/skill/assets/policy in {plan["arm"]}')
        identities[plan['arm']] = identity
        summary_path = run / 'summary.json'
        summary = json.loads(summary_path.read_text(encoding='utf-8')) if summary_path.is_file() else None
        cleanup = finished.get('cleanup', {})
        violations = list(violations) + ((summary or {}).get('safeguard_violations') or [])
        if cleanup.get('passed') is not True or cleanup.get('cursor_scheme_restored') is not True:
            violations.append('cleanup failed or is unverified')
        violations = list(dict.fromkeys(violations))
        passed = summary is not None and summary.get('passed') is True and not violations
        if passed and (not (run / 'events.jsonl').is_file() or not (run / 'workspace/Cloud9-Recreated.png').is_file()):
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
               'safeguard_violations': violations}
        groups.setdefault(plan['arm'], []).append(row)
        image = run / 'workspace/Cloud9-Recreated.png'
        attempts.append({'run_dir': str(run), 'arm': plan['arm'], 'passed': passed,
                         'output_image': str(image) if image.is_file() else None,
                         'statistics': statistics_row, 'metric_error': metric_error, 'safeguard_violations': violations})
    if set(groups) != set(ARMS):
        raise ValueError('a full round requires all five configurations, with five attempts each')
    if len({identity['prompt_sha256'] for identity in identities.values()}) != 1 or len({json.dumps(identity['assets'], sort_keys=True) for identity in identities.values()}) != 1:
        raise ValueError('unmatched prompts/assets between configurations')
    for attempts_in_group in groups.values():
        if len({attempt['started_at'] for attempt in attempts_in_group}) != len(attempts_in_group):
            raise ValueError('ambiguous persisted trial order')
        attempts_in_group.sort(key=lambda attempt: attempt['started_at'])
    for prefix in ('pi-', 'claude-'):
        if len({(identity['model'], identity['reasoning']) for arm, identity in identities.items() if arm.startswith(prefix)}) != 1:
            raise ValueError('unmatched model/reasoning within a harness comparison')
    if len({identity['measurement_policy'] for identity in identities.values()}) != 1:
        raise ValueError('unmatched measurement policies between configurations')
    return {'policy': 'five-attempts-trim-only-if-all-succeed-v1', 'attempts': attempts,
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
