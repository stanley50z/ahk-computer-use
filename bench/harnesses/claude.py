"""Claude Code commands, isolated profiles, transcript normalization and session audit."""
from pathlib import Path
import json
import re
import uuid

from bench.common import actor_path, expand_user_root, read_jsonl, executable_command
from bench.intervals import busy_seconds
from bench.tool_calls import tool_call

name = 'claude'
live = True
supports_interrupted_exclusion = False
credential = ('.claude/.credentials.json', '.credentials.json')
model, reasoning = 'claude-opus-5-5', 'low'
CLAUDE_TOOLS = ['Read', 'Write', 'Edit', 'Bash']
CLAUDE_RECOVERY_POLICY = {'retry': 'harness-default', 'compaction': 'harness-default'}
recovery_policy = CLAUDE_RECOVERY_POLICY

# Claude Code is a public seam too: safe mode drops CLAUDE.md, skills, hooks and plugins; the selected skill is
# declared by path, like the Codex arm, and only the four ordinary file/shell tools exist.
def claude_command(skill, prompt, session_id, *, arm='claude-acu'):
    from bench.arms import ARM_TABLE
    effort = reasoning
    skill_name = ARM_TABLE[arm].skill_name
    declaration = (f'The only enabled skill is {skill_name}. Read {actor_path(Path(skill) / "SKILL.md")} before desktop interaction. '
                   'No other skill or desktop automation route is enabled.')
    return ['claude', '-p', '--safe-mode', '--disable-slash-commands', '--strict-mcp-config',
            '--setting-sources', 'user', '--tools', ','.join(CLAUDE_TOOLS),
            '--permission-mode', 'bypassPermissions', '--model', model, '--effort', effort,
            '--session-id', session_id, '--output-format', 'stream-json', '--verbose',
            '--include-partial-messages', '--append-system-prompt', declaration, prompt]


