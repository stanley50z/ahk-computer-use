"""Profile preparation is offline and does not launch an agent or touch the desktop."""

import json
import pytest

from bench.run import ARMS, prepare


def test_interrupted_turn_exclusion_is_offline_only_and_does_not_prepare_a_trial(tmp_path):
    import subprocess
    import sys
    from bench.run import ROOT
    target = tmp_path / 'not-a-trial'
    result = subprocess.run([sys.executable, str(ROOT / 'bench/run.py'), 'prepare', '--run-dir', str(target),
                             '--exclude-interrupted-turns'], capture_output=True, text=True, encoding='utf-8', timeout=15)
    assert result.returncode != 0 and 'only available for offline analyse' in result.stderr
    assert not target.exists()


# Supply filesystem/config boundary fixtures so ordinary checks need no installed CUA or Codex.
def skill_fixture(root, name):
    path = root / name
    path.mkdir()
    (path / 'SKILL.md').write_text(f'---\nname: {name}\ndescription: test fixture\n---\n', encoding='utf-8')
    return path


def test_all_illustrator_configurations_receive_the_same_simple_drawing_and_appearance_task(tmp_path):
    templates = []
    for arm in ARMS:
        folder = tmp_path / arm
        folder.mkdir()
        name = 'computer-use' if arm == 'pi-computer-use' else ('cua-driver' if arm.endswith('cua') else 'acu')
        native = {'mcp_servers': {'node_repl': {'command': 'native-fixture', 'args': []}}}
        plan = prepare(arm, folder / 'trial', scenario='illustrator-pen-export',
                       skill=skill_fixture(folder, name), native_config=native)
        template = (folder / 'trial/prompt-template.txt').read_text(encoding='utf-8')
        assert 'using the Pen tool' in template and 'genuine Bézier curves' in template
        assert 'Set the fill color to #00AEEF. Set the stroke to None (no stroke).' in template
        for removed in ('Use only the Pen tool', 'Do not use other Illustrator tools', 'initial zoom', 'fit-to-window'):
            assert removed not in template
        assert plan['scenario_version'] == 'Adobe Illustrator Pen and Export v0.11'
        assert plan['window_audit_policy'] == 'diagnostic-only-v1'
        assert not (folder / 'trial/state.json').exists()
        templates.append(template)
    assert len(set(templates)) == 1


@pytest.mark.parametrize('arm', ARMS)
def test_preparation_disables_snippets_before_actor_start(tmp_path, monkeypatch, arm):
    from pathlib import Path
    from acu.settings import snippets_enabled

    global_file = tmp_path / 'global-settings.json'
    global_file.write_text('{"snippets": {"enabled": true}}', encoding='utf-8')
    monkeypatch.setenv('ACU_SETTINGS_FILE', str(global_file))
    native = {'mcp_servers': {'node_repl': {'command': 'native-fixture', 'args': []}}}
    plan = prepare(arm, tmp_path / 'trial', skill=skill_fixture(tmp_path, 'skill'), native_config=native)
    workspace = Path(plan['workspace'])
    setting = workspace / '.ahk-computer-use/settings.json'
    assert json.loads(setting.read_text(encoding='utf-8')) == {'snippets': {'enabled': False}}
    assert snippets_enabled(workspace) is False
    assert not (tmp_path / 'trial/state.json').exists()
    assert json.loads(global_file.read_text(encoding='utf-8')) == {'snippets': {'enabled': True}}


def test_stale_provider_profile_is_rejected_before_actor_or_desktop_startup(tmp_path):
    from bench.run import run_trial
    plan = prepare('pi-acu', tmp_path/'trial', skill=skill_fixture(tmp_path, 'acu'))
    plan['provider'] = 'openai'
    with pytest.raises(ValueError, match='explicit provider'):
        run_trial(plan)
    assert not (tmp_path/'trial/state.json').exists()
    assert not (tmp_path/'trial/agent-home/auth.json').exists()
    assert not (tmp_path/'trial/observer-probe-before.log').exists()


