"""Trial contracts through scenario, actor capture and observer boundaries; no desktop work."""
import json
from pathlib import Path
import sys
import tempfile

import pytest

from bench import run


# Give real measurement/audit code a small, complete Pi session in an isolated fake home.
def trial_plan(tmp_path, monkeypatch, scenario='calculator'):
    home, shared, directory = [tmp_path / name for name in ('home', 'temp', 'trial')]
    for path in (home / '.pi/agent', shared, directory / 'workspace', directory / 'agent-home'):
        path.mkdir(parents=True)
    (home / '.pi/agent/auth.json').write_text('{}', encoding='utf-8')
    monkeypatch.setattr(Path, 'home', classmethod(lambda cls: home))
    monkeypatch.setattr(tempfile, 'gettempdir', lambda: str(shared))
    return {'run_dir': str(directory), 'workspace': str(directory / 'workspace'), 'arm': 'pi-acu',
            'scenario': scenario, 'provider': run.PI_PROVIDER, 'environment_overrides': {},
            'command': [sys.executable, '-c', 'pass'], 'skill_names': ['acu'],
            'skill_path': str(directory / 'workspace/acu/SKILL.md'), 'model': 'test', 'reasoning': 'low'}


# This capture writes the same evidence files as the real actor boundary, without launching a harness.
def actor_capture(command, cwd, environment, directory):
    entries = [
        {'type': 'model_change', 'provider': 'openai-codex', 'modelId': 'test'},
        {'type': 'thinking_level_change', 'thinkingLevel': 'low'},
        {'type': 'message', 'message': {'role': 'system', 'sections': {'skills': '<name>acu</name>'},
                                     'toolsAdded': [{'name': name} for name in ('read', 'bash', 'edit', 'write')]}},
    ]
    (directory / 'session.jsonl').write_text('\n'.join(map(json.dumps, entries)), encoding='utf-8')
    run.save_json(directory / 'capture.json', {'passed': True})
    return [
        {'elapsed_s': 0, 'event': {'type': 'agent_start'}},
        {'elapsed_s': 0.1, 'event': {'type': 'message_start', 'message': {'role': 'assistant'}}},
        {'elapsed_s': 1, 'event': {'type': 'message_end', 'message': {
            'role': 'assistant', 'content': [], 'stopReason': 'stop',
            'usage': {'input': 10, 'output': 2, 'cacheRead': 0, 'cacheWrite': 0, 'totalTokens': 12}}}},
        {'elapsed_s': 1, 'event': {'type': 'agent_settled', 'aborted': False}},
    ], 1.0, 0


# A new scenario participates without any orchestrator edits or patches.
def fake_scenario(events):
    from bench.scenario import Scenario

    class FakeScenario(Scenario):
        application = 'fake'

        def approved_apps(self):
            return []

        def prepare_desktop(self, trial):
            events.append('prepare')

        def collect_and_grade(self, trial, tools):
            events.append('collect')
            assert (trial.run_dir / 'conduct.json').is_file()
            return {'passed': True}

        def cleanup(self, trial):
            events.append('cleanup')
            return {'passed': True}

    return FakeScenario()


def test_new_scenario_uses_the_shared_trial_lifecycle(tmp_path, monkeypatch):
    plan = trial_plan(tmp_path, monkeypatch, scenario='new-scenario')
    events = []

    def observer(directory, script, *args, **kwargs):
        events.append(Path(script).stem + kwargs.get('suffix', ''))
        return ''

    def capture(*args):
        events.append('actor')
        return actor_capture(*args)

    summary = run.run_trial(plan, scenario=fake_scenario(events), capture_actor=capture, observer=observer)
    assert summary['passed'] is True
    assert events == ['probe-before', 'prepare', 'probe-before-actor', 'actor', 'probe-conduct',
                      'collect', 'cleanup', 'restore_cursor']
    directory = Path(plan['run_dir'])
    assert run.load_actor_json(directory / 'verification.json') == {'passed': True}
    assert run.load_actor_json(directory / 'cleanup.json') == {
        'passed': True, 'cursor_scheme_restored': True,
        'cursor_verification': 'Saved Windows scheme reloaded and OS showing flag checked; not pixel-level proof.'}
    assert not (directory / 'agent-home/auth.json').exists()


