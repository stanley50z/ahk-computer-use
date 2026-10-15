"""Quiet checks of the benchmark's public launch, isolation-audit, and measurement interfaces."""

import pytest

from bench.run import analyse_pi, audit_pi_session, pi_command


def test_pi_launch_exposes_only_selected_skill_with_fixed_model_and_reasoning(tmp_path):
    command = pi_command(tmp_path, tmp_path / 'acu', 'task')
    assert command[1:6] == ['-ne', '-ns', '-nc', '-np', '--no-themes']
    assert command[command.index('--skill') + 1] == str(tmp_path / 'acu')
    assert command[command.index('--model') + 1] == 'openai-codex/gpt-6-astra'
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


@pytest.mark.parametrize('recovery', ['retry', 'compaction'])
def test_pi_recovery_can_complete_without_erasing_interruption_or_unknown_usage(recovery):
    error = '503 upstream connect error'
    failed = {'role': 'assistant', 'content': [], 'usage': {'input': 0, 'output': 0, 'totalTokens': 0},
              'stopReason': 'error', 'errorMessage': error}
    success = {'role': 'assistant', 'content': [], 'usage': {'input': 100, 'output': 20, 'totalTokens': 120},
               'stopReason': 'stop'}
    records = [{'elapsed_s': 0, 'event': {'type': 'agent_start'}},
               {'elapsed_s': 1, 'event': {'type': 'tool_execution_start', 'toolCallId': 'once', 'toolName': 'bash', 'args': {'command': 'acu run draw.ahk'}}},
               {'elapsed_s': 2, 'event': {'type': 'tool_execution_end', 'toolCallId': 'once', 'isError': False}},
               {'elapsed_s': 3, 'event': {'type': 'message_start', 'message': {'role': 'assistant'}}},
               {'elapsed_s': 4, 'event': {'type': 'message_end', 'message': failed}}]
    if recovery == 'retry':
        records += [{'elapsed_s': 4, 'event': {'type': 'auto_retry_start', 'attempt': 1, 'maxAttempts': 3, 'delayMs': 2000, 'errorMessage': error}},
                    {'elapsed_s': 6, 'event': {'type': 'auto_retry_end', 'success': True, 'attempt': 1}}]
    else:
        records += [{'elapsed_s': 4, 'event': {'type': 'compaction_start', 'reason': 'overflow'}},
                    {'elapsed_s': 6, 'event': {'type': 'compaction_end', 'reason': 'overflow', 'aborted': False, 'willRetry': True,
                     'result': {'usage': {'input': 10, 'cacheRead': 5, 'output': 5, 'totalTokens': 20}}}}]
    records += [{'elapsed_s': 7, 'event': {'type': 'message_start', 'message': {'role': 'assistant'}}},
                {'elapsed_s': 8, 'event': {'type': 'message_end', 'message': success}},
                {'elapsed_s': 9, 'event': {'type': 'agent_settled', 'aborted': False}}]
    result = analyse_pi(records, wall_s=9)
    assert result['agent_completed'] is True
    assert result['unexpected_failure'] is None
    assert result['recovered_provider_errors'] == [error]
    assert result['model_errors'] == [error], 'original errors remain diagnostic evidence'
    assert result['token_counts_complete'] is False, 'unreported failed-request consumption is not invented'
    assert result['tokens']['total'] == (140 if recovery == 'compaction' else 120)
    assert [tool['id'] for tool in result['tools']] == ['once'], 'recovery does not replay completed UI calls'


