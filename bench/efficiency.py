"""Benchmark generated-code tokens and computer-use tool time, independent of model latency.

Attribution follows captured arguments and generated helper provenance, never the
workspace's final files. It is a reviewable static estimate, not execution tracing
or provider-billed per-tool usage. Mixed shell payloads/times are inclusive.
"""

import ast
from dataclasses import dataclass, field
import hashlib
from importlib.metadata import version
import json
import re
import shlex
import posixpath
from pathlib import PurePosixPath

import tiktoken

from bench.intervals import busy_seconds

ENCODING = 'o200k_base'
RUNTIMES = {'pi-acu': 'ACU', 'claude-acu': 'ACU', 'pi-cua': 'CUA', 'claude-cua': 'CUA',
            'pi-computer-use': 'Codex computer use', 'codex-computer-use': 'Codex computer use'}
SCRIPT_SUFFIXES = {'.ahk', '.py', '.js', '.mjs', '.ps1', '.sh'}


@dataclass
class Script:
    text: str
    payloads: set[str] = field(default_factory=set)


# Use a fixed public reference encoding across arms; it is not claimed to be Astra's or Opus's billing tokenizer.
def token_count(text):
    return len(tiktoken.get_encoding(ENCODING).encode(text, disallowed_special=()))


# Script names link generated files to later shell invocations even if moved or deleted before analysis.
def script_name(value):
    return PurePosixPath(str(value).strip('\"\'').replace('\\', '/')).name.casefold()