@pytest.mark.parametrize('name', ['calculator', 'illustrator-pen-tool', 'tb3.1', 'tb3.2', 'tb3.3', 'tb3.4'])
def test_registered_scenarios_preserve_summary_cleanup_and_collection_order(tmp_path, monkeypatch, name):
    from bench import illustrator_pen_tool as illustrator, tb3

    plan = trial_plan(tmp_path, monkeypatch, name)
    directory = Path(plan['run_dir'])
    events = []
    drawing = {'passed': True, 'problems': []}
    collection = {'passed': True, 'closed_documents': [], 'preserved_documents': [],
                  'application_closed': False, 'drawing_verification': drawing,
                  'export': {'output': 'grading/Cloud9-Recreated.png', 'quality': {'foreground_iou': 0.75}},
                  'infrastructure_failure': None}

    def prepare_illustrator(plan, observer):
        events.append('prepare')
        run.save_json(directory / 'illustrator-before.json', [])
        run.save_json(directory / 'illustrator-identity.json', {})

    def snapshot(*args):
        events.append('document-audit')
        assert not (directory / 'conduct.json').exists()
        return {'documents': []}

    def collect_illustrator(*args, **kwargs):
        assert kwargs == {'export_drawing': True}
        assert (directory / 'conduct.json').is_file()
        assert not (directory / 'verification.json').exists()
        events.append('collect')
        return collection

    def start_recorder(*args):
        events.append('record-start')
        return 'recorder'

    def stop_recorder(directory, recorder):
        assert recorder == 'recorder'
        events.append('record-stop')

    def collect_office(*args):
        assert (directory / 'conduct.json').is_file()
        assert not (directory / 'verification.json').exists()
        events.append('collect')

    def cleanup_office(*args):
        events.append('cleanup')
        return {'passed': True, 'note': 'Office was not launched'}

    monkeypatch.setattr(illustrator, 'prepare_desktop', prepare_illustrator)
    monkeypatch.setattr(illustrator, 'native_observer', snapshot)
    monkeypatch.setattr(illustrator, 'cleanup_desktop', collect_illustrator)
    monkeypatch.setattr(tb3, 'prepare_desktop', lambda *args: events.append('prepare'))
    monkeypatch.setattr(tb3, 'start_recorder', start_recorder)
    monkeypatch.setattr(tb3, 'stop_recorder', stop_recorder)
    monkeypatch.setattr(tb3, 'collect', collect_office)
    monkeypatch.setattr(tb3, 'cleanup', cleanup_office)
    if name.startswith('tb3.'):
        plan['tb3'] = dict(tb3.TASKS[name])

    def observer(directory, script, *args, **kwargs):
        phase = Path(script).stem + kwargs.get('suffix', '')
        events.append(phase)
        if phase == 'probe-conduct':
            assert (directory / 'verification.json').exists() is (name == 'calculator')
        return ''

    def capture(*args):
        events.append('actor')
        return actor_capture(*args)

    summary = run.run(plan, capture_actor=capture, observer=observer)
    assert run.load_actor_json(directory / 'summary.json') == summary
    cleanup = run.load_actor_json(directory / 'cleanup.json')
    assert run.load_actor_json(directory / 'finished.json')['cleanup'] == cleanup
    core = {'arm', 'model', 'reasoning', 'exit_code', 'benchmark', 'diagnostics', 'passed',
            'unexpected_failure', 'recovered_provider_errors', 'metrics', 'evidence_dir'}
    conventional = {'isolation_passed', 'task_passed', 'conduct_passed', 'conduct_problems', 'cleanup_passed'}
    assert summary['diagnostics'] == {'wall_s': 1.0, 'note': 'Not a benchmark ranking metric.'}
    assert summary['unexpected_failure'] is None
    assert summary['recovered_provider_errors'] == []
    assert (summary['arm'], summary['model'], summary['reasoning'], summary['exit_code']) == ('pi-acu', 'test', 'low', 0)
    assert summary['evidence_dir'] == str(directory)
    if name == 'calculator':
        assert set(summary) == core | conventional
        assert summary['passed'] is False and summary['task_passed'] is False
        assert summary['isolation_passed'] and summary['conduct_passed'] and summary['cleanup_passed']
        assert run.load_actor_json(directory / 'verification.json') == {'passed': False, 'reason': 'agent did not write result.json'}
        assert cleanup == {'passed': True, 'remaining_new_calculator_windows': [], 'cursor_scheme_restored': True,
                           'cursor_verification': 'Saved Windows scheme reloaded and OS showing flag checked; not a pixel-level visibility proof.'}
        assert events == ['probe-before', 'actor', 'probe-conduct', 'probe-cleanup-bind', 'probe-after', 'restore_cursor']
    elif name == 'illustrator-pen-tool':
        assert set(summary) == core | {'scenario', 'output_image', 'quality', 'problems', 'drawing_passed',
                                      'infrastructure_failure', 'safeguard_violations'}
        assert summary['passed'] is True and summary['drawing_passed'] is True
        assert summary['scenario'] == name
        assert summary['output_image'] == 'grading/Cloud9-Recreated.png'
        assert summary['quality'] == {'foreground_iou': 0.75}
        assert summary['problems'] == summary['safeguard_violations'] == []
        assert summary['infrastructure_failure'] is None
        assert run.load_actor_json(directory / 'verification.json') == drawing
        assert cleanup == {**collection, 'cursor_scheme_restored': True,
                           'cursor_verification': 'Saved Windows scheme reloaded and OS showing flag checked; not pixel-level proof.'}
        assert events == ['probe-before', 'prepare', 'probe-before-actor', 'actor', 'probe-conduct',
                          'document-audit', 'collect', 'restore_cursor']
    else:
        assert set(summary) == core | conventional | {'scenario', 'gui360_id', 'file_check', 'input_check',
                                                       'office_com_used', 'tool_calls'}
        assert summary['passed'] is False and summary['task_passed'] is False
        assert summary['isolation_passed'] and summary['conduct_passed'] and summary['cleanup_passed']
        assert summary['scenario'] == name
        assert summary['gui360_id'] == {'tb3.1': 'excel_4s_13432', 'tb3.2': 'word_4s_1023', 'tb3.3': None, 'tb3.4': None}[name]
        check = {'passed': False, 'sub_scores': {}, 'error': 'no saved document to check'}
        assert summary['file_check'] == check
        input_check = None if name == 'tb3.1' else {'passed': False, 'required': plan['tb3']['required_input'], 'error': 'no input log'}
        assert summary['input_check'] == input_check
        assert summary['office_com_used'] is False and summary['tool_calls'] == 0
        assert run.load_actor_json(directory / 'verification.json') == {
            'passed': False, 'file_check': check, 'input_check': input_check, 'tool_calls': 0,
            'office_com_used': False, 'office_com_evidence': []}
        assert cleanup == {'passed': True, 'note': 'Office was not launched', 'collected': True,
                           'cursor_scheme_restored': True,
                           'cursor_verification': 'Saved Windows scheme reloaded and OS showing flag checked; not pixel-level proof.'}
        assert events == ['probe-before', 'prepare', 'probe-before-actor', 'record-start', 'actor', 'record-stop',
                          'probe-conduct', 'collect', 'cleanup', 'restore_cursor']