def test_pi_interrupted_turn_can_be_excluded_without_claiming_full_request_consumption():
    failed = {'role': 'assistant', 'content': [], 'stopReason': 'error', 'errorMessage': 'interrupted',
              'usage': {'input': 7, 'output': 3, 'cacheRead': 2, 'totalTokens': 12}}
    success = {'role': 'assistant', 'content': [], 'stopReason': 'stop',
               'usage': {'input': 100, 'output': 20, 'totalTokens': 120}}
    records = [
        {'elapsed_s': 0, 'event': {'type': 'agent_start'}},
        {'elapsed_s': 1, 'event': {'type': 'message_start', 'message': {'role': 'assistant'}}},
        {'elapsed_s': 2, 'event': {'type': 'message_end', 'message': failed}},
        {'elapsed_s': 3, 'event': {'type': 'message_start', 'message': {'role': 'assistant'}}},
        {'elapsed_s': 4, 'event': {'type': 'message_end', 'message': success}},
        {'elapsed_s': 5, 'event': {'type': 'agent_settled', 'aborted': False}},
    ]
    original = analyse_pi(records, wall_s=5)
    counted = analyse_pi(records, wall_s=5, exclude_interrupted_turns=True)
    assert original['tokens']['total'] == 132 and not original['token_counts_complete']
    assert counted['tokens']['total'] == 120 and counted['token_counts_complete']
    assert counted['agent_completed'] and counted['model_errors'] == ['interrupted']
    assert counted['recovered_provider_errors'] == ['interrupted']
    assert len(counted['model_turns']) == 1
    assert len(counted['excluded_model_turns']) == 1
    assert counted['excluded_model_turns'][0]['usage']['totalTokens'] == 12
    assert counted['token_usage_scope'] == 'excluding-interrupted-turns'
    assert counted['full_request_consumption_complete'] is False
    from bench.efficiency import measure_efficiency
    benchmark = measure_efficiency(counted, 'pi-cua')
    assert benchmark['policy'] == 'tokens-and-computer-use-excluding-interrupted-turns-v1'
    assert benchmark['token_usage_scope'] == 'excluding-interrupted-turns'
    assert benchmark['excluded_model_turn_count'] == 1


@pytest.mark.parametrize('exclude_interrupted_turns', [False, True])
def test_pi_compaction_usage_is_counted_once_and_missing_usage_stays_unknown(exclude_interrupted_turns):
    usage = {'input': 7, 'cacheRead': 3, 'output': 5, 'reasoning': 2, 'totalTokens': 15}
    records = [{'elapsed_s': 0, 'event': {'type': 'agent_start'}},
               {'elapsed_s': 1, 'event': {'type': 'compaction_start', 'reason': 'threshold'}},
               {'elapsed_s': 2, 'event': {'type': 'compaction_end', 'reason': 'threshold', 'aborted': False,
                                        'willRetry': False, 'result': {'usage': usage}}},
               {'elapsed_s': 3, 'event': {'type': 'message_start', 'message': {'role': 'assistant'}}},
               {'elapsed_s': 4, 'event': {'type': 'message_end', 'message': {'role': 'assistant', 'content': [],
                'stopReason': 'stop', 'durationMs': 1000,
                'usage': {'input': 10, 'output': 2, 'reasoning': 1, 'totalTokens': 12}}}},
               {'elapsed_s': 5, 'event': {'type': 'agent_settled', 'aborted': False}}]
    result = analyse_pi(records, wall_s=5, reference_tps=10, exclude_interrupted_turns=exclude_interrupted_turns)
    assert result['agent_completed'] and result['token_counts_complete']
    assert result['tokens'] == {'input_uncached': 17, 'cache_read': 3, 'cache_write': 0,
                               'output_including_reasoning': 7, 'reasoning_subset': 3, 'total': 27}
    assert result['compactions'] == 1 and len(result['recovery_events']) == 2
    assert result['model_response_s'] is None, 'unexposed summarization timing must not produce a misleading model rate'
    assert result['estimated_wall_at_reference_tps_s'] is None
    summary_retry = [{'elapsed_s': .5, 'event': {'type': 'summarization_retry_scheduled', 'attempt': 1, 'errorMessage': '503'}}]
    retried = analyse_pi(records[:1] + summary_retry + records[1:], wall_s=5, exclude_interrupted_turns=exclude_interrupted_turns)
    assert retried['agent_completed'] and not retried['token_counts_complete']
    assert retried['tokens']['total'] == 27, 'failed summary consumption remains unknown despite reported successful summary usage'
    records[2]['event']['result'].pop('usage')
    missing = analyse_pi(records, wall_s=5, exclude_interrupted_turns=exclude_interrupted_turns)
    assert missing['agent_completed'] and not missing['token_counts_complete']
    assert missing['tokens']['total'] == 12, 'retain recorded consumption only, not fabricated summary usage'


