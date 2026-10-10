"""Profile preparation is offline and does not launch an agent or touch the desktop."""

import json
import tomllib

from bench.run import prepare


# Supply filesystem/config boundary fixtures so ordinary checks need no installed CUA or Codex.
def skill_fixture(root, name):
    path = root / name
    path.mkdir()
    (path / 'SKILL.md').write_text(f'---\nname: {name}\ndescription: test fixture\n---\n', encoding='utf-8')
    return path


def test_prepare_pi_arms_share_scenario_and_do_not_inherit_user_configuration(tmp_path):
    acu = prepare('pi-acu', tmp_path / 'acu-run', skill=skill_fixture(tmp_path, 'acu'))
    cua = prepare('pi-cua', tmp_path / 'cua-run', skill=skill_fixture(tmp_path, 'cua-driver'))
    assert acu['scenario_sha256'] == cua['scenario_sha256']
    assert acu['model'] == cua['model'] == 'gpt-6.1-sol'
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


def test_prepare_codex_selects_only_native_computer_runtime_and_corresponding_skill(tmp_path):
    source_config = {'mcp_servers': {'node_repl': {'command': str(tmp_path / 'native-node.exe'), 'env': {}}}}
    unrelated_root = tmp_path / 'unrelated-skills'
    unrelated_root.mkdir()
    unrelated = skill_fixture(unrelated_root, 'cua-driver')
    builtin_root = tmp_path / 'builtin-skills'
    builtin_root.mkdir()
    builtin = skill_fixture(builtin_root, 'imagegen')
    plan = prepare('codex-computer-use', tmp_path / 'codex-run', skill=skill_fixture(tmp_path, 'computer-use'), native_config=source_config,
                   native_skill_roots=[unrelated_root], native_builtin_root=builtin_root)
    config = tomllib.loads((tmp_path / 'codex-run/agent-home/config.toml').read_text(encoding='utf-8'))
    assert config['model'] == 'gpt-6.1-sol'
    assert config['model_reasoning_effort'] == 'low'
    assert config['project_doc_max_bytes'] == 0
    assert not config['features']['plugins']
    assert not config['features']['hooks']
    assert not config['features']['browser_use']
    assert config['features']['skip_host_skill_discovery']
    assert list(config['mcp_servers']) == ['node_repl']
    assert json.loads(config['mcp_servers']['node_repl']['env']['NODE_REPL_TRUSTED_SERVICES']) == {'sky': '@oai/sky/service'}
    assert config['mcp_servers']['node_repl']['env']['SKY_CUA_NATIVE_PIPE'] == '0'
    overrides = {item['path']: item['enabled'] for item in config['skills']['config']}
    assert overrides[str(unrelated / 'SKILL.md')] is False
    assert overrides[str(tmp_path / 'codex-run/agent-home/skills/.system/imagegen/SKILL.md')] is False
    assert (tmp_path / 'codex-run/agent-home/skills/.system/imagegen/SKILL.md').read_text(encoding='utf-8') == (builtin / 'SKILL.md').read_text(encoding='utf-8')
    assert plan['skill_names'] == ['computer-use']
    assert '--no-daemon' in plan['command']
    assert '--ignore-rules' in plan['command']
