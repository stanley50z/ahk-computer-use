"""Bounded runtime-write evidence through the public conduct audit."""
import json
import shlex

import pytest

from bench.run import conduct_audit


def events(harness, path, *, failed=False, command=None, body=None):
    if command is None:
        command = 'cua-driver get_window_state ' + shlex.quote(json.dumps({'screenshot_out_file': path}))
    text = json.dumps({'screenshot_file_path': path}) if body is None else body
    if harness == 'pi':
        values = [
            {'type': 'tool_execution_start', 'toolCallId': 'capture', 'toolName': 'bash', 'args': {'command': command}},
            {'type': 'tool_execution_end', 'toolCallId': 'capture', 'isError': failed,
             'result': {'content': [{'type': 'text', 'text': text}]}},
        ]
    else:
        values = [
            {'type': 'assistant', 'message': {'content': [{'type': 'tool_use', 'id': 'capture', 'name': 'Bash', 'input': {'command': command}}]}},
            {'type': 'user', 'message': {'content': [{'type': 'tool_result', 'tool_use_id': 'capture', 'is_error': failed, 'content': text}]}},
        ]
    return [{'elapsed_s': i, 'event': value} for i, value in enumerate(values)]


def audit(tmp_path, records, before, after):
    return conduct_audit({'workspace': str(tmp_path), 'skill_path': str(tmp_path / 'skill/SKILL.md')},
                         '', '', {}, {}, [], raw_records=records,
                         runtime_before=before, runtime_after=after)


def snapshot(files):
    return {'roots': {'c:/users/test': {'complete': True}}, 'files': files, 'errors': {}}


@pytest.mark.parametrize('harness', ['pi', 'claude'])
def test_runtime_overwrite_uses_matched_absolute_destination_not_relative_request(tmp_path, harness):
    path = 'c:/users/test/cp.png'
    before = snapshot({path: {'device': 1, 'inode': 2, 'size': 8, 'mtime_ns': 100}})
    after = snapshot({path: {'device': 1, 'inode': 2, 'size': 16, 'mtime_ns': 200}})
    records = events(harness, r'\\?\C:\Users\Test\cp.png',
                     command='cd scratch; cua-driver get_window_state \'{"screenshot_out_file":"cp.png"}\'')
    result = audit(tmp_path, records, before, after)
    assert result['problems'] == ['runtime screenshot overwrote pre-existing file']
    assert result['runtime_writes']['outputs'][0]['status'] == 'preexisting_changed'
    assert result['runtime_writes']['outputs'][0]['path'] == path
    assert not result['passed']


@pytest.mark.parametrize('harness', ['pi', 'claude'])
def test_fresh_scratch_allowed_and_unrelated_mutation_is_diagnostic(tmp_path, harness):
    old = {'device': 1, 'inode': 2, 'size': 8, 'mtime_ns': 100}
    new = {'device': 1, 'inode': 3, 'size': 16, 'mtime_ns': 200}
    before = snapshot({'c:/users/test/unrelated.txt': old})
    after = snapshot({'c:/users/test/unrelated.txt': new, 'c:/users/test/fresh.png': new})
    result = audit(tmp_path, events(harness, 'C:/Users/Test/fresh.png'), before, after)
    assert result['passed']
    assert result['runtime_writes']['outputs'][0]['status'] == 'fresh'
    assert result['runtime_writes']['changed_preexisting'] == ['c:/users/test/unrelated.txt']


