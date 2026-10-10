"""Codex audit checks against persisted turn context rather than its launch flags alone."""

from bench.run import audit_codex_session


def test_codex_runtime_audit_rejects_polluted_skills_and_wrong_model_or_reasoning():
    entries = [
        {'type': 'turn_context', 'payload': {'model': 'gpt-6.1-sol', 'effort': 'low'}},
        {'type': 'response_item', 'payload': {'role': 'developer', 'content': [{'type': 'input_text', 'text': 'The only enabled skill is computer-use. Read C:/native/skills/computer-use/SKILL.md before desktop interaction.'}]}},
    ]
    assert audit_codex_session(entries)['passed']
    other_skill = {'type': 'response_item', 'payload': {'role': 'developer', 'content': [{'type': 'input_text', 'text': '### Available skills\n- cua-driver: other desktop skill (file: C:/global/cua-driver/SKILL.md)'}]}}
    assert not audit_codex_session([*entries, other_skill])['passed']
    assert not audit_codex_session([*entries, {'type': 'turn_context', 'payload': {'model': 'gpt-6-astra', 'effort': 'high'}}])['passed']
    assert not audit_codex_session([])['passed']
