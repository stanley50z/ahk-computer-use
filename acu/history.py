"""Read-only, deterministic session history; captured code is inspected, never executed."""

import ast
from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from datetime import datetime
import hashlib
import json
import posixpath
from pathlib import Path
import re
import shlex
import warnings

from .run import acu_home, is_app_process
from .snippets import snippets_root
from .tool import BUNDLED_SCRIPTS, resolve_script

RULES = ("Candidates end at an ok action run after at least one error/timeout or two looks "
         "(tree.ahk/screenshot.ahk). Success means launcher ok, not verified task success. "
         "Frequently failing means at least 3 failures and at least 50% of all recorded runs "
         "for an existing snippet. Missing or ambiguous log matches stay unknown.")


@dataclass
class Call:
    """One persisted tool request and its correlated result, in transcript order."""

    id: str
    name: str
    args: dict
    start: float | None
    cwd: str
    end: float | None = None
    output: str = ""
    failed: bool | None = False  # None: the harness recorded no status ACU can read.

    # Writes count only when the result shows they succeeded.
    @property
    def succeeded(self):
        return self.failed is False and self.end is not None


# Normalize timestamps across native JSONL formats, not wall-clock file mtimes.
def timestamp(value):
    if value is None:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


CODEX_FAILURES = ("apply_patch verification failed", "execution error", "exec command rejected",
                  "failed to parse function arguments")


# Codex results carry no error flag; read the status its shell and patch tools print. Other output stays unknown.
def codex_failed(output):
    if isinstance(output, list):
        output = "\n".join(block.get("text", "") for block in output if isinstance(block, dict))
    text = output if isinstance(output, str) else ""
    if text.lstrip().startswith("{"):
        try:
            metadata = json.loads(text).get("metadata")
        except (json.JSONDecodeError, AttributeError):
            metadata = None
        if isinstance(metadata, dict) and isinstance(metadata.get("exit_code"), int):
            return metadata["exit_code"] != 0
    status = re.match(r"(?:Exit code:|Process exited with code) (-?\d+)", text)
    if status:
        return status.group(1) != "0"
    if text.startswith(CODEX_FAILURES) or "aborted by user" in text.splitlines()[:2]:
        return True
    if text.startswith("Success."):
        return False
    return None