@pytest.mark.parametrize('exclude_interrupted_turns', [False, True])
def test_pi_recovered_error_does_not_hide_a_later_terminal_failure_or_user_abort(exclude_interrupted_turns):
    records = []
    for index, (reason, error) in enumerate([('error', 'first 503'), ('toolUse', None), ('error', 'last 503')]):
        message = {'role': 'assistant', 'content': [], 'stopReason': reason,
                   'usage': {'input': 0, 'output': 0, 'totalTokens': 0}}
        if error:
            message['errorMessage'] = error
        records += [{'elapsed_s': index*2, 'event': {'type': 'message_start', 'message': {'role': 'assistant'}}},
                    {'elapsed_s': index*2+1, 'event': {'type': 'message_end', 'message': message}}]
    records += [{'elapsed_s': 6, 'event': {'type': 'auto_retry_end', 'success': False, 'attempt': 3, 'finalError': 'last 503'}},
                {'elapsed_s': 7, 'event': {'type': 'agent_settled', 'aborted': False}}]
    result = analyse_pi(records, wall_s=7, exclude_interrupted_turns=exclude_interrupted_turns)
    assert not result['agent_completed'] and not result['token_counts_complete']
    assert result['recovered_provider_errors'] == ['first 503']
    assert result['unexpected_failure'] == {'kind': 'unexpected_provider_failure', 'errors': ['last 503']}
    records[-2]['event']['finalError'] = 'Retry cancelled'
    records[-1]['event']['aborted'] = True
    cancelled = analyse_pi(records, wall_s=7, exclude_interrupted_turns=exclude_interrupted_turns)
    assert not cancelled['agent_completed'] and cancelled['unexpected_failure'] is None
    assert cancelled['model_errors'] == ['first 503', 'last 503'], 'raw provider errors survive cancellation'
    records.pop()  # A host cancellation can kill the CLI during backoff before it emits settled/cancelled events.
    records.pop()
    host_cancelled = analyse_pi(records, wall_s=7, cancelled=True, exclude_interrupted_turns=exclude_interrupted_turns)
    assert not host_cancelled['agent_completed'] and host_cancelled['unexpected_failure'] is None
    assert host_cancelled['model_errors'] == ['first 503', 'last 503']


def test_pi_a_later_unsettled_run_cannot_reuse_an_earlier_completion():
    records = [{'elapsed_s': 0, 'event': {'type': 'agent_start'}},
               {'elapsed_s': 1, 'event': {'type': 'message_start', 'message': {'role': 'assistant'}}},
               {'elapsed_s': 2, 'event': {'type': 'message_end', 'message': {'role': 'assistant', 'content': [],
                'stopReason': 'stop', 'usage': {'input': 10, 'output': 2, 'totalTokens': 12}}}},
               {'elapsed_s': 3, 'event': {'type': 'agent_settled', 'aborted': False}},
               {'elapsed_s': 4, 'event': {'type': 'agent_start'}},
               {'elapsed_s': 5, 'event': {'type': 'message_start', 'message': {'role': 'assistant'}}},
               {'elapsed_s': 6, 'event': {'type': 'message_end', 'message': {'role': 'assistant', 'content': [],
                'stopReason': 'error', 'errorMessage': '503', 'usage': {'input': 0, 'output': 0, 'totalTokens': 0}}}}]
    assert not analyse_pi(records, wall_s=6)['agent_completed']


