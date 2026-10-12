"""Native Pi isolation is checked from persisted tool declarations, not launch flags alone."""

from bench.run import NATIVE_TOOLS, TOOLS, audit_pi_session, task_time


def test_native_pi_audit_accepts_only_the_selected_runtime_and_frozen_model():
    entries = [
        {'type': 'model_change', 'provider': 'openai', 'modelId': 'gpt-6-astra'},
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
    assert not audit_pi_session(entries[:3], 'computer-use')['passed'], 'missing MCP declarations cannot pass'
    polluted = {'type': 'message', 'message': {'role': 'system', 'toolsAdded': [{'name': 'mcp__browser__click'}]}}
    assert not audit_pi_session([*entries, polluted], 'computer-use')['passed']
    removed = {'type': 'message', 'message': {'role': 'system', 'toolsRemoved': [NATIVE_TOOLS[0]]}}
    assert not audit_pi_session([*entries, removed], 'computer-use')['passed']
    old = [{'type': 'model_change', 'provider': 'openai', 'modelId': 'gpt-6.1-sol'},
           *entries[1:3]]
    assert not audit_pi_session(old, 'acu')['passed']


def test_native_pi_timing_includes_persistent_js_helpers_but_not_result_evidence(tmp_path):
    calls = [
        {'name': 'mcp__node_repl__js', 'start_s': 1, 'end_s': 2,
         'text': 'globalThis.next=async()=>{await sky.click({window:w,x:1,y:2})}; await next()'},
        {'name': 'mcp__node_repl__js', 'start_s': 3, 'end_s': 4, 'text': 'await next()'},
        {'name': 'write', 'start_s': 5, 'end_s': 6, 'text': 'result.json\n{}'},
    ]
    result = task_time(.5, calls, r'\bsky\.', tmp_path)
    assert result['task_s'] == 3.5 and result['computer_use_calls'] == 2
