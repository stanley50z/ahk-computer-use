"""CUA daemon restart before a trial, and the native arm's app-pipe transport option. Quiet: stand-in driver, no desktop."""

import json
import sys

import pytest

from bench.run import ARMS, prepare, restart_cua_daemon, uses_cua_daemon

STUB = '''
import json, sys
from pathlib import Path
state = Path(sys.argv[-1]) if sys.argv[-1].endswith('.state') else None
args = [a for a in sys.argv[1:] if not a.endswith('.state')]
log = state.with_suffix('.log')
log.open('a').write(' '.join(args) + '\\n')
if args[0] == 'status':
    print('Cua Driver daemon is running' if state.read_text() == 'up' else 'Cua Driver daemon is not running')
elif args[0] == 'stop':
    state.write_text('down'); print('stopped')
elif args[:2] == ['autostart', 'kick'] or args[0] == 'bench-task':
    state.write_text('up'); print('Started ' + args[0])
elif args[0] == 'list_sessions':
    print(json.dumps({'next_cursor': None, 'sessions': []}, indent=2))
'''


def skill_fixture(root, name):
    path = root / name
    path.mkdir()
    (path / 'SKILL.md').write_text(f'---\nname: {name}\ndescription: test fixture\n---\n', encoding='utf-8')
    return path


def test_only_the_cua_arm_restarts_the_daemon():
    assert [arm for arm in ARMS if uses_cua_daemon(arm)] == ['pi-cua', 'claude-cua'], 'the selected runtime, not the harness prefix, decides'


# A stand-in cua-driver whose daemon state lives in a file; every call is logged beside it.
def driver_stub(tmp_path):
    stub = tmp_path / 'driver.py'
    stub.write_text(STUB, encoding='utf-8')
    state = tmp_path / 'daemon.state'
    state.write_text('up', encoding='utf-8')
    wrapper = tmp_path / ('driver.cmd' if sys.platform == 'win32' else 'driver.sh')
    if sys.platform == 'win32':
        wrapper.write_text(f'@"{sys.executable}" "{stub}" %* "{state}"\n', encoding='utf-8')
    else:
        wrapper.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{stub}" "$@" "{state}"\n', encoding='utf-8')
        wrapper.chmod(0o755)
    return wrapper


def test_cua_daemon_is_stopped_and_restarted_before_a_trial_and_the_record_is_kept(tmp_path):
    wrapper = driver_stub(tmp_path)

    record = restart_cua_daemon(tmp_path, driver=str(wrapper))

    assert record['passed']
    calls = (tmp_path / 'daemon.log').read_text(encoding='utf-8').splitlines()
    assert calls.index('stop') < calls.index('autostart kick') < calls.index('list_sessions {}')
    saved = json.loads((tmp_path / 'daemon-restart.json').read_text(encoding='utf-8'))
    assert 'is running' in saved['after'] and 'not running' not in saved['after']


# A trial restarts the daemon through the bench task in its workspace; the restore uses the installed entry.
def test_cua_daemon_starts_in_the_trial_workspace_through_the_bench_task(tmp_path, monkeypatch):
    import bench.cua_bench_task as task
    wrapper = driver_stub(tmp_path)
    monkeypatch.setattr(task, 'CWD_FILE', tmp_path / 'cwd.txt')
    monkeypatch.setattr(task, 'installed', lambda: True)
    monkeypatch.setattr(task, 'start_command', lambda: [str(wrapper), 'bench-task'])

    record = restart_cua_daemon(tmp_path, driver=str(wrapper), cwd=tmp_path / 'workspace')
    restore = restart_cua_daemon(tmp_path, driver=str(wrapper), record_name='daemon-restore.json')

    assert record['passed'] and restore['passed']
    assert (tmp_path / 'cwd.txt').read_text(encoding='utf-8') == str((tmp_path / 'workspace').resolve())
    calls = (tmp_path / 'daemon.log').read_text(encoding='utf-8').splitlines()
    assert calls.index('bench-task') < calls.index('autostart kick')
    assert (tmp_path / 'daemon-restart.json').is_file() and (tmp_path / 'daemon-restore.json').is_file()
    monkeypatch.setattr(task, 'installed', lambda: False)
    with pytest.raises(RuntimeError, match='cua_bench_task.py install'):
        restart_cua_daemon(tmp_path, driver=str(wrapper), cwd=tmp_path)


def test_native_app_pipe_transport_keeps_the_app_pipe_and_records_it(tmp_path):
    source_config = {'mcp_servers': {'node_repl': {'command': str(tmp_path / 'node.exe'), 'env': {
        'SKY_CUA_NATIVE_PIPE': '1', 'SKY_CUA_NATIVE_PIPE_DIRECTORY': r'\\.\pipe\codex-computer-use-test'}}}}
    builtin_root = tmp_path / 'builtin'
    builtin_root.mkdir()
    helper = prepare('pi-computer-use', tmp_path / 'helper-run', skill=skill_fixture(tmp_path, 'computer-use'), native_config=source_config)
    pipe = prepare('pi-computer-use', tmp_path / 'pipe-run', skill=tmp_path / 'computer-use', native_config=source_config, native_transport='app-pipe')
    helper_env = json.loads((tmp_path / 'helper-run/agent-home/mcp.json').read_text(encoding='utf-8'))['mcpServers']['node_repl']['env']
    pipe_env = json.loads((tmp_path / 'pipe-run/agent-home/mcp.json').read_text(encoding='utf-8'))['mcpServers']['node_repl']['env']
    assert helper_env['SKY_CUA_NATIVE_PIPE'] == '0' and 'SKY_CUA_NATIVE_PIPE_DIRECTORY' not in helper_env
    assert helper['native_transport'] == 'sdk-helper' and 'native_pipe' not in helper
    assert pipe_env['SKY_CUA_NATIVE_PIPE'] == '1' and pipe_env['SKY_CUA_NATIVE_PIPE_DIRECTORY'] == r'\\.\pipe\codex-computer-use-test'
    assert pipe['native_transport'] == 'app-pipe' and pipe['native_pipe'] == r'\\.\pipe\codex-computer-use-test'
    with pytest.raises(ValueError):
        prepare('pi-computer-use', tmp_path / 'bad-run', skill=tmp_path / 'computer-use', native_config={'mcp_servers': {'node_repl': {'command': 'x', 'env': {}}}}, native_transport='app-pipe')
