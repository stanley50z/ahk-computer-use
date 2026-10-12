"""Profile preparation is offline and does not launch an agent or touch the desktop."""

import json
import pytest

from bench.run import ARMS, prepare


# Supply filesystem/config boundary fixtures so ordinary checks need no installed CUA or Codex.
def skill_fixture(root, name):
    path = root / name
    path.mkdir()
    (path / 'SKILL.md').write_text(f'---\nname: {name}\ndescription: test fixture\n---\n', encoding='utf-8')
    return path


@pytest.mark.parametrize('scenario', ['calculator', 'illustrator-pen-export'])
def test_prepare_pi_arms_share_scenario_and_do_not_inherit_user_configuration(tmp_path, scenario):
    acu = prepare('pi-acu', tmp_path / 'acu-run', scenario=scenario, skill=skill_fixture(tmp_path, 'acu'))
    cua = prepare('pi-cua', tmp_path / 'cua-run', scenario=scenario, skill=skill_fixture(tmp_path, 'cua-driver'))
    assert acu['scenario_sha256'] == cua['scenario_sha256']
    assert acu['model'] == cua['model'] == 'gpt-6-astra'
    assert acu['reasoning'] == cua['reasoning'] == 'low'
    assert acu['skill_names'] == ['acu']
    assert cua['skill_names'] == ['cua-driver']
    for run_dir in [tmp_path / 'acu-run', tmp_path / 'cua-run']:
        assert not (run_dir / 'agent-home/auth.json').exists()
        settings = json.loads((run_dir / 'agent-home/settings.json').read_text(encoding='utf-8'))
        assert settings['packages'] == []
        assert settings['extensions'] == []
        assert not (run_dir / 'agent-home/APPEND_SYSTEM.md').exists()
        assert (run_dir / 'workspace').is_dir()


@pytest.mark.parametrize('scenario', ['calculator', 'illustrator-pen-export'])
@pytest.mark.parametrize('arm,skill_name', [('claude-acu', 'acu'), ('claude-cua', 'cua-driver')])
def test_prepare_claude_arm_runs_opus_low_in_safe_mode_with_only_four_tools(tmp_path, arm, skill_name, scenario):
    plan = prepare(arm, tmp_path / 'claude-run', scenario=scenario, skill=skill_fixture(tmp_path, skill_name))
    command = plan['command']
    assert (plan['model'], plan['reasoning']) == ('claude-opus-5-5', 'low')
    assert plan['skill_names'] == [skill_name]
    assert command[:2] == ['claude', '-p']
    for flag in ('--safe-mode', '--disable-slash-commands', '--strict-mcp-config', '--include-partial-messages', '--verbose'):
        assert flag in command
    assert command[command.index('--model') + 1] == 'claude-opus-5-5'
    assert command[command.index('--effort') + 1] == 'low'
    assert command[command.index('--tools') + 1] == 'Read,Write,Edit,Bash'
    assert command[command.index('--setting-sources') + 1] == 'user'
    assert command[command.index('--output-format') + 1] == 'stream-json'
    assert command[command.index('--session-id') + 1] == plan['session_id']
    assert str(tmp_path / skill_name / 'SKILL.md') in command[command.index('--append-system-prompt') + 1]
    assert f'The only enabled skill is {skill_name}.' in command[command.index('--append-system-prompt') + 1]
    assert '--continue' not in command and '--resume' not in command
    assert plan['environment_overrides']['CLAUDE_CONFIG_DIR'] == str(tmp_path / 'claude-run/agent-home')
    assert not (tmp_path / 'claude-run/agent-home/.credentials.json').exists()
    pi = prepare('pi-acu', tmp_path / 'acu-run', scenario=scenario, skill=skill_fixture(tmp_path, 'acu-pi'))
    assert plan['scenario_sha256'] == pi['scenario_sha256']
    assert (pi['model'], pi['reasoning']) == ('gpt-6-astra', 'low')


@pytest.mark.parametrize('scenario,allowed,forbidden', [('calculator', 'calc.exe', 'Illustrator.exe'),
                                                     ('illustrator-pen-export', 'Illustrator.exe', 'calc.exe')])
def test_prepare_pi_native_keeps_the_same_gpt_profile_and_only_native_mcp(tmp_path, scenario, allowed, forbidden):
    source_config = {'mcp_servers': {'node_repl': {'command': str(tmp_path / 'native-node.exe'), 'args': ['--fixture'],
                                                   'env': {'SKY_CUA_NATIVE_PIPE': '1', 'SKY_CUA_NATIVE_PIPE_DIRECTORY': 'old-pipe'}}}}
    plan = prepare('pi-computer-use', tmp_path / 'native-run', scenario=scenario, skill=skill_fixture(tmp_path, 'computer-use'), native_config=source_config)
    config = json.loads((tmp_path / 'native-run/agent-home/mcp.json').read_text(encoding='utf-8'))
    assert list(config['mcpServers']) == ['node_repl']
    native = config['mcpServers']['node_repl']
    assert native['args'][0].endswith('native_mcp.py')
    bridge = json.loads((tmp_path / 'native-run/agent-home/native-bridge.json').read_text(encoding='utf-8'))
    assert bridge['command'] == source_config['mcp_servers']['node_repl']['command']
    assert bridge['args'] == ['--fixture', '--disable-sandbox']
    assert allowed in bridge['approved_apps'] and forbidden not in bridge['approved_apps']
    from bench.native_mcp import approval
    request = {'requestedSchema': {'type': 'object'}, '_meta': {'connector_id': 'computer-use',
               'codex_approval_kind': 'mcp_tool_call', 'riskLevel': 'low', 'tool_params': {'app': allowed}}}
    assert approval(request, bridge['approved_apps'])['action'] == 'accept'
    request['_meta']['tool_params']['app'] = forbidden
    assert approval(request, bridge['approved_apps'])['action'] == 'decline'
    assert native['exposure'] == 'direct'
    assert native['env']['SKY_CUA_NATIVE_PIPE'] == '0'
    assert 'SKY_CUA_NATIVE_PIPE_DIRECTORY' not in native['env']
    assert json.loads(native['env']['NODE_REPL_TRUSTED_SERVICES']) == {'sky': '@oai/sky/service'}
    assert native['env']['BROWSER_USE_AVAILABLE_BACKENDS'] == ''
    assert plan['skill_names'] == ['computer-use']
    assert (plan['model'], plan['reasoning']) == ('gpt-6-astra', 'low')
    command = plan['command']
    assert command[0] == 'pi' and '--no-mcp' not in command
    assert command[command.index('-e') + 1] == 'builtin:mcp'
    assert command[command.index('--tools') + 1] == 'read,bash,edit,write,mcp__node_repl__js,mcp__node_repl__js_reset,mcp__node_repl__js_add_node_module_dir,mcp__node_repl__turn_ended'
    assert not (tmp_path / 'native-run/agent-home/auth.json').exists()
    assert not (tmp_path / 'native-run/agent-home/config.toml').exists()
    assert ARMS == ('pi-acu', 'pi-cua', 'pi-computer-use', 'claude-acu', 'claude-cua')
    with pytest.raises(ValueError, match='unknown arm'):
        prepare('codex-computer-use', tmp_path / 'retired-run')
