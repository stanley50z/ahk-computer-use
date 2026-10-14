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
PYTHON_COMMAND = re.compile(r'(?:python(?:\d+(?:\.\d+)?)?|py)(?:\.exe)?')
EXECUTION_WRAPPERS = {'timeout', 'nohup', 'exec', 'xargs', 'cmd', 'cmd.exe', 'powershell', 'powershell.exe', 'uv', 'env'}


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
    lexer = shlex.shlex(text, posix=True, punctuation_chars=';&|\n()')
    lexer.whitespace = ' \t\r'
    lexer.whitespace_split = True
    commands, current = [], []
    for token in lexer:
        if token and all(char in ';&|\n()' for char in token):
            if current:
                commands.append(current)
                current = []
        else:
            current.append(token)
    if current:
        commands.append(current)
    normalized = []
    for command in commands:
        # Loop/branch bodies and environment assignments precede the actual executable.
        while command:
            if command[0] in ('do', 'then', 'else', 'if', 'while', 'until', '!') or re.match(r'^[A-Za-z_]\w*=', command[0]):
                command = command[1:]
            elif command[0] == 'env' and len(command) > 1 and not command[1].startswith('-'):
                command = command[1:]
            else:
                break
        if command:
            normalized.append(command)
    return normalized


# Identify Python helper imports and actual subprocess invocation literals; quoted report text is not a route.
def python_routes(text):
    try:
        tree = ast.parse(text)
    except SyntaxError as error:
        raise ValueError(f'Python source cannot be parsed at line {error.lineno}; attribution needs review') from error
    route, imports, warnings, invoked = False, set(), [], set()
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
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == 'sys' and node.attr == 'executable':
            return 'python'
        return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None

    # A literal Python executable/script prefix is enough; trailing coordinates/JSON can stay dynamic.
    def command_items(node, seen=None):
        seen = set() if seen is None else seen
        if isinstance(node, ast.Name) and node.id in assignments and node.id not in seen:
            return command_items(assignments[node.id], seen | {node.id})
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            return command_items(node.left, seen)
        return node.elts if isinstance(node, (ast.List, ast.Tuple)) else []

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split('.')[0] + '.py')
        elif isinstance(node, ast.Import):
            imports.update(alias.name.split('.')[0] + '.py' for alias in node.names)
        elif isinstance(node, ast.Call):
            name = node.func.attr if isinstance(node.func, ast.Attribute) else ''
            os_system = (name == 'system' and isinstance(node.func.value, ast.Name) and node.func.value.id == 'os')
            if (name in ('run', 'Popen', 'check_output', 'check_call', 'call') or os_system) and node.args:
                first = command_head(node.args[0])
                if first is None:
                    warnings.append(f'dynamic subprocess command at Python line {node.lineno}; cannot attribute statically')
                elif isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                    child_route, child_imports, child_warnings, child_invoked = shell_routes(node.args[0].value)
                    route |= child_route
                    imports.update(child_imports)
                    warnings.extend(child_warnings)
                    invoked.update(child_invoked)
                elif PYTHON_COMMAND.fullmatch(script_name(first)):
                    items = command_items(node.args[0])
                    program = None
                    for item in items[1:]:
                        value = command_head(item)
                        if value is None or value in ('-c', '-m'):
                            break
                        if not value.startswith('-'):
                            program = value
                            break
                    if program and script_name(program).endswith('.py'):
                        invoked.add(program)
                    else:
                        warnings.append(f'unresolved Python script prefix at line {node.lineno}; attribution needs review')
                else:
                    route |= script_name(first) in ('cua-driver', 'cua-driver.exe') or bool(re.match(r'^(?:cua-driver(?:\s|$)|acu\s+run\b)', first))
    return route, imports, warnings, invoked


