"""Quiet checks of the benchmark's public launch, isolation-audit, and measurement interfaces."""

import pytest

from bench.run import analyse_pi, audit_pi_session, pi_command


def test_pi_launch_exposes_only_selected_skill_with_fixed_model_and_reasoning(tmp_path):
    command = pi_command(tmp_path, tmp_path / 'acu', 'task')
    assert command[1:6] == ['-ne', '-ns', '-nc', '-np', '--no-themes']
    assert command[command.index('--skill') + 1] == str(tmp_path / 'acu')
    assert command[command.index('--model') + 1] == 'openai/gpt-6.1-sol'
    assert command[command.index('--thinking') + 1] == 'low'
    assert command[command.index('--tools') + 1] == 'read,bash,edit,write'
    assert '--continue' not in command and '--resume' not in command


def test_metrics_count_final_usage_once_and_do_not_double_count_reasoning():
    message = {'role': 'assistant', 'model': 'gpt-6.1-sol', 'thinkingLevel': 'low',
               'usage': {'input': 100, 'cacheRead': 50, 'cacheWrite': 0,
                         'output': 20, 'reasoning': 5, 'totalTokens': 170},
               'content': [], 'stopReason': 'stop', 'durationMs': 2000}
    records = [
        {'elapsed_s': 1, 'event': {'type': 'agent_start'}},
        {'elapsed_s': 2, 'event': {'type': 'message_start', 'message': {'role': 'assistant'}}},
        {'elapsed_s': 3, 'event': {'type': 'message_update', 'usage': message['usage'], 'assistantMessageEvent': {'type': 'text_delta', 'delta': 'a'}}},
        {'elapsed_s': 4, 'event': {'type': 'message_end', 'message': message}},
        {'elapsed_s': 4, 'event': {'type': 'turn_end', 'message': message}},
        {'elapsed_s': 4, 'event': {'type': 'tool_execution_start', 'toolCallId': 'a', 'toolName': 'bash'}},
        {'elapsed_s': 4.5, 'event': {'type': 'tool_execution_start', 'toolCallId': 'b', 'toolName': 'read'}},
        {'elapsed_s': 5.5, 'event': {'type': 'tool_execution_end', 'toolCallId': 'b', 'toolName': 'read', 'isError': False}},
        {'elapsed_s': 6, 'event': {'type': 'tool_execution_end', 'toolCallId': 'a', 'toolName': 'bash', 'isError': False}},
        {'elapsed_s': 7, 'event': {'type': 'agent_settled', 'aborted': False}},
    ]
    result = analyse_pi(records, wall_s=8, reference_tps=10)
    assert result['tokens'] == {'input_uncached': 100, 'cache_read': 50, 'cache_write': 0, 'output_including_reasoning': 20, 'reasoning_subset': 5, 'total': 170}
    assert result['model_response_s'] == 2
    assert result['tool_busy_s'] == 2  # union, not 3 seconds summed across concurrent tools
    assert result['agent_elapsed_s'] == 6
    assert result['effective_output_tps'] == 10
    assert result['estimated_wall_at_reference_tps_s'] == 8
    assert result['model_turns'][0]['first_visible_delta_s'] == 1


def test_model_timing_includes_wait_before_pi_emits_message_start():
    records = [
        {'elapsed_s': 2, 'event': {'type': 'message_start', 'message': {'role': 'assistant'}}},
        {'elapsed_s': 3, 'event': {'type': 'message_update', 'assistantMessageEvent': {'type': 'text_delta'}}},
        {'elapsed_s': 4, 'event': {'type': 'message_end', 'message': {'role': 'assistant', 'content': [], 'stopReason': 'stop', 'durationMs': 4000, 'usage': {'input': 100, 'output': 20, 'totalTokens': 120}}}},
    ]
    result = analyse_pi(records, wall_s=5, reference_tps=10)
    assert result['model_response_s'] == 4
    assert result['effective_output_tps'] == 5
    assert result['model_turns'][0]['first_visible_delta_s'] == 3
    assert result['estimated_wall_at_reference_tps_s'] == 3


def test_isolation_audit_rejects_extra_skills_context_and_wrong_reasoning():
    entries = [
        {'type': 'model_change', 'provider': 'openai', 'modelId': 'gpt-6.1-sol'},
        {'type': 'thinking_level_change', 'thinkingLevel': 'low'},
        {'type': 'message', 'message': {'role': 'system', 'sections': {'skills': '<name>acu</name>', 'cwd': '/work'}, 'toolsAdded': [{'name': n} for n in ['read', 'bash', 'edit', 'write']]}},
    ]
    assert audit_pi_session(entries, 'acu')['passed']
    polluted = [*entries, {'type': 'message', 'message': {'role': 'system', 'sections': {'skills': '<name>acu</name><name>cua-driver</name>', 'project_context': 'AGENTS.md'}}}]
    assert not audit_pi_session(polluted, 'acu')['passed']
    assert not audit_pi_session([*entries, {'type': 'thinking_level_change', 'thinkingLevel': 'high'}], 'acu')['passed']


def test_failed_or_aborted_model_run_is_not_reported_as_success():
    records = [{'elapsed_s': 1, 'event': {'type': 'agent_start'}},
               {'elapsed_s': 2, 'event': {'type': 'message_start', 'message': {'role': 'assistant'}}},
               {'elapsed_s': 3, 'event': {'type': 'message_end', 'message': {'role': 'assistant', 'content': [], 'usage': {'input': 10, 'output': 0, 'totalTokens': 10}, 'stopReason': 'error', 'errorMessage': 'quota', 'durationMs': 1000}}},
               {'elapsed_s': 3, 'event': {'type': 'agent_settled', 'aborted': True}}]
    result = analyse_pi(records, wall_s=3)
    assert not result['agent_completed']
    assert result['model_errors'] == ['quota']
    assert result['effective_output_tps'] == 0