@pytest.mark.parametrize('name', ['illustrator-pen-tool', 'tb3.1'])
@pytest.mark.parametrize('failure_at', ['prepare', 'actor', 'collect', 'cleanup'])
def test_failure_cleans_up_and_restores_cursor_without_repeating_collection(tmp_path, monkeypatch, name, failure_at):
    from bench import illustrator_pen_tool as illustrator, tb3

    plan = trial_plan(tmp_path, monkeypatch, name)
    plan['tb3'] = dict(tb3.TASKS['tb3.1'])
    directory = Path(plan['run_dir'])
    events = []

    def step(name):
        events.append(name)
        if name == failure_at:
            raise RuntimeError(f'{name} failed')

    def prepare(plan, observer):
        run.save_json(directory / 'illustrator-before.json', [])
        run.save_json(directory / 'illustrator-identity.json', {})
        step('prepare')

    def illustrator_collection(*args, **kwargs):
        # Illustrator collects and cleans in the same operation. A refusal must never invoke it twice.
        step('collect' if failure_at == 'collect' else 'cleanup')
        return {'passed': True}

    def collect(*args):
        assert (directory / 'conduct.json').is_file()
        step('collect')

    def cleanup(*args):
        step('cleanup')
        return {'passed': True, 'note': 'Office was not launched'}

    monkeypatch.setattr(illustrator, 'prepare_desktop', prepare)
    monkeypatch.setattr(illustrator, 'native_observer', lambda *args: {'documents': []})
    monkeypatch.setattr(illustrator, 'cleanup_desktop', illustrator_collection)
    monkeypatch.setattr(tb3, 'prepare_desktop', prepare)
    monkeypatch.setattr(tb3, 'start_recorder', lambda *args: events.append('record-start') or 'recorder')
    monkeypatch.setattr(tb3, 'stop_recorder', lambda *args: events.append('record-stop'))
    monkeypatch.setattr(tb3, 'collect', collect)
    monkeypatch.setattr(tb3, 'cleanup', cleanup)

    def capture(*args):
        step('actor')
        return actor_capture(*args)

    def observer(directory, script, *args, **kwargs):
        events.append(Path(script).stem + kwargs.get('suffix', ''))
        return ''

    with pytest.raises(RuntimeError, match=f'{failure_at} failed'):
        run.run(plan, capture_actor=capture, observer=observer)
    assert events[-1] == 'restore_cursor'
    assert not (directory / 'agent-home/auth.json').exists()
    assert f'{failure_at} failed' in (directory / 'crash.txt').read_text(encoding='utf-8')
    cleanup_result = run.load_actor_json(directory / 'cleanup.json')
    assert run.load_actor_json(directory / 'finished.json')['cleanup'] == cleanup_result
    if name == 'illustrator-pen-tool':
        assert events.count('collect') + events.count('cleanup') == 1
        if failure_at in ('collect', 'cleanup'):
            assert cleanup_result['passed'] is False
            assert cleanup_result['cursor_scheme_restored'] is True
            assert cleanup_result['note'] == 'Collection was already attempted and refused; not repeating export or close'
            assert cleanup_result['infrastructure_failure'] == run.load_actor_json(directory / 'infrastructure-failure.json')
            assert cleanup_result['infrastructure_failure']['kind'] == 'maintainer_collection_failure'
            assert f'{failure_at} failed' in cleanup_result['error']
    else:
        assert events.count('cleanup') == 1
        if failure_at == 'cleanup':
            assert set(cleanup_result) == {'passed', 'error'}
            assert cleanup_result['passed'] is False and 'cleanup failed' in cleanup_result['error']
        else:
            assert cleanup_result == {'passed': True, 'note': 'Office was not launched',
                                      'collected': failure_at == 'collect', 'cursor_scheme_restored': True,
                                      'cursor_verification': 'Saved Windows scheme reloaded and OS showing flag checked; not pixel-level proof.'}
        if failure_at != 'prepare':
            assert events.index('record-start') < events.index('actor') < events.index('record-stop')
            assert events.index('record-stop') < events.index('cleanup')
            if 'collect' in events:
                assert events.index('probe-conduct') < events.index('collect')