# Strip string/comment contents before matching executable JS route references, avoiding JSON evidence false positives.
def js_code(text):
    return re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|`(?:\\.|[^`\\])*`|//[^\n]*|/\*[\s\S]*?\*/', ' ', text)


# Only functions whose bodies reference the runtime become persistent computer-use helpers.
def js_helpers(clean, known):
    names = set()
    pattern = r'(?:globalThis\.)?(\w+)\s*=\s*(?:async\s*)?(?:\([^)]*\)|\w+)\s*=>\s*|\bfunction\s+(\w+)\s*\([^)]*\)\s*'
    for match in re.finditer(pattern, clean):
        start = match.end()
        end = start
        if start < len(clean) and clean[start] == '{':
            depth = 1
            end += 1
            while end < len(clean) and depth:
                depth += (clean[end] == '{') - (clean[end] == '}')
                end += 1
        else:
            separator = clean.find(';', start)
            end = len(clean) if separator < 0 else separator
        body = clean[start:end]
        if re.search(r'\bsky\s*\.', body) or any(re.search(rf'\b{re.escape(name)}\s*\(', body) for name in known):
            names.add(match.group(1) or match.group(2))
    return names


# Separate heredoc bodies from shell commands; data written to result.json must never imply a runtime invocation.
def heredocs(command):
    files = []
    executable = []
    lines = command.splitlines(keepends=True)
    i = 0
    while i < len(lines):
        line = lines[i]
        match = re.search(r"<<-?\s*(['\"]?)([\w-]+)\1", line)
        if not match:
            executable.append(line)
            i += 1
            continue
        marker = match.group(2)
        body = []
        i += 1
        while i < len(lines) and lines[i].strip() != marker:
            body.append(lines[i])
            i += 1
        if i == len(lines):
            raise ValueError('unterminated captured heredoc; attribution needs review')
        i += 1
        destination = re.search(r"\b(?:cat\s*(?:>>|>)|tee\s+(?:-a\s+)?)([^<>]+?)\s*<<", line)
        if destination:
            files.append((destination.group(1).strip(), ''.join(body), '>>' in destination.group(0) or bool(re.search(r'\btee\s+-a\b', destination.group(0)))))
            executable.append(line[:destination.start()] + line[match.end():] + '\n')
        else:
            trailing = re.match(r'''\s*(>>?)\s*("[^"]*"|'[^']*'|[^\s;&|]+)(.*)''', line[match.end():])
            cat = re.search(r'\bcat\s*$', line[:match.start()])
            if trailing and cat:
                files.append((trailing.group(2), ''.join(body), trailing.group(1) == '>>'))
                executable.append(line[:cat.start()] + trailing.group(3) + '\n')
            else:
                # An inline Python program is executable code, unlike a JSON-writing heredoc.
                executable.append(line[:match.start()] + '\n')
                files.append((None, ''.join(body), False))
    return ''.join(executable), files


# Read actual shell command positions, rather than runtime names appearing in quoted prose/arguments.
def shell_commands(text):
    lexer = shlex.shlex(text, posix=True, punctuation_chars=';&|\n')
    lexer.whitespace = ' \t\r'
    lexer.whitespace_split = True
    commands, current = [], []
    for token in lexer:
        if token and all(char in ';&|\n' for char in token):
            if current:
                commands.append(current)
                current = []
        else:
            current.append(token)
    if current:
        commands.append(current)
    return commands


# Identify Python helper imports and actual subprocess invocation literals; quoted report text is not a route.
def python_routes(text):
    try:
        tree = ast.parse(text)
    except SyntaxError as error:
        raise ValueError(f'Python source cannot be parsed at line {error.lineno}; attribution needs review') from error
    route, imports, warnings = False, set(), []
    assignments = {target.id: node.value for node in ast.walk(tree) if isinstance(node, ast.Assign)
                   for target in node.targets if isinstance(target, ast.Name)}

    # Resolve only captured literal command prefixes; never evaluate arbitrary actor code.
    def command_head(node, seen=None):
        seen = set() if seen is None else seen
        if isinstance(node, ast.Name) and node.id in assignments and node.id not in seen:
            return command_head(assignments[node.id], seen | {node.id})
        if isinstance(node, (ast.List, ast.Tuple)) and node.elts:
            first = command_head(node.elts[0], seen)
            if first is not None and script_name(first) in ('acu', 'acu.exe'):
                second = command_head(node.elts[1], seen) if len(node.elts) > 1 else None
                return 'acu ' + second if second is not None else None
            return first
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            return command_head(node.left, seen)
        return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split('.')[0] + '.py')
        elif isinstance(node, ast.Import):
            imports.update(alias.name.split('.')[0] + '.py' for alias in node.names)
        elif isinstance(node, ast.Call):
            name = node.func.attr if isinstance(node.func, ast.Attribute) else ''
            if name in ('run', 'Popen', 'check_output', 'check_call', 'call') and node.args:
                first = command_head(node.args[0])
                if first is None:
                    warnings.append(f'dynamic subprocess command at Python line {node.lineno}; cannot attribute statically')
                else:
                    route |= script_name(first) in ('cua-driver', 'cua-driver.exe') or bool(re.match(r'^(?:cua-driver(?:\s|$)|acu\s+run\b)', first))
    return route, imports, warnings


# Attribute captured code payloads and execution spans; emit the selection ledger and unresolved cases for review.
def measure_efficiency(measurements, arm):
    runtime = RUNTIMES[arm]
    scripts, payloads, included = {}, {}, set()
    calls, notes, helpers = [], [], set()

    def payload(call_id, key, text, kind):
        identity = f'{call_id}:{key}'
        payloads[identity] = {'call_id': call_id, 'text': text, 'kind': kind}
        return identity

    def binding(reference, call_id, create=False):
        key = posixpath.normpath(str(reference).strip('\"\'').replace('\\', '/')).casefold()
        if key in scripts:
            return key
        base = script_name(reference)
        if '/' in key and create:
            # A later explicit path disambiguates an earlier bare filename from a shell working directory.
            if base in scripts:
                scripts.pop(base)
            return key
        candidates = [path for path in scripts if script_name(path) == base]
        if len(candidates) == 1:
            return candidates[0]
        if len(candidates) > 1:
            notes.append({'call_id': call_id, 'reason': f'ambiguous script basename {base}; attribution needs review'})
            return None
        return key if create else None

    def dependencies(name, call_id, seen=None):
        seen = set() if seen is None else seen
        key = binding(name, call_id)
        if key is None or key in seen:
            return False, set()
        seen.add(key)
        script = scripts[key]
        try:
            route, imported, warnings = python_routes(script.text) if name.endswith('.py') else (False, set(), [])
            notes.extend({'call_id': call_id, 'reason': f'{name}: {warning}'} for warning in warnings)
        except ValueError as error:
            notes.append({'call_id': call_id, 'reason': f'{name}: {error}'})
            return False, set()
        if name.endswith(('.js', '.mjs')):
            route |= bool(re.search(r'\bsky\s*\.', js_code(script.text)))
        used = set(script.payloads)
        for dep in imported:
            child_route, child_payloads = dependencies(dep, call_id, seen)
            if child_route:
                route = True
                used.update(child_payloads)
        return route, used

    for tool in sorted(measurements['tools'], key=lambda item: item['start_s'] if item['start_s'] is not None else item['end_s']):
        identity, name = tool['id'], tool['name'].casefold()
        args = tool.get('arguments')
        if not isinstance(args, dict):
            notes.append({'call_id': identity, 'reason': 'structured arguments unavailable; reanalyse original events'})
            continue
        if name == 'read':
            continue
        if name == 'write':
            path = args.get('path', args.get('file_path', ''))
            if PurePosixPath(script_name(path)).suffix in SCRIPT_SUFFIXES:
                key = binding(path, identity, create=True)
                if key is not None:
                    text = args.get('content', '')
                    scripts[key] = Script(text, {payload(identity, 'script', text, 'generated script')})
            continue
        if name == 'edit':
            key = binding(args.get('path', args.get('file_path', '')), identity)
            if key is None:
                continue
            edits = args.get('edits')
            if edits is None:
                edits = [{'oldText': args.get('old_string', ''), 'newText': args.get('new_string', '')}]
            for index, edit in enumerate(edits):
                old, new = edit['oldText'], edit['newText']
                matches = scripts[key].text.count(old) if old else 0
                if not matches or (matches != 1 and not args.get('replace_all')):
                    notes.append({'call_id': identity, 'reason': 'edit match is absent or ambiguous in captured source; attribution needs review'})
                    continue
                scripts[key].text = scripts[key].text.replace(old, new, -1 if args.get('replace_all') else 1)
                scripts[key].payloads.add(payload(identity, f'edit-{index}', new, 'generated script edit'))
            continue

        code = args.get('code', args.get('command', ''))
        if not isinstance(code, str):
            notes.append({'call_id': identity, 'reason': 'no supported code/command payload'})
            continue
        used, is_use = set(), False
        if 'node_repl' in name:
            if name.endswith(('js_reset', 'js_add_node_module_dir', 'turn_ended')):
                is_use = True
                code = json.dumps(args, ensure_ascii=False, separators=(',', ':'))
                if name.endswith('js_reset'):
                    helpers.clear()
            else:
                clean = js_code(code)
                assigned = {value for pair in re.findall(r'globalThis\.(\w+)\s*=|\b(?:var|let|const)\s+(\w+)\s*=', clean) for value in pair if value}
                helpers.difference_update(assigned)
                is_use = bool(re.search(r'\bsky\s*\.', clean) or any(re.search(rf'\b{re.escape(h)}\s*\(', clean) for h in helpers))
                helpers.update(js_helpers(clean, helpers))
        elif name in ('bash', 'command_execution'):
            try:
                executable, bodies = heredocs(code)
                commands = shell_commands(executable)
            except ValueError as error:
                notes.append({'call_id': identity, 'reason': str(error)})
                continue
            inline_python = []
            for index, (path, text, append) in enumerate(bodies):
                if path is None:
                    inline_python.append(text)
                    continue
                if PurePosixPath(script_name(path)).suffix in SCRIPT_SUFFIXES:
                    key = binding(path, identity, create=True)
                    if key is None:
                        continue
                    part = payload(identity, f'heredoc-{index}', text, 'generated script')
                    if append and key in scripts:
                        scripts[key].text += text
                        scripts[key].payloads.add(part)
                    else:
                        scripts[key] = Script(text, {part})
            for command in commands:
                if not command:
                    continue
                executable_name = script_name(command[0])
                if executable_name in ('acu', 'acu.exe') and len(command)>1 and command[1]=='run':
                    is_use = True
                    if len(command)>2:
                        key = binding(command[2], identity)
                        if key is not None:
                            used.update(scripts[key].payloads)
                elif executable_name in ('cua-driver', 'cua-driver.exe'):
                    is_use |= len(command)>1 and command[1] not in ('--help', '--version', 'describe')
                elif re.fullmatch(r'(?:python(?:\d+(?:\.\d+)?)?|py)(?:\.exe)?', executable_name):
                    if '-c' in command:
                        at = command.index('-c')+1
                        if at<len(command):
                            inline_python.append(command[at])
                    for argument in command[1:]:
                        if script_name(argument).endswith('.py'):
                            route, found = dependencies(argument, identity)
                            is_use |= route
                            if route:
                                used.update(found)
                elif executable_name in ('mv', 'cp') and len(command) > 2:
                    destination = command[-1]
                    for source in command[1:-1]:
                        old = binding(source, identity)
                        if old is None:
                            continue
                        target = destination if PurePosixPath(destination).suffix in SCRIPT_SUFFIXES else destination.rstrip('/') + '/' + script_name(source)
                        new = posixpath.normpath(target.replace('\\', '/')).casefold()
                        scripts[new] = scripts[old]
                        if executable_name == 'mv' and old != new:
                            del scripts[old]
                elif executable_name in ('sed', 'perl') and any('-i' in argument for argument in command[1:]):
                    for argument in command[1:]:
                        key = binding(argument, identity)
                        if key is not None:
                            scripts[key].payloads.add(payload(identity, f'patch-{key}', code, 'generated script edit command'))
            for text in inline_python:
                try:
                    route, imported, warnings = python_routes(text)
                    notes.extend({'call_id': identity, 'reason': warning} for warning in warnings)
                except ValueError as error:
                    notes.append({'call_id': identity, 'reason': str(error)})
                    continue
                is_use |= route
                for key in imported:
                    child_route, found = dependencies(key, identity)
                    is_use |= child_route
                    if child_route:
                        used.update(found)
        else:
            notes.append({'call_id': identity, 'reason': f'unsupported tool {tool["name"]}; attribution needs review'})
            continue
        if is_use:
            # The execution payload includes its inline script definitions; do not count their bodies twice.
            execution = payload(identity, 'execution', code, 'computer-use invocation arguments')
            included.update(part for part in used if payloads[part]['call_id'] != identity)
            included.add(execution)
            calls.append({'id': identity, 'tool': tool['name'], 'start_s': tool['start_s'], 'end_s': tool['end_s'],
                          'duration_s': tool['duration_s'], 'tool_reported_error': tool.get('is_error'),
                          'attribution': 'captured invocation or generated-helper dependency'})
    # If a script generated inside a previous execution is reused, its source was already in that call payload.
    execution_call_ids = {payloads[key]['call_id'] for key in included if payloads[key]['kind']=='computer-use invocation arguments'}
    included = {key for key in included if payloads[key]['kind']=='computer-use invocation arguments' or payloads[key]['call_id'] not in execution_call_ids}
    ledger = []
    for key in sorted(included):
        item = payloads[key]
        ledger.append({'id': key, 'call_id': item['call_id'], 'kind': item['kind'],
                       'estimated_tokens': token_count(item['text']), 'characters': len(item['text']),
                       'sha256': hashlib.sha256(item['text'].encode('utf-8')).hexdigest()})
    estimated = sum(item['estimated_tokens'] for item in ledger)
    tokens = measurements.get('tokens')
    output = tokens.get('output_including_reasoning') if tokens else None
    complete = measurements.get('token_counts_complete') is True
    percentage = 100*estimated/output if complete and output and not notes else None
    timed_calls = [call for call in calls if call['start_s'] is not None and call['duration_s'] is not None]
    durations_complete = len(timed_calls) == len(calls) and not measurements.get('unfinished_tools')
    known_busy = busy_seconds((call['start_s'], call['end_s']) for call in timed_calls)
    known_sum = sum(call['duration_s'] for call in timed_calls)
    return {'policy': 'tokens-and-computer-use-v1', 'runtime': runtime, 'api_tokens': tokens,
            'token_counts_complete': complete,
            'code_tokens': {'estimated_tokens': estimated, 'encoding': ENCODING, 'tokenizer': 'tiktoken', 'tokenizer_version': version('tiktoken'),
                            'denominator_output_including_reasoning': output,
                            'output_share_percent_estimate': percentage, 'payloads': ledger,
                            'attribution': 'automatic static estimate; review ledger before comparison',
                            'review_required': bool(notes), 'review_notes': notes,
                            'scope': 'Decoded code/command payloads and generated script/edit text used by identified calls; excludes prose, reasoning, reads and standalone evidence writes. Re-emitted code counts again; replay never recounts an earlier source payload.'},
            'computer_use': {'call_count': len(calls), 'attribution_complete': not notes,
                             'busy_seconds': known_busy if durations_complete else None,
                             'sum_call_seconds': known_sum if durations_complete else None,
                             'known_busy_seconds': known_busy, 'known_sum_call_seconds': known_sum, 'calls': calls,
                             'durations_complete': durations_complete,
                             'unfinished_call_ids': measurements.get('unfinished_tools', []),
                             'timing_basis': 'Top-level tool request through result receipt; mixed shell payloads include shell/setup/inspection overhead, not model response time.'}}