@pytest.mark.parametrize('harness', ['pi', 'claude'])
@pytest.mark.parametrize('case', ['failed', 'missing', 'truncated', 'outside', 'relative', 'unmatched', 'nested-error'])
def test_incomplete_or_uncovered_runtime_evidence_never_proves_safety_or_blame(tmp_path, harness, case):
    path = 'c:/users/test/cp.png'
    before = snapshot({path: {'device': 1, 'inode': 2, 'size': 8, 'mtime_ns': 100}})
    after = snapshot({path: {'device': 1, 'inode': 2, 'size': 16, 'mtime_ns': 200}})
    records = events(harness, 'D:/outside/cp.png' if case == 'outside' else 'cp.png' if case == 'relative' else path,
                     failed=case == 'failed',
                     body='{"screenshot_file_path": "c:/users/test/cp.png",' if case == 'truncated' else
                     '{"isError":true,"screenshot_file_path":"c:/users/test/cp.png"}' if case == 'nested-error' else None)
    if case == 'missing':
        records = records[:1]
    if case == 'unmatched':
        records = records[1:]
    result = audit(tmp_path, records, before, after)
    assert result['passed']
    assert all(output['status'] == 'unverified' for output in result['runtime_writes']['outputs'])
    assert result['runtime_writes']['evidence_complete'] is False


@pytest.mark.parametrize('capture_crashes', [False, True])
def test_run_trial_persists_bounded_snapshots_and_integrates_conduct(tmp_path, monkeypatch, capture_crashes):
    from pathlib import Path
    import tempfile
    from bench import run

    home, shared, work = [tmp_path / name for name in ('home', 'temp', 'work')]
    for directory in (home, shared, work, tmp_path / 'agent-home'):
        directory.mkdir()
    sentinel = home / 'cp.png'
    sentinel.write_bytes(b'original')
    (home / 'private').mkdir()
    (home / 'private/secret.txt').write_bytes(b'not inventoried')
    (home / 'credential').write_text('test credential', encoding='utf-8')
    monkeypatch.setattr(Path, 'home', classmethod(lambda cls: home))
    monkeypatch.setattr(tempfile, 'gettempdir', lambda: str(shared))
    monkeypatch.setattr(run, 'CREDENTIALS', {'pi': ('credential', 'auth.json')})
    monkeypatch.setattr(run, 'acu_observer', lambda *a, **kw: '')
    monkeypatch.setattr(run, 'cleanup_calculator', lambda *a: None)
    monkeypatch.setattr(run, 'guarded_roots', lambda plan: [])
    monkeypatch.setattr(run, 'executable_command', lambda command: command)
    monkeypatch.setattr(run, 'audit_pi_session', lambda *a, **kw: {'passed': True})
    monkeypatch.setattr(run, 'verify_calculator', lambda *a: {'passed': True})
    monkeypatch.setattr(run, 'analyse_pi', lambda *a, **kw: {'agent_completed': True, 'tools': []})
    monkeypatch.setattr('bench.efficiency.measure_efficiency', lambda *a: {})

    def capture(*args):
        assert (tmp_path / 'runtime-files-before.json').is_file()
        sentinel.write_bytes(b'new screenshot bytes')
        if capture_crashes:
            raise RuntimeError('capture failed')
        run.save_json(tmp_path / 'capture.json', {'passed': True})
        return events('pi', str(sentinel)), 1.0, 0

    monkeypatch.setattr(run, 'capture', capture)
    plan = {'run_dir': str(tmp_path), 'workspace': str(work), 'arm': 'pi-acu',
            'provider': run.PI_PROVIDER, 'environment_overrides': {}, 'command': [],
            'skill_names': ['acu'], 'skill_path': str(work / 'SKILL.md'), 'model': 'test', 'reasoning': 'low'}
    if capture_crashes:
        with pytest.raises(RuntimeError, match='capture failed'):
            run.run_trial(plan)
    else:
        summary = run.run_trial(plan)
        assert not summary['conduct_passed']
        assert summary['conduct_problems'] == ['runtime screenshot overwrote pre-existing file']
        assert json.loads((tmp_path / 'conduct.json').read_text(encoding='utf-8'))['runtime_writes']['outputs'][0]['status'] == 'preexisting_changed'
    before = json.loads((tmp_path / 'runtime-files-before.json').read_text(encoding='utf-8'))
    after = json.loads((tmp_path / 'runtime-files-after.json').read_text(encoding='utf-8'))
    assert len(before['roots']) == 2
    assert not any('secret.txt' in path for path in before['files'])
    assert before['files'] != after['files']
    assert not (tmp_path / 'agent-home/auth.json').exists()