def test_export_infrastructure_failure_keeps_drawing_verdict_separate(tmp_path, monkeypatch):
    from bench import illustrator_pen_tool as illustrator

    plan = trial_plan(tmp_path, monkeypatch, 'illustrator-pen-tool')
    directory = Path(plan['run_dir'])
    run.save_json(directory / 'illustrator-before.json', [])
    failure = {'kind': 'maintainer_export_failure', 'errors': ['export refused']}
    monkeypatch.setattr(illustrator, 'prepare_desktop', lambda *args: None)
    monkeypatch.setattr(illustrator, 'native_observer', lambda *args: {'documents': []})
    monkeypatch.setattr(illustrator, 'cleanup_desktop', lambda *args, **kwargs: {
        'passed': False, 'drawing_verification': {'passed': True, 'problems': []},
        'export': {'output': None, 'quality': None}, 'infrastructure_failure': failure})
    summary = run.run(plan, capture_actor=actor_capture, observer=lambda *args, **kwargs: '')
    assert summary['passed'] is False and summary['drawing_passed'] is True
    assert summary['infrastructure_failure'] == failure
    assert summary['safeguard_violations'] == []
    assert run.load_actor_json(directory / 'cleanup.json') == {
        'passed': False, 'drawing_verification': {'passed': True, 'problems': []},
        'export': {'output': None, 'quality': None}, 'infrastructure_failure': failure,
        'cursor_scheme_restored': True,
        'cursor_verification': 'Saved Windows scheme reloaded and OS showing flag checked; not pixel-level proof.'}


