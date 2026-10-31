"""Harness transcripts share one result-bearing tool-call contract."""
import pytest

from bench.run import analyse_claude, analyse_pi


@pytest.mark.parametrize('analyse,name,events', [
    (analyse_pi, 'bash', [
        {'type': 'tool_execution_start', 'toolCallId': 'shot', 'toolName': 'bash', 'args': {'command': 'capture'}},
        {'type': 'tool_execution_end', 'toolCallId': 'shot', 'isError': False,
         'result': {'content': [{'type': 'text', 'text': 'output'}], 'details': {'truncation': {'truncated': True}}}},
    ]),
    (analyse_claude, 'Bash', [
        {'type': 'assistant', 'message': {'content': [{'type': 'tool_use', 'id': 'shot', 'name': 'Bash', 'input': {'command': 'capture'}}]}},
        {'type': 'user', 'message': {'content': [{'type': 'tool_result', 'tool_use_id': 'shot', 'content': '<persisted-output>output'}]}},
    ]),
])
def test_normalized_calls_keep_results_and_distinguish_truncation_from_tool_errors(analyse, name, events):
    records = [{'elapsed_s': elapsed, 'event': event} for elapsed, event in zip((2, 5), events)]
    call, = analyse(records, 7)['tools']
    assert call['name'] == name
    assert call['arguments'] == {'command': 'capture'}
    assert (call['start_s'], call['end_s'], call['duration_s']) == (2, 5, 3)
    assert call['result'] == (events[1].get('result') or '<persisted-output>output')
    assert call['matched'] and call['completed'] and call['truncated']
    assert call['is_error'] is False


def test_arm_table_routes_all_current_profiles_and_archived_codex():
    from bench.arms import ARM_TABLE, ARMS

    assert ARMS == ('pi-acu', 'pi-cua', 'pi-computer-use', 'claude-acu', 'claude-cua')
    assert [(arm.harness.name, arm.skill_name, arm.runtime) for arm in ARM_TABLE.values()] == [
        ('pi', 'acu', 'ACU'), ('pi', 'cua-driver', 'CUA'), ('pi', 'computer-use', 'Codex computer use'),
        ('claude', 'acu', 'ACU'), ('claude', 'cua-driver', 'CUA'), ('codex', 'computer-use', 'Codex computer use')]
    assert not ARM_TABLE['codex-computer-use'].harness.live
    assert ARM_TABLE['pi-cua'].uses_cua_daemon
    assert not ARM_TABLE['pi-computer-use'].uses_cua_daemon


def test_archived_codex_retains_result_arguments_and_unknown_request_timing():
    from bench.arms import ARM_TABLE
    records = [
        {'elapsed_s': 4, 'event': {'type': 'item.completed', 'item': {
            'id': 'native', 'type': 'mcp_tool_call', 'server': 'node_repl', 'tool': 'js',
            'arguments': {'code': 'await sky.get_app_state()'}, 'result': {'content': []}, 'status': 'completed'}}},
        {'elapsed_s': 5, 'event': {'type': 'turn.completed', 'usage': {'input_tokens': 20, 'cached_input_tokens': 5, 'output_tokens': 10}}},
    ]
    result = ARM_TABLE['codex-computer-use'].harness.analyse(records, 6)
    call, = result['tools']
    assert call['result'] == {'content': []}
    assert call['start_s'] is None and call['duration_s'] is None
    assert call['completed'] and call['matched'], 'completed Codex items contain their own request arguments'
    assert call['is_error'] is None, 'Codex does not report the Pi/Claude tool error boolean'
    assert result['tokens']['total'] == 30


@pytest.mark.parametrize('analyse,start,end', [
    (analyse_pi,
     {'type': 'tool_execution_start', 'toolCallId': 'shot', 'toolName': 'bash', 'args': {'command': 'acu run shot.ahk'}},
     {'type': 'tool_execution_end', 'toolCallId': 'shot', 'result': {'content': []}}),
    (analyse_claude,
     {'type': 'assistant', 'message': {'content': [{'type': 'tool_use', 'id': 'shot', 'name': 'Bash', 'input': {'command': 'acu run shot.ahk'}}]}},
     {'type': 'user', 'message': {'content': [{'type': 'tool_result', 'tool_use_id': 'shot', 'content': []}]}}),
])
def test_missing_request_result_and_error_flags_remain_distinct(analyse, start, end):
    from bench.efficiency import measure_efficiency
    records = [{'elapsed_s': 2, 'event': start}, {'elapsed_s': 5, 'event': end}]
    unfinished = analyse(records[:1], 7)
    pending, = unfinished['tools']
    assert pending['matched'] and not pending['completed'] and pending['result'] is None
    assert pending['end_s'] is None and pending['duration_s'] is None
    assert unfinished['unfinished_tools'] == ['shot']
    measured = measure_efficiency(unfinished, 'pi-acu')
    assert measured['computer_use']['call_count'] == 0
    assert measured['computer_use']['busy_seconds'] is None
    orphan, = analyse(records[1:], 7)['tools']
    assert not orphan['matched'] and orphan['completed'] and orphan['name'] == 'unmatched'
    assert orphan['arguments'] is None and orphan['start_s'] is None
    matched = analyse(records, 7)
    call, = matched['tools']
    assert call['is_error'] is (None if analyse is analyse_pi else False)
    assert matched['tool_busy_s'] == 3


def test_claude_role_misplaced_blocks_keep_runtime_audit_pairing():
    records = [
        {'elapsed_s': 2, 'event': {'type': 'user', 'message': {'content': [{'type': 'tool_use', 'id': 'odd', 'name': 'Bash', 'input': {'command': 'capture'}}]}}},
        {'elapsed_s': 5, 'event': {'type': 'assistant', 'message': {'content': [{'type': 'tool_result', 'tool_use_id': 'odd', 'content': 'captured'}]}}},
    ]
    call, = analyse_claude(records, 7)['tools']
    assert call['matched'] and call['completed'] and call['result'] == 'captured'
