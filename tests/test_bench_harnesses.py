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


def pi_events(name, arguments):
    return [{'type': 'tool_execution_start', 'toolCallId': 'c', 'toolName': name, 'args': arguments},
            {'type': 'tool_execution_end', 'toolCallId': 'c', 'isError': False, 'result': {'content': []}}]


def claude_events(name, arguments):
    return [{'type': 'assistant', 'message': {'content': [{'type': 'tool_use', 'id': 'c', 'name': name, 'input': arguments}]}},
            {'type': 'user', 'message': {'content': [{'type': 'tool_result', 'tool_use_id': 'c', 'content': 'ok'}]}}]


def codex_events(item):
    item = {'id': 'c', **item}
    return [{'type': 'item.started', 'item': item}, {'type': 'item.completed', 'item': {**item, 'status': 'completed'}}]


EDIT = [{'oldText': 'Click 1', 'newText': 'Click 2'}]


# Each adapter owns its tool vocabulary; consumers see only the request kind and its normalized facts.
@pytest.mark.parametrize('harness,events,expected', [
    ('pi', pi_events('read', {'path': 'SKILL.md', 'offset': 1, 'limit': 50}), {'kind': 'read'}),
    ('pi', pi_events('write', {'path': 'draw.ahk', 'content': 'Click 1'}), {'kind': 'write', 'path': 'draw.ahk', 'content': 'Click 1'}),
    ('pi', pi_events('edit', {'path': 'draw.ahk', 'edits': EDIT}),
     {'kind': 'edit', 'path': 'draw.ahk', 'edits': [{'old': 'Click 1', 'new': 'Click 2'}], 'replace_all': False}),
    ('pi', pi_events('bash', {'command': 'acu run draw.ahk', 'timeout': 30}), {'kind': 'shell', 'command': 'acu run draw.ahk'}),
    ('pi', pi_events('mcp__node_repl__js', {'code': 'await sky.list_apps()', 'title': 'apps'}),
     {'kind': 'javascript_cell', 'code': 'await sky.list_apps()'}),
    ('pi', pi_events('mcp__node_repl__js_reset', {}), {'kind': 'javascript_runtime', 'resets': True}),
    ('pi', pi_events('mcp__node_repl__js_add_node_module_dir', {'path': 'C:/modules'}), {'kind': 'javascript_runtime', 'resets': False}),
    ('pi', pi_events('mcp__node_repl__turn_ended', {}), {'kind': 'javascript_runtime', 'resets': False}),
    ('pi', pi_events('grep', {'pattern': 'Click'}), {'kind': 'unknown'}),
    ('pi', pi_events('bash', {'command': ['acu', 'run']}), {'kind': 'unknown'}),
    # Pi's edit tool rewrites these shapes before applying them, and events keep the raw arguments.
    ('pi', pi_events('edit', {'path': 'draw.ahk', 'edits': '[{"oldText": "Click 1", "newText": "Click 2"}]'}),
     {'kind': 'edit', 'path': 'draw.ahk', 'edits': [{'old': 'Click 1', 'new': 'Click 2'}], 'replace_all': False}),
    ('pi', pi_events('edit', {'path': 'draw.ahk', 'edits': '{"oldText": "Click 1", "newText": "Click 2"}'}),
     {'kind': 'edit', 'path': 'draw.ahk', 'edits': [{'old': 'Click 1', 'new': 'Click 2'}], 'replace_all': False}),
    ('pi', pi_events('edit', {'path': 'draw.ahk', 'edits': EDIT[0]}),
     {'kind': 'edit', 'path': 'draw.ahk', 'edits': [{'old': 'Click 1', 'new': 'Click 2'}], 'replace_all': False}),
    ('pi', pi_events('edit', {'path': 'draw.ahk', 'oldText': 'Click 1', 'newText': 'Click 2'}),
     {'kind': 'edit', 'path': 'draw.ahk', 'edits': [{'old': 'Click 1', 'new': 'Click 2'}], 'replace_all': False}),
    ('pi', pi_events('edit', {'path': 'draw.ahk', 'edits': [{'oldText': 'a', 'newText': 'b'}], 'oldText': 'Click 1', 'newText': 'Click 2'}),
     {'kind': 'edit', 'path': 'draw.ahk', 'edits': [{'old': 'a', 'new': 'b'}, {'old': 'Click 1', 'new': 'Click 2'}], 'replace_all': False}),
    ('pi', pi_events('edit', {'path': 'draw.ahk', 'edits': 'not json'}), {'kind': 'unknown'}),
    ('pi', pi_events('edit', {'path': 'draw.ahk', 'edits': []}), {'kind': 'unknown'}),
    ('pi', pi_events('edit', {'path': 'draw.ahk', 'edits': [{'oldText': 'Click 1'}]}), {'kind': 'unknown'}),
    ('pi', pi_events('read', {}), {'kind': 'unknown'}),
    ('pi', pi_events('read', {'path': 1}), {'kind': 'unknown'}),
    ('pi', pi_events('mcp__node_repl__js_add_node_module_dir', {}), {'kind': 'unknown'}),
    ('pi', pi_events('Bash', {'command': 'acu run draw.ahk'}), {'kind': 'unknown'}),
    ('pi', pi_events('js', {'code': 'await sky.list_apps()'}), {'kind': 'unknown'}),
    ('pi', pi_events('read', None), {'kind': 'unknown'}),
    ('pi', pi_events('mcp__node_repl__js_reset', None), {'kind': 'unknown'}),
    ('claude', claude_events('Read', None), {'kind': 'unknown'}),
    ('claude', claude_events('Read', {'file_path': 'SKILL.md'}), {'kind': 'read'}),
    ('claude', claude_events('Read', {'path': 'SKILL.md'}), {'kind': 'unknown'}),
    ('claude', claude_events('Write', {'file_path': 'draw.ahk', 'content': 'Click 1'}),
     {'kind': 'write', 'path': 'draw.ahk', 'content': 'Click 1'}),
    ('claude', claude_events('Edit', {'file_path': 'draw.ahk', 'old_string': 'Click 1', 'new_string': 'Click 2', 'replace_all': True}),
     {'kind': 'edit', 'path': 'draw.ahk', 'edits': [{'old': 'Click 1', 'new': 'Click 2'}], 'replace_all': True}),
    ('claude', claude_events('Edit', {'file_path': 'draw.ahk', 'old_string': 'Click 1', 'new_string': 'Click 2'}),
     {'kind': 'edit', 'path': 'draw.ahk', 'edits': [{'old': 'Click 1', 'new': 'Click 2'}], 'replace_all': False}),
    ('claude', claude_events('Bash', {'command': 'acu run draw.ahk', 'description': 'run'}), {'kind': 'shell', 'command': 'acu run draw.ahk'}),
    ('claude', claude_events('Glob', {'pattern': '*.ahk'}), {'kind': 'unknown'}),
    ('claude', claude_events('Write', {'path': 'draw.ahk', 'content': 'Click 1'}), {'kind': 'unknown'}),
    ('codex', codex_events({'type': 'command_execution', 'command': 'acu run draw.ahk', 'aggregated_output': 'ok', 'exit_code': 0}),
     {'kind': 'shell', 'command': 'acu run draw.ahk'}),
    ('codex', codex_events({'type': 'mcp_tool_call', 'server': 'node_repl', 'tool': 'js', 'arguments': {'code': 'await sky.list_apps()'}}),
     {'kind': 'javascript_cell', 'code': 'await sky.list_apps()'}),
    ('codex', codex_events({'type': 'mcp_tool_call', 'server': 'node_repl', 'tool': 'js_reset', 'arguments': {}}),
     {'kind': 'javascript_runtime', 'resets': True}),
    ('codex', codex_events({'type': 'mcp_tool_call', 'server': 'computer-use', 'tool': 'js', 'arguments': {'code': 'x'}}), {'kind': 'unknown'}),
])
def test_adapters_map_their_tool_vocabulary_onto_request_kinds(harness, events, expected):
    from bench.arms import ARM_TABLE
    host = next(arm.harness for arm in ARM_TABLE.values() if arm.harness.name == harness)
    call, = host.analyse([{'elapsed_s': elapsed, 'event': event} for elapsed, event in enumerate(events)], 5)['tools']
    assert call['request'] == expected


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
    assert orphan['request'] == {'kind': 'unknown'}, 'a result without its request cannot have a kind'
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
