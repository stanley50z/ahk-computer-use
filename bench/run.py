"""Run fresh, isolated computer-use sessions and measure their JSON event streams.

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
import traceback
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bench.common import ROOT, load_actor_json, read_jsonl, save_json, actor_path, expand_user_root
from bench.calculator import (EXPRESSION, EXPECTED, actor_window, bind_owned_window,
                              new_calculator_window, owned_window, script_input_methods)
from bench.scenario import Trial
from bench.scenarios import SCENARIOS, get_scenario
from bench.runtime import ensure_project_runtime
from bench.tool_calls import ToolCall, completed_calls, argument_text

from bench.arms import ARM_TABLE, ARMS, arm_model, uses_cua_daemon
# Preserve the established analysis/command imports while implementation lives in each adapter.
from bench.harnesses.pi import (MODEL, PI_PROVIDER, REASONING, PI_RECOVERY_POLICY, TOOLS, NATIVE_TOOLS,
                                analyse_pi, audit_pi_session, pi_command, native_skill, native_server)
from bench.harnesses.claude import CLAUDE_RECOVERY_POLICY, CLAUDE_TOOLS, analyse_claude, audit_claude_session, claude_command
from bench.harnesses.codex import analyse_codex, audit_codex_session

WINDOW_AUDIT_POLICY = 'diagnostic-only-v1'


# Historical end-to-end timing only. New benchmark scoring uses measure_efficiency; old evidence remains unchanged.
def task_time(agent_start_s, tools: list[ToolCall], pattern, workspace):
    helpers = set()  # names a computer-use call defined; a persistent REPL lets later calls reach the route through them

    def uses_computer(text):
        if re.search(pattern, text) or any(re.search(rf'\b{re.escape(name)}\s*\(', text) for name in helpers):
            return True
        for name in set(re.findall(r'[\w.-]+\.(?:py|ahk|js|mjs|ps1|sh)\b', text)):
            script = Path(workspace) / name
            if script.is_file() and re.search(pattern, script.read_text(encoding='utf-8-sig', errors='replace')):
                return True
        return False

    uses = []
    for tool in sorted(completed_calls(tools), key=lambda tool: tool['start_s'] if tool['start_s'] is not None else tool['end_s']):
        if str(tool.get('name', '')).casefold() in ('read', 'write', 'edit'):
            continue
        text = tool.get('text', '')
        if uses_computer(text):
            uses.append(tool)
            helpers.update(name for pair in re.findall(r'globalThis\.(\w+)\s*=|\b(?:const|let|var|function|def)\s+(\w+)', text) for name in pair if name)
    definition = 'Session start (skill received) to the end of the last computer-use tool call, by receipt timestamps. Result files and the final answer are excluded.'
    if agent_start_s is None or not uses:
        return {'task_s': None, 'computer_use_calls': len(uses), 'definition': definition,
                'reason': 'no session start or no computer-use call was observed'}
    last = max(tool['end_s'] for tool in uses)
    return {'task_s': last - agent_start_s, 'start_s': agent_start_s, 'last_computer_use_end_s': last,
            'computer_use_calls': len(uses), 'definition': definition}


# The shared cua-driver daemon remembers ended session labels, and every fresh CUA actor named its first session after
# the scenario, so each trial after the first paid a rejected call. By the user's decision (2026-10-10) the daemon is
# restarted before every CUA trial, outside timing, so the actor meets the same empty state the first one did.
# With cwd, the daemon restarts through the bench copy of its autostart task (bench/cua_bench_task.py) in that
# directory, so a relative screenshot_out_file lands there instead of the home folder; without cwd, the installed
# autostart entry restores the as-installed daemon.
def restart_cua_daemon(run_dir, driver='cua-driver', timeout_s=30, cwd=None, record_name='daemon-restart.json'):
    from bench.cua_bench_task import BENCH_TASK, CWD_FILE, installed, start_command

    if cwd and not installed():
        raise RuntimeError(f'{BENCH_TASK} is not registered; run python bench/cua_bench_task.py install once (UAC)')

    def status():
        return subprocess.run([driver, 'status'], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=30).stdout

    record = {'driver': driver, 'cwd': str(cwd) if cwd else None, 'before': status()}
    record['stop'] = subprocess.run([driver, 'stop'], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=60).stdout
    deadline = time.monotonic() + timeout_s
    while 'is running' in status() and time.monotonic() < deadline:
        time.sleep(0.5)
    if cwd:
        CWD_FILE.parent.mkdir(parents=True, exist_ok=True)
        CWD_FILE.write_text(str(Path(cwd).resolve()), encoding='utf-8')
    start = start_command() if cwd else [driver, 'autostart', 'kick']
    record['start'] = subprocess.run(start, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=60).stdout
    while 'is running' not in status() and time.monotonic() < deadline:
        time.sleep(0.5)
    record['after'] = status()
    record['sessions'] = subprocess.run([driver, 'list_sessions', '{}'], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=60).stdout
    record['passed'] = 'is running' in record['after'] and '"sessions": []' in record['sessions'].replace('\n', '').replace(' ', '').replace('"sessions":[]', '"sessions": []')
    save_json(Path(run_dir) / record_name, record)
    if not record['passed']:
        raise RuntimeError(f'cua-driver daemon did not come back empty; see {record_name}')
    return record


# Prepare reproducible, offline profiles without credentials or a live desktop session.
def prepare(arm, run_dir, *, scenario='calculator', skill=None, native_config=None, native_transport='sdk-helper'):
    adapter = get_scenario(scenario)
    scenario_name = scenario
    if arm not in ARMS:
        raise ValueError(f'unknown arm: {arm}')
    if native_transport not in ('sdk-helper', 'app-pipe'):
        raise ValueError(f'unknown native transport: {native_transport}')
    adapter.validate_assets()
    run_dir = Path(run_dir).resolve()
    run_dir.mkdir(parents=True, exist_ok=False)
    workspace, home = run_dir / 'workspace', run_dir / 'agent-home'
    workspace.mkdir()
    (workspace / '.ahk-computer-use').mkdir()
    save_json(workspace / '.ahk-computer-use/settings.json', {'snippets': {'enabled': False}})
    home.mkdir()
    scenario = (ROOT / f'bench/scenarios/{scenario_name}.md').read_text(encoding='utf-8')
    (run_dir / 'scenario.md').write_text(scenario, encoding='utf-8')
    # The first line is the file's own title and version, for people. The actor receives only the body.
    heading, _, prompt = scenario.partition('\n')
    template = prompt.strip() + '\n'
    prompt = template.replace('<WORKSPACE>', actor_path(workspace))
    (run_dir / 'prompt-template.txt').write_text(template, encoding='utf-8')
    (run_dir / 'prompt.txt').write_text(prompt, encoding='utf-8')
    arm_spec = ARM_TABLE[arm]
    host = arm_spec.harness
    model, reasoning = arm_model(arm)
    profile = host.profile(arm_spec, run_dir, prompt, skill, native_config, native_transport,
                           adapter.approved_apps() if arm_spec.native else [])
    skill = profile.pop('skill')
    skill_file = skill / 'SKILL.md'
    if not skill_file.is_file():
        raise FileNotFoundError(skill_file)
    plan = {'arm': arm, 'scenario': scenario_name, 'model': model, 'reasoning': reasoning, 'skill_names': [arm_spec.skill_name],
            'skill_path': str(skill_file), 'skill_sha256': hashlib.sha256(skill_file.read_bytes()).hexdigest(),
            'scenario_version': heading.lstrip('# ').strip(), 'prompt_sha256': hashlib.sha256(prompt.encode('utf-8')).hexdigest(),
            'prompt_template_sha256': hashlib.sha256(template.encode('utf-8')).hexdigest(),
            'scenario_sha256': hashlib.sha256(scenario.encode('utf-8')).hexdigest(),
            'measurement_policy': 'tokens-and-computer-use-v1', 'window_audit_policy': WINDOW_AUDIT_POLICY,
            'recovery_policy': deepcopy(host.recovery_policy),
            'workspace': str(workspace), 'run_dir': str(run_dir), **profile, 'isolation': 'configuration/prompt, not OS sandbox',
            'runtime_validated': False}
    adapter.prepare_files(plan)
    save_json(run_dir / 'plan.json', plan)
    return plan


# Delegate command resolution to its harness, leaving ordinary test emitters unchanged.
def executable_command(command):
    from bench.common import executable_command as installed_command
    host = next((arm.harness for arm in ARM_TABLE.values() if arm.harness.name == command[0]), None)
    return host.executable_command(command) if host else installed_command(command)


# Capture raw JSONL until normal exit or explicit cancellation; there is no overall elapsed-time deadline.
def capture(command, cwd, environment, run_dir):
    from bench.processes import OwnedProcessTree

    records = []
    reader_errors = []
    failure = None
    cancelled = False
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
                time.sleep(0.1)
            reader.join(timeout=2)
            if reader.is_alive():
                raise RuntimeError('a descendant held the stream open after root exit')
            if reader_errors:
                raise RuntimeError(reader_errors[0])
        except Exception as error:
            cancelled = isinstance(error, InterruptedError)
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
                                        'process_tree_stopped': True, 'cancelled': cancelled})
    save_json(run_dir / 'state.json', {'worker_pid': os.getpid(), 'agent_pid': process.pid,
                                     'status': 'exited', 'exit_code': process.returncode})
    return records, wall, process.returncode


# ---------------------------------------------------------------------------------------------------------------
# Conduct audit. The prompt carries no safeguards (user decision, 2026-10-11); instead the bench checks after every
# trial whether the actor stayed inside its lane, and reports what it finds. Evidence sources:
#   1. a SHA-256 fingerprint of the files an actor could tamper with, taken before and after;
#   2. the transcript: write/edit tool calls and shell commands that name a path outside the workspace;
#   3. the window probes: pre-existing visible windows that vanished, and new non-Calculator windows left behind;
#   4. bounded external-file metadata correlated with verified runtime capture requests and returned destinations.

FINGERPRINT_SKIP = {'.git', '.pi', '.venv', '__pycache__', 'openwiki', 'node_modules', '.pytest_cache', 'dist', '.agents', '.claude'}


# relpath -> sha256 for every file under the given roots, skipping caches and the bench's own evidence.
def fingerprint(roots):
    digest = {}
    for root in roots:
        root = Path(root)
        if root.is_file():
            digest[str(root)] = hashlib.sha256(root.read_bytes()).hexdigest()
            continue
        if not root.is_dir():
            continue
        for path in sorted(root.rglob('*')):
            if path.is_file() and not (set(path.relative_to(root).parts[:-1]) & FINGERPRINT_SKIP):
                try:
                    digest[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
                except OSError:
                    digest[str(path)] = 'unreadable'
    return digest


# The roots an actor of this arm could tamper with: the whole checkout (minus FINGERPRINT_SKIP) and its installed skill.
# On 2026-10-21 a TB3 actor saved a screenshot into the repository root, which the earlier per-directory list missed.
def guarded_roots(plan, scenario=None):
    scenario = scenario if scenario is not None else get_scenario(plan.get('scenario', 'calculator'))
    roots = [ROOT, Path(plan['skill_path']).parent]
    if plan.get('arm') and ARM_TABLE[plan['arm']].native:
        roots += [Path(plan['run_dir']) / 'agent-home/mcp.json', Path(plan['run_dir']) / 'agent-home/native-bridge.json']
    roots += scenario.guarded_roots(plan)
    return [root for root in roots if root.exists()]


# Move files the actor demonstrably created outside its run folder into <run>/stray/, so none outlives the trial and
# trips a later one. Evidence: files added under a guarded root, and screenshot paths the runtime reported that were
# absent from the home or temp folder before the trial. Overwritten pre-existing files stay put; conduct is unchanged.
def move_stray_files(run_dir, conduct):
    run_dir = Path(run_dir).resolve()
    candidates = list(conduct['guarded_files']['added'])
    candidates += [output['path'] for output in conduct['runtime_writes']['outputs']
                   if 'after' in output and output['before'] is None and output['after'] is not None]
    moved = []
    for source in dict.fromkeys(Path(path) for path in candidates):
        if not source.is_file() or source.resolve().is_relative_to(run_dir):
            continue
        target = run_dir / 'stray' / source.name
        for number in range(2, 1000):
            if not target.exists():
                break
            target = target.with_name(f'{source.stem}-{number}{source.suffix}')
        target.parent.mkdir(exist_ok=True)
        try:
            shutil.move(source, target)
            moved.append({'from': str(source), 'to': str(target)})
        except OSError as error:
            moved.append({'from': str(source), 'error': str(error)})
    return moved


def fingerprint_diff(before, after):
    return {'changed': sorted(p for p in before if p in after and before[p] != after[p]),
            'added': sorted(p for p in after if p not in before), 'removed': sorted(p for p in before if p not in after)}


WRITE_VERBS = r'(?:>>?|\bsed\s+-i|\brm\b|\bmv\b|\bcp\b|\btee\b|\bdel\b|\bmkdir\b|Set-Content|Out-File|Add-Content|New-Item|Remove-Item|Move-Item|Copy-Item|writeFile|FileAppend|FileDelete|FileMove|FileCopy|FileOpen\([^)]*["\x27]\s*[wa])'
PATH_TOKEN = r'(?<![\w/.])(?:[A-Za-z]:[\\/]|/[a-z]/|~/|\$HOME/|\$env:USERPROFILE)[^\s"\x27`)>;|&]*'  # a path token, not a sed pattern like s/a/b/


# Is a path inside the workspace? Relative paths resolve against it, which is the actor's working directory.
def inside_workspace(path, workspace):
    text = str(path).strip().strip('"\x27')
    if re.match(r'^/[a-z]/', text):  # Git Bash form
        text = f'{text[1]}:{text[2:]}'
    try:
        target = expand_user_root(text)
        resolved = (Path(workspace) / target).resolve() if not target.is_absolute() else target.resolve()
        resolved.relative_to(Path(workspace).resolve())
        return True
    except (ValueError, OSError):
        return False


# Transcript scan: explicit write/edit tool calls outside the workspace, and commands or scripts that pair a write verb
# with an absolute path outside it. The second list is a heuristic and is reported as such.
def transcript_writes(tools: list[ToolCall], workspace):
    outside, suspicious = [], []
    for tool in completed_calls(tools):
        name = str(tool.get('name', '')).casefold()
        text = tool.get('text', '')
        if name in ('write', 'edit'):
            target = text.split('\n', 1)[0]
            if not inside_workspace(target, workspace):
                outside.append({'tool': tool.get('name'), 'path': target})
            continue
        if re.search(WRITE_VERBS, text):
            for token in set(re.findall(PATH_TOKEN, text)):
                if not inside_workspace(token, workspace) and not re.search(r'SKILL\.md$|\.md$|/acu/(?:tree|screenshot)\.ahk$|\bacu\b$', token.replace('\\', '/')):
                    suspicious.append({'tool': tool.get('name'), 'path': token, 'command': text[:200]})
    return outside, suspicious


# Window diff from the observer probes. A handle is pre-existing if the before probe listed it visible or hidden:
# background windows toggle visibility on their own (a tray flyout did so between trials), and that is not the actor's
# doing. Closed means a visible pre-existing handle no longer exists at all; left open means a visible non-Calculator
# handle that did not exist before.
def window_diff(before, after, application='calculator', *, group_process_windows=False):
    def visible(probe):
        return dict(re.findall(r'^window=(\d+) pid=(\d+)\s*$', probe, re.MULTILINE))

    def every(probe):
        return set(re.findall(r'^(?:window|hiddenwindow)=(\d+) pid=', probe, re.MULTILINE))
    old, new, existed, exists = visible(before), visible(after), every(before), every(after)
    task_windows = set(re.findall(rf'^{application}=(\d+)', after, re.MULTILINE))
    ignored_shadows = set()
    if group_process_windows:
        # Illustrator owns its floating panels and contextual task bars in the same process as its main frame.
        # Do not generalize this to Calculator's shared ApplicationFrameHost.
        task_pids = {new[hwnd] for hwnd in task_windows if hwnd in new}
        task_windows.update(hwnd for hwnd, pid in new.items() if pid in task_pids)
        old_classes = dict(re.findall(r'^class=(\d+) (.+)$', before, re.MULTILINE))
        ignored_shadows = {hwnd for hwnd, cls in old_classes.items() if cls == 'SysShadow' and old.get(hwnd) in task_pids}
    return {'closed_preexisting': sorted(h for h in old if h not in exists and h not in ignored_shadows),
            'new_non_calculator': sorted(h for h in new if h not in existed and h not in task_windows)}


# Combine guarded-file, transcript, window and bounded runtime-output evidence before maintainer cleanup.
def conduct_audit(plan, before_probe, after_probe, before_files, after_files, tools: list[ToolCall], *,
                  runtime_before=None, runtime_after=None, scenario=None):
    from bench.runtime_writes import audit_runtime_writes

    runtime_writes = audit_runtime_writes(tools, runtime_before, runtime_after)
    files = fingerprint_diff(before_files, after_files)
    outside, suspicious = transcript_writes(tools, plan['workspace'])
    scenario = scenario if scenario is not None else get_scenario(plan.get('scenario', 'calculator'))
    windows = window_diff(before_probe, after_probe, scenario.application, group_process_windows=scenario.group_process_windows)
    problems = []
    if files['changed'] or files['added'] or files['removed']:
        problems.append('guarded files changed')
    if outside and scenario.fail_outside_writes:
        problems.append('write tool used outside the workspace')
    if any(output['status'] == 'preexisting_changed' for output in runtime_writes['outputs']):
        problems.append('runtime screenshot overwrote pre-existing file')
    return {'passed': not problems, 'problems': problems, 'runtime_writes': runtime_writes, 'guarded_files': files, 'guarded_roots': [str(r) for r in guarded_roots(plan, scenario)],
            'writes_outside_workspace': outside, 'suspicious_commands': suspicious, 'windows': windows,
            'window_audit_policy': WINDOW_AUDIT_POLICY,
            'note': ('Detection after the fact, not prevention. Window-handle changes and suspicious_commands are diagnostic only; '
                     'Illustrator scratch locations are observations, not disqualifiers. Verified pre-existing runtime-output overwrites fail conduct; '
                     'ambiguous runtime evidence stays unverified. Guarded-file and protected-document checks remain authoritative.')}


# A finished worker does not imply successful cleanup.
def cleanup_finished(finished):
    cleanup = finished.get('cleanup', {})
    return finished.get('worker_finished') is True and cleanup.get('passed') is True and cleanup.get('cursor_scheme_restored') is True

# The observer runs outside agent timing and is identical for all arms; it never solves the task.
def acu_observer(run_dir, script, *args, suffix='', timeout=15):
    command = [sys.executable, str(ROOT / 'acu/run.py'), str(script), '--timeout', str(timeout), '--', *map(str, args)]
    result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', timeout=timeout + 10)
    name = Path(script).stem + suffix
    (run_dir / f'observer-{name}.log').write_text(result.stdout + result.stderr, encoding='utf-8')
    if result.returncode:
        raise RuntimeError(f'observer {name} exited {result.returncode}; see observer-{name}.log')
    return result.stdout



# Run one authorized trial without an overall time limit; individual runtime/watchdog waits still apply.
def run_trial(plan, reference_tps=None, *, scenario=None, capture_actor=None, observer=None):
    from bench.efficiency import measure_efficiency, token_count

    scenario = scenario if scenario is not None else get_scenario(plan.get('scenario', 'calculator'))
    capture_actor = capture_actor if capture_actor is not None else capture
    observer = observer if observer is not None else acu_observer
    token_count('')  # Load the pinned reference encoding before starting any desktop work.
    run_dir = Path(plan['run_dir'])
    arm = plan['arm']
    host = ARM_TABLE[arm].harness
    host.validate_plan(plan)
    source, private_name = host.credential
    credential = Path.home() / source
    private_auth = run_dir / 'agent-home' / private_name
    if not credential.is_file():
        raise FileNotFoundError(f'saved login not found: {credential}')
    environment = {key: value for key, value in os.environ.items()
                   if not key.startswith(('PI_', 'CODEX_', 'CUA_', 'SKY_', 'NODE_REPL_', 'BROWSER_USE_', 'BH_', 'BU_', 'CLAUDE_', 'ANTHROPIC_'))}
    environment.update(plan['environment_overrides'])
    environment['PYTHONUTF8'] = '1'
    if uses_cua_daemon(arm):
        restart_cua_daemon(run_dir, cwd=plan['workspace'])
    if plan.get('native_transport') == 'app-pipe':
        pipe_name = plan['native_pipe'].rsplit('\\', 1)[-1]
        if os.name == 'nt' and pipe_name not in os.listdir('\\\\.\\pipe\\'):
            raise RuntimeError(f'the Codex Desktop app pipe {pipe_name} is not open; start the app before an app-pipe trial')
    before = observer(run_dir, ROOT / 'bench/probe.ahk', suffix='-before')
    trial = Trial(plan, observer, before)
    recorder = None
    try:
        scenario.prepare_desktop(trial)
        before_actor = observer(run_dir, ROOT / 'bench/probe.ahk', suffix='-before-actor') if scenario.prepares_desktop else before
        before_files = fingerprint(guarded_roots(plan, scenario))
        save_json(run_dir / 'fingerprint-before.json', before_files)
        shutil.copyfile(credential, private_auth)
        from bench.runtime_writes import snapshot_runtime_files
        runtime_before = snapshot_runtime_files()
        save_json(run_dir / 'runtime-files-before.json', runtime_before)
        recorder = scenario.start_recorder(run_dir)  # Only actor input falls inside the recording.
        trial.actor_started = True
        try:
            records, wall, exit_code = capture_actor(executable_command(plan['command']), plan['workspace'], environment, run_dir)
        finally:
            if recorder is not None:
                scenario.stop_recorder(run_dir, recorder)
            runtime_after = snapshot_runtime_files()
            save_json(run_dir / 'runtime-files-after.json', runtime_after)
        measurements = host.analyse(records, wall, reference_tps,
                                    cancelled=load_actor_json(run_dir / 'capture.json').get('cancelled') is True)
        # Persist before transcript IO, grading or cleanup so a later failure cannot hide the provider error.
        unexpected_failure = measurements.get('unexpected_failure')
        if unexpected_failure:
            save_json(run_dir / 'failure.json', unexpected_failure)
        isolation = host.audit(plan, records)
        measurements['capture'] = json.loads((run_dir / 'capture.json').read_text(encoding='utf-8'))
        measurements['benchmark'] = measure_efficiency(measurements, arm)
        save_json(run_dir / 'metrics.json', measurements)
        save_json(run_dir / 'isolation.json', isolation)
        plan['runtime_validated'] = isolation['passed']
        save_json(run_dir / 'plan.json', plan)
        if scenario.verify_before_audit:
            verification = scenario.collect_and_grade(trial, measurements.get('tools', []))
            save_json(run_dir / 'verification.json', verification)
        after_probe = observer(run_dir, ROOT / 'bench/probe.ahk', suffix='-conduct')
        after_files = fingerprint(guarded_roots(plan, scenario))
        save_json(run_dir / 'fingerprint-after.json', after_files)
        conduct = conduct_audit(plan, before_actor, after_probe, before_files, after_files, measurements.get('tools', []),
                                runtime_before=runtime_before, runtime_after=runtime_after, scenario=scenario)
        scenario.audit(trial, conduct)
        conduct['stray_files'] = move_stray_files(run_dir, conduct)
        save_json(run_dir / 'conduct.json', conduct)
        if not scenario.verify_before_audit:
            verification = scenario.collect_and_grade(trial, measurements.get('tools', []))
            save_json(run_dir / 'verification.json', verification)
        summary = {'arm': arm, 'model': plan['model'], 'reasoning': plan['reasoning'], 'exit_code': exit_code,
                   'benchmark': measurements['benchmark'],
                   'diagnostics': {'wall_s': wall, 'note': 'Not a benchmark ranking metric.'},
                   'isolation_passed': isolation['passed'], 'task_passed': verification['passed'], 'conduct_passed': conduct['passed'],
                   'conduct_problems': conduct['problems'],
                   'passed': exit_code == 0 and measurements['agent_completed'] and isolation['passed'] and verification['passed'] and conduct['passed'] and measurements['capture']['passed'],
                   'unexpected_failure': unexpected_failure,
                   'recovered_provider_errors': measurements.get('recovered_provider_errors', []),
                   'metrics': measurements, 'evidence_dir': str(run_dir)}
        scenario.summarize(summary, plan, verification, conduct, isolation)
        save_json(run_dir / 'summary.json', summary)
        return summary
    except Exception:
        (run_dir / 'crash.txt').write_text(traceback.format_exc(), encoding='utf-8')
        raise
    finally:
        private_auth.unlink(missing_ok=True)
        if uses_cua_daemon(arm):
            try:
                restart_cua_daemon(run_dir, record_name='daemon-restore.json')
            except Exception:  # noqa: BLE001 - the next CUA trial restarts it anyway; keep the evidence, finish cleanup
                (run_dir / 'daemon-restore-error.txt').write_text(traceback.format_exc(), encoding='utf-8')
        try:
            try:
                cleanup = scenario.cleanup(trial)
            finally:
                observer(run_dir, ROOT / 'bench/restore_cursor.ahk')
            cleanup['cursor_scheme_restored'] = True
            cleanup['cursor_verification'] = scenario.cursor_verification
            save_json(run_dir / 'cleanup.json', cleanup)
            scenario.check_cleanup(cleanup)
        except Exception:
            save_json(run_dir / 'cleanup.json', {'passed': False, 'error': traceback.format_exc()})
            raise


# Enforce one bench controller at a time and preserve a traceback even for setup/cleanup failures.
def run(plan, reference_tps=None, *, scenario=None, capture_actor=None, observer=None):
    run_dir = Path(plan['run_dir'])
    scenario = scenario if scenario is not None else get_scenario(plan.get('scenario', 'calculator'))
    control_dir = ROOT / '.pi/bench'
    control_dir.mkdir(parents=True, exist_ok=True)
    lock = control_dir / 'active.lock'
    with lock.open('x', encoding='utf-8') as handle:
        json.dump({'worker_pid': os.getpid(), 'run_dir': str(run_dir)}, handle)
    try:
        attempt = run_dir / 'run-attempt.json'
        with attempt.open('x', encoding='utf-8') as handle:
            json.dump({'worker_pid': os.getpid(), 'started_at': datetime.now(timezone.utc).isoformat()}, handle)
        value = run_trial(plan, reference_tps, scenario=scenario, capture_actor=capture_actor, observer=observer)
        cleanup = load_actor_json(run_dir / 'cleanup.json')
        scenario.finalize_summary(value, cleanup)
        save_json(run_dir / 'summary.json', value)
        return value
    except Exception:
        (run_dir / 'crash.txt').write_text(traceback.format_exc(), encoding='utf-8')
        summary_path = run_dir / 'summary.json'
        if summary_path.is_file():
            value = load_actor_json(summary_path)
            scenario.finalize_summary(value, {}, failed=True)
            save_json(summary_path, value)
        raise
    finally:
        for private_name in {arm.harness.credential[1] for arm in ARM_TABLE.values()}:
            (run_dir / 'agent-home' / private_name).unlink(missing_ok=True)
        lock.unlink()
        cleanup_path = run_dir / 'cleanup.json'
        cleanup = json.loads(cleanup_path.read_text(encoding='utf-8')) if cleanup_path.is_file() else {'passed': False, 'error': 'cleanup was not recorded'}
        save_json(run_dir / 'finished.json', {'worker_pid': os.getpid(), 'worker_finished': True,
                  'cleanup': cleanup, 'finished_at': datetime.now(timezone.utc).isoformat()})

# Public CLI: prepare is read-only/offline; run is an explicit desktop operation.
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'run', 'analyse'))
    parser.add_argument('--arm', choices=ARMS, default='pi-acu')
    parser.add_argument('--scenario', choices=SCENARIOS, default='calculator')
    parser.add_argument('--run-dir', type=Path)
    parser.add_argument('--desktop-approved', action='store_true')
    parser.add_argument('--native-transport', choices=('sdk-helper', 'app-pipe'), default='sdk-helper',
                        help="pi-computer-use only: the shipped SDK helper (default) or the running Codex Desktop app's pipe")
    parser.add_argument('--exclude-interrupted-turns', action='store_true',
                        help='Pi offline analysis only: exclude interrupted assistant responses from the counted cohort')
    args = parser.parse_args()
    if args.exclude_interrupted_turns and args.action != 'analyse':
        parser.error('--exclude-interrupted-turns is only available for offline analyse')
    if args.action == 'run' and not args.desktop_approved:
        parser.error('run requires approval for this specific desktop trial (--desktop-approved)')
    if args.action == 'analyse' and not args.run_dir:
        parser.error('analyse requires --run-dir')
    ensure_project_runtime(Path(__file__).resolve())
    if args.action == 'analyse':
        from bench.efficiency import measure_efficiency
        prior = json.loads((args.run_dir / 'metrics.json').read_text(encoding='utf-8'))
        plan = json.loads((args.run_dir / 'plan.json').read_text(encoding='utf-8'))
        records = read_jsonl(args.run_dir / 'events.jsonl')
        host = ARM_TABLE[plan['arm']].harness
        if args.exclude_interrupted_turns and not host.supports_interrupted_exclusion:
            parser.error('--exclude-interrupted-turns requires per-response Pi usage; other harnesses are unsupported')
        value = host.analyse(records, prior['wall_s'], cancelled=(prior.get('capture') or {}).get('cancelled') is True,
                             exclude_interrupted_turns=args.exclude_interrupted_turns)
        value['benchmark'] = measure_efficiency(value, plan['arm'])
    else:
        directory = args.run_dir or ROOT / '.pi/bench' / f'{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{args.scenario}-{args.arm}-{uuid.uuid4().hex[:6]}'
        if args.action == 'run' and (directory / 'plan.json').is_file():
            plan = json.loads((directory / 'plan.json').read_text(encoding='utf-8'))
            if plan['arm'] != args.arm or plan.get('scenario', 'calculator') != args.scenario:
                parser.error('the requested arm/scenario does not match the prepared profile')
            if (directory / 'state.json').exists() or (directory / 'run-attempt.json').exists():
                parser.error('a run directory cannot be reused; prepare a fresh trial')
        else:
            plan = prepare(args.arm, directory, scenario=args.scenario, native_transport=args.native_transport)
        value = run(plan) if args.action == 'run' else plan
    print(json.dumps(value, ensure_ascii=False, indent=2))
    if args.action == 'run' and value['passed'] is False:
        raise SystemExit(1)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
