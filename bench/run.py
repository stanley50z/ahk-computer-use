"""Run fresh GPT-6.1/low computer-use sessions and measure their JSON event streams.

Desktop runs require --desktop-approved. Raw evidence stays in .pi/bench/<run-id>/.
The bench isolates configuration, not filesystem permissions or the shared desktop.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import tomllib
import traceback
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
MODEL = 'gpt-6.1-sol'
TOOLS = ['read', 'bash', 'edit', 'write']
ARMS = ('pi-acu', 'pi-cua', 'codex-computer-use')
EXPRESSION = '128+465*12387/138473-12343'
SKILLS = {
    'pi-acu': ROOT / 'acu',
    'pi-cua': Path.home() / '.agents/skills/cua-driver',
}


# The CLI is a public seam: only one explicitly selected skill and the four ordinary file/shell tools.
def pi_command(run_dir, skill, prompt):
    return ['pi', '-ne', '-ns', '-nc', '-np', '--no-themes', '--no-mcp',
            '--skill', str(skill), '--tools', ','.join(TOOLS),
            '--model', f'openai/{MODEL}', '--thinking', 'low', '--offline',
            '--approve', '--session', str(run_dir / 'session.jsonl'),
            '--mode', 'json', '--print', prompt]


# Merge tool intervals instead of summing their durations when calls overlap.
def busy_seconds(intervals):
    end = None
    total = 0.0
    for start, finish in sorted(intervals):
        if end is None or start >= end:
            total += finish - start
        elif finish > end:
            total += finish - end
        end = max(finish, end) if end is not None else finish
    return total


# Analyse final message usage once; streaming usage and turn_end repeat the same counts.
def analyse_pi(records, wall_s, reference_tps=None):
    tokens = dict(input_uncached=0, cache_read=0, cache_write=0,
                  output_including_reasoning=0, reasoning_subset=None, total=0)
    turns, tools, intervals, errors = [], [], [], []
    current = None
    starts = {}
    agent_start = agent_end = None
    completed = False
    for record in records:
        elapsed, event = record['elapsed_s'], record['event']
        kind = event['type']
        if kind == 'agent_start' and agent_start is None:
            agent_start = elapsed
        if kind == 'message_start' and event['message']['role'] == 'assistant':
            current = {'start_s': elapsed, 'first_visible_delta_s': None}
        elif kind == 'message_update' and current is not None:
            if event['assistantMessageEvent']['type'] in ('text_delta', 'toolcall_delta', 'thinking_delta') and current['first_visible_delta_s'] is None:
                current['first_visible_delta_s'] = elapsed - current['start_s']
        elif kind == 'message_end' and event['message']['role'] == 'assistant':
            message = event['message']
            if current is None:
                raise ValueError('assistant ended without a matching message_start')
            usage = message['usage']
            tokens['input_uncached'] += usage['input']
            tokens['cache_read'] += usage.get('cacheRead', 0)
            tokens['cache_write'] += usage.get('cacheWrite', 0)
            tokens['output_including_reasoning'] += usage['output']
            tokens['total'] += usage['totalTokens']
            if 'reasoning' in usage:
                tokens['reasoning_subset'] = (tokens['reasoning_subset'] or 0) + usage['reasoning']
            stream_duration = elapsed - current['start_s']
            duration = message['durationMs'] / 1000 if 'durationMs' in message else None
            first_delta = current['first_visible_delta_s']
            if first_delta is not None and duration is not None:
                first_delta += duration - stream_duration
            turns.append({**current, 'first_visible_delta_s': first_delta, 'duration_s': duration,
                          'stream_observed_s': stream_duration, 'output_tokens': usage['output'],
                          'effective_output_tps': usage['output'] / duration if duration is not None and duration > 0 else None,
                          'usage': usage, 'model': message.get('model'),
                          'response_model': message.get('responseModel'),
                          'thinking': message.get('thinkingLevel'), 'stop_reason': message['stopReason']})
            if message['stopReason'] in ('error', 'aborted'):
                errors.append(message.get('errorMessage', message['stopReason']))
            current = None
        elif kind == 'tool_execution_start':
            starts[event['toolCallId']] = (elapsed, event['toolName'])
        elif kind == 'tool_execution_end':
            start, name = starts.pop(event['toolCallId'])
            intervals.append((start, elapsed))
            tools.append({'id': event['toolCallId'], 'name': name, 'duration_s': elapsed - start,
                          'is_error': event['isError'], 'reported_duration_ms': event.get('durationMs')})
        elif kind == 'agent_settled':
            agent_end = elapsed
            completed = not event['aborted'] and not errors
    model_s = sum(turn['duration_s'] for turn in turns) if all(turn['duration_s'] is not None for turn in turns) else None
    result = {'wall_s': wall_s, 'agent_elapsed_s': agent_end - agent_start if agent_start is not None and agent_end is not None else None,
              'model_response_s': model_s, 'tool_busy_s': busy_seconds(intervals),
              'tokens': tokens, 'effective_output_tps': tokens['output_including_reasoning'] / model_s if model_s is not None and model_s > 0 else None,
              'end_to_end_output_tps': tokens['output_including_reasoning'] / wall_s if wall_s > 0 else None,
              'model_turns': turns, 'tools': tools, 'model_errors': errors,
              'agent_completed': completed, 'unfinished_tools': list(starts)}
    if reference_tps is not None:
        if reference_tps <= 0:
            raise ValueError('reference throughput must be positive')
        result['reference_tps'] = reference_tps
        result['estimated_wall_at_reference_tps_s'] = wall_s - model_s + tokens['output_including_reasoning'] / reference_tps if model_s is not None else None
        result['normalization_method'] = 'Whole-response effective-rate counterfactual, including prefill/queueing; not pure decoding speed.'
        visible_turns = [turn for turn in turns if turn['duration_s'] is not None and turn['first_visible_delta_s'] is not None]
        if len(visible_turns) == len(turns):
            post_delta_s = sum(turn['duration_s'] - turn['first_visible_delta_s'] for turn in visible_turns)
            visible_output = sum(turn['output_tokens'] - (turn['usage'].get('reasoning') or 0) for turn in visible_turns)
            result['estimated_wall_preserving_first_delta_at_reference_visible_tps_s'] = wall_s - post_delta_s + visible_output / reference_tps
        else:
            result['estimated_wall_preserving_first_delta_at_reference_visible_tps_s'] = None
    return result


# Audit the actual persisted prompt, declarations and model state, not just intended launch flags.
def audit_pi_session(entries, expected_skill):
    problems = []
    saw_system = saw_model = saw_thinking = False
    sections = {}
    skills = []
    for entry in entries:
        if entry['type'] == 'model_change':
            saw_model = True
            if (entry['provider'], entry['modelId']) != ('openai', MODEL):
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
            if 'toolsAdded' in message and sorted(tool['name'] for tool in message['toolsAdded']) != sorted(TOOLS):
                problems.append('unexpected declared tools')
        if message['role'] == 'assistant':
            if message.get('model') != MODEL or message.get('thinkingLevel') != 'low':
                problems.append('assistant used wrong model/reasoning')
            for block in message.get('content', []):
                if block['type'] == 'toolCall' and block['name'] == 'read':
                    path = block['arguments']['path'].replace('\\', '/')
                    if path.endswith('/SKILL.md') and f'/{expected_skill}/' not in path:
                        problems.append(f'other skill read: {path}')
    if not all((saw_system, saw_model, saw_thinking)):
        problems.append('missing system/model/reasoning evidence')
    return {'passed': not problems, 'skills': skills, 'problems': sorted(set(problems))}



# Inspect Codex's persisted turn model and developer skill catalog; absent evidence fails explicitly.
def audit_codex_session(entries):
    problems = []
    contexts = [entry['payload'] for entry in entries if entry['type'] == 'turn_context']
    if not contexts:
        problems.append('no persisted turn_context evidence')
    for context in contexts:
        if context.get('model') != MODEL or context.get('effort') != 'low':
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


# Read the actor's JSON as UTF-8, including the BOM that Windows PowerShell may emit.
def load_actor_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


# Read LF-delimited files without treating Unicode paragraph separators as record boundaries.
def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').split('\n') if line.strip()]


# Store structured evidence atomically so a stopped worker cannot leave half a JSON report.
def save_json(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


# Prepare reproducible, offline profiles without credentials or a live desktop session.
def prepare(arm, run_dir, *, skill=None, native_config=None, native_skill_roots=None, native_builtin_root=None):
    if arm not in ARMS:
        raise ValueError(f'unknown arm: {arm}')
    run_dir = Path(run_dir).resolve()
    run_dir.mkdir(parents=True, exist_ok=False)
    workspace, home = run_dir / 'workspace', run_dir / 'agent-home'
    workspace.mkdir()
    home.mkdir()
    scenario = (ROOT / 'bench/scenarios/calculator.md').read_text(encoding='utf-8')
    (run_dir / 'scenario.md').write_text(scenario, encoding='utf-8')
    prompt = scenario
    if arm.startswith('pi-'):
        skill = Path(skill) if skill is not None else SKILLS[arm]
        settings = {'packages': [], 'extensions': [], 'skills': [], 'prompts': [],
                    'cacheWarming': 'off', 'compaction': {'enabled': False},
                    'retry': {'enabled': False}, 'defaultTools': TOOLS}
        if os.name == 'nt':
            settings['shellPath'] = 'C:/Program Files/Git/bin/bash.exe'
            if not Path(settings['shellPath']).is_file():
                raise FileNotFoundError(settings['shellPath'])
        save_json(home / 'settings.json', settings)
        command = pi_command(run_dir, skill, prompt)
        environment = {'PI_CODING_AGENT_DIR': str(home), 'PI_OFFLINE': '1'}
        skill_name = 'acu' if arm == 'pi-acu' else 'cua-driver'
    else:
        original = native_config if native_config is not None else tomllib.loads((Path.home() / '.codex/config.toml').read_text(encoding='utf-8'))
        node_repl = original['mcp_servers']['node_repl']
        if skill is None:
            native_root = Path.home() / '.codex/plugins/cache/openai-bundled/computer-use'
            versions = sorted(p for p in native_root.iterdir() if (p / 'skills/computer-use/SKILL.md').is_file())
            if not versions:
                raise FileNotFoundError(f'no installed computer-use skill under {native_root}')
            skill = versions[-1] / 'skills/computer-use'
        else:
            skill = Path(skill)
        skill_name = 'computer-use'
        native_env = dict(node_repl['env'])
        native_env['CODEX_HOME'] = str(home)
        native_env['SKY_CUA_NATIVE_PIPE'] = '0'  # CLI uses the shipped SDK-owned helper, not an app-owned pipe.
        native_env.pop('SKY_CUA_NATIVE_PIPE_DIRECTORY', None)
        native_env['NODE_REPL_TRUSTED_SERVICES'] = json.dumps({'sky': '@oai/sky/service'})
        native_env['BROWSER_USE_AVAILABLE_BACKENDS'] = ''
        native_env['BROWSER_USE_TINYSKY_ENABLED'] = '0'
        native_env['NODE_REPL_INSTRUCTIONS_USE_CASE_BROWSER'] = ''
        native_env['NODE_REPL_INSTRUCTIONS_USE_CASE_CHROME'] = ''
        developer = f'The only enabled skill is computer-use. Read {skill / "SKILL.md"} before desktop interaction. No other skill or desktop automation route is enabled.'
        scalar = {'model': MODEL, 'model_reasoning_effort': 'low', 'approval_policy': 'never',
                  'sandbox_mode': 'danger-full-access', 'project_doc_max_bytes': 0,
                  'service_tier': 'default', 'developer_instructions': developer,
                  'suppress_unstable_features_warning': True}
        lines = [f'{key} = {json.dumps(value)}' for key, value in scalar.items()]
        lines += ['[features]', 'skip_host_skill_discovery = true', 'hooks = false',
                  'plugins = false', 'apps = false', 'memories = false', 'multi_agent = false',
                  'computer_use = true', 'browser_use = false', 'browser_use_external = false',
                  'in_app_browser = false', '[mcp_servers.node_repl]',
                  f'command = {json.dumps(node_repl["command"])}', 'args = []', 'startup_timeout_sec = 120',
                  '[mcp_servers.node_repl.env]']
        lines += [f'{json.dumps(key)} = {json.dumps(value)}' for key, value in native_env.items()]
        # The skip-host flag did not suppress discovery in the real CLI. Disable exact resources too.
        roots = native_skill_roots if native_skill_roots is not None else [Path.home() / '.agents/skills', ROOT / '.agents/skills']
        exclusions = {path for root in roots for path in Path(root).rglob('SKILL.md')}
        builtin_root = Path(native_builtin_root) if native_builtin_root is not None else Path.home() / '.codex/skills/.system'
        for source in builtin_root.rglob('SKILL.md'):
            target = home / 'skills/.system' / source.relative_to(builtin_root)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            exclusions.add(target)
        for path in sorted({str(item) for source in exclusions for item in (source, source.parent)}):
            lines += ['[[skills.config]]', f'path = {json.dumps(path)}', 'enabled = false']
        (home / 'config.toml').write_text('\n'.join(lines) + '\n', encoding='utf-8')
        command = ['codex', '--no-daemon', 'exec', '--strict-config', '--ignore-rules',
                   '--skip-git-repo-check', '--json', '--model', MODEL,
                   '-c', 'model_reasoning_effort="low"', '-C', str(workspace), prompt]
        environment = {'CODEX_HOME': str(home)}
    skill_file = skill / 'SKILL.md'
    if not skill_file.is_file():
        raise FileNotFoundError(skill_file)
    plan = {'arm': arm, 'model': MODEL, 'reasoning': 'low', 'skill_names': [skill_name],
            'skill_path': str(skill_file), 'skill_sha256': hashlib.sha256(skill_file.read_bytes()).hexdigest(),
            'scenario_sha256': hashlib.sha256(scenario.encode('utf-8')).hexdigest(),
            'workspace': str(workspace), 'run_dir': str(run_dir), 'command': command,
            'environment_overrides': environment, 'isolation': 'configuration/prompt, not OS sandbox',
            'runtime_validated': False}
    save_json(run_dir / 'plan.json', plan)
    return plan


# Windows npm's .cmd launcher is replaced by its Node entry point, keeping prompts out of cmd.exe parsing.
def executable_command(command):
    executable = shutil.which(command[0])
    if executable is None:
        raise FileNotFoundError(f'{command[0]} is not on PATH')
    if Path(executable).suffix.lower() == '.cmd' and command[0] == 'pi':
        entry = Path(executable).parent / 'node_modules/@earendil-works/pi-coding-agent/dist/cli.js'
        if not entry.is_file():
            raise FileNotFoundError(entry)
        node = shutil.which('node')
        if node is None:
            raise FileNotFoundError('node is not on PATH')
        return [node, str(entry), *command[1:]]
    return [executable, *command[1:]]


# Capture raw JSONL and monotonic receipt timestamps, including failed or cancelled attempts.
def capture(command, cwd, environment, run_dir, timeout_s):
    from bench.processes import OwnedProcessTree

    records = []
    reader_errors = []
    failure = None
    started = time.perf_counter()
    tree = OwnedProcessTree()
    with (run_dir / 'stderr.log').open('w', encoding='utf-8') as stderr, (run_dir / 'stdout.jsonl').open('w', encoding='utf-8') as raw, (run_dir / 'events.jsonl').open('w', encoding='utf-8') as timed:
        try:
            process = tree.spawn(command, cwd=cwd, env=environment, stdin=subprocess.DEVNULL,
                                 stdout=subprocess.PIPE, stderr=stderr, text=True, encoding='utf-8')
        except BaseException:
            tree.stop()
            raise
        save_json(run_dir / 'state.json', {'worker_pid': os.getpid(), 'agent_pid': process.pid, 'status': 'running'})

        def drain():
            try:
                for line in process.stdout:
                    raw.write(line)
                    raw.flush()
                    event = json.loads(line)
                    record = {'elapsed_s': time.perf_counter() - started, 'event': event}
                    records.append(record)
                    timed.write(json.dumps(record, ensure_ascii=False) + '\n')
                    timed.flush()
            except Exception:
                reader_errors.append(traceback.format_exc())

        reader = threading.Thread(target=drain, daemon=True)
        reader.start()
        try:
            while process.poll() is None:
                if reader_errors:
                    raise RuntimeError(reader_errors[0])
                if (run_dir / 'cancel.request').exists():
                    raise InterruptedError('bench stop requested')
                if time.perf_counter() - started > timeout_s:
                    raise TimeoutError(f'agent exceeded {timeout_s}s')
                time.sleep(0.1)
            reader.join(timeout=2)
            if reader.is_alive():
                raise RuntimeError('a descendant held the stream open after root exit')
            if reader_errors:
                raise RuntimeError(reader_errors[0])
        except Exception:
            failure = traceback.format_exc()
            (run_dir / 'capture-crash.txt').write_text(failure, encoding='utf-8')
        finally:
            tree.stop()
            reader.join(timeout=10)
            if reader.is_alive():
                raise RuntimeError('stream reader did not stop after owned process tree termination')
            process.stdout.close()
    wall = time.perf_counter() - started
    save_json(run_dir / 'capture.json', {'passed': failure is None and process.returncode == 0,
                                        'error': failure, 'wall_s': wall, 'exit_code': process.returncode,
                                        'process_tree_stopped': True})
    save_json(run_dir / 'state.json', {'worker_pid': os.getpid(), 'agent_pid': process.pid,
                                     'status': 'exited', 'exit_code': process.returncode})
    return records, wall, process.returncode


# A claim never authorizes closing a pre-existing handle; current PID must also be checked by cleanup.ahk.
def owned_window(before, claim):
    hwnd = str(claim.get('hwnd', ''))
    pid = str(claim.get('pid', ''))
    if not hwnd.isdigit() or not int(hwnd) or not pid.isdigit() or not int(pid):
        raise ValueError('missing or invalid window/process identity')
    protected = set(re.findall(r'^(?:window|calculator)=(\d+)', before, re.MULTILINE))
    if hwnd in protected:
        raise ValueError('refusing cleanup of a pre-existing window')
    return hwnd, int(pid)



# Bind a returned numeric window ID to observed Win32 identity; reject guesses, old windows and PID changes.
def bind_owned_window(before, claim, observed):
    if 'hwnd' in claim:
        raw_id = claim['hwnd']
    elif 'window_id' in claim:
        raw_id = claim['window_id']
    elif 'window' in claim and 'id' in claim['window']:
        raw_id = claim['window']['id']
    else:
        raise ValueError('the actor supplied no returned window identity')
    value = str(raw_id)
    if not re.fullmatch(r'(?:0x[0-9a-fA-F]+|[0-9]+)', value):
        raise ValueError(f'unsupported opaque window identity: {value}')
    hwnd = str(int(value, 16 if value.startswith('0x') else 10))
    pids = dict(re.findall(r'^window=(\d+) pid=(\d+)\s*$', observed, re.MULTILINE))
    if hwnd not in pids:
        raise ValueError('returned window was not observed by the independent inspector')
    pid = int(pids[hwnd])
    if 'pid' in claim and int(claim['pid']) != pid:
        raise ValueError('claimed process identity does not match the observed window')
    return owned_window(before, {'hwnd': hwnd, 'pid': pid})


# A finished worker does not imply successful cleanup.
def cleanup_finished(finished):
    cleanup = finished.get('cleanup', {})
    return finished.get('worker_finished') is True and cleanup.get('passed') is True and cleanup.get('cursor_scheme_restored') is True

# The observer runs outside agent timing and is identical for all arms; it never solves the task.
def acu_observer(run_dir, script, *args, suffix=''):
    command = [sys.executable, str(ROOT / 'acu/run.py'), str(script), '--timeout', '15', '--', *map(str, args)]
    result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', timeout=25)
    name = Path(script).stem + suffix
    (run_dir / f'observer-{name}.log').write_text(result.stdout + result.stderr, encoding='utf-8')
    if result.returncode:
        raise RuntimeError(f'observer {name} exited {result.returncode}; see observer-{name}.log')
    return result.stdout



# Screen explicit keyboard/text/value injection; UI click and Invoke are allowed by scenario v3.
def script_input_violations(text):
    patterns = {
        'keyboard/text input': r'\b(?:Send|SendText|ControlSend|ControlSetText)\s*(?:\(|["\x27])',
        'direct field value': r'\.Value\s*:=|\.(?:SetValue|type_text|press_key|hotkey|set_value)\s*\(',
    }
    return [name for name, pattern in patterns.items() if re.search(pattern, text, re.IGNORECASE)]


# Independently verify displayed arithmetic against a fixed decimal reference, and preserve a screenshot.
def verify_calculator(run_dir, before):
    from decimal import Decimal
    result_file = run_dir / 'workspace/result.json'
    if not result_file.is_file():
        return {'passed': False, 'reason': 'agent did not write result.json'}
    claimed = load_actor_json(result_file)
    if claimed['status'] == 'blocked':
        return {'passed': False, 'reason': 'actor reported blocked', 'claim': claimed}
    identity = acu_observer(run_dir, ROOT / 'bench/probe.ahk', suffix='-bind')
    try:
        hwnd, pid = bind_owned_window(before, claimed, identity)
    except ValueError as error:
        return {'passed': False, 'reason': str(error), 'claim': claimed}
    observed = acu_observer(run_dir, ROOT / 'bench/verify.ahk', hwnd)
    displayed = re.search(r'^result=(.*)', observed, re.MULTILINE).group(1).strip()
    expression = re.search(r'^expression=(.*)', observed, re.MULTILINE).group(1).strip()
    number = re.search(r'[-−]?[\d,]+(?:\.\d+)?', displayed)
    if number is None:
        raise ValueError(f'cannot parse Calculator display: {displayed}')
    actual = Decimal(number.group().replace(',', '').replace('−', '-'))
    expected = Decimal('-12173.403768243628721844691744961')
    screenshot = run_dir / 'calculator-result.png'
    acu_observer(run_dir, ROOT / 'acu/screenshot.ahk', 'app', f'ahk_id {hwnd}', '--out', screenshot, '--max', '0')
    scripts = [path for path in (run_dir / 'workspace').rglob('*') if path.suffix.lower() in ('.ahk', '.py', '.js', '.mjs', '.ps1', '.sh')]
    forbidden = [str(script.relative_to(run_dir / 'workspace')) for script in scripts
                 if script_input_violations(script.read_text(encoding='utf-8-sig'))]
    return {'passed': abs(actual - expected) < Decimal('0.000000000001') and claimed['status'] == 'completed' and not forbidden,
            'hwnd': hwnd, 'observed_result': displayed, 'observed_expression': expression,
            'expected': str(expected), 'screenshot': str(screenshot), 'claim': claimed,
            'script_audit': {'forbidden_input_scripts': forbidden, 'note': 'Static screening plus transcript review; not a security boundary.'}}


# Run a single authorized desktop trial with fresh configuration and no parent coaching.
def run_trial(plan, timeout_s=240, reference_tps=None):
    run_dir = Path(plan['run_dir'])
    arm = plan['arm']
    credential = Path.home() / ('.pi/agent/auth.json' if arm.startswith('pi-') else '.codex/auth.json')
    private_auth = run_dir / 'agent-home/auth.json'
    if not credential.is_file():
        raise FileNotFoundError(f'saved login not found: {credential}')
    environment = {key: value for key, value in os.environ.items() if not key.startswith(('PI_', 'CODEX_', 'CUA_', 'SKY_', 'NODE_REPL_', 'BROWSER_USE_', 'BH_', 'BU_'))}
    environment.update(plan['environment_overrides'])
    environment['PYTHONUTF8'] = '1'
    before = acu_observer(run_dir, ROOT / 'bench/probe.ahk', suffix='-before')
    shutil.copyfile(credential, private_auth)
    try:
        records, wall, exit_code = capture(executable_command(plan['command']), plan['workspace'], environment, run_dir, timeout_s)
        if arm.startswith('pi-'):
            measurements = analyse_pi(records, wall, reference_tps)
            session_path = run_dir / 'session.jsonl'
            entries = read_jsonl(session_path) if session_path.is_file() else []
            isolation = audit_pi_session(entries, plan['skill_names'][0])
        else:
            measurements = analyse_codex(records, wall)
            native_sessions = list((run_dir / 'agent-home/sessions').rglob('*.jsonl'))
            native_entries = [entry for path in native_sessions for entry in read_jsonl(path)]
            isolation = audit_codex_session(native_entries)
        measurements['capture'] = json.loads((run_dir / 'capture.json').read_text(encoding='utf-8'))
        measurements['token_counts_complete'] = measurements.get('agent_completed', False)
        save_json(run_dir / 'metrics.json', measurements)
        save_json(run_dir / 'isolation.json', isolation)
        plan['runtime_validated'] = isolation['passed']
        save_json(run_dir / 'plan.json', plan)
        verification = verify_calculator(run_dir, before)
        save_json(run_dir / 'verification.json', verification)
        summary = {'arm': arm, 'model': MODEL, 'reasoning': 'low', 'exit_code': exit_code,
                   'isolation_passed': isolation['passed'], 'task_passed': verification['passed'],
                   'passed': exit_code == 0 and isolation['passed'] and verification['passed'] and measurements['capture']['passed'],
                   'metrics': measurements, 'evidence_dir': str(run_dir)}
        save_json(run_dir / 'summary.json', summary)
        return summary
    except Exception:
        (run_dir / 'crash.txt').write_text(traceback.format_exc(), encoding='utf-8')
        raise
    finally:
        private_auth.unlink(missing_ok=True)
        ownership_file = run_dir / 'workspace/ownership.json'
        try:
            if ownership_file.is_file():
                claimed = load_actor_json(ownership_file)
                identity = acu_observer(run_dir, ROOT / 'bench/probe.ahk', suffix='-cleanup-bind')
                hwnd, pid = bind_owned_window(before, claimed, identity)
                acu_observer(run_dir, ROOT / 'bench/cleanup.ahk', hwnd, pid)
            after = acu_observer(run_dir, ROOT / 'bench/probe.ahk', suffix='-after')
            old = set(re.findall(r'^calculator=(\d+)', before, re.MULTILINE))
            remaining = set(re.findall(r'^calculator=(\d+)', after, re.MULTILINE)) - old
            acu_observer(run_dir, ROOT / 'bench/restore_cursor.ahk')
            cleanup = {'passed': not remaining, 'remaining_new_calculator_windows': sorted(remaining),
                       'cursor_scheme_restored': True, 'cursor_verification': 'Saved Windows scheme reloaded and OS showing flag checked; not a pixel-level visibility proof.'}
            save_json(run_dir / 'cleanup.json', cleanup)
            if remaining:
                raise RuntimeError(f'unclaimed Calculator windows remain; do not auto-close: {sorted(remaining)}')
        except Exception:
            save_json(run_dir / 'cleanup.json', {'passed': False, 'error': traceback.format_exc()})
            raise



# Enforce one bench controller at a time and preserve a traceback even for setup/cleanup failures.
def run(plan, timeout_s=240, reference_tps=None):
    run_dir = Path(plan['run_dir'])
    control_dir = ROOT / '.pi/bench'
    control_dir.mkdir(parents=True, exist_ok=True)
    lock = control_dir / 'active.lock'
    with lock.open('x', encoding='utf-8') as handle:
        json.dump({'worker_pid': os.getpid(), 'run_dir': str(run_dir)}, handle)
    try:
        attempt = run_dir / 'run-attempt.json'
        with attempt.open('x', encoding='utf-8') as handle:
            json.dump({'worker_pid': os.getpid(), 'started_at': datetime.now(timezone.utc).isoformat()}, handle)
        value = run_trial(plan, timeout_s, reference_tps)
        cleanup = load_actor_json(run_dir / 'cleanup.json')
        value['cleanup_passed'] = cleanup.get('passed') is True and cleanup.get('cursor_scheme_restored') is True
        value['passed'] = value['passed'] and value['cleanup_passed']
        save_json(run_dir / 'summary.json', value)
        return value
    except Exception:
        (run_dir / 'crash.txt').write_text(traceback.format_exc(), encoding='utf-8')
        summary_path = run_dir / 'summary.json'
        if summary_path.is_file():
            value = load_actor_json(summary_path)
            value.update(passed=False, cleanup_passed=False)
            save_json(summary_path, value)
        raise
    finally:
        (run_dir / 'agent-home/auth.json').unlink(missing_ok=True)
        lock.unlink()
        cleanup_path = run_dir / 'cleanup.json'
        cleanup = json.loads(cleanup_path.read_text(encoding='utf-8')) if cleanup_path.is_file() else {'passed': False, 'error': 'cleanup was not recorded'}
        save_json(run_dir / 'finished.json', {'worker_pid': os.getpid(), 'worker_finished': True,
                  'cleanup': cleanup, 'finished_at': datetime.now(timezone.utc).isoformat()})

# Codex exec exposes final aggregate usage; its stream does not expose a true decoding-rate denominator.
def analyse_codex(records, wall_s):
    completed = [r for r in records if r['event']['type'] == 'turn.completed']
    if not completed:
        return {'wall_s': wall_s, 'tokens': None, 'model_response_s': None,
                'effective_output_tps': None, 'end_to_end_output_tps': None,
                'agent_completed': False, 'timing_limitation': 'No final Codex usage was reported; token totals are unknown, not zero.'}
    if len(completed) != 1:
        raise ValueError('expected exactly one Codex turn.completed usage record')
    usage = completed[0]['event']['usage']
    return {'wall_s': wall_s, 'tokens': {'input_including_cached': usage['input_tokens'],
            'cache_read': usage['cached_input_tokens'], 'output_including_reasoning': usage['output_tokens'],
            'total': usage['input_tokens'] + usage['output_tokens'], 'reasoning_subset': None},
            'model_response_s': None, 'effective_output_tps': None,
            'end_to_end_output_tps': usage['output_tokens'] / wall_s,
            'timing_limitation': 'Exec has no per-response model latency. End-to-end throughput includes tool time; do not treat it as decoding speed.',
            'agent_completed': True}


# Public CLI: prepare is read-only/offline; run is an explicit desktop operation.
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'run', 'analyse'))
    parser.add_argument('--arm', choices=ARMS, default='pi-acu')
    parser.add_argument('--run-dir', type=Path)
    parser.add_argument('--desktop-approved', action='store_true')
    parser.add_argument('--timeout', type=float, default=240)
    parser.add_argument('--reference-tps', type=float)
    args = parser.parse_args()
    if args.action == 'run' and not args.desktop_approved:
        parser.error('run requires approval for this specific desktop trial (--desktop-approved)')
    if args.action == 'analyse':
        if not args.run_dir:
            parser.error('analyse requires --run-dir')
        prior = json.loads((args.run_dir / 'metrics.json').read_text(encoding='utf-8'))
        value = analyse_pi(read_jsonl(args.run_dir / 'events.jsonl'), prior['wall_s'], args.reference_tps)
    else:
        directory = args.run_dir or ROOT / '.pi/bench' / f'{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{args.arm}'
        if args.action == 'run' and (directory / 'plan.json').is_file():
            plan = json.loads((directory / 'plan.json').read_text(encoding='utf-8'))
            if plan['arm'] != args.arm:
                parser.error('the requested arm does not match the prepared profile')
            if (directory / 'state.json').exists() or (directory / 'run-attempt.json').exists():
                parser.error('a run directory cannot be reused; prepare a fresh trial')
        else:
            plan = prepare(args.arm, directory)
        value = run(plan, args.timeout, args.reference_tps) if args.action == 'run' else plan
    print(json.dumps(value, ensure_ascii=False, indent=2))
    if args.action == 'run' and not value['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
