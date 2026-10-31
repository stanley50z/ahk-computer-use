"""Archived Codex exec transcript replay and persisted session isolation audit."""
from pathlib import Path
import re

from bench.common import read_jsonl, executable_command
from bench.intervals import busy_seconds
from bench.tool_calls import tool_call

name = 'codex'
live = False
supports_interrupted_exclusion = False
credential = ('.codex/auth.json', 'auth.json')
model, reasoning = 'gpt-6.1-sol', 'low'
recovery_policy = {'retry': 'harness-default', 'compaction': 'harness-default'}

# Inspect Codex's persisted turn model and developer skill catalog; absent evidence fails explicitly.
def audit_codex_session(entries, expected_model='gpt-6.1-sol'):
    problems = []
    contexts = [entry['payload'] for entry in entries if entry['type'] == 'turn_context']
    if not contexts:
        problems.append('no persisted turn_context evidence')
    for context in contexts:
        if context.get('model') != expected_model or context.get('effort') != 'low':
            problems.append('wrong model/reasoning in native turn context')
    developer_texts = []
    for entry in entries:
        if entry['type'] != 'response_item':
            continue
        payload = entry['payload']
        if payload.get('role') == 'developer':
            developer_texts.extend(block.get('text', '') for block in payload.get('content', []))
        if payload.get('type') == 'function_call':
            name = payload.get('name', '')
            if name.startswith('mcp__') and not name.startswith('mcp__node_repl__'):
                problems.append(f'unexpected native MCP tool: {name}')
    text = '\n'.join(developer_texts)
    catalog = re.findall(r'^- ([a-z][a-z0-9-]*):.*\(file: .*SKILL\.md\)', text, re.MULTILINE)
    if catalog and set(catalog) != {'computer-use'}:
        problems.append(f'unexpected native skills: {catalog}')
    if not catalog and 'The only enabled skill is computer-use.' not in text:
        problems.append('missing native skill-catalog evidence')
    if re.search(r'<project_instructions|# AGENTS\.md instructions', text):
        problems.append('unexpected project instructions')
    return {'passed': not problems, 'skills': catalog or ['computer-use'] if not problems else catalog,
            'problems': problems, 'evidence_kind': 'persisted native turn context and developer skill declaration'}


# Codex exec exposes final aggregate usage; its stream does not expose a true decoding-rate denominator.
def analyse_codex(records, wall_s, reference_tps=None, *, cancelled=False, exclude_interrupted_turns=False):
    if exclude_interrupted_turns:
        raise ValueError('--exclude-interrupted-turns requires per-response Pi usage; other harnesses are unsupported')
    completed = [r for r in records if r['event']['type'] == 'turn.completed']
    agent_start = next((r['elapsed_s'] for r in records if r['event']['type'] == 'thread.started'), None)
    tools, intervals, starts = [], [], {}
    for record in records:
        elapsed, event = record['elapsed_s'], record['event']
        item = event.get('item') if isinstance(event.get('item'), dict) else None
        if item is None or item.get('type') not in ('command_execution', 'mcp_tool_call'):
            continue
        arguments = {'command': item.get('command', '')} if item['type'] == 'command_execution' else item.get('arguments', {})
        name = item['type'] if item['type'] == 'command_execution' else f"{item.get('server')}.{item.get('tool')}"
        if event['type'] == 'item.started':
            starts[item['id']] = (elapsed, name, arguments)
        elif event['type'] == 'item.completed':
            start, _, _ = starts.pop(item['id'], (None, None, None))
            if start is not None:
                intervals.append((start, elapsed))
            # Retain native status/exit/error evidence; no Pi/Claude is_error flag is reported.
            body = ({'output': item.get('aggregated_output'), 'exit_code': item.get('exit_code')}
                    if item['type'] == 'command_execution' else item.get('result'))
            tools.append({**tool_call(item['id'], name, arguments, start, elapsed, body, None),
                          'status': item.get('status'), 'error': item.get('error')})
    tools.extend(tool_call(identity, name, arguments, start, None, None, None, completed=False)
                 for identity, (start, name, arguments) in starts.items())
    timing = {'agent_start_s': agent_start, 'tool_busy_s': busy_seconds(intervals), 'tools': tools, 'unfinished_tools': list(starts)}
    if not completed:
        return {'wall_s': wall_s, 'tokens': None, 'model_response_s': None,
                'effective_output_tps': None, 'end_to_end_output_tps': None, **timing,
                'agent_completed': False, 'token_counts_complete': False,
                'timing_limitation': 'No final Codex usage was reported; token totals are unknown, not zero.'}
    if len(completed) != 1:
        raise ValueError('expected exactly one Codex turn.completed usage record')
    usage = completed[0]['event']['usage']
    return {'wall_s': wall_s, 'tokens': {'input_including_cached': usage['input_tokens'],
            'cache_read': usage['cached_input_tokens'], 'output_including_reasoning': usage['output_tokens'],
            'total': usage['input_tokens'] + usage['output_tokens'], 'reasoning_subset': None},
            'model_response_s': None, 'effective_output_tps': None,
            'end_to_end_output_tps': usage['output_tokens'] / wall_s, **timing,
            'timing_limitation': 'Exec has no per-response model latency. End-to-end throughput includes tool time; do not treat it as decoding speed.',
            'agent_completed': True, 'token_counts_complete': True}


# Archived-only adapters cannot build or launch new trials.
def profile(*args, **kwargs):
    raise ValueError('Codex supports archived trial replay only')


# Reject archived-only plans before any live credentials or desktop access.
def validate_plan(plan, *, aggregate=False):
    raise ValueError('Codex supports archived trial replay only')


# Inspect the archived trial's native persisted session evidence.
def audit(plan, records):
    paths = (Path(plan['run_dir']) / 'agent-home/sessions').rglob('*.jsonl')
    entries = [entry for path in paths for entry in read_jsonl(path)]
    return audit_codex_session(entries, expected_model=plan['model'])


analyse = analyse_codex