def test_actor_prompt_paths_use_the_current_user_root_without_exposing_the_account(tmp_path, monkeypatch):
    import shutil
    from pathlib import Path
    import bench.run as bench
    home = tmp_path / 'different-account'
    checkout = home / 'portable-checkout'
    shutil.copytree(bench.ROOT / 'bench/assets/illustrator-pen-export', checkout / 'bench/assets/illustrator-pen-export')
    shutil.copytree(bench.ROOT / 'bench/scenarios', checkout / 'bench/scenarios')
    monkeypatch.setattr(Path, 'home', classmethod(lambda cls: home))
    monkeypatch.setattr(bench, 'ROOT', checkout)
    (home / '.agents').mkdir()
    skill = skill_fixture(home / '.agents', 'cua-driver')
    directory = checkout / '.pi/bench/trial'
    plan = prepare('claude-cua', directory, scenario='illustrator-pen-export', skill=skill)
    prompt = (directory / 'prompt.txt').read_text(encoding='utf-8')
    declaration = plan['command'][plan['command'].index('--append-system-prompt') + 1]
    assert 'Workspace: ~/portable-checkout/.pi/bench/trial/workspace' in prompt
    assert 'Scratch folder: ~/portable-checkout/.pi/bench/trial/workspace/scratch' in prompt
    assert 'Read ~/.agents/cua-driver/SKILL.md before desktop interaction.' in declaration
    assert 'different-account' not in prompt + declaration
    assert plan['workspace'] == str(directory / 'workspace')
    assert plan['skill_path'] == str(skill / 'SKILL.md')


@pytest.mark.parametrize('scenario', ['calculator', 'illustrator-pen-export'])
def test_prepare_pi_arms_share_scenario_and_do_not_inherit_user_configuration(tmp_path, scenario):
    acu = prepare('pi-acu', tmp_path / 'acu-run', scenario=scenario, skill=skill_fixture(tmp_path, 'acu'))
    cua = prepare('pi-cua', tmp_path / 'cua-run', scenario=scenario, skill=skill_fixture(tmp_path, 'cua-driver'))
    assert acu['scenario_sha256'] == cua['scenario_sha256']
    assert acu['model'] == cua['model'] == 'gpt-6-astra'
    assert acu['provider'] == cua['provider'] == 'openai-codex'
    for profile in (acu, cua):
        command = profile['command']
        assert command[command.index('--model') + 1] == 'openai-codex/gpt-6-astra'
    assert acu['reasoning'] == cua['reasoning'] == 'low'
    assert acu['skill_names'] == ['acu']
    assert cua['skill_names'] == ['cua-driver']
    for run_dir in [tmp_path / 'acu-run', tmp_path / 'cua-run']:
        assert not (run_dir / 'agent-home/auth.json').exists()
        settings = json.loads((run_dir / 'agent-home/settings.json').read_text(encoding='utf-8'))
        assert settings['packages'] == []
        assert settings['extensions'] == []
        assert settings['retry'] == {'enabled': True, 'maxRetries': 3, 'baseDelayMs': 2000,
                                     'maxAgentDelayMs': 60000, 'provider': {'maxRetries': 0}}
        assert settings['compaction'] == {'enabled': True, 'reserveTokens': 16384, 'keepRecentTokens': 20000}
        plan = acu if run_dir.name == 'acu-run' else cua
        assert plan['recovery_policy'] == {'retry': settings['retry'], 'compaction': settings['compaction']}
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
    from pathlib import Path
    declaration = command[command.index('--append-system-prompt') + 1]
    reference = declaration.split(' Read ', 1)[1].split(' before desktop interaction.', 1)[0]
    assert Path(reference).expanduser().resolve() == (tmp_path / skill_name / 'SKILL.md').resolve()
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
    settings = json.loads((tmp_path / 'native-run/agent-home/settings.json').read_text(encoding='utf-8'))
    assert settings['retry']['enabled'] and settings['compaction']['enabled']
    assert plan['recovery_policy'] == {'retry': settings['retry'], 'compaction': settings['compaction']}
    assert (plan['model'], plan['reasoning']) == ('gpt-6-astra', 'low')
    assert plan['provider'] == 'openai-codex'
    command = plan['command']
    assert command[command.index('--model') + 1] == 'openai-codex/gpt-6-astra'
    assert command[0] == 'pi' and '--no-mcp' not in command
    assert command[command.index('-e') + 1] == 'builtin:mcp'
    assert command[command.index('--tools') + 1] == 'read,bash,edit,write,mcp__node_repl__js,mcp__node_repl__js_reset,mcp__node_repl__js_add_node_module_dir,mcp__node_repl__turn_ended'
    assert not (tmp_path / 'native-run/agent-home/auth.json').exists()
    assert not (tmp_path / 'native-run/agent-home/config.toml').exists()
    assert ARMS == ('pi-acu', 'pi-cua', 'pi-computer-use', 'claude-acu', 'claude-cua')
    with pytest.raises(ValueError, match='unknown arm'):
        prepare('codex-computer-use', tmp_path / 'retired-run')