def test_calculator_verifies_observed_result_and_closes_only_its_window(tmp_path, monkeypatch):
    plan = trial_plan(tmp_path, monkeypatch)
    directory = Path(plan['run_dir'])
    events = []
    claim = {'status': 'completed', 'result': '4676.04588620271'}

    def capture(*args):
        run.save_json(directory / 'workspace/result.json', claim)
        return actor_capture(*args)

    def observer(directory, script, *args, **kwargs):
        phase = Path(script).stem + kwargs.get('suffix', '')
        events.append(phase)
        if phase in ('probe-bind', 'probe-cleanup-bind', 'probe-conduct'):
            return 'window=100 pid=9\ncalculator=100\npid=9\n'
        if phase == 'verify':
            assert args == ('100',)
            return 'result=4,676.04588620271\nexpression=98765 × 432 ÷ 1234 × 56 ÷ 789 + 6543 − 4321\n'
        if phase == 'cleanup':
            assert args == ('100', 9)
        return ''

    summary = run.run(plan, capture_actor=capture, observer=observer)
    assert summary['passed'] is True
    assert run.load_actor_json(directory / 'verification.json') == {
        'passed': True, 'hwnd': '100', 'observed_result': '4,676.04588620271',
        'observed_expression': '98765 × 432 ÷ 1234 × 56 ÷ 789 + 6543 − 4321',
        'expected': '4676.045886202710280949769213229720652488',
        'screenshot': str(directory / 'calculator-result.png'), 'claim': claim,
        'script_audit': {'input_methods_by_script': {}, 'note': 'Static screening of workspace scripts for the report; the scenario names no input route. Not a security boundary.'}}
    assert events == ['probe-before', 'probe-bind', 'verify', 'screenshot', 'probe-conduct',
                      'probe-cleanup-bind', 'cleanup', 'probe-after', 'restore_cursor']


def test_registering_one_adapter_enables_prepare_and_run(tmp_path, monkeypatch):
    from bench.scenarios import SCENARIOS

    events = []
    adapter = type(fake_scenario(events))

    class RegisteredScenario(adapter):
        def prepare_files(self, plan):
            events.append('files')
            Path(plan['workspace'], 'input.txt').write_text('fixture input', encoding='utf-8')

    monkeypatch.setitem(SCENARIOS, 'new-scenario', RegisteredScenario)
    checkout = tmp_path / 'checkout'
    prompts = checkout / 'bench/scenarios'
    prompts.mkdir(parents=True)
    (prompts / 'new-scenario.md').write_text('# New scenario v1\nUse <WORKSPACE>/input.txt.\n', encoding='utf-8')
    monkeypatch.setattr(run, 'ROOT', checkout)
    # Reuse isolated credentials; preparation must create its own fresh trial directory.
    fixture = trial_plan(tmp_path, monkeypatch)
    skill = Path(fixture['workspace']) / 'acu'
    skill.mkdir()
    (skill / 'SKILL.md').write_text('fixture skill', encoding='utf-8')
    plan = run.prepare('pi-acu', tmp_path / 'registered', scenario='new-scenario', skill=skill)
    plan['model'] = 'test'
    plan['command'] = [sys.executable, '-c', 'pass']
    assert Path(plan['workspace'], 'input.txt').read_text(encoding='utf-8') == 'fixture input'
    summary = run.run(plan, capture_actor=actor_capture, observer=lambda *args, **kwargs: '')
    assert summary['passed'] is True
    assert events == ['files', 'prepare', 'collect', 'cleanup']
