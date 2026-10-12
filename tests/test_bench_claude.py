"""Claude Code arm: stream-json measurement, isolation audit from the init event and transcript, and task time."""

import pytest

from bench.run import ARMS, analyse_claude, audit_claude_session, task_time

INIT = {'type': 'system', 'subtype': 'init', 'model': 'claude-opus-5-5', 'tools': ['Bash', 'Edit', 'Read', 'Write'],
        'mcp_servers': [], 'skills': [], 'slash_commands': []}


def stream(elapsed, inner):
    return {'elapsed_s': elapsed, 'event': {'type': 'stream_event', 'event': inner}}


def test_arms_group_comparisons_by_model_and_harness():
    assert ARMS == ('pi-acu', 'pi-cua', 'pi-computer-use', 'claude-acu', 'claude-cua')


def test_claude_metrics_time_responses_from_request_to_stop_and_count_final_usage_once():
    assistant = {'type': 'assistant', 'message': {'id': 'm1', 'model': 'claude-opus-5-5',
                 'content': [{'type': 'tool_use', 'id': 't1', 'name': 'Bash', 'input': {'command': 'acu run "C:/w/a.ahk"'}}],
                 'usage': {'input_tokens': 2, 'cache_creation_input_tokens': 100, 'cache_read_input_tokens': 0, 'output_tokens': 10}}}
    records = [
        {'elapsed_s': 1, 'event': INIT},
        {'elapsed_s': 2, 'event': {'type': 'system', 'subtype': 'status', 'status': 'requesting'}},
        stream(3, {'type': 'message_start', 'message': {'id': 'm1', 'model': 'claude-opus-5-5'}}),
        stream(3.5, {'type': 'content_block_delta', 'index': 0, 'delta': {'type': 'input_json_delta', 'partial_json': '{'}}),
        {'elapsed_s': 3.9, 'event': assistant},
        {'elapsed_s': 3.9, 'event': assistant},  # Claude Code repeats the assistant event per content block
        stream(4, {'type': 'message_delta', 'usage': {'output_tokens': 20}}),
        stream(4, {'type': 'message_stop'}),
        {'elapsed_s': 6, 'event': {'type': 'user', 'message': {'role': 'user', 'content': [{'type': 'tool_result', 'tool_use_id': 't1', 'content': 'ok', 'is_error': False}]}}},
        {'elapsed_s': 6.5, 'event': {'type': 'system', 'subtype': 'status', 'status': 'requesting'}},
        stream(7, {'type': 'message_start', 'message': {'id': 'm2', 'model': 'claude-opus-5-5'}}),
        stream(7.5, {'type': 'content_block_delta', 'index': 0, 'delta': {'type': 'text_delta', 'text': 'done'}}),
        {'elapsed_s': 7.6, 'event': {'type': 'assistant', 'message': {'id': 'm2', 'model': 'claude-opus-5-5', 'content': [{'type': 'text', 'text': 'done'}],
                                     'usage': {'input_tokens': 1, 'cache_creation_input_tokens': 5, 'cache_read_input_tokens': 100, 'output_tokens': 4}}}},
        stream(8, {'type': 'message_delta', 'usage': {'output_tokens': 5}}),
        stream(8, {'type': 'message_stop'}),
        {'elapsed_s': 9, 'event': {'type': 'result', 'subtype': 'success', 'is_error': False, 'duration_api_ms': 3500,
                                   'usage': {'input_tokens': 3, 'cache_creation_input_tokens': 105, 'cache_read_input_tokens': 100,
                                             'output_tokens': 25, 'output_tokens_details': {'thinking_tokens': 2}}}},
    ]
    result = analyse_claude(records, wall_s=10, reference_tps=10)
    assert result['agent_start_s'] == 1
    assert result['model_response_s'] == pytest.approx(3.5)  # request status to message_stop, both responses
    assert result['model_turns'][0]['first_visible_delta_s'] == pytest.approx(1.5)
    assert result['model_turns'][0]['output_tokens'] == 20
    assert result['tool_busy_s'] == pytest.approx(2.1)
    assert result['tokens'] == {'input_uncached': 3, 'cache_read': 100, 'cache_write': 105,
                                'output_including_reasoning': 25, 'reasoning_subset': 2, 'total': 233}
    assert result['agent_completed'] and result['token_counts_complete']
    assert result['reported_api_duration_s'] == 3.5
    assert result['estimated_wall_at_reference_tps_s'] == pytest.approx(10 - 3.5 + 2.5)


