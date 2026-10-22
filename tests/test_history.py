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


# Persist a minimal native Pi shell call for CLI path-resolution regressions.
def shell_session(tmp_path, command, cwd):
    session = tmp_path / 'shell.jsonl'
    rows = [
        {'type': 'session', 'timestamp': '2026-10-20T10:00:00Z', 'cwd': str(cwd)},
        {'type': 'message', 'timestamp': '2026-10-20T10:00:01Z', 'message': {'role': 'assistant', 'content': [
            {'type': 'toolCall', 'id': 'r', 'name': 'bash', 'arguments': {'command': command}}]}},
        {'type': 'message', 'timestamp': '2026-10-20T10:00:04Z', 'message': {'role': 'toolResult', 'toolCallId': 'r', 'content': []}},
    ]
    session.write_text(''.join(json.dumps(row) + '\n' for row in rows), encoding='utf-8')
    return session


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