def test_pi_unresolved_compaction_failure_is_not_a_completed_session():
    records = [{'elapsed_s': 0, 'event': {'type': 'message_start', 'message': {'role': 'assistant'}}},
               {'elapsed_s': 1, 'event': {'type': 'message_end', 'message': {'role': 'assistant', 'content': [],
                'stopReason': 'toolUse', 'usage': {'input': 10, 'output': 2, 'totalTokens': 12}}}},
               {'elapsed_s': 2, 'event': {'type': 'compaction_end', 'reason': 'overflow', 'aborted': False,
                                        'result': None, 'willRetry': False, 'errorMessage': 'Compaction failed'}},
               {'elapsed_s': 3, 'event': {'type': 'agent_settled', 'aborted': False}}]
    result = analyse_pi(records, wall_s=3)
    assert not result['agent_completed'] and not result['token_counts_complete']
    assert result['recovery_errors'] == ['Compaction failed']
    assert result['unexpected_failure'] is None, 'a summary failure without a provider response is not automatically a provider fault'
    records[2]['event'].pop('errorMessage')
    records[2]['event']['aborted'] = True
    aborted = analyse_pi(records, wall_s=3)
    assert not aborted['agent_completed'] and aborted['recovery_errors'] == ['Compaction aborted']
    assert not analyse_pi(records[:2] + records[-1:], wall_s=3)['agent_completed'], 'a tool-use response is not final completion'


@pytest.mark.parametrize(('recovered', 'export_failure', 'inspection_refused'),
                         [(False, False, False), (True, False, False), (True, True, False), (True, False, True)])
