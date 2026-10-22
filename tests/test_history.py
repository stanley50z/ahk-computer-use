"""Read-only history behavior through the installed CLI, never through the desktop."""
import hashlib
import json
import os
from pathlib import Path
import subprocess

import pytest

FIXTURES = Path(__file__).parent / 'fixtures' / 'history'


# Isolate all persistent state and invoke the same entry point agents use.
def history(tmp_path, fixture='pi.jsonl', logs=()):
    home = tmp_path / 'acu-home'
    (home / 'logs').mkdir(parents=True, exist_ok=True)
    (home / 'logs' / 'runs.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in logs), encoding='utf-8')
    env = {**os.environ, 'ACU_HOME': str(home), 'ACU_SNIPPETS_ROOT': str(tmp_path / 'snippets')}
    session = tmp_path / 'session.jsonl'
    session.write_text((FIXTURES / fixture).read_text(encoding='utf-8').replace('SNIPPETS', (tmp_path / 'snippets').as_posix()), encoding='utf-8')
    return subprocess.run(['acu', 'history', str(session)], env=env, capture_output=True, text=True, encoding='utf-8', timeout=20)


def test_pi_error_then_success_is_candidate_without_script_text(tmp_path):
    result = history(tmp_path, logs=[
        {'ts': '2026-10-20T10:00:02Z', 'script': 'C:/history-test/action.ahk', 'outcome': 'error'},
        {'ts': '2026-10-20T10:00:05Z', 'script': 'C:/history-test/action.ahk', 'outcome': 'ok'},
        {'ts': '2026-10-19T10:00:05Z', 'script': 'C:/history-test/action.ahk', 'outcome': 'timeout'},
    ])
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'Editor.exe: 2 runs (1 ok, 1 error, 0 timeout, 0 unknown)' in result.stdout
    assert 'candidate: 2 runs, 1 errors, 0 looks; last C:/history-test/action.ahk (2 lines)' in result.stdout
    assert 'WinActivate' not in result.stdout
    assert 'Send(' not in result.stdout


@pytest.mark.parametrize("missing", ["both", "request", "result"])
def test_pi_stream_without_timestamps_stays_unknown(tmp_path, missing):
    session = tmp_path / "stream.jsonl"
    rows = [
        {"type": "message_end", "message": {"role": "assistant", "content": [
            {"type": "toolCall", "id": "r", "name": "bash", "arguments": {
                "command": "acu run C:/history-test/action.ahk -- ahk_exe Editor.exe"}}]}},
        {"type": "message", "message": {"role": "toolResult", "toolCallId": "r", "content": []}},
    ]
    if missing == "request":
        rows[1]["timestamp"] = "2026-10-20T10:00:03Z"
    elif missing == "result":
        rows[0]["timestamp"] = "2026-10-20T10:00:01Z"
    session.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    result = history(tmp_path, session, logs=[
        {"ts": "2026-10-20T10:00:02Z", "script": "C:/history-test/action.ahk", "outcome": "ok"},
    ])
    assert result.returncode == 0, result.stdout + result.stderr
    assert "1 unknown" in result.stdout
    assert "candidate:" not in result.stdout


def test_codex_extra_looks_resolve_bundled_scripts(tmp_path):
    result = history(tmp_path, 'codex.jsonl', logs=[
        {'ts': '2026-10-20T10:00:02Z', 'script': str(Path('acu/tree.ahk').resolve()), 'outcome': 'ok'},
        {'ts': '2026-10-20T10:00:03Z', 'script': str(Path('acu/screenshot.ahk').resolve()), 'outcome': 'ok'},
        {'ts': '2026-10-20T10:00:06Z', 'script': 'C:/history-test/action.ahk', 'outcome': 'ok'},
    ])
    assert result.returncode == 0, result.stdout
    assert 'Editor.exe: 3 runs (3 ok, 0 error, 0 timeout, 0 unknown)' in result.stdout
    assert 'candidate: 3 runs, 0 errors, 2 looks' in result.stdout


def test_claude_snippet_runs_changes_and_store_wide_failures(tmp_path):
    snippet = tmp_path / 'snippets' / 'Editor.exe' / 'open.ahk'
    snippet.parent.mkdir(parents=True)
    snippet.write_text('; does: Open dialog\n', encoding='utf-8')
    logs = [
        {'ts': '2026-10-20T10:00:04Z', 'script': str(snippet), 'outcome': 'error'},
        {'ts': '2026-10-20T10:00:05Z', 'script': str(snippet), 'outcome': 'ok'},
        *[{'ts': f'2026-10-19T10:00:0{i}Z', 'script': str(snippet), 'outcome': outcome}
          for i, outcome in enumerate(['error', 'timeout', 'ok', 'ok'])],
    ]
    result = history(tmp_path, 'claude.jsonl', logs)
    assert result.returncode == 0, result.stdout
    assert f'snippet: {snippet.as_posix()} -> error' in result.stdout
    assert f'snippet: {snippet.as_posix()} -> ok' in result.stdout
    assert f'Changed snippet (editor.exe): {snippet.as_posix()}' in result.stdout
    assert f'Frequently failing snippet: {snippet.as_posix()} (3/6 failed' in result.stdout
    assert 'WinActivate' not in result.stdout
    # The threshold is inclusive, but deleted snippets and a <50% failure rate do not qualify.
    logs.append({'ts': '2026-10-19T10:00:09Z', 'script': str(snippet), 'outcome': 'ok'})
    assert 'Frequently failing snippet' not in history(tmp_path, 'claude.jsonl', logs).stdout
    snippet.unlink()
    assert 'Frequently failing snippet' not in history(tmp_path, 'claude.jsonl', logs[:-1]).stdout


def test_unmatched_and_ambiguous_runs_are_not_successes(tmp_path):
    logs = [
        {'ts': '2026-10-20T10:00:02Z', 'script': 'C:/history-test/action.ahk', 'outcome': 'ok'},
        {'ts': '2026-10-20T10:00:02.5Z', 'script': 'C:/history-test/action.ahk', 'outcome': 'error'},
    ]
    result = history(tmp_path, logs=logs)
    assert result.returncode == 0
    assert '2 unknown' in result.stdout
    assert result.stdout.count('unmatched:') == 2
    assert 'candidate:' not in result.stdout


def test_shell_cwd_before_inline_write_and_parallel_tool_requests(tmp_path):
    result = history(tmp_path, 'pi-shell.jsonl', logs=[
        {'ts': '2026-10-20T10:00:02Z', 'script': 'C:/history-test/scripts/action.ahk', 'outcome': 'error'},
        {'ts': '2026-10-20T10:00:05Z', 'script': 'C:/history-test/scripts/action.ahk', 'outcome': 'ok'},
    ])
    assert result.returncode == 0, result.stdout
    assert 'Editor.exe: 2 runs' in result.stdout
    assert 'last C:/history-test/scripts/action.ahk (2 lines)' in result.stdout
    assert 'fake.ahk' not in result.stdout


def test_codex_python_write_and_patch_mark_snippet_changes(tmp_path):
    snippet = (tmp_path / 'snippets' / 'Editor.exe' / 'open.ahk').as_posix()
    result = history(tmp_path, 'codex-writes.jsonl', logs=[
        {'ts': '2026-10-20T10:00:02Z', 'script': snippet, 'outcome': 'error'},
        {'ts': '2026-10-20T10:00:07Z', 'script': snippet, 'outcome': 'ok'},
    ])
    assert result.returncode == 0, result.stdout
    assert f'Changed snippet (editor.exe): {snippet}' in result.stdout
    assert f'last {snippet} (2 lines)' in result.stdout


def test_recorded_hash_prevents_stale_source_from_naming_app(tmp_path):
    result = history(tmp_path, logs=[
        {'ts': '2026-10-20T10:00:02Z', 'script': 'C:/history-test/action.ahk', 'outcome': 'error', 'sha256': '0' * 64},
        {'ts': '2026-10-20T10:00:05Z', 'script': 'C:/history-test/action.ahk', 'outcome': 'ok', 'sha256': '0' * 64},
    ])
    assert result.returncode == 0, result.stdout
    assert 'unknown app: 2 runs' in result.stdout
    assert 'candidate:' not in result.stdout


def test_missing_log_and_corrupt_session_are_explicit_and_read_only(tmp_path):
    env = {**os.environ, 'ACU_HOME': str(tmp_path / 'missing'), 'ACU_SNIPPETS_ROOT': str(tmp_path / 'snippets')}
    result = subprocess.run(['acu', 'history', str(FIXTURES / 'pi.jsonl')], env=env,
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 0
    assert 'Run log missing:' in result.stdout and '2 unknown' in result.stdout
    assert not (tmp_path / 'missing').exists()
    assert not (tmp_path / 'snippets').exists()
    broken = tmp_path / 'broken.jsonl'
    broken.write_text('{private document content', encoding='utf-8')
    result = subprocess.run(['acu', 'history', str(broken)], env=env, capture_output=True, text=True, timeout=20)
    assert result.returncode == 2
    assert 'line 1' in result.stdout
    assert 'private document' not in result.stdout


def test_current_script_is_used_only_with_matching_recorded_hash(tmp_path):
    script = tmp_path / 'action.ahk'
    data = b'WinActivate("ahk_exe Editor.exe")\n'
    script.write_bytes(data)
    session = tmp_path / 'disk.jsonl'
    rows = [
        {'type': 'session', 'timestamp': '2026-10-20T10:00:00Z', 'cwd': str(tmp_path)},
        {'type': 'message', 'timestamp': '2026-10-20T10:00:01Z', 'message': {'role': 'assistant', 'content': [
            {'type': 'toolCall', 'id': 'r', 'name': 'bash', 'arguments': {'command': f'acu run "{script.as_posix()}"; acu run "{script.as_posix()}"'}}]}},
        {'type': 'message', 'timestamp': '2026-10-20T10:00:04Z', 'message': {'role': 'toolResult', 'toolCallId': 'r', 'content': []}},
    ]
    session.write_text(''.join(json.dumps(row) + '\n' for row in rows), encoding='utf-8')
    logs = [{'ts': f'2026-10-20T10:00:0{i}Z', 'script': str(script), 'outcome': outcome,
             'sha256': hashlib.sha256(data).hexdigest()} for i, outcome in [(2, 'error'), (3, 'ok')]]
    result = history(tmp_path, session, logs)
    assert result.returncode == 0, result.stdout
    assert '(1 lines)' in result.stdout
    script.write_text('private changed contents', encoding='utf-8')
    result = history(tmp_path, session, logs)
    assert 'unknown app: 2 runs' in result.stdout
    assert 'private changed contents' not in result.stdout


# Persist a minimal native Pi shell call; outputs become the tool result's CLI JSON lines.
def shell_session(tmp_path, command, cwd, outputs=()):
    session = tmp_path / 'shell.jsonl'
    rows = [
        {'type': 'session', 'timestamp': '2026-10-20T10:00:00Z', 'cwd': str(cwd)},
        {'type': 'message', 'timestamp': '2026-10-20T10:00:01Z', 'message': {'role': 'assistant', 'content': [
            {'type': 'toolCall', 'id': 'r', 'name': 'bash', 'arguments': {'command': command}}]}},
        {'type': 'message', 'timestamp': '2026-10-20T10:00:04Z', 'message': {'role': 'toolResult', 'toolCallId': 'r', 'content': [
            {'type': 'text', 'text': ''.join(json.dumps({'outcome': 'ok', 'output': output}) + '\n' for output in outputs)}]}},
    ]
    session.write_text(''.join(json.dumps(row) + '\n' for row in rows), encoding='utf-8')
    return session


def test_unparsable_python_write_leaves_the_report_intact(tmp_path):
    session = shell_session(tmp_path, 'python -c "print(\\(1)"; acu run action.ahk', tmp_path)
    result = history(tmp_path, session, logs=[
        {'ts': '2026-10-20T10:00:02Z', 'script': str(tmp_path / 'action.ahk'), 'outcome': 'ok'}])
    assert result.returncode == 0, result.stdout + result.stderr
    assert '1 runs (1 ok, 0 error, 0 timeout, 0 unknown)' in result.stdout
    assert result.stderr == ''


def test_executable_names_with_plus_signs_identify_the_app(tmp_path):
    command = "cat > action.ahk <<'AHK'\nWinActivate(\"ahk_exe notepad++.exe\")\nAHK\nacu run tree.ahk -- Notes; acu run action.ahk"
    session = shell_session(tmp_path, command, tmp_path, outputs=[
        'window=1 "Notes" notepad++.exe\nelements=0\ntruncated=no\n', ''])
    result = history(tmp_path, session, logs=[
        {'ts': '2026-10-20T10:00:02Z', 'script': str(Path('acu/tree.ahk').resolve()), 'outcome': 'ok'},
        {'ts': '2026-10-20T10:00:03Z', 'script': str(tmp_path / 'action.ahk'), 'outcome': 'ok'},
    ])
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'notepad++.exe: 2 runs (2 ok, 0 error, 0 timeout, 0 unknown)' in result.stdout


def test_each_run_in_a_shell_call_gets_only_its_own_result(tmp_path):
    tree = str(Path('acu/tree.ahk').resolve())
    command = 'acu run tree.ahk -- "ahk_exe Editor.exe"; acu run tree.ahk -- "ahk_exe Browser.exe"'
    logs = [{'ts': f'2026-10-20T10:00:0{second}Z', 'script': tree, 'outcome': 'ok'} for second in (2, 3)]
    outputs = [f'window={index} "{app}" {app}.exe\nelements=0\ntruncated=no\n' for index, app in enumerate(['Editor', 'Browser'])]
    result = history(tmp_path, shell_session(tmp_path, command, tmp_path, outputs), logs)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'Editor.exe: 1 runs (1 ok' in result.stdout and 'Browser.exe: 1 runs (1 ok' in result.stdout
    # A result count that does not match the runs attributes no output, rather than guessing.
    result = history(tmp_path, shell_session(tmp_path, 'acu run tree.ahk; acu run tree.ahk', tmp_path, outputs[:1]), logs)
    assert 'unknown app: 2 runs' in result.stdout


@pytest.mark.parametrize('data, decoded', [
    ('WinActivate("ahk_exe Editor.exe")\n'.encode('utf-16'), True),
    (b'\xffWinActivate("ahk_exe Editor.exe")\n', False),  # Neither UTF-8 nor UTF-16 with a BOM: source stays unknown.
])
def test_on_disk_script_in_another_encoding_does_not_abort_the_report(tmp_path, data, decoded):
    script = tmp_path / 'action.ahk'
    script.write_bytes(data)
    session = shell_session(tmp_path, f'acu run "{script.as_posix()}"', tmp_path)
    result = history(tmp_path, session, logs=[
        {'ts': '2026-10-20T10:00:02Z', 'script': str(script), 'outcome': 'ok', 'sha256': hashlib.sha256(data).hexdigest()}])
    assert result.returncode == 0, result.stdout + result.stderr
    assert ('Editor.exe: 1 runs (1 ok' in result.stdout) is decoded
    assert '1 runs (1 ok, 0 error, 0 timeout, 0 unknown)' in result.stdout


def test_bare_bundled_name_uses_cli_resolution_not_both_paths(tmp_path):
    local = tmp_path / 'tree.ahk'
    bundled = Path('acu/tree.ahk').resolve()
    session = shell_session(tmp_path, 'acu run tree.ahk', tmp_path)
    logs = [
        {'ts': '2026-10-20T10:00:02Z', 'script': str(bundled), 'outcome': 'ok'},
        {'ts': '2026-10-20T10:00:03Z', 'script': str(local), 'outcome': 'error'},
    ]
    result = history(tmp_path, session, logs)
    assert result.returncode == 0, result.stdout + result.stderr
    assert '1 runs (1 ok, 0 error, 0 timeout, 0 unknown)' in result.stdout
    # An existing file in the captured working directory wins over the bundle.
    local.write_text('; local tree\n', encoding='utf-8')
    result = history(tmp_path, session, logs)
    assert result.returncode == 0, result.stdout + result.stderr
    assert '1 runs (0 ok, 1 error, 0 timeout, 0 unknown)' in result.stdout


@pytest.mark.parametrize('script', [
    '$PWD/.pi/artifacts/x/start.ahk',
    '"$PWD/.pi/artifacts/x/start.ahk"',
    '${PWD}/.pi/artifacts/x/start.ahk',
    '"${PWD}/.pi/artifacts/x/start.ahk"',
    '~/.pi/artifacts/x/start.ahk',
])
def test_shell_paths_expand_pwd_and_home_only(tmp_path, script):
    cwd = tmp_path / 'working folder'
    # cd updates PWD without changing the harness process's working folder.
    session = shell_session(tmp_path, f'cd "{cwd.as_posix()}"; acu run {script}; acu run "$PWD_OTHER/start.ahk"', tmp_path)
    base = Path.home() if script.startswith('~') else cwd
    result = history(tmp_path, session, logs=[
        {'ts': '2026-10-20T10:00:02Z', 'script': str(base / '.pi/artifacts/x/start.ahk'), 'outcome': 'ok'},
    ])
    assert result.returncode == 0, result.stdout + result.stderr
    assert '2 runs (1 ok, 0 error, 0 timeout, 1 unknown)' in result.stdout
    assert f'unmatched: {cwd.as_posix()}/$PWD_OTHER/start.ahk' in result.stdout


def test_help_states_fixed_rules():
    result = subprocess.run(['acu', 'history', '--help'], capture_output=True, text=True, timeout=20)
    assert result.returncode == 0
    assert 'two looks' in ' '.join(result.stdout.split())
    assert '3 failures' in result.stdout
    assert '50%' in result.stdout


# Persist a native Codex session from (request payload, output) pairs, one second apart.
def codex_session(tmp_path, steps):
    rows = [{'type': 'session_meta', 'timestamp': '2026-10-20T10:00:00Z', 'payload': {'cwd': 'C:/history-test'}}]
    for index, (request, output) in enumerate(steps):
        call_id = f'c{index}'
        kind = 'custom_tool_call' if request['name'] == 'apply_patch' else 'function_call'
        rows.append({'type': 'response_item', 'timestamp': f'2026-10-20T10:00:{index * 2 + 1:02}Z',
                     'payload': {'type': kind, 'call_id': call_id, **request}})
        rows.append({'type': 'response_item', 'timestamp': f'2026-10-20T10:00:{index * 2 + 2:02}Z',
                     'payload': {'type': f'{kind}_output', 'call_id': call_id, 'output': output}})
    session = tmp_path / 'codex-session.jsonl'
    session.write_text(''.join(json.dumps(row) + '\n' for row in rows), encoding='utf-8')
    return session


def patch(path, kind, lines):
    return {'name': 'apply_patch', 'input': f'*** Begin Patch\n*** {kind} File: {path}\n' + ''.join(
        line + '\n' for line in lines) + '*** End Patch'}


def shell(command):
    return {'name': 'shell_command', 'arguments': json.dumps({'command': command})}


@pytest.mark.parametrize('output, changed', [
    ('{"output":"Success. Updated the following files:\\nA x\\n","metadata":{"exit_code":0}}', True),
    ('Exit code: 0\nWall time: 0 seconds\nOutput:\nSuccess. Updated the following files:\n', True),
    ('{"output":"Failed to write file","metadata":{"exit_code":1}}', False),
    ('apply_patch verification failed: Failed to find expected lines in x', False),
    ('execution error: Io(Os { code: 206 })', False),
    ('', False),  # No readable status: the write stays unconfirmed.
])
def test_codex_patch_counts_as_snippet_change_only_when_its_result_succeeded(tmp_path, output, changed):
    snippet = (tmp_path / 'snippets' / 'Editor.exe' / 'open.ahk').as_posix()
    session = codex_session(tmp_path, [(patch(snippet, 'Add', ['+WinActivate("ahk_exe Editor.exe")']), output)])
    result = history(tmp_path, session)
    assert result.returncode == 0, result.stdout + result.stderr
    assert (f'Changed snippet (editor.exe): {snippet}' in result.stdout) is changed


def test_codex_failed_shell_write_is_not_a_snippet_change(tmp_path):
    snippet = (tmp_path / 'snippets' / 'Editor.exe' / 'open.ahk').as_posix()
    session = codex_session(tmp_path, [(shell(f"cat > '{snippet}' <<'AHK'\nExitApp\nAHK"), 'Exit code: 1\nOutput:\n')])
    assert 'Changed snippet' not in history(tmp_path, session).stdout


def test_codex_added_script_keeps_its_failed_first_run_in_the_chain(tmp_path):
    script = 'C:/history-test/action.ahk'
    ok = '{"output":"Success.","metadata":{"exit_code":0}}'
    session = codex_session(tmp_path, [
        (patch(script, 'Add', ['+WinActivate("ahk_exe Editor.exe")', '+Send("^o")']), ok),
        (shell(f'acu run {script}'), 'Exit code: 1\nOutput:\n'),
        (patch(script, 'Update', ['@@', ' WinActivate("ahk_exe Editor.exe")', '-Send("^o")', '+Send("^+o")']), ok),
        (shell(f'acu run {script}'), 'Exit code: 0\nOutput:\n'),
    ])
    result = history(tmp_path, session, logs=[
        {'ts': '2026-10-20T10:00:03.5Z', 'script': script, 'outcome': 'error'},
        {'ts': '2026-10-20T10:00:07.5Z', 'script': script, 'outcome': 'ok'},
    ])
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'Editor.exe: 2 runs (1 ok, 1 error, 0 timeout, 0 unknown)' in result.stdout
    assert f'candidate: 2 runs, 1 errors, 0 looks; last {script} (2 lines)' in result.stdout
    assert 'unknown app' not in result.stdout


def test_store_app_looks_group_under_the_hosted_app_not_its_frame_host(tmp_path):
    script = (tmp_path / 'square.ahk').as_posix()
    tree = str(Path('acu/tree.ahk').resolve())

    def result_text(output):
        return [{'type': 'text', 'text': json.dumps({'outcome': 'ok', 'output': output})}]

    commands = [
        ('acu run tree.ahk -- "ahk_exe CalculatorApp.exe"', result_text(
            'window=1 "Calculator" ApplicationFrameHost.exe\nelements=0\ntruncated=no\n')),
        ('acu run tree.ahk -- Calculator', result_text(
            'window=1 "Calculator" ApplicationFrameHost.exe\nelements=0\ntruncated=no\n'
            'snippets C:\\store\\CalculatorApp.exe\nsquare.ahk | args: n | does: Square\n')),
        (f"cat > '{script}' <<'AHK'\nWinActivate(\"ahk_exe CalculatorApp.exe\")\nAHK\nacu run '{script}'", []),
    ]
    rows = [{'type': 'session', 'timestamp': '2026-10-20T10:00:00Z', 'cwd': str(tmp_path)}]
    for index, (command, content) in enumerate(commands):
        rows.append({'type': 'message', 'timestamp': f'2026-10-20T10:00:{index * 2 + 1:02}Z', 'message': {
            'role': 'assistant', 'content': [{'type': 'toolCall', 'id': f'r{index}', 'name': 'bash',
                                              'arguments': {'command': command}}]}})
        rows.append({'type': 'message', 'timestamp': f'2026-10-20T10:00:{index * 2 + 2:02}Z', 'message': {
            'role': 'toolResult', 'toolCallId': f'r{index}', 'content': content}})
    session = tmp_path / 'store-app.jsonl'
    session.write_text(''.join(json.dumps(row) + '\n' for row in rows), encoding='utf-8')
    result = history(tmp_path, session, logs=[
        {'ts': '2026-10-20T10:00:01.5Z', 'script': tree, 'outcome': 'ok'},
        {'ts': '2026-10-20T10:00:03.5Z', 'script': tree, 'outcome': 'ok'},
        {'ts': '2026-10-20T10:00:05.5Z', 'script': script, 'outcome': 'ok'},
    ])
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'CalculatorApp.exe: 3 runs (3 ok, 0 error, 0 timeout, 0 unknown)' in result.stdout
    assert 'candidate: 3 runs, 0 errors, 2 looks' in result.stdout
    assert 'ApplicationFrameHost' not in result.stdout
