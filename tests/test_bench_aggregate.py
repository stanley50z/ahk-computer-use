"""Three scheduled trials: average all successes over the same cohort; never trim or replace failures."""

import pytest

from bench.aggregate import aggregate_configuration


def attempt(index, tokens, busy, passed=True, share=50):
    return {'id': str(index), 'passed': passed,
            'statistics': {'total_api_tokens': tokens, 'computer_use_busy_s': busy, 'code_share_percent': share}}


def test_three_successes_include_both_token_extremes_in_every_average():
    rows = [attempt(1, 10, 1, share=10), attempt(2, 100, 10, share=20),
            attempt(3, 1000, 100, share=90)]
    result = aggregate_configuration(rows)
    assert result['retained_ids'] == ['1', '2', '3']
    assert 'trimmed_ids' not in result
    assert result['successes'] == 3 and result['failures'] == 0
    assert result['averages'] == {'total_api_tokens': 370, 'computer_use_busy_s': 37, 'code_share_percent': 40}


@pytest.mark.parametrize('successes', [0, 1, 2])
def test_every_success_counts_and_failures_are_excluded_from_every_mean(successes):
    rows = [attempt(i, (i+1)*10, i+1, passed=i<successes) for i in range(3)]
    result = aggregate_configuration(rows)
    assert result['retained_ids'] == [str(i) for i in range(successes)]
    assert result['failed_ids'] == [str(i) for i in range(successes,3)]
    assert result['sample_size'] == successes
    if successes:
        assert result['averages']['total_api_tokens'] == 5*(successes+1)
    else:
        assert result['averages'] is None


def test_unknown_tokens_do_not_prevent_averaging_other_metrics_over_all_successes():
    rows = [attempt(i, 10, i) for i in range(3)]
    rows[2]['statistics']['code_share_percent'] = None
    result = aggregate_configuration(rows)
    assert result['retained_ids'] == ['0','1','2']
    assert result['averages']['code_share_percent'] is None
    assert result['missing_metrics'] == ['code_share_percent']
    rows[0]['statistics']['total_api_tokens'] = None
    result = aggregate_configuration(rows)
    assert result['averages']['total_api_tokens'] is None
    assert result['averages']['computer_use_busy_s'] == 1
    assert result['retained_ids'] == ['0','1','2']


def test_exactly_three_unique_attempts_are_required():
    rows = [attempt(i, 10, 1) for i in range(5)]
    for count in (2, 4, 5):
        with pytest.raises(ValueError, match='three'):
            aggregate_configuration(rows[:count])
    with pytest.raises(ValueError, match='unique'):
        aggregate_configuration([rows[0]]*3)