# Do not reproduce captured data in parse errors: it may contain private document text.
def records(path):
    with path.open(encoding="utf-8-sig") as source:
        for number, line in enumerate(source, 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                raise ValueError(f"Invalid JSON in {path} at line {number}") from None
            if not isinstance(value, dict):
                raise ValueError(f"Expected JSON object in {path} at line {number}")
            yield value


# Mirror bench/run.py's toolCall/tool_use/function_call envelopes and ID correlation.
# Native session files contain messages rather than Pi's benchmark streaming events.
def session_calls(path):
    calls = {}
    cwd = ""
    recognized = False
    for entry in records(path):
        kind = entry.get("type")
        if kind in ("assistant", "user") and isinstance(entry.get("message"), dict):
            recognized = True
        message = entry.get("message", {})
        payload = entry.get("payload", {})
        if kind in ("session", "session_meta", "turn_context"):
            recognized = True
            cwd = entry.get("cwd", payload.get("cwd", cwd))
        cwd = entry.get("cwd", cwd)
        stamp = entry.get("timestamp")
        blocks = message.get("content", []) if isinstance(message, dict) else []
        if not isinstance(blocks, list):
            blocks = []
        requests, results = [], []
        if kind == "message" and message.get("role") == "toolResult":
            recognized = True
            results.append((message["toolCallId"], blocks, message.get("isError", False)))
        if message.get("role") == "assistant":
            for block in blocks:
                if block.get("type") in ("toolCall", "tool_use"):
                    recognized = True
                    requests.append((block["id"], block["name"], block.get("arguments", block.get("input", {}))))
        if kind == "user":
            for block in blocks:
                if block.get("type") == "tool_result":
                    results.append((block["tool_use_id"], block.get("content", ""), block.get("is_error", False)))
        if kind == "response_item":
            recognized = True
            if payload.get("type") == "function_call":
                requests.append((payload["call_id"], payload["name"], json.loads(payload["arguments"])))
            elif payload.get("type") == "custom_tool_call":
                requests.append((payload["call_id"], payload["name"], {"patch": payload["input"]}))
            elif payload.get("type") in ("function_call_output", "custom_tool_call_output"):
                results.append((payload["call_id"], payload.get("output", ""), codex_failed(payload.get("output", ""))))
        for id_, name, args in requests:
            if id_ not in calls:
                calls[id_] = Call(id_, name.split("__")[-1].split(".")[-1].lower(), args,
                                  timestamp(stamp), args.get("workdir", args.get("cwd", cwd)))
        for id_, content, failed in results:
            if id_ in calls:
                call = calls[id_]
                call.end = timestamp(stamp)
                call.output = content if isinstance(content, str) else "\n".join(
                    block.get("text", "") for block in content if isinstance(block, dict))
                call.failed = failed
    if not recognized:
        raise ValueError("Not a recognized Pi, Codex or Claude Code session")
    return [child for call in calls.values() for child in expand_call(call)]


# Pi/OpenAI parallel wrappers retain one time interval but contain several tool requests.
def expand_call(call):
    if call.name == "parallel":
        for index, item in enumerate(call.args.get("tool_uses", [])):
            yield from expand_call(replace(call, id=f"{call.id}/{index}",
                                           name=item["recipient_name"].split(".")[-1].lower(),
                                           args=item["parameters"]))
    else:
        yield call


# Normalize Windows/Git Bash paths and known shell locations; leave other variables literal.
def normalized(path, cwd=""):
    cwd = str(cwd).replace("\\", "/")
    cwd = re.sub(r"^/([a-zA-Z])/", r"\1:/", cwd)
    path = str(path).strip('\"\'').replace("\\", "/")
    conversion = re.fullmatch(r'\$\(cygpath -w [\"\']?\$PWD/([^$`]+?)[\"\']?\)', path)
    if conversion and cwd:
        path = cwd.rstrip("/\\") + "/" + conversion.group(1).rstrip('\"\'')
    if cwd:
        path = re.sub(r"\$\{PWD\}|\$PWD(?![A-Za-z0-9_])", lambda _: cwd, path)
    path = re.sub(r"^/([a-zA-Z])/", r"\1:/", path)
    if path == "~" or path.startswith("~/"):
        path = Path.home().as_posix() + path[1:]
    if not re.match(r"^(?:[A-Za-z]:/|/)", path) and cwd:
        path = cwd.rstrip("/\\") + "/" + path
    return posixpath.normpath(path)


# Separate heredoc data from executable shell text (mirrors bench/efficiency.py).
def heredocs(command):
    files, executable = [], []
    lines = command.splitlines(keepends=True)
    i = 0
    while i < len(lines):
        line = lines[i]
        match = re.search(r"<<-?\s*(['\"]?)([\w-]+)\1", line)
        if not match:
            executable.append(line)
            i += 1
            continue
        marker, body = match.group(2), []
        i += 1
        while i < len(lines) and lines[i].strip() != marker:
            body.append(lines[i])
            i += 1
        if i == len(lines):
            raise ValueError("Unterminated captured heredoc")
        i += 1
        destination = re.search(r"\b(?:cat\s*(?:>>|>)|tee\s+(?:-a\s+)?)([^<>]+?)\s*<<", line)
        if destination:
            files.append((destination.group(1).strip(), "".join(body), ">>" in destination.group(0)))
            executable.append(line[:destination.start()] + f"__acu_history_write__ {len(files) - 1};" + line[match.end():] + "\n")
        else:
            trailing = re.match(r'''\s*(>>?)\s*("[^"]*"|'[^']*'|[^\s;&|]+)(.*)''', line[match.end():])
            cat = re.search(r"\bcat\s*$", line[:match.start()])
            if trailing and cat:
                files.append((trailing.group(2), "".join(body), trailing.group(1) == ">>"))
                executable.append(line[:cat.start()] + f"__acu_history_write__ {len(files) - 1};" + trailing.group(3) + "\n")
            else:
                interpreter = re.search(r"\b(python(?:\d+(?:\.\d+)?)?|py|apply_patch)\s*(?:-\s*)?$", line[:match.start()])
                if interpreter:
                    name = interpreter.group(1)
                    words = [name, "".join(body)] if name == "apply_patch" else [name, "-c", "".join(body)]
                    executable.append(line[:interpreter.start()] + shlex.join(words) + "\n")
                else:
                    executable.append(line[:match.start()] + "\n")
    return "".join(executable), files


# Mirror bench/efficiency.py command-position parsing; quoted prose is not a run.
def shell_commands(text):
    lexer = shlex.shlex(text, posix=True, punctuation_chars=";&|\n()")
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    commands, current = [], []
    for token in lexer:
        if token and all(char in ";&|\n()" for char in token):
            if current:
                commands.append(current)
                current = []
        else:
            current.append(token)
    if current:
        commands.append(current)
    for command in commands:
        while command and (command[0] in ("do", "then", "else", "if", "while", "until", "!", "&", "env")
                           or re.match(r"^[A-Za-z_]\w*=", command[0])):
            command = command[1:]
        if command:
            yield command


@dataclass
class Run:
    """A requested ACU run; unknown is distinct from an unsuccessful launcher verdict."""

    path: str
    call: Call
    source: str | None
    arguments: str
    outcome: str = "unknown"
    app: str = "unknown app"
    lines: int | None = None
    snippet: bool = False
    look: bool = False


# Extract literal app selectors only; never guess an app from a document title.
def app_names(text):
    return set(re.findall(r"\bahk_exe\s+([\w .+-]+?\.exe)\b", text, re.I))


# The `output` of each acu CLI result line, in order; acu prints one JSON line per run, error or not.
def cli_outputs(text):
    outputs = []
    for line in text.splitlines():
        if not line.lstrip().startswith("{"):
            continue
        try:
            result = json.loads(line)
        except json.JSONDecodeError:
            continue  # Not every output line beginning with { is a JSON result.
        if isinstance(result, dict) and ("output" in result or "error" in result):
            outputs.append(result["output"] if isinstance(result.get("output"), str) else "")
    return outputs


# Decode a script as AutoHotkey reads it: UTF-8, or UTF-16 with a byte-order mark. Anything else stays unknown.
def decoded_source(data):
    encoding = "utf-16" if data.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
    try:
        return data.decode(encoding)
    except UnicodeDecodeError:
        return None


# The snippet store, not a directory merely named snippets, defines snippet identity.
def snippet_app(path, root):
    relative = normalized(path).casefold().removeprefix(root.casefold().rstrip("/") + "/")
    if relative != normalized(path).casefold() and "/" in relative:
        return relative.split("/")[0]
    return None


# Replay literal Python writes like bench/efficiency.py, without executing captured code.
def python_writes(text, sources, cwd):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)  # Captured code is data; its escape warnings are noise.
            tree = ast.parse(text)
    except SyntaxError:  # Shell quoting can leave code Python never ran; its writes stay unknown.
        return
    values = {}

    def value(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.Name):
            return values.get(node.id)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr == "read_text":
                path = reference(node.func.value)
                return sources.get(normalized(path, cwd).casefold()) if path else None
            if node.func.attr == "replace" and len(node.args) == 2:
                parts = [value(node.func.value), *(value(arg) for arg in node.args)]
                if all(part is not None for part in parts):
                    return parts[0].replace(parts[1], parts[2])
        return None

    def reference(node):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ("Path", "open") and node.args:
            return value(node.args[0])
        return None

    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    values[target.id] = value(node.value)
        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            operation = node.value
            if isinstance(operation.func, ast.Attribute) and operation.func.attr in ("write", "write_text") and operation.args:
                path = reference(operation.func.value)
                if path:
                    yield path, value(operation.args[0])


