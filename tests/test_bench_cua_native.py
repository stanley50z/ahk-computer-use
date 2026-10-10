"""CUA daemon restart before a trial, and the native arm's app-pipe transport option. Quiet: stand-in driver, no desktop."""

import json
import sys
import tomllib

import pytest

from bench.run import prepare, restart_cua_daemon

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
elif args[:2] == ['autostart', 'kick']:
    state.write_text('up'); print('Started autostart entry')
elif args[0] == 'list_sessions':
    print(json.dumps({'next_cursor': None, 'sessions': []}, indent=2))
'''


def skill_fixture(root, name):
    path = root / name
    path.mkdir()
    (path / 'SKILL.md').write_text(f'---\nname: {name}\ndescription: test fixture\n---\n', encoding='utf-8')
    return path


def test_cua_daemon_is_stopped_and_restarted_before_a_trial_and_the_record_is_kept(tmp_path):
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

    record = restart_cua_daemon(tmp_path, driver=str(wrapper))

    assert record['passed']
    calls = (tmp_path / 'daemon.log').read_text(encoding='utf-8').splitlines()
    assert calls.index('stop') < calls.index('autostart kick') < calls.index('list_sessions {}')
    saved = json.loads((tmp_path / 'daemon-restart.json').read_text(encoding='utf-8'))
    assert 'is running' in saved['after'] and 'not running' not in saved['after']


def test_native_app_pipe_transport_keeps_the_app_pipe_and_records_it(tmp_path):
    source_config = {'mcp_servers': {'node_repl': {'command': str(tmp_path / 'node.exe'), 'env': {
        'SKY_CUA_NATIVE_PIPE': '1', 'SKY_CUA_NATIVE_PIPE_DIRECTORY': r'\\.\pipe\codex-computer-use-test'}}}}
    builtin_root = tmp_path / 'builtin'
    builtin_root.mkdir()
    common = dict(skill=None, native_config=source_config, native_skill_roots=[], native_builtin_root=builtin_root)
    helper = prepare('codex-computer-use', tmp_path / 'helper-run', skill=skill_fixture(tmp_path, 'computer-use'), native_config=source_config, native_skill_roots=[], native_builtin_root=builtin_root)
    pipe = prepare('codex-computer-use', tmp_path / 'pipe-run', skill=tmp_path / 'computer-use', native_config=source_config, native_skill_roots=[], native_builtin_root=builtin_root, native_transport='app-pipe')
    helper_env = tomllib.loads((tmp_path / 'helper-run/agent-home/config.toml').read_text(encoding='utf-8'))['mcp_servers']['node_repl']['env']
    pipe_env = tomllib.loads((tmp_path / 'pipe-run/agent-home/config.toml').read_text(encoding='utf-8'))['mcp_servers']['node_repl']['env']
    assert helper_env['SKY_CUA_NATIVE_PIPE'] == '0' and 'SKY_CUA_NATIVE_PIPE_DIRECTORY' not in helper_env
    assert helper['native_transport'] == 'sdk-helper' and 'native_pipe' not in helper
    assert pipe_env['SKY_CUA_NATIVE_PIPE'] == '1' and pipe_env['SKY_CUA_NATIVE_PIPE_DIRECTORY'] == r'\\.\pipe\codex-computer-use-test'
    assert pipe['native_transport'] == 'app-pipe' and pipe['native_pipe'] == r'\\.\pipe\codex-computer-use-test'
    with pytest.raises(ValueError):
        prepare('codex-computer-use', tmp_path / 'bad-run', skill=tmp_path / 'computer-use', native_config={'mcp_servers': {'node_repl': {'command': 'x', 'env': {}}}}, native_skill_roots=[], native_builtin_root=builtin_root, native_transport='app-pipe')