def test_cli_reads_three_attempts_per_arm_and_keeps_safeguard_failures_out(tmp_path):
    import hashlib
    import json
    import subprocess
    import sys
    from bench.run import ARMS, ROOT, PI_RECOVERY_POLICY

    entries = []
    template = 'Workspace: <WORKSPACE>\nScratch folder: <WORKSPACE>/scratch\nLeave the drawing open.\n'
    for arm in ARMS:
        for index in range(3):
            folder = tmp_path / arm / str(index)
            folder.mkdir(parents=True)
            workspace = folder / 'workspace'
            prompt = template.replace('<WORKSPACE>', workspace.as_posix())
            (folder/'prompt-template.txt').write_text(template, encoding='utf-8')
            (folder/'prompt.txt').write_text(prompt, encoding='utf-8')
            plan = {'arm':arm,'model':'gpt-6-astra' if arm.startswith('pi-') else 'claude-opus-5-5','reasoning':'low','scenario':'illustrator-pen-export',
                    'workspace':str(workspace), 'prompt_sha256':hashlib.sha256(prompt.encode('utf-8')).hexdigest(),
                    'prompt_template_sha256':hashlib.sha256(template.encode('utf-8')).hexdigest(), 'skill_sha256':'skill-' + arm,
                    'assets':{'reference':'fixed'},'measurement_policy':'tokens-and-computer-use-v1',
                    'scenario_version':'Adobe Illustrator Pen and Export v0.8',
                    'actor_deliverables':[],
                    'export_policy':{'owner':'maintainer-cleanup','attempts':2,'output':'grading/Cloud9-Recreated.png',
                                     'dimensions':[800,800],'background':'opaque-white','dpi':72,'interlaced':False,
                                     'failure_classification':'infrastructure'},
                    'recovery_policy':PI_RECOVERY_POLICY if arm.startswith('pi-') else
                                      {'retry':'harness-default','compaction':'harness-default'},
                    'skill_guidance_policy':'benchmark-neutral-v1',
                    'trial_policy':{'attempts_per_configuration':3,'aggregation':'all-successes','replace_failed_attempts':False}}
            (folder/'plan.json').write_text(json.dumps(plan),encoding='utf-8')
            (folder/'run-attempt.json').write_text(json.dumps({'started_at':f'2026-10-12T10:00:0{index}+00:00'}),encoding='utf-8')
            (folder/'finished.json').write_text(json.dumps({'worker_finished':True,
                'cleanup':{'passed':True,'cursor_scheme_restored':True}}),encoding='utf-8')
            (folder/'grading').mkdir()
            output = folder/'grading/Cloud9-Recreated.png'
            recovered = arm=='pi-computer-use' and index==2
            (folder/'summary.json').write_text(json.dumps({'passed':True,'quality':{'foreground_iou':.9},
                'output_image':str(output), 'drawing_passed':True, 'infrastructure_failure':None, 'safeguard_violations':[],
                'recovered_provider_errors':['503 recovered'] if recovered else []}),encoding='utf-8')
            (folder/'metrics.json').write_text(json.dumps({'benchmark':{'token_counts_complete':not recovered,
                'api_tokens':{'total':100 if arm=='claude-cua' else (index+1)*10,'output_including_reasoning':5},
                'code_tokens':{'estimated_tokens':2,'output_share_percent_estimate':40,'review_required':False},
                'computer_use':{'call_count':1,'busy_seconds':index+1,'sum_call_seconds':index+1,
                                'attribution_complete':True,'durations_complete':True}}}),encoding='utf-8')
            (folder/'events.jsonl').write_text('{}\n',encoding='utf-8')
            (folder/'workspace').mkdir()
            output.write_bytes(b'fixture; independently checked by the collector')
            entries.append({'run_dir':str(folder.relative_to(tmp_path)), 'safeguard_violations':
                            ['Pen tool not used'] if arm=='pi-acu' and index==0 else []})
    (tmp_path/'pi-acu/0/metrics.json').write_text('{interrupted metrics', encoding='utf-8')
    interrupted = tmp_path/'pi-cua/0'
    (interrupted/'summary.json').unlink()
    (interrupted/'metrics.json').unlink()
    (interrupted/'failure.json').write_text(json.dumps({'kind':'unexpected_provider_failure',
        'errors':['503 subscription_sharing_user_unavailable']}), encoding='utf-8')
    export_failed = tmp_path/'claude-cua/0'
    infrastructure = {'kind':'maintainer_export_failure','errors':['renderer failed twice']}
    summary = json.loads((export_failed/'summary.json').read_text(encoding='utf-8'))
    summary.update(passed=False, drawing_passed=True, output_image=None, infrastructure_failure=infrastructure)
    (export_failed/'summary.json').write_text(json.dumps(summary),encoding='utf-8')
    (export_failed/'infrastructure-failure.json').write_text(json.dumps(infrastructure),encoding='utf-8')
    (export_failed/'finished.json').write_text(json.dumps({'worker_finished':True,
        'cleanup':{'passed':False,'cursor_scheme_restored':True,'infrastructure_failure':infrastructure}}),encoding='utf-8')
    manifest = tmp_path/'round.json'
    manifest.write_text(json.dumps({'attempts':entries}),encoding='utf-8')
    result = subprocess.run([sys.executable,str(ROOT/'bench/aggregate.py'),str(manifest)],
                            capture_output=True,text=True,encoding='utf-8',timeout=20)
    assert result.returncode==0,result.stderr
    groups=json.loads(result.stdout)['configurations']
    assert json.loads(result.stdout)['policy']=='three-attempts-all-successes-v1'
    assert groups['pi-acu']['sample_size']==2
    assert groups['pi-acu']['averages']['total_api_tokens']==25
    assert json.loads(result.stdout)['attempts'][0]['metric_error'], 'failed attempts may lack usable metrics without blocking the successful cohort'
    assert groups['pi-cua']['successes']==2
    assert groups['pi-cua']['unexpected_failure_ids']==[str(interrupted)]
    provider_row = next(row for row in json.loads(result.stdout)['attempts'] if row['run_dir']==str(interrupted))
    assert provider_row['unexpected_failure']['kind']=='unexpected_provider_failure'
    assert groups['pi-computer-use']['sample_size']==3, 'a recovered interruption does not exclude a successful export'
    assert groups['pi-computer-use']['averages']['total_api_tokens'] is None, 'missing usage withholds the whole cohort metric'
    assert groups['pi-computer-use']['averages']['computer_use_busy_s']==2
    assert json.loads(result.stdout)['attempts'][8]['recovered_provider_errors']==['503 recovered']
    assert groups['claude-acu']['sample_size']==3
    assert groups['claude-acu']['averages']['total_api_tokens']==20
    assert groups['claude-cua']['sample_size']==2, 'an infrastructure failure does not enter drawing comparison averages'
    assert groups['claude-cua']['infrastructure_failure_ids']==[str(export_failed)]
    infra_row = next(row for row in json.loads(result.stdout)['attempts'] if row['run_dir']==str(export_failed))
    assert infra_row['infrastructure_failure']==infrastructure and infra_row['safeguard_violations']==[]
    from pathlib import Path
    retained_image = next(row for row in json.loads(result.stdout)['attempts'] if row['arm']=='claude-cua' and row['passed'])['output_image']
    assert Path(retained_image) == tmp_path/'claude-cua/1/grading/Cloud9-Recreated.png'
    manifest.write_text(json.dumps({'attempts':entries[::-1]}),encoding='utf-8')
    reordered=subprocess.run([sys.executable,str(ROOT/'bench/aggregate.py'),str(manifest)],
                             capture_output=True,text=True,encoding='utf-8',timeout=20)
    assert reordered.returncode==0,reordered.stderr
    assert json.loads(reordered.stdout)['configurations']['claude-cua']['retained_ids'] == groups['claude-cua']['retained_ids']
    # Only the canonical maintainer output inside this run is valid evidence.
    summary_path = tmp_path/'claude-cua/2/summary.json'
    summary = json.loads(summary_path.read_text(encoding='utf-8'))
    recorded_output = summary['output_image']
    summary['output_image'] = str(tmp_path/'outside/Cloud9-Recreated-Drawing.png')
    summary_path.write_text(json.dumps(summary), encoding='utf-8')
    outside=subprocess.run([sys.executable,str(ROOT/'bench/aggregate.py'),str(manifest)],
                           capture_output=True,text=True,encoding='utf-8',timeout=20)
    assert outside.returncode!=0 and 'maintainer output' in outside.stderr
    summary['output_image'] = recorded_output
    summary_path.write_text(json.dumps(summary), encoding='utf-8')
    # Mixing prompt/model/skill revisions cannot produce a supposedly matched aggregate.
    plan_path=tmp_path/'claude-acu/2/plan.json'
    plan=json.loads(plan_path.read_text(encoding='utf-8'))
    plan['trial_policy']['attempts_per_configuration']=5
    plan_path.write_text(json.dumps(plan),encoding='utf-8')
    stale=subprocess.run([sys.executable,str(ROOT/'bench/aggregate.py'),str(manifest)],
                         capture_output=True,text=True,encoding='utf-8',timeout=20)
    assert stale.returncode!=0 and 'three-attempt' in stale.stderr
    plan['trial_policy']['attempts_per_configuration']=3
    original_recovery=plan['recovery_policy']
    plan['recovery_policy']={'retry':{'enabled':False},'compaction':{'enabled':False}}
    plan_path.write_text(json.dumps(plan),encoding='utf-8')
    disabled=subprocess.run([sys.executable,str(ROOT/'bench/aggregate.py'),str(manifest)],
                            capture_output=True,text=True,encoding='utf-8',timeout=20)
    assert disabled.returncode!=0 and 'recovery' in disabled.stderr
    plan['recovery_policy']=original_recovery
    plan['prompt_template_sha256']='other'
    plan_path.write_text(json.dumps(plan),encoding='utf-8')
    mixed=subprocess.run([sys.executable,str(ROOT/'bench/aggregate.py'),str(manifest)],
                         capture_output=True,text=True,encoding='utf-8',timeout=20)
    assert mixed.returncode!=0 and 'matched' in mixed.stderr
    plan['prompt_template_sha256']=hashlib.sha256(template.encode('utf-8')).hexdigest()
    # Even a correctly hashed rendered prompt must be the exact expansion of the frozen common template.
    changed_prompt = (tmp_path/'claude-acu/2/prompt.txt').read_text(encoding='utf-8') + 'Different instruction\n'
    (tmp_path/'claude-acu/2/prompt.txt').write_text(changed_prompt, encoding='utf-8')
    plan['prompt_sha256']=hashlib.sha256(changed_prompt.encode('utf-8')).hexdigest()
    plan_path.write_text(json.dumps(plan), encoding='utf-8')
    changed=subprocess.run([sys.executable,str(ROOT/'bench/aggregate.py'),str(manifest)],
                           capture_output=True,text=True,encoding='utf-8',timeout=20)
    assert changed.returncode!=0 and 'template' in changed.stderr
    plan['scenario_version']='Adobe Illustrator Pen and Export v0.6'
    for index in range(3):
        (tmp_path/f'claude-acu/{index}/plan.json').write_text(json.dumps(plan),encoding='utf-8')
    historical=subprocess.run([sys.executable,str(ROOT/'bench/aggregate.py'),str(manifest)],
                              capture_output=True,text=True,encoding='utf-8',timeout=20)
    assert historical.returncode!=0 and 'historical protocols' in historical.stderr
