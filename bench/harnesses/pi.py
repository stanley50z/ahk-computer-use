"""Pi commands, isolated profiles, transcript normalization and session audit."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tomllib
import re
import shutil
from copy import deepcopy

from bench.common import ROOT, read_jsonl, save_json
from bench.common import executable_command as installed_command
from bench.intervals import busy_seconds
from bench.tool_calls import tool_call

name = 'pi'
live = True
supports_interrupted_exclusion = True
credential = ('.pi/agent/auth.json', 'auth.json')

MODEL = 'gpt-6-astra'
PI_PROVIDER = 'openai-codex'
REASONING = 'low'
# Freeze normal Pi session recovery so retries/compaction remain reproducible within the same scheduled trial.
PI_RECOVERY_POLICY = {
    'retry': {'enabled': True, 'maxRetries': 3, 'baseDelayMs': 2000, 'maxAgentDelayMs': 60000,
              'provider': {'maxRetries': 0}},
    'compaction': {'enabled': True, 'reserveTokens': 16384, 'keepRecentTokens': 20000},
}
TOOLS = ['read', 'bash', 'edit', 'write']
NATIVE_TOOLS = ['mcp__node_repl__js', 'mcp__node_repl__js_reset',
                'mcp__node_repl__js_add_node_module_dir', 'mcp__node_repl__turn_ended']

recovery_policy = PI_RECOVERY_POLICY
model, reasoning = MODEL, REASONING


# Bypass the Windows npm shim so prompts never pass through cmd.exe parsing.
def executable_command(command):
    resolved = installed_command(command)
    if Path(resolved[0]).suffix.lower() != '.cmd':
        return resolved
    entry = Path(resolved[0]).parent / 'node_modules/@earendil-works/pi-coding-agent/dist/cli.js'
    if not entry.is_file():
        raise FileNotFoundError(entry)
    node = shutil.which('node')
    if node is None:
        raise FileNotFoundError('node is not on PATH')
    return [node, str(entry), *command[1:]]

# The CLI is a public seam: only one explicitly selected skill and the four ordinary file/shell tools.
def pi_command(run_dir, skill, prompt, *, native=False):
    runtime = ['-e', 'builtin:mcp'] if native else ['--no-mcp']
    tools = TOOLS + NATIVE_TOOLS if native else TOOLS
    return ['pi', '-ne', '-ns', '-nc', '-np', '--no-themes', *runtime,
            '--skill', str(skill), '--tools', ','.join(tools),
            '--model', f'{PI_PROVIDER}/{MODEL}', '--thinking', 'low', '--offline',
            '--approve', '--session', str(run_dir / 'session.jsonl'),
            '--mode', 'json', '--print', prompt]


# Analyse final usage once; optional offline exclusion keeps interrupted responses as separate evidence.
def analyse_pi(records, wall_s, reference_tps=None, *, cancelled=False, exclude_interrupted_turns=False):
    tokens = dict(input_uncached=0, cache_read=0, cache_write=0,
                  output_including_reasoning=0, reasoning_subset=None, total=0)
    turns, tools, intervals, errors = [], [], [], []
    excluded_turns = []
    pending_provider_errors, recovered_provider_errors, pending_recovery_errors, recovery_events = [], [], [], []
    current = None
    starts = {}
    agent_start = agent_end = None
    last_stop_reason = None
    usage_unknown = retry_cancelled = False
    completed = False
    compactions = 0

    # Both agent responses and compaction summaries report the same Pi usage schema, once at completion.
    def add_usage(usage):
        tokens['input_uncached'] += usage['input']
        tokens['cache_read'] += usage.get('cacheRead', 0)
        tokens['cache_write'] += usage.get('cacheWrite', 0)
        tokens['output_including_reasoning'] += usage['output']
        tokens['total'] += usage['totalTokens']
        if 'reasoning' in usage:
            tokens['reasoning_subset'] = (tokens['reasoning_subset'] or 0) + usage['reasoning']
    for record in records:
        elapsed, event = record['elapsed_s'], record['event']
        kind = event['type']
        if kind.startswith(('auto_retry_', 'summarization_retry_')) or kind in ('compaction_start', 'compaction_end'):
            recovery_events.append(record)
        if kind == 'auto_retry_end' and event.get('finalError') == 'Retry cancelled':
            retry_cancelled = True
        if kind == 'summarization_retry_scheduled':
            usage_unknown = True  # Failed summary requests may have unreported consumption.
        if kind == 'compaction_start':
            completed = False
        if kind == 'compaction_end':
            completed = False
            compactions += 1
            result = event.get('result')
            usage = (result or {}).get('usage')
            if usage:
                add_usage(usage)
            else:
                usage_unknown = True
            if result is not None and not event.get('aborted'):
                pending_recovery_errors.clear()
            elif event.get('errorMessage'):
                pending_recovery_errors.append(event['errorMessage'])
            elif event.get('aborted'):
                pending_recovery_errors.append('Compaction aborted')
        if kind == 'agent_start':
            completed = retry_cancelled = False
            if agent_start is None:
                agent_start = elapsed
        if kind == 'message_start' and event['message']['role'] == 'assistant':
            completed = False
            current = {'start_s': elapsed, 'first_visible_delta_s': None}
        elif kind == 'message_update' and current is not None:
            if event['assistantMessageEvent']['type'] in ('text_delta', 'toolcall_delta', 'thinking_delta') and current['first_visible_delta_s'] is None:
                current['first_visible_delta_s'] = elapsed - current['start_s']
        elif kind == 'message_end' and event['message']['role'] == 'assistant':
            message = event['message']
            if current is None:
                raise ValueError('assistant ended without a matching message_start')
            usage = message['usage']
            interrupted = message['stopReason'] in ('error', 'aborted')
            if not (exclude_interrupted_turns and interrupted):
                add_usage(usage)
            last_stop_reason = message['stopReason']
            stream_duration = elapsed - current['start_s']
            duration = message['durationMs'] / 1000 if 'durationMs' in message else None
            first_delta = current['first_visible_delta_s']
            if first_delta is not None and duration is not None:
                first_delta += duration - stream_duration
            turn = {**current, 'first_visible_delta_s': first_delta, 'duration_s': duration,
                    'stream_observed_s': stream_duration, 'output_tokens': usage['output'],
                    'effective_output_tps': usage['output'] / duration if duration is not None and duration > 0 else None,
                    'usage': usage, 'model': message.get('model'),
                    'response_model': message.get('responseModel'),
                    'thinking': message.get('thinkingLevel'), 'stop_reason': message['stopReason']}
            if exclude_interrupted_turns and interrupted:
                excluded_turns.append({**turn, 'error': message.get('errorMessage', message['stopReason']),
                                       'response_index': len(turns) + len(excluded_turns)})
            else:
                turns.append(turn)
            if interrupted:
                error = message.get('errorMessage', message['stopReason'])
                errors.append(error)
                if not exclude_interrupted_turns:
                    usage_unknown = True
                if message['stopReason'] == 'error':
                    pending_provider_errors.append(error)  # Provider-response failure, not a desktop tool result.
            else:
                recovered_provider_errors.extend(pending_provider_errors)
                pending_provider_errors.clear()
                pending_recovery_errors.clear()
            current = None
        elif kind == 'tool_execution_start':
            starts[event['toolCallId']] = (elapsed, event['toolName'], event.get('args', {}))
        elif kind == 'tool_execution_end':
            start, name, arguments = starts.pop(event['toolCallId'], (None, 'unmatched', None))
            if start is not None:
                intervals.append((start, elapsed))
            body = event.get('result')
            truncated = isinstance(body, dict) and bool((body.get('details') or {}).get('truncation', {}).get('truncated'))
            tools.append({**tool_call(event['toolCallId'], name, arguments, start, elapsed, body, event.get('isError'),
                                     matched=start is not None, truncated=truncated),
                          'reported_duration_ms': event.get('durationMs')})
        elif kind == 'agent_settled':
            agent_end = elapsed
            completed = not event['aborted'] and last_stop_reason == 'stop' and not pending_recovery_errors
    tools.extend(tool_call(identity, name, arguments, start, None, None, None, completed=False)
                 for identity, (start, name, arguments) in starts.items())
    model_s = sum(turn['duration_s'] for turn in turns) if not compactions and all(turn['duration_s'] is not None for turn in turns) else None
    if cancelled:
        completed = False
    result = {'wall_s': wall_s, 'agent_start_s': agent_start, 'agent_elapsed_s': agent_end - agent_start if agent_start is not None and agent_end is not None else None,
              'model_response_s': model_s, 'tool_busy_s': busy_seconds(intervals),
              'tokens': tokens, 'effective_output_tps': tokens['output_including_reasoning'] / model_s if model_s is not None and model_s > 0 else None,
              'end_to_end_output_tps': tokens['output_including_reasoning'] / wall_s if wall_s > 0 else None,
              'model_turns': turns, 'tools': tools, 'model_errors': errors,
              'agent_completed': completed, 'token_counts_complete': completed and not usage_unknown, 'unfinished_tools': list(starts),
              'recovered_provider_errors': recovered_provider_errors, 'recovery_events': recovery_events,
              'recovery_errors': pending_recovery_errors, 'compactions': compactions,
              'unexpected_failure': {'kind': 'unexpected_provider_failure', 'errors': pending_provider_errors}
                                    if pending_provider_errors and not retry_cancelled and not cancelled else None}
    if exclude_interrupted_turns:
        result.update(token_usage_scope='excluding-interrupted-turns', excluded_model_turns=excluded_turns,
                      full_request_consumption_complete=completed and not usage_unknown and not excluded_turns)
    if compactions:
        result['timing_limitation'] = 'Compaction usage is included, but its provider-response duration is not exposed; model-rate diagnostics are unknown.'
    if reference_tps is not None:
        if reference_tps <= 0:
            raise ValueError('reference throughput must be positive')
        result['reference_tps'] = reference_tps
        result['estimated_wall_at_reference_tps_s'] = wall_s - model_s + tokens['output_including_reasoning'] / reference_tps if model_s is not None else None
        result['normalization_method'] = 'Whole-response effective-rate counterfactual, including prefill/queueing; not pure decoding speed.'
        visible_turns = [turn for turn in turns if turn['duration_s'] is not None and turn['first_visible_delta_s'] is not None]
        if not compactions and len(visible_turns) == len(turns):
            post_delta_s = sum(turn['duration_s'] - turn['first_visible_delta_s'] for turn in visible_turns)
            visible_output = sum(turn['output_tokens'] - (turn['usage'].get('reasoning') or 0) for turn in visible_turns)
            result['estimated_wall_preserving_first_delta_at_reference_visible_tps_s'] = wall_s - post_delta_s + visible_output / reference_tps
        else:
            result['estimated_wall_preserving_first_delta_at_reference_visible_tps_s'] = None
    return result


# Audit the actual persisted prompt, declarations and model state, not just intended launch flags.
def audit_pi_session(entries, expected_skill, *, expected_model=MODEL, expected_provider=PI_PROVIDER):
    problems = []
    expected_tools = set(TOOLS + (NATIVE_TOOLS if expected_skill == 'computer-use' else []))
    declared_tools = set()
    saw_system = saw_model = saw_thinking = False
    sections = {}
    skills = []
    for entry in entries:
        if entry['type'] == 'model_change':
            saw_model = True
            if (entry['provider'], entry['modelId']) != (expected_provider, expected_model):
                problems.append('model/provider changed')
        if entry['type'] == 'thinking_level_change':
            saw_thinking = True
            if entry['thinkingLevel'] != 'low':
                problems.append('reasoning is not low')
        if entry['type'] != 'message':
            continue
        message = entry['message']
        if message['role'] == 'system':
            saw_system = True
            sections.update(message.get('sections', {}))
            skills = re.findall(r'<name>(.*?)</name>', sections.get('skills') or '')
            if skills != [expected_skill]:
                problems.append(f'unexpected skills: {skills}')
            for key in ('project_context', 'addendum'):
                if sections.get(key):
                    problems.append(f'unexpected {key}')
            additions = {tool['name'] for tool in message.get('toolsAdded', [])}
            if additions - expected_tools:
                problems.append('unexpected declared tools')
            declared_tools.update(additions)
            declared_tools.difference_update(message.get('toolsRemoved', []))
            if sections.get('mcp_servers') and expected_skill != 'computer-use':
                problems.append('unexpected MCP servers')
        if message['role'] == 'assistant':
            if message.get('model') != expected_model or message.get('thinkingLevel') != 'low':
                problems.append('assistant used wrong model/reasoning')
            for block in message.get('content', []):
                if block['type'] == 'toolCall' and block['name'] not in expected_tools:
                    problems.append(f'unexpected invoked tool: {block["name"]}')
                if block['type'] == 'toolCall' and block['name'] == 'read':
                    path = block['arguments']['path'].replace('\\', '/')
                    if path.endswith('/SKILL.md') and f'/{expected_skill}/' not in path:
                        problems.append(f'other skill read: {path}')
    if declared_tools != expected_tools:
        problems.append('missing or changed tool declarations')
    if not all((saw_system, saw_model, saw_thinking)):
        problems.append('missing system/model/reasoning evidence')
    return {'passed': not problems, 'skills': skills, 'problems': sorted(set(problems))}



# Resolve the installed vendor skill without modifying it or copying prior benchmark knowledge.
def native_skill():
    root = Path.home() / '.codex/plugins/cache/openai-bundled/computer-use'
    versions = sorted((path for path in root.iterdir() if (path / 'skills/computer-use/SKILL.md').is_file()),
                      key=lambda path: tuple(int(part) for part in path.name.split('.')))
    if not versions:
        raise FileNotFoundError(f'no installed computer-use skill under {root}')
    return versions[-1] / 'skills/computer-use'


# Reuse the installed native MCP runtime, but isolate its home and allow only the desktop service.
def native_server(home, config=None, transport='sdk-helper'):
    original = config if config is not None else tomllib.loads((Path.home() / '.codex/config.toml').read_text(encoding='utf-8'))
    source = original['mcp_servers']['node_repl']
    environment = dict(source.get('env', {}))
    environment['CODEX_HOME'] = str(home)
    environment['SKY_CUA_NATIVE_PIPE'] = '1' if transport == 'app-pipe' else '0'
    if transport == 'app-pipe':
        if not environment.get('SKY_CUA_NATIVE_PIPE_DIRECTORY'):
            raise ValueError('the user configuration names no app-owned native pipe')
    else:
        environment.pop('SKY_CUA_NATIVE_PIPE_DIRECTORY', None)
    environment.update(NODE_REPL_TRUSTED_SERVICES=json.dumps({'sky': '@oai/sky/service'}),
                       BROWSER_USE_AVAILABLE_BACKENDS='', BROWSER_USE_TINYSKY_ENABLED='0',
                       NODE_REPL_INSTRUCTIONS_USE_CASE_BROWSER='', NODE_REPL_INSTRUCTIONS_USE_CASE_CHROME='')
    args = list(source.get('args', []))
    # Match the former native Codex arm's explicit full-access mode. Without this supported runtime
    # option the standalone MCP server sandboxes its kernel and SDK helper startup fails with spawn EPERM.
    if '--disable-sandbox' not in args:
        args.append('--disable-sandbox')
    return {'command': source['command'], 'args': args, 'env': environment,
            'exposure': 'direct', 'timeout': 120}


# Build only the selected skill/runtime profile; scenario permissions arrive from the scenario adapter.
def profile(arm, run_dir, prompt, skill, native_config, native_transport, approved_apps):
    home = run_dir / 'agent-home'
    skill = Path(skill) if skill is not None else arm.skill_path()
    if arm.native:
        server = native_server(home, native_config, native_transport)
        bridge = {'command': server['command'], 'args': server['args'], 'approved_apps': approved_apps,
                  'log_path': str(run_dir / 'native-approvals.jsonl')}
        save_json(home / 'native-bridge.json', bridge)
        server.update(command=sys.executable, args=[str(ROOT / 'bench/native_mcp.py'), str(home / 'native-bridge.json')])
        save_json(home / 'mcp.json', {'mcpServers': {'node_repl': server}, 'autoEnableCodemode': False})
    settings = {'packages': [], 'extensions': [], 'skills': [], 'prompts': [],
                'cacheWarming': 'off', 'defaultTools': TOOLS, **deepcopy(PI_RECOVERY_POLICY)}
    if os.name == 'nt':
        settings['shellPath'] = 'C:/Program Files/Git/bin/bash.exe'
        if not Path(settings['shellPath']).is_file():
            raise FileNotFoundError(settings['shellPath'])
    save_json(home / 'settings.json', settings)
    result = {'skill': skill, 'command': pi_command(run_dir, skill, prompt, native=arm.native),
              'environment_overrides': {'PI_CODING_AGENT_DIR': str(home), 'PI_OFFLINE': '1'}, 'provider': PI_PROVIDER}
    if arm.native:
        result.update(native_transport=native_transport,
                      mcp_config_sha256=hashlib.sha256((home / 'mcp.json').read_bytes()).hexdigest(),
                      native_bridge_sha256=hashlib.sha256((home / 'native-bridge.json').read_bytes()).hexdigest())
        if native_transport == 'app-pipe':
            result['native_pipe'] = server['env']['SKY_CUA_NATIVE_PIPE_DIRECTORY']
    return result


# Reject stale provider profiles before credentials, desktop preparation or aggregation.
def validate_plan(plan, *, aggregate=False):
    if plan.get('provider') != PI_PROVIDER:
        if aggregate:
            raise ValueError('round requires the explicit openai-codex Pi provider; historical providers cannot be mixed')
        raise ValueError('Prepared Pi provider does not match the current explicit provider; prepare a fresh trial')


# Read the persisted session from this trial only, retaining the existing missing-evidence failure.
def audit(plan, records):
    path = Path(plan['run_dir']) / 'session.jsonl'
    entries = read_jsonl(path) if path.is_file() else []
    return audit_pi_session(entries, plan['skill_names'][0], expected_model=plan['model'])


analyse = analyse_pi