# Follow captured shell helpers through literal runtime/Python/script prefixes, not quoted data.
def shell_routes(text):
    executable, bodies = heredocs(text)
    route, imports, warnings, invoked = False, set(), [], set()
    inline = [body for path, body, _ in bodies if path is None]
    written = {path for path, _, _ in bodies if path is not None and PurePosixPath(script_name(path)).suffix in SCRIPT_SUFFIXES}
    warnings.extend(f'shell helper writes {path}; source effects require review' for path in sorted(written))
    for command in shell_commands(executable):
        name = script_name(command[0])
        if name in ('cua-driver', 'cua-driver.exe'):
            route |= len(command) > 1 and command[1] not in ('--help', '--version', 'describe')
        elif name in ('acu', 'acu.exe'):
            route |= len(command) > 1 and command[1] == 'run'
        elif PYTHON_COMMAND.fullmatch(name):
            if '-c' in command and command.index('-c') + 1 < len(command):
                inline.append(command[command.index('-c') + 1])
            invoked.update(argument for argument in command[1:] if script_name(argument).endswith('.py'))
        elif name in ('sh', 'bash', 'source') or command[0] == '.':
            invoked.update(argument for argument in command[1:] if script_name(argument).endswith('.sh'))
        elif name in EXECUTION_WRAPPERS:
            warnings.append(f'unsupported execution wrapper {name}; attribution needs review')
        elif name in ('mv', 'cp', 'sed', 'perl'):
            warnings.append(f'shell helper source effects from {name} require review')
    for source in inline:
        child_route, child_imports, child_warnings, child_invoked = python_routes(source)
        # Inline writes inside a helper are not replayed here; suppress stale child links explicitly.
        for node in ast.walk(ast.parse(source)):
            target = None
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Attribute) and node.func.attr in ('write', 'write_text'):
                receiver = node.func.value
                if isinstance(receiver, ast.Call) and receiver.args:
                    target = receiver.args[0]
            elif isinstance(node.func, ast.Name) and node.func.id == 'open' and len(node.args) > 1:
                mode = node.args[1]
                if isinstance(mode, ast.Constant) and isinstance(mode.value, str) and any(char in mode.value for char in 'wax+'):
                    target = node.args[0]
            if isinstance(target, ast.Constant) and isinstance(target.value, str) and PurePosixPath(script_name(target.value)).suffix in SCRIPT_SUFFIXES:
                written.add(target.value)
                warnings.append(f'shell helper Python writes {target.value}; source effects require review')
        route |= child_route
        imports.update(child_imports)
        warnings.extend(child_warnings)
        invoked.update(child_invoked)
    written_names = {script_name(target) for target in written}
    invoked = {path for path in invoked if script_name(path) not in written_names}
    imports = {path for path in imports if script_name(path) not in written_names}
    return route, imports, warnings, invoked


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

    def dependencies(name, call_id, seen=None, *, required=False):
        seen = set() if seen is None else seen
        key = binding(name, call_id)
        if key is None:
            if required:
                notes.append({'call_id': call_id, 'reason': f'captured source unavailable for invoked helper {name}'})
            return False, set()
        if key in seen:
            return False, set()
        seen.add(key)
        script = scripts[key]
        try:
            route, imported, warnings, invoked = (False, set(), [], set())
            if name.endswith('.py'):
                route, imported, warnings, invoked = python_routes(script.text)
            elif name.endswith('.sh'):
                route, imported, warnings, invoked = shell_routes(script.text)
            notes.extend({'call_id': call_id, 'reason': f'{name}: {warning}'} for warning in warnings)
        except ValueError as error:
            notes.append({'call_id': call_id, 'reason': f'{name}: {error}'})
            return False, set()
        if name.endswith(('.js', '.mjs')):
            route |= bool(re.search(r'\bsky\s*\.', js_code(script.text)))
        used = set(script.payloads)
        for dep in imported | invoked:
            child_route, child_payloads = dependencies(dep, call_id, seen, required=dep in invoked)
            if child_route:
                route = True
                used.update(child_payloads)
        return route, used

    def invalidate_source(path, call_id, reason):
        notes.append({'call_id': call_id, 'reason': reason})
        key = binding(path, call_id) if path else None
        if key is not None:
            del scripts[key]

    # Replay only literal copies/replacements of already-captured scripts; never read files or eval actor code.
    def replay_python_writes(text, call_id):
        tree = ast.parse(text)
        values, handled = {}, set()
        aliases = {target.id: node.value for node in ast.walk(tree) if isinstance(node, ast.Assign)
                   for target in node.targets if isinstance(target, ast.Name)}

        def file_reference(node, seen=None):
            seen = set() if seen is None else seen
            if isinstance(node, ast.Name) and node.id in aliases and node.id not in seen:
                return file_reference(aliases[node.id], seen | {node.id})
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ('Path', 'open') and node.args:
                path = node.args[0]
                if isinstance(path, ast.Constant) and isinstance(path.value, str):
                    return path.value
            return None

        def resolve_script(node):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                return Script(node.value)
            if isinstance(node, ast.Name):
                return values.get(node.id)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                method, receiver = node.func.attr, node.func.value
                if method in ('read', 'read_text'):
                    path = file_reference(receiver)
                    key = binding(path, call_id) if path else None
                    return scripts.get(key)
                if method == 'replace' and len(node.args) == 2:
                    original, old, new = resolve_script(receiver), resolve_script(node.args[0]), resolve_script(node.args[1])
                    if original is not None and old is not None and new is not None:
                        return Script(original.text.replace(old.text, new.text), set(original.payloads))
            return None

        for node in tree.body:
            if isinstance(node, ast.Assign):
                copied = resolve_script(node.value)
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        values[target.id] = copied
            elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                operation = node.value
                if not isinstance(operation.func, ast.Attribute) or operation.func.attr not in ('write', 'write_text') or not operation.args:
                    continue
                path = file_reference(operation.func.value)
                if path and PurePosixPath(script_name(path)).suffix in SCRIPT_SUFFIXES:
                    handled.add(operation)
                    handled.add(operation.func.value)
                    copied = resolve_script(operation.args[0])
                    if copied is None:
                        invalidate_source(path, call_id, f'unresolved Python source transformation for {path}')
                        continue
                    key = binding(path, call_id, create=True)
                    if key is not None:
                        part = payload(call_id, f'transform-{key}', text, 'generated script transformation')
                        scripts[key] = Script(copied.text, copied.payloads | {part})
        # Unreplayed write forms must invalidate cached text, not silently certify a stale route.
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or node in handled:
                continue
            path = None
            if isinstance(node.func, ast.Name) and node.func.id == 'open' and len(node.args) > 1:
                mode = node.args[1]
                if isinstance(mode, ast.Constant) and isinstance(mode.value, str) and any(char in mode.value for char in 'wax+'):
                    path = file_reference(node)
            elif isinstance(node.func, ast.Attribute):
                if node.func.attr in ('write', 'write_text'):
                    path = file_reference(node.func.value)
                elif node.func.attr in ('copy', 'copyfile', 'move', 'rename') and len(node.args) > 1:
                    destination = node.args[1]
                    if isinstance(destination, ast.Constant) and isinstance(destination.value, str):
                        path = destination.value
            if path and PurePosixPath(script_name(path)).suffix in SCRIPT_SUFFIXES:
                invalidate_source(path, call_id, f'unreplayed Python source mutation for {path}')

    for tool in sorted(measurements['tools'], key=lambda item: item['start_s'] if item['start_s'] is not None else item['end_s']):
        identity, name = tool['id'], tool['name'].casefold()
        args = tool.get('arguments')
        if not isinstance(args, dict):
            notes.append({'call_id': identity, 'reason': 'structured arguments unavailable; reanalyse original events'})
            continue
        if name == 'read':
            continue
        # Rejected file mutations never reached the script; do not replay or charge unapplied text.
        if name in ('write', 'edit') and tool.get('is_error'):
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
            original, replacements, valid = scripts[key].text, [], True
            for index, edit in enumerate(edits):
                old, new = edit['oldText'], edit['newText']
                matches = list(re.finditer(re.escape(old), original)) if old else []
                if not matches or (len(matches) != 1 and not args.get('replace_all')):
                    notes.append({'call_id': identity, 'reason': 'edit match is absent or ambiguous in captured source; attribution needs review'})
                    valid = False
                    continue
                replacements.extend((match.start(), match.end(), new) for match in matches)
            replacements.sort()
            if any(previous[1] > following[0] for previous, following in zip(replacements, replacements[1:])):
                notes.append({'call_id': identity, 'reason': 'overlapping captured edit regions; attribution needs review'})
                valid = False
            if valid:
                for start, end, new in reversed(replacements):
                    original = original[:start] + new + original[end:]
                scripts[key].text = original
                for index, edit in enumerate(edits):
                    scripts[key].payloads.add(payload(identity, f'edit-{index}', edit['newText'], 'generated script edit'))
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
                    try:
                        replay_python_writes(text, identity)
                    except SyntaxError:
                        pass  # python_routes below retains the explicit parse warning.
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
                elif PYTHON_COMMAND.fullmatch(executable_name):
                    if '-c' in command:
                        at = command.index('-c')+1
                        if at<len(command):
                            inline_python.append(command[at])
                            try:
                                replay_python_writes(command[at], identity)
                            except SyntaxError:
                                pass  # python_routes below retains the explicit parse warning.
                    for argument in command[1:]:
                        if script_name(argument).endswith('.py'):
                            route, found = dependencies(argument, identity, required=True)
                            is_use |= route
                            if route:
                                used.update(found)
                elif executable_name in ('sh', 'bash', 'source') or command[0] == '.':
                    for argument in command[1:]:
                        if script_name(argument).endswith('.sh'):
                            route, found = dependencies(argument, identity, required=True)
                            is_use |= route
                            if route:
                                used.update(found)
                elif executable_name in EXECUTION_WRAPPERS:
                    notes.append({'call_id': identity, 'reason': f'unsupported execution wrapper {executable_name}; attribution needs review'})
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
                    expressions = [argument for argument in command[1:] if re.match(r'^s[^\w\s]', argument)]
                    for argument in command[1:]:
                        key = binding(argument, identity)
                        if key is None:
                            continue
                        if not expressions:
                            invalidate_source(argument, identity, f'unsupported in-place source patch for {argument}')
                            continue
                        patched, valid = scripts[key].text, True
                        for expression in expressions:
                            parts = expression[2:].split(expression[1])
                            if (executable_name != 'sed' or len(parts) != 3 or not parts[0]
                                    or parts[2] not in ('', 'g') or any(char in parts[0] for char in '.*[^$\\')
                                    or any(char in parts[1] for char in '&\\')):
                                invalidate_source(argument, identity, f'unsupported in-place source patch for {argument}')
                                valid = False
                                break
                            old, new, flags = parts
                            patched = ''.join(line.replace(old, new, -1 if flags == 'g' else 1)
                                              for line in patched.splitlines(keepends=True))
                        if valid:
                            scripts[key].text = patched
                            scripts[key].payloads.add(payload(identity, f'patch-{key}', code, 'generated script edit command'))
            for text in inline_python:
                try:
                    route, imported, warnings, invoked = python_routes(text)
                    notes.extend({'call_id': identity, 'reason': warning} for warning in warnings)
                except ValueError as error:
                    notes.append({'call_id': identity, 'reason': str(error)})
                    continue
                is_use |= route
                for key in imported | invoked:
                    child_route, found = dependencies(key, identity, required=key in invoked)
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
    scope = measurements.get('token_usage_scope', 'all-requests')
    if scope not in ('all-requests', 'excluding-interrupted-turns'):
        raise ValueError(f'unsupported token usage scope: {scope}')
    percentage = 100*estimated/output if complete and output and not notes else None
    timed_calls = [call for call in calls if call['start_s'] is not None and call['duration_s'] is not None]
    durations_complete = len(timed_calls) == len(calls) and not measurements.get('unfinished_tools')
    known_busy = busy_seconds((call['start_s'], call['end_s']) for call in timed_calls)
    known_sum = sum(call['duration_s'] for call in timed_calls)
    policy = 'tokens-and-computer-use-excluding-interrupted-turns-v1' if scope == 'excluding-interrupted-turns' else 'tokens-and-computer-use-v1'
    return {'policy': policy, 'runtime': runtime, 'api_tokens': tokens,
            'token_counts_complete': complete, 'token_usage_scope': scope,
            'excluded_model_turn_count': len(measurements.get('excluded_model_turns', [])),
            'full_request_consumption_complete': measurements.get('full_request_consumption_complete', complete),
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