def test_controller_preserves_actor_outcome_and_separates_maintainer_export_failure(tmp_path, monkeypatch, recovered, export_failure, inspection_refused):
    import json
    import sys
    from bench import run as bench

    executable = tmp_path / 'programs/Adobe/Adobe Illustrator Fixture/Support Files/Contents/Windows/Illustrator.exe'
    executable.parent.mkdir(parents=True)
    executable.touch()
    monkeypatch.setenv('ProgramFiles', str(tmp_path / 'programs'))
    plan = bench.prepare('pi-acu', tmp_path / 'trial', scenario='illustrator-pen-export')
    directory = tmp_path / 'trial'
    credential = tmp_path / 'fixture-auth.json'
    credential.write_text('{}', encoding='utf-8')
    monkeypatch.setitem(bench.CREDENTIALS, 'pi', (str(credential), 'auth.json'))
    entries = [{'type': 'model_change', 'provider': 'openai-codex', 'modelId': 'gpt-6-astra'},
               {'type': 'thinking_level_change', 'thinkingLevel': 'low'},
               {'type': 'message', 'message': {'role': 'system', 'sections': {'skills': '<name>acu</name>'},
                'toolsAdded': [{'name': name} for name in bench.TOOLS]}}]
    transcript = '\n'.join(json.dumps(entry) for entry in entries) if recovered else '{truncated transcript'
    (directory / 'session.jsonl').write_text(transcript, encoding='utf-8')
    error = 'OpenAI Responses stream ended before a terminal response event'
    events = [{'type': 'agent_start'}, {'type': 'message_start', 'message': {'role': 'assistant'}},
              {'type': 'message_end', 'message': {'role': 'assistant', 'content': [], 'stopReason': 'error',
               'errorMessage': error, 'usage': {'input': 0, 'output': 0, 'totalTokens': 0}}}]
    if recovered:
        events += [{'type': 'auto_retry_start', 'attempt': 1, 'maxAttempts': 3, 'delayMs': 2000},
                   {'type': 'auto_retry_end', 'attempt': 1, 'success': True},
                   {'type': 'message_start', 'message': {'role': 'assistant'}},
                   {'type': 'message_end', 'message': {'role': 'assistant', 'content': [], 'stopReason': 'stop',
                    'usage': {'input': 10, 'output': 2, 'totalTokens': 12}}}]
    events += [{'type': 'agent_settled', 'aborted': False}]
    emitter = tmp_path / 'provider-fixture.py'
    emitter.write_text('from pathlib import Path\n' +
                       'with Path("invocations.txt").open("a") as log: log.write("once\\n")\n' +
                       '\n'.join('print(' + repr(json.dumps(event)) + ', flush=True)' for event in events), encoding='utf-8')
    plan['command'] = [sys.executable, str(emitter)]
    prepared = False
    inspection_calls = 0

    # Only the external desktop boundary is simulated; controller, capture, audits, PNG and cleanup are real.
    def observer(run_dir, script, *args, **kwargs):
        nonlocal prepared, inspection_calls
        if script.name == 'probe.ahk':
            return 'window=10 pid=20\nclass=10 illustrator\nillustrator=10\npid=20\n' if prepared else ''
        if script.name == 'ensure.ahk':
            return 'illustrator=10\npid=20\nstarted=1\n'
        if script.name == 'window.ahk':
            args[2].write_text('{"maximized":true}', encoding='utf-8')
            return ''
        if script.name == 'run-jsx.ahk':
            config = json.loads(args[0].read_text(encoding='utf-8').split('\n', 1)[0].removeprefix('var config = ').removesuffix(';'))
            if config['phase'] == 'prepare':
                prepared = True
            elif config['phase'] == 'cleanup':
                prepared = False
            drawing = {'path': str(directory / 'workspace/Cloud9-Pen-Starter.ai'), 'name': 'Cloud9-Pen-Starter.ai',
                       'saved': False, 'artwork_signature': 'unchanged'}
            documents = [drawing] if prepared else []
            result = {'documents': documents, 'zoom': 1, 'png_preferences': {}}
            if config['phase'] == 'drawing':
                inspection_calls += 1
                result = {'document': drawing, 'checks': {'artboard': True, 'editable_paths': True, 'blue_fill': True},
                          'paths': [{'closed': True, 'points': [
                              {'anchor': [100, 100], 'left': [100, 100], 'right': [100, 200]},
                              {'anchor': [300, 100], 'left': [300, 200], 'right': [300, 100]}]}]}
                if inspection_refused and inspection_calls == 1:
                    result = {'error': 'fixture refuses collection', 'stack': 'fixture native stack'}
            elif config['phase'] == 'export':
                if export_failure:
                    result = {'error': 'fixture maintainer export failed', 'stack': 'fixture native stack'}
                else:
                    from pathlib import Path
                    Path(config['render']).write_bytes((directory / 'workspace/Cloud9-Reference.png').read_bytes())
                    result = {'document_before': drawing, 'document_after': drawing}
            args[1].write_text(json.dumps(result), encoding='utf-8')
            return ''
        if script.name == 'restore_cursor.ahk' and not recovered:
            raise RuntimeError('fixture cleanup failed')
        assert script.name in ('input-state.ahk', 'dismiss-dialogs.ahk', 'close.ahk', 'restore_cursor.ahk')
        return ''

    monkeypatch.setattr(bench, 'acu_observer', observer)
    if recovered and not inspection_refused:
        result = bench.run(plan)
        assert result['passed'] is (not export_failure)
        assert result['drawing_passed'] is True
        assert result['recovered_provider_errors'] == [error]
        assert result['unexpected_failure'] is None and not (directory / 'failure.json').exists()
        assert result['benchmark']['token_counts_complete'] is False
        assert result['benchmark']['api_tokens']['total'] == 12
        assert json.loads((directory / 'verification.json').read_text(encoding='utf-8'))['passed']
        assert json.loads((directory / 'finished.json').read_text(encoding='utf-8'))['cleanup']['passed'] is (not export_failure)
        if export_failure:
            assert result['infrastructure_failure']['kind'] == 'maintainer_export_failure'
            assert result['problems'] == [] and result['safeguard_violations'] == []
            assert result['output_image'] is None and prepared, 'leave the unexported document open'
        else:
            assert result['infrastructure_failure'] is None
            assert result['output_image'] == str(directory / 'grading/Cloud9-Recreated.png')
            assert not (directory / 'workspace/Cloud9-Recreated.png').exists()
    elif inspection_refused:
        with pytest.raises(RuntimeError, match='Illustrator drawing failed'):
            bench.run(plan)
        assert inspection_calls == 1 and prepared, 'never repeat refused collection or destroy its unexported drawing'
        refused = json.loads((directory / 'finished.json').read_text(encoding='utf-8'))['cleanup']
        assert not refused['passed']
        assert refused['infrastructure_failure']['kind'] == 'maintainer_collection_failure'
        assert json.loads((directory / 'infrastructure-failure.json').read_text(encoding='utf-8')) == refused['infrastructure_failure']
    else:
        with pytest.raises(RuntimeError, match='fixture cleanup failed'):
            bench.run(plan)
        assert json.loads((directory / 'failure.json').read_text(encoding='utf-8')) == {
            'kind': 'unexpected_provider_failure', 'errors': [error]}
        assert not json.loads((directory / 'finished.json').read_text(encoding='utf-8'))['cleanup']['passed']
    assert (directory / 'workspace/invocations.txt').read_text(encoding='utf-8') == 'once\n'
    assert not (directory / 'agent-home/auth.json').exists()
    assert json.loads((directory / 'capture.json').read_text(encoding='utf-8'))['process_tree_stopped']


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