def test_claude_run_without_a_final_result_is_incomplete_not_zero():
    records = [{'elapsed_s': 1, 'event': INIT},
               {'elapsed_s': 2, 'event': {'type': 'assistant', 'message': {'id': 'm1', 'model': 'claude-opus-5-5', 'content': [],
                                          'usage': {'input_tokens': 7, 'cache_creation_input_tokens': 0, 'cache_read_input_tokens': 0, 'output_tokens': 3}}}}]
    result = analyse_claude(records, wall_s=3)
    assert not result['agent_completed'] and not result['token_counts_complete']
    assert result['tokens']['total'] == 10 and result['model_response_s'] is None


@pytest.mark.parametrize('skill_name', ['acu', 'cua-driver'])
def test_claude_audit_requires_init_and_transcript_evidence_and_rejects_pollution(skill_name):
    records = [{'elapsed_s': 1, 'event': INIT}]
    entries = [{'type': 'assistant', 'effort': 'low', 'requestedModel': 'claude-opus-5-5',
                'message': {'model': 'claude-opus-5-5', 'content': [{'type': 'tool_use', 'name': 'Read', 'input': {'file_path': 'C:\\repo\\acu\\SKILL.md'}}]}}]
    selected = f'C:/repo/{skill_name}'
    entries[0]['message']['content'][0]['input']['file_path'] = selected + '/SKILL.md'
    audit = audit_claude_session(records, entries, selected)
    assert audit['passed'] and audit['skills'] == [skill_name]
    entries[0]['message']['content'][0]['input']['file_path'] = 'C:/repo/acu/SKILL.md'
    assert not audit_claude_session([], entries, 'C:/repo/acu')['passed']
    assert not audit_claude_session(records, [], 'C:/repo/acu')['passed']
    polluted = [{'elapsed_s': 1, 'event': {**INIT, 'skills': ['deep-research']}}]
    assert not audit_claude_session(polluted, entries, 'C:/repo/acu')['passed']
    assert not audit_claude_session([{'elapsed_s': 1, 'event': {**INIT, 'tools': ['Bash', 'Read', 'WebFetch']}}], entries, 'C:/repo/acu')['passed']
    assert not audit_claude_session(records, [{**entries[0], 'effort': 'high'}], 'C:/repo/acu')['passed']
    other = {**entries[0], 'message': {'model': 'claude-opus-5-5', 'content': [{'type': 'tool_use', 'name': 'Read', 'input': {'file_path': 'C:/global/cua-driver/SKILL.md'}}]}}
    assert 'other skill read: C:/global/cua-driver/SKILL.md' in audit_claude_session(records, [*entries, other], 'C:/repo/acu')['problems']


def test_task_time_ends_at_the_last_computer_use_call_not_the_evidence_write(tmp_path):
    (tmp_path / 'helper.py').write_text("subprocess.run(['cua-driver', 'click'])", encoding='utf-8')
    tools = [
        {'name': 'read', 'start_s': 2, 'end_s': 2.1, 'text': '{"path": "SKILL.md"}'},
        {'name': 'bash', 'start_s': 5, 'end_s': 6, 'text': '{"command": "acu run \\"C:/w/launch.ahk\\""}'},
        {'name': 'bash', 'start_s': 10, 'end_s': 14, 'text': '{"command": "python helper.py One Two"}'},
        {'name': 'write', 'start_s': 20, 'end_s': 20.1, 'text': '{"path": "result.json", "content": "acu run cua-driver"}'},
        {'name': 'bash', 'start_s': 21, 'end_s': 21.5, 'text': '{"command": "cat result.json"}'},
    ]
    assert task_time(1, tools, r'\bacu run\b', tmp_path)['task_s'] == 5
    assert task_time(1, tools, r'cua-driver', tmp_path)['task_s'] == 13
    assert task_time(None, tools, r'cua-driver', tmp_path)['task_s'] is None
    assert task_time(1, tools, r'\bsky\.', tmp_path)['task_s'] is None


def test_task_time_follows_helpers_a_computer_use_cell_defined_in_a_persistent_repl(tmp_path):
    cells = [
        {'name': 'node_repl.js', 'start_s': 10, 'end_s': 13, 'text': '{"code": "globalThis.tap=async(x,y)=>{await sky.click({x,y}); state=await sky.get_window_state({})}; await tap(1,2);"}'},
        {'name': 'node_repl.js', 'start_s': 20, 'end_s': 23, 'text': '{"code": "await tap(3,4);"}'},
        {'name': 'node_repl.js', 'start_s': 30, 'end_s': 30.1, 'text': '{"code": "await fs.writeFile(nodeRepl.cwd+\'/result.json\', JSON.stringify({window_id: targetWindow.id}));"}'},
    ]
    result = task_time(1, cells, r'\bsky\.', tmp_path)
    assert result['task_s'] == 22 and result['computer_use_calls'] == 2