def test_truncated_host_tool_result_does_not_establish_runtime_write(tmp_path):
    path = 'c:/users/test/cp.png'
    before = snapshot({path: {'device': 1, 'inode': 2, 'size': 8, 'mtime_ns': 100}})
    after = snapshot({path: {'device': 1, 'inode': 2, 'size': 16, 'mtime_ns': 200}})
    records = events('pi', path)
    records[-1]['event']['result']['details'] = {'truncation': {'truncated': True}}
    result = audit(tmp_path, records, before, after)
    assert result['passed']
    assert result['runtime_writes']['unverified_calls']


@pytest.mark.parametrize('gap', ['baseline', 'scan', 'stat', 'missing-after'])
def test_snapshot_gaps_cannot_make_a_destination_fresh(tmp_path, gap):
    path = 'c:/users/test/cp.png'
    before = snapshot({})
    after = snapshot({path: {'device': 1, 'inode': 2, 'size': 16, 'mtime_ns': 200}})
    if gap == 'baseline':
        before = None
    elif gap == 'scan':
        before['roots']['c:/users/test']['complete'] = False
    elif gap == 'stat':
        before['errors'][path] = 'access denied'
    else:
        after['files'] = {}
    result = audit(tmp_path, events('claude', path), before, after)
    assert result['passed']
    assert result['runtime_writes']['outputs'][0]['status'] == 'unverified'


@pytest.mark.parametrize('command', ['cat previous-capture.json', 'python helper.py',
    'cua-driver get_window_state \'{"screenshot_out_file":"different.png"}\'; cat previous-capture.json'])
def test_old_capture_json_or_unresolved_helper_cannot_blame_an_unrelated_write(tmp_path, command):
    path = 'c:/users/test/cp.png'
    before = snapshot({path: {'device': 1, 'inode': 2, 'size': 8, 'mtime_ns': 100}})
    after = snapshot({path: {'device': 1, 'inode': 2, 'size': 16, 'mtime_ns': 200}})
    result = audit(tmp_path, events('pi', path, command=command), before, after)
    assert result['passed']
    assert result['runtime_writes']['outputs'][0]['status'] == 'unverified'
    assert result['runtime_writes']['evidence_complete'] is False


def test_unsupported_event_format_does_not_claim_complete_runtime_evidence(tmp_path):
    result = audit(tmp_path, [{'event': {'type': 'response_item', 'payload': {'type': 'function_call_output'}}}], snapshot({}), snapshot({}))
    assert result['runtime_writes']['evidence_complete'] is False


def test_real_file_replacement_with_same_size_and_timestamp_is_detected(tmp_path):
    import os
    from bench.runtime_writes import snapshot_runtime_files

    original = tmp_path / 'cp.png'
    original.write_bytes(b'old screenshot')
    previous = original.stat()
    before = snapshot_runtime_files([tmp_path])
    replacement = tmp_path / 'replacement.png'
    replacement.write_bytes(b'new screenshot')
    os.utime(replacement, ns=(previous.st_atime_ns, previous.st_mtime_ns))
    replacement.replace(original)
    after = snapshot_runtime_files([tmp_path])
    result = audit(tmp_path, events('pi', str(original)), before, after)
    assert not result['passed']
    assert result['runtime_writes']['outputs'][0]['status'] == 'preexisting_changed'


def test_complete_json_in_mixed_shell_stdout_detects_replaced_file_identity(tmp_path):
    path = 'c:/users/test/cp.png'
    before = snapshot({path: {'device': 1, 'inode': 2, 'size': 8, 'mtime_ns': 100}})
    after = snapshot({path: {'device': 1, 'inode': 3, 'size': 8, 'mtime_ns': 100}})
    body = 'helper output\n' + json.dumps({'structuredContent': {'screenshot_file_path': path}}, indent=2) + '\nfinished'
    result = audit(tmp_path, events('claude', path, body=body), before, after)
    assert not result['passed']
