"""Five-attempt aggregation: one retained cohort for every metric; failures are never replacement trials."""

import pytest

from bench.aggregate import aggregate_configuration


def attempt(index, tokens, busy, passed=True, share=50):
    return {'id': str(index), 'passed': passed,
            'statistics': {'total_api_tokens': tokens, 'computer_use_busy_s': busy, 'code_share_percent': share}}


def test_five_successes_trim_only_by_tokens_and_average_the_same_three():
    rows = [attempt(1, 50, 2, share=1), attempt(2, 10, 1, share=99),
            attempt(3, 40, 1000, share=90), attempt(4, 20, 100, share=10), attempt(5, 30, 10, share=20)]
    result = aggregate_configuration(rows)
    assert result['retained_ids'] == ['4', '5', '3']
    assert result['trimmed_ids'] == ['2', '1']
    assert result['successes'] == 5 and result['failures'] == 0
    assert result['averages'] == {'total_api_tokens': 30, 'computer_use_busy_s': 370, 'code_share_percent': 40}


@pytest.mark.parametrize('successes', [0, 1, 2, 3, 4])
def test_any_failure_disables_trimming_and_is_excluded_from_every_mean(successes):
    rows = [attempt(i, (i+1)*10, i+1, passed=i<successes) for i in range(5)]
    result = aggregate_configuration(rows)
    assert result['retained_ids'] == [str(i) for i in range(successes)]
    assert result['trimmed_ids'] == []
    assert result['failed_ids'] == [str(i) for i in range(successes,5)]
    assert result['sample_size'] == successes
    if successes:
        assert result['averages']['total_api_tokens'] == 5*(successes+1)
    else:
        assert result['averages'] is None


def test_ties_follow_original_trial_order_and_unknown_metrics_are_not_zero():
    rows = [attempt(i, 10, i) for i in range(5)]
    rows[2]['statistics']['code_share_percent'] = None
    result = aggregate_configuration(rows)
    assert result['trimmed_ids'] == ['0','4']
    assert result['retained_ids'] == ['1','2','3']
    assert result['averages']['code_share_percent'] is None
    assert result['missing_metrics'] == ['code_share_percent']
    rows[0]['statistics']['total_api_tokens'] = None
    assert aggregate_configuration(rows)['averages'] is None, 'cannot trim five successes without a complete sorting key'


def test_exactly_five_unique_attempts_are_required():
    rows = [attempt(i, 10, 1) for i in range(5)]
    with pytest.raises(ValueError, match='five'):
        aggregate_configuration(rows[:4])
    with pytest.raises(ValueError, match='unique'):
        aggregate_configuration([rows[0]]*5)


def test_cli_reads_five_attempts_per_arm_and_keeps_safeguard_failures_out(tmp_path):
    import json
    import subprocess
    import sys
    from bench.run import ARMS, ROOT

    entries = []
    for arm in ARMS:
        for index in range(5):
            folder = tmp_path / arm / str(index)
            folder.mkdir(parents=True)
            plan = {'arm':arm,'model':'gpt-6-astra' if arm.startswith('pi-') else 'claude-opus-5-5','reasoning':'low','scenario':'illustrator-pen-export',
                    'prompt_sha256':'single-pass','skill_sha256':'skill-' + arm,
                    'assets':{'reference':'fixed'},'measurement_policy':'tokens-and-computer-use-v1',
                    'scenario_version':'Adobe Illustrator Pen and Export v0.4 (single attempt)',
                    'skill_guidance_policy':'benchmark-neutral-v1'}
            (folder/'plan.json').write_text(json.dumps(plan),encoding='utf-8')
            (folder/'run-attempt.json').write_text(json.dumps({'started_at':f'2026-10-12T10:00:0{index}+00:00'}),encoding='utf-8')
            (folder/'finished.json').write_text(json.dumps({'worker_finished':True,
                'cleanup':{'passed':True,'cursor_scheme_restored':True}}),encoding='utf-8')
            (folder/'summary.json').write_text(json.dumps({'passed':True,'quality':{'foreground_iou':.9},
                'safeguard_violations':[]}),encoding='utf-8')
            (folder/'metrics.json').write_text(json.dumps({'benchmark':{'token_counts_complete':True,
                'api_tokens':{'total':100 if arm=='claude-cua' else (index+1)*10,'output_including_reasoning':5},
                'code_tokens':{'estimated_tokens':2,'output_share_percent_estimate':40,'review_required':False},
                'computer_use':{'call_count':1,'busy_seconds':index+1,'sum_call_seconds':index+1,
                                'attribution_complete':True,'durations_complete':True}}}),encoding='utf-8')
            (folder/'events.jsonl').write_text('{}\n',encoding='utf-8')
            (folder/'workspace').mkdir()
            (folder/'workspace/Cloud9-Recreated.png').write_bytes(b'fixture; independently checked by the collector')
            entries.append({'run_dir':str(folder.relative_to(tmp_path)), 'safeguard_violations':
                            ['full redraw'] if arm=='pi-acu' and index==0 else []})
    (tmp_path/'pi-acu/0/metrics.json').write_text('{interrupted metrics', encoding='utf-8')
    manifest = tmp_path/'round.json'
    manifest.write_text(json.dumps({'attempts':entries}),encoding='utf-8')
    result = subprocess.run([sys.executable,str(ROOT/'bench/aggregate.py'),str(manifest)],
                            capture_output=True,text=True,encoding='utf-8',timeout=20)
    assert result.returncode==0,result.stderr
    groups=json.loads(result.stdout)['configurations']
    assert groups['pi-acu']['sample_size']==4 and groups['pi-acu']['trimmed_ids']==[]
    assert groups['pi-acu']['averages']['total_api_tokens']==35
    assert json.loads(result.stdout)['attempts'][0]['metric_error'], 'failed attempts may lack usable metrics without blocking the successful cohort'
    assert groups['claude-acu']['sample_size']==3
    assert groups['claude-acu']['averages']['total_api_tokens']==30
    manifest.write_text(json.dumps({'attempts':entries[::-1]}),encoding='utf-8')
    reordered=subprocess.run([sys.executable,str(ROOT/'bench/aggregate.py'),str(manifest)],
                             capture_output=True,text=True,encoding='utf-8',timeout=20)
    assert reordered.returncode==0,reordered.stderr
    assert json.loads(reordered.stdout)['configurations']['claude-cua']['trimmed_ids'] == groups['claude-cua']['trimmed_ids']
    # Mixing prompt/model/skill revisions cannot produce a supposedly matched aggregate.
    plan_path=tmp_path/'claude-acu/4/plan.json'
    plan=json.loads(plan_path.read_text(encoding='utf-8'));plan['prompt_sha256']='other'
    plan_path.write_text(json.dumps(plan),encoding='utf-8')
    mixed=subprocess.run([sys.executable,str(ROOT/'bench/aggregate.py'),str(manifest)],
                         capture_output=True,text=True,encoding='utf-8',timeout=20)
    assert mixed.returncode!=0 and 'matched' in mixed.stderr
    plan['prompt_sha256']='single-pass';plan['scenario_version']='Adobe Illustrator Pen and Export v0.3 (pilot)'
    for index in range(5):
        (tmp_path/f'claude-acu/{index}/plan.json').write_text(json.dumps(plan),encoding='utf-8')
    historical=subprocess.run([sys.executable,str(ROOT/'bench/aggregate.py'),str(manifest)],
                              capture_output=True,text=True,encoding='utf-8',timeout=20)
    assert historical.returncode!=0 and 'historical tuned' in historical.stderr