# Claude Code stream-json carries no server-side response duration: a response is timed from the request status
# event to message_stop receipt. Token totals come from the final result; per-message usage is deduplicated by id.
def analyse_claude(records, wall_s, reference_tps=None, *, cancelled=False, exclude_interrupted_turns=False):
    if exclude_interrupted_turns:
        raise ValueError('--exclude-interrupted-turns requires per-response Pi usage; other harnesses are unsupported')
    tokens = dict(input_uncached=0, cache_read=0, cache_write=0,
                  output_including_reasoning=0, reasoning_subset=None, total=0)
    turns, tools, intervals, errors, provider_errors = [], [], [], [], []
    pending_provider_errors, recovered_provider_errors = [], []
    usage_by_message, tool_starts = {}, {}
    agent_start = agent_end = request_start = None
    current = None
    final = None
    for record in records:
        elapsed, event = record['elapsed_s'], record['event']
        kind = event.get('type')
        if kind == 'system':
            if event.get('subtype') == 'init' and agent_start is None:
                agent_start = elapsed
            elif event.get('subtype') == 'status' and event.get('status') == 'requesting':
                request_start = elapsed
        elif kind == 'stream_event':
            inner = event['event']
            if inner['type'] == 'error':
                error = json.dumps(inner['error'], ensure_ascii=False)
                errors.append(error)
                provider_errors.append(error)
                pending_provider_errors.append(error)
            elif inner['type'] == 'message_start':
                current = {'start_s': request_start if request_start is not None else elapsed, 'first_visible_delta_s': None,
                           'message_id': inner['message'].get('id'), 'model': inner['message'].get('model'), 'delta_usage': None}
            elif current is None:
                continue
            elif inner['type'] == 'content_block_delta' and current['first_visible_delta_s'] is None:
                current['first_visible_delta_s'] = elapsed - current['start_s']
            elif inner['type'] == 'message_delta':
                current['delta_usage'] = inner.get('usage')
            elif inner['type'] == 'message_stop':
                usage = current.pop('delta_usage') or usage_by_message.get(current['message_id'], {})
                output = usage.get('output_tokens', 0)
                duration = elapsed - current['start_s']
                turns.append({**current, 'duration_s': duration, 'output_tokens': output,
                              'effective_output_tps': output / duration if duration > 0 else None, 'usage': usage})
                recovered_provider_errors.extend(pending_provider_errors)
                pending_provider_errors.clear()
                current = request_start = None
        elif kind in ('assistant', 'user'):
            if kind == 'assistant':
                message = event['message']
                usage_by_message[message.get('id')] = message.get('usage', {})
            content = event.get('message', {}).get('content', [])
            for block in content if isinstance(content, list) else []:
                if block.get('type') == 'tool_use':
                    tool_starts[block['id']] = (elapsed, block.get('name'), block.get('input', {}))
                elif block.get('type') == 'tool_result':
                    start, name, arguments = tool_starts.pop(block['tool_use_id'], (None, 'unmatched', None))
                    if start is not None:
                        intervals.append((start, elapsed))
                    body = block.get('content')
                    tools.append(tool_call(block['tool_use_id'], name, arguments, start, elapsed, body, bool(block.get('is_error')),
                                           matched=start is not None, truncated=isinstance(body, str) and '<persisted-output>' in body))
        elif kind == 'result':
            agent_end = elapsed
            final = event
            if event.get('is_error') or event.get('subtype') != 'success':
                reported = event.get('errors') or [str(event.get('result') or event.get('subtype'))]
                errors.extend(reported)
                terminal_errors = [error for error in reported if error.lstrip().lower().startswith('api error:')]
                provider_errors.extend(terminal_errors)
                pending_provider_errors.extend(terminal_errors)
    tools.extend(tool_call(identity, name, arguments, start, None, None, None, completed=False)
                 for identity, (start, name, arguments) in tool_starts.items())
    if final is not None and final.get('usage'):
        usage = final['usage']
        tokens.update(input_uncached=usage.get('input_tokens', 0), cache_read=usage.get('cache_read_input_tokens', 0),
                      cache_write=usage.get('cache_creation_input_tokens', 0), output_including_reasoning=usage.get('output_tokens', 0),
                      reasoning_subset=(usage.get('output_tokens_details') or {}).get('thinking_tokens'))
    else:
        for usage in usage_by_message.values():
            tokens['input_uncached'] += usage.get('input_tokens', 0)
            tokens['cache_read'] += usage.get('cache_read_input_tokens', 0)
            tokens['cache_write'] += usage.get('cache_creation_input_tokens', 0)
            tokens['output_including_reasoning'] += usage.get('output_tokens', 0)
    tokens['total'] = tokens['input_uncached'] + tokens['cache_read'] + tokens['cache_write'] + tokens['output_including_reasoning']
    model_s = sum(turn['duration_s'] for turn in turns) if turns else None
    completed = final is not None and final.get('subtype') == 'success' and not final.get('is_error') and not cancelled
    if completed:
        recovered_provider_errors.extend(pending_provider_errors)
        pending_provider_errors.clear()
    result = {'wall_s': wall_s, 'agent_start_s': agent_start,
              'agent_elapsed_s': agent_end - agent_start if agent_start is not None and agent_end is not None else None,
              'model_response_s': model_s, 'tool_busy_s': busy_seconds(intervals), 'tokens': tokens,
              'effective_output_tps': tokens['output_including_reasoning'] / model_s if model_s else None,
              'end_to_end_output_tps': tokens['output_including_reasoning'] / wall_s if wall_s > 0 else None,
              'reported_api_duration_s': final['duration_api_ms'] / 1000 if final and 'duration_api_ms' in final else None,
              'model_turns': turns, 'tools': tools, 'model_errors': errors, 'agent_completed': completed,
              'recovered_provider_errors': list(dict.fromkeys(recovered_provider_errors)),
              'unexpected_failure': {'kind': 'unexpected_provider_failure', 'errors': list(dict.fromkeys(pending_provider_errors))}
                                    if pending_provider_errors and not cancelled else None,
              'unfinished_tools': list(tool_starts), 'token_counts_complete': final is not None and bool(final.get('usage')) and not provider_errors,
              'timing_basis': 'Receipt intervals from the request status event to message_stop; Claude Code exposes no per-response server duration.'}
    if reference_tps is not None:
        if reference_tps <= 0:
            raise ValueError('reference throughput must be positive')
        result['reference_tps'] = reference_tps
        result['estimated_wall_at_reference_tps_s'] = wall_s - model_s + tokens['output_including_reasoning'] / reference_tps if model_s is not None else None
        result['normalization_method'] = 'Whole-response effective-rate counterfactual, including prefill/queueing; not pure decoding speed.'
    return result


