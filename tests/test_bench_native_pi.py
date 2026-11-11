"""Native Pi isolation is checked from persisted tool declarations, not launch flags alone."""

from bench.run import NATIVE_TOOLS, TOOLS, audit_pi_session


def test_native_pi_audit_accepts_only_the_selected_runtime_and_frozen_model():
    entries = [
        {'type': 'model_change', 'provider': 'openai-codex', 'modelId': 'gpt-6-astra'},
        {'type': 'thinking_level_change', 'thinkingLevel': 'low'},
        {'type': 'message', 'message': {'role': 'system',
            'sections': {'skills': '<name>computer-use</name>'},
            'toolsAdded': [{'name': name} for name in TOOLS]}},
        {'type': 'message', 'message': {'role': 'system',
            'sections': {'mcp_servers': 'node_repl native desktop'},
            'toolsAdded': [{'name': name} for name in NATIVE_TOOLS]}},
        {'type': 'message', 'message': {'role': 'assistant', 'model': 'gpt-6-astra', 'thinkingLevel': 'low',
            'content': [{'type': 'toolCall', 'name': 'mcp__node_repl__js', 'arguments': {'code': 'await sky.list_apps()'}}]}},
    ]
    assert audit_pi_session(entries, 'computer-use')['passed']
    other_provider = [{**entries[0], 'provider': 'openai'}, *entries[1:]]
    assert not audit_pi_session(other_provider, 'computer-use')['passed']
    assert not audit_pi_session(entries[:3], 'computer-use')['passed'], 'missing MCP declarations cannot pass'
    polluted = {'type': 'message', 'message': {'role': 'system', 'toolsAdded': [{'name': 'mcp__browser__click'}]}}
    assert not audit_pi_session([*entries, polluted], 'computer-use')['passed']
    removed = {'type': 'message', 'message': {'role': 'system', 'toolsRemoved': [NATIVE_TOOLS[0]]}}
    assert not audit_pi_session([*entries, removed], 'computer-use')['passed']
    old = [{'type': 'model_change', 'provider': 'openai', 'modelId': 'gpt-6.1-sol'},
           *entries[1:3]]
    assert not audit_pi_session(old, 'acu')['passed']