def test_isolation_audit_rejects_extra_skills_context_wrong_reasoning_and_wrong_provider():
    entries = [
        {'type': 'model_change', 'provider': 'openai-codex', 'modelId': 'gpt-6-astra'},
        {'type': 'thinking_level_change', 'thinkingLevel': 'low'},
        {'type': 'message', 'message': {'role': 'system', 'sections': {'skills': '<name>acu</name>', 'cwd': '/work'}, 'toolsAdded': [{'name': n} for n in ['read', 'bash', 'edit', 'write']]}},
    ]
    assert audit_pi_session(entries, 'acu')['passed']
    wrong_provider = [{**entries[0], 'provider': 'openai'}, *entries[1:]]
    assert not audit_pi_session(wrong_provider, 'acu')['passed']
    polluted = [*entries, {'type': 'message', 'message': {'role': 'system', 'sections': {'skills': '<name>acu</name><name>cua-driver</name>', 'project_context': 'AGENTS.md'}}}]
    assert not audit_pi_session(polluted, 'acu')['passed']
    assert not audit_pi_session([*entries, {'type': 'thinking_level_change', 'thinkingLevel': 'high'}], 'acu')['passed']


@pytest.mark.parametrize('error', ['quota', '503 subscription_sharing_user_unavailable',
                                  'OpenAI Responses stream ended before a terminal response event'])
def test_provider_failure_is_unexpected_not_a_model_or_desktop_failure(error):
    records = [{'elapsed_s': 1, 'event': {'type': 'agent_start'}},
               {'elapsed_s': 2, 'event': {'type': 'message_start', 'message': {'role': 'assistant'}}},
               {'elapsed_s': 3, 'event': {'type': 'message_end', 'message': {'role': 'assistant', 'content': [], 'usage': {'input': 10, 'output': 0, 'totalTokens': 10}, 'stopReason': 'error', 'errorMessage': error, 'durationMs': 1000}}},
               {'elapsed_s': 3, 'event': {'type': 'agent_settled', 'aborted': True}}]
    result = analyse_pi(records, wall_s=3)
    assert not result['agent_completed']
    assert result['model_errors'] == [error]
    assert result['unexpected_failure'] == {'kind': 'unexpected_provider_failure', 'errors': [error]}
    assert result['token_counts_complete'] is False
    assert result['effective_output_tps'] == 0

    records[2]['event']['message']['stopReason'] = 'aborted'
    assert analyse_pi(records, wall_s=3)['unexpected_failure'] is None, 'user interruption is not a provider failure'