# Audit the stream's init event and the persisted transcript; absent evidence fails rather than passing by default.
def audit_claude_session(records, entries, expected_skill_dir):
    effort = reasoning
    problems = []
    inits = [r['event'] for r in records if r['event'].get('type') == 'system' and r['event'].get('subtype') == 'init']
    if not inits:
        problems.append('no init evidence in the stream')
    for init in inits:
        if init.get('model') != model:
            problems.append('wrong model in init')
        if sorted(init.get('tools', [])) != sorted(CLAUDE_TOOLS):
            problems.append(f"unexpected tools: {init.get('tools')}")
        if init.get('mcp_servers'):
            problems.append('unexpected MCP servers')
        if init.get('skills') or init.get('slash_commands'):
            problems.append(f"unexpected skills: {init.get('skills') or init.get('slash_commands')}")
    assistants = [entry for entry in entries if entry.get('type') == 'assistant']
    if not assistants:
        problems.append('no persisted assistant evidence')
    expected = Path(expected_skill_dir).resolve().as_posix().casefold().rstrip('/') + '/'
    for entry in assistants:
        if entry.get('effort') != effort:
            problems.append(f'effort is not {effort}')
        if entry.get('requestedModel', entry.get('message', {}).get('model')) != model:
            problems.append('assistant used wrong model')
        for block in entry.get('message', {}).get('content', []):
            if isinstance(block, dict) and block.get('type') == 'tool_use' and block.get('name') == 'Read':
                path = str(block.get('input', {}).get('file_path', '')).replace('\\', '/')
                if path.endswith('/SKILL.md'):
                    resolved = expand_user_root(path).resolve().as_posix().casefold()
                    if not resolved.startswith(expected):
                        problems.append(f'other skill read: {path}')
    return {'passed': not problems, 'skills': [Path(expected_skill_dir).name], 'problems': sorted(set(problems)),
            'evidence_kind': 'stream init event (model, tools, MCP, skills) and persisted transcript (effort, model, reads)',
            'limitation': 'Safe mode disables CLAUDE.md, hooks and plugins by flag; the stream lists no memory files, so that part is not independently evidenced.'}


# Safe mode uses a fresh config home and explicit selected skill declaration.
def profile(arm, run_dir, prompt, skill, native_config, native_transport, approved_apps):
    skill = Path(skill) if skill is not None else arm.skill_path()
    session_id = str(uuid.uuid4())
    return {'skill': skill, 'session_id': session_id,
            'command': claude_command(skill, prompt, session_id, arm=arm.id),
            'environment_overrides': {'CLAUDE_CONFIG_DIR': str(run_dir / 'agent-home'),
                                      'CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC': '1'}}


# Claude profiles have no extra provider gate beyond aggregation's model/policy matching.
def validate_plan(plan, *, aggregate=False):
    pass


# Read only this profile's persisted project transcripts.
def audit(plan, records):
    directory = Path(plan['run_dir']) / 'agent-home/projects'
    transcripts = sorted(directory.rglob('*.jsonl')) if directory.is_dir() else []
    entries = [entry for path in transcripts for entry in read_jsonl(path)]
    return audit_claude_session(records, entries, Path(plan['skill_path']).parent)


analyse = analyse_claude