# Apply captured patch hunks only when their context matches a known source version. An added file is its + lines.
def patch_writes(text, sources, cwd):
    sections = re.split(r"^\*\*\* (Update|Add) File: (.+)\n", text, flags=re.M)
    for index in range(1, len(sections), 3):
        kind, path, body = sections[index:index + 3]
        if kind == "Add":
            yield path, "".join(line[1:] for line in body.splitlines(keepends=True) if line.startswith("+"))
            continue
        source = sources.get(normalized(path, cwd).casefold())
        if source is None:
            yield path, None
            continue
        for hunk in re.split(r"^@@[^\n]*\n", body, flags=re.M)[1:]:
            before, after = [], []
            for line in hunk.splitlines(keepends=True):
                if line.startswith((" ", "-")):
                    before.append(line[1:])
                if line.startswith((" ", "+")):
                    after.append(line[1:])
            old = "".join(before)
            if not old or source.count(old) != 1:
                source = None
                break
            source = source.replace(old, "".join(after), 1)
        yield path, source


# Collect requests and captured source versions without importing benchmark dependencies.
def collect(calls, root):
    sources, runs, changed = {}, [], set()

    # Record only confirmed successful writes inside the configured snippet store.
    def mark_changed(path, call):
        if snippet_app(path, root) and call.succeeded:
            changed.add(path)

    for call in calls:
        args = call.args
        path = args.get("path", args.get("file_path", ""))
        if call.name in ("write", "edit", "multiedit") and path:
            path = normalized(path, call.cwd)
            if call.succeeded:
                mark_changed(path, call)
                if call.name == "write":
                    sources[path.casefold()] = args.get("content", "")
                else:
                    source = sources.get(path.casefold())
                    edits = args.get("edits", [args])
                    for edit in edits:
                        old = edit.get("oldText", edit.get("old_string"))
                        new = edit.get("newText", edit.get("new_string"))
                        if source is not None and old and new is not None and old in source:
                            source = source.replace(old, new)
                        else:
                            source = None
                    sources[path.casefold()] = source
        if call.name == "apply_patch" and call.succeeded:
            for path, source in patch_writes(args.get("patch", ""), sources, call.cwd):
                path = normalized(path, call.cwd)
                sources[path.casefold()] = source
                mark_changed(path, call)
        if call.name not in ("bash", "shell", "shell_command", "exec_command", "powershell"):
            continue
        command = args.get("command", args.get("cmd", ""))
        if isinstance(command, list):
            command = " ".join(command)
        executable, files = heredocs(command)
        cwd = call.cwd
        for words in shell_commands(executable):
            if words[0] == "__acu_history_write__":
                destination, source, append = files[int(words[1])]
                path = normalized(destination, cwd)
                previous = sources.get(path.casefold())
                sources[path.casefold()] = (previous + source if previous is not None else None) if append else source
                mark_changed(path, call)
                continue
            if words[0].lower() in ("cd", "set-location") and len(words) == 2:
                cwd = normalized(words[1], cwd)
            name = posixpath.basename(words[0].replace("\\", "/")).lower()
            if re.fullmatch(r"(?:python(?:\d+(?:\.\d+)?)?|py)(?:\.exe)?", name) and "-c" in words:
                code_index = words.index("-c") + 1
                if code_index < len(words):
                    for path, source in python_writes(words[code_index], sources, cwd):
                        path = normalized(path, cwd)
                        sources[path.casefold()] = source
                        mark_changed(path, call)
            if name == "apply_patch" and len(words) > 1 and call.succeeded:
                for path, source in patch_writes(words[1], sources, cwd):
                    path = normalized(path, cwd)
                    sources[path.casefold()] = source
                    mark_changed(path, call)
            if name not in ("acu", "acu.exe") or len(words) < 3 or words[1] != "run":
                continue
            if words[2] in BUNDLED_SCRIPTS:
                path = normalized(resolve_script(words[2], normalized(cwd)))
            else:
                path = normalized(words[2], cwd)
            run = Run(path, call, sources.get(path.casefold()), " ".join(words[3:]))
            runs.append(run)
    return runs, changed


# Require a unique path+tool interval assignment. Never consume another session's old run.
def join_runs(runs, logs, root):
    grouped = defaultdict(list)
    recorded_apps = {}
    for run in runs:
        grouped[(run.call.id, run.path.casefold())].append(run)
    assignments = defaultdict(list)
    for row in logs:
        owners = []
        for key, group in grouped.items():
            run = group[0]
            if (normalized(row["script"]).casefold() == run.path.casefold() and run.call.end is not None
                    and run.call.start is not None
                    and run.call.start <= timestamp(row["ts"]) <= run.call.end):
                owners.append(key)
        if len(owners) == 1:
            assignments[owners[0]].append(row)
    for key, group in grouped.items():
        matches = assignments[key]
        if len(matches) == len(group):
            for run, row in zip(group, sorted(matches, key=lambda row: timestamp(row["ts"]))):
                run.outcome = row["outcome"]
                if "app" in row:
                    recorded_apps[id(run)] = row["app"]
                if run.source is not None and row.get("sha256"):
                    variants = {run.source.encode("utf-8"), run.source.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8")}
                    if row["sha256"] not in {hashlib.sha256(data).hexdigest() for data in variants}:
                        run.source = None
                if run.source is None and Path(run.path).is_file():
                    data = Path(run.path).read_bytes()
                    if hashlib.sha256(data).hexdigest() == row.get("sha256"):
                        run.source = decoded_source(data)
    # Legacy rows without app: pair CLI results in order, never attributing mismatched counts.
    by_call, outputs = defaultdict(list), {}
    for run in runs:
        by_call[run.call.id].append(run)
    for call_runs in by_call.values():
        if all(id(run) in recorded_apps for run in call_runs):
            continue
        results = cli_outputs(call_runs[0].call.output)
        if len(results) == len(call_runs):
            outputs.update(zip(map(id, call_runs), results))
    for run in runs:
        app = snippet_app(run.path, root)
        run.snippet = app is not None
        run.look = posixpath.basename(run.path).lower() in ("tree.ahk", "screenshot.ahk")
        if run.source is not None:
            run.lines = len(run.source.splitlines())
        if id(run) in recorded_apps:
            run.app = recorded_apps[id(run)] or "unknown app"
            continue
        # Compatibility only for rows predating app (or unmatched requests).
        names = app_names((run.source or "") + "\n" + run.arguments)
        output = outputs.get(id(run), "")
        names.update(re.findall(r"^window=\d+ .*? ([\w.+-]+\.exe)\s*$", output, re.M))
        # The snippet list names a store app's own process; its frame host names no app.
        names.update(re.findall(r"^snippets .*[\\/]([\w.+-]+\.exe)\s*$", output, re.M))
        names = {name for name in names if is_app_process(name)}
        if app:
            run.app = app
        elif len({name.casefold() for name in names}) == 1:
            run.app = sorted(names)[0]


# Summarize all requests while keeping code and raw result text out of the report.
def summarize(session_file):
    path = Path(session_file)
    if not path.is_file():
        raise ValueError(f"Session file not found: {path}")
    root = snippets_root().as_posix()
    calls = session_calls(path)
    runs, changed = collect(calls, root)
    log_path = acu_home() / "logs" / "runs.jsonl"
    logs = list(records(log_path)) if log_path.is_file() else []
    join_runs(runs, logs, root)
    lines = [f"ACU history: {len(runs)} runs. Success = launcher ok, not task verification."]
    if not log_path.is_file():
        lines.append(f"Run log missing: {log_path}; outcomes unknown.")
    apps = defaultdict(list)
    for run in runs:
        apps[run.app.casefold()].append(run)
    for app_runs in apps.values():
        counts = Counter(run.outcome for run in app_runs)
        lines.append(f'{app_runs[0].app}: {len(app_runs)} runs ({counts["ok"]} ok, {counts["error"]} error, '
                     f'{counts["timeout"]} timeout, {counts["unknown"]} unknown)')
        chain = []
        for run in app_runs:
            chain.append(run)
            if run.snippet:
                lines.append(f"  snippet: {run.path} -> {run.outcome}")
            if run.outcome == "unknown":
                lines.append(f"  unmatched: {run.path}")
                chain = []
            elif run.outcome == "ok" and not run.look:
                errors = sum(item.outcome in ("error", "timeout") for item in chain)
                looks = sum(item.look for item in chain)
                if run.app != "unknown app" and (errors or looks >= 2):
                    length = f"{run.lines} lines" if run.lines is not None else "length unknown"
                    lines.append(f"  candidate: {len(chain)} runs, {errors} errors, {looks} looks; last {run.path} ({length})")
                chain = []
    for path in sorted(changed, key=str.casefold):
        lines.append(f"Changed snippet ({snippet_app(path, root)}): {path}")
    failures = defaultdict(Counter)
    existing = {}
    for row in logs:
        script = normalized(row["script"])
        if snippet_app(script, root) and Path(script).is_file():
            failures[script.casefold()][row["outcome"]] += 1
            existing[script.casefold()] = script
    for key, counts in sorted(failures.items()):
        failed = counts["error"] + counts["timeout"]
        total = sum(counts.values())
        if failed >= 3 and failed * 2 >= total:
            lines.append(f"Frequently failing snippet: {existing[key]} ({failed}/{total} failed, all recorded runs)")
    return "\n".join(lines)
