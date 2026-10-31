"""Bounded metadata correlation for runtime-reported screenshot destinations."""

import json
import ntpath
import os
from pathlib import Path
import re
import shlex
import stat
import tempfile

from bench.tool_calls import ToolCall


# Normalize returned absolute paths without interpreting them relative to actor cwd.
def absolute_path(value):
    value = value.replace('\\', '/')
    if value.startswith('//?/UNC/'):
        value = '//' + value[8:]
    elif value.startswith('//?/'):
        value = value[4:]
    if re.match(r'^[A-Za-z]:/', value) or value.startswith('//'):
        return ntpath.normpath(value).replace('\\', '/').casefold()
    if value.startswith('/'):
        return os.path.normpath(value)
    return None


# Inventory only direct entries, never following links or reading file contents.
def snapshot_runtime_files(roots=None):
    roots = [Path.home(), Path(tempfile.gettempdir())] if roots is None else roots
    result = {'roots': {}, 'files': {}, 'errors': {}}
    for root in roots:
        root = Path(root).absolute()
        key = absolute_path(str(root))
        coverage = result['roots'][key] = {'complete': False}
        try:
            with os.scandir(root) as entries:
                for entry in entries:
                    path = absolute_path(entry.path)
                    try:
                        # DirEntry.stat caches zero device/inode values on Windows; stat the path for file identity.
                        info = os.stat(entry.path, follow_symlinks=False)
                        if not stat.S_ISREG(info.st_mode) or entry.is_symlink():
                            result['errors'][path] = 'not a direct regular file'
                            continue
                        result['files'][path] = {'device': info.st_dev, 'inode': info.st_ino,
                                                 'size': info.st_size, 'mtime_ns': info.st_mtime_ns}
                    except OSError as exc:
                        result['errors'][path] = str(exc)
            coverage['complete'] = True
        except OSError as exc:
            coverage['error'] = str(exc)
    return result


# Read complete JSON objects from structured results or shell stdout, not request text.
def result_destinations(value):
    if isinstance(value, dict):
        if value.get('isError') or value.get('is_error') or value.get('error'):
            return
        path = value.get('screenshot_file_path')
        if isinstance(path, str):
            yield path
        for key, child in value.items():
            if key != 'screenshot_file_path':
                yield from result_destinations(child)
    elif isinstance(value, list):
        for child in value:
            yield from result_destinations(child)
    elif isinstance(value, str):
        decoder = json.JSONDecoder()
        # CLI JSON starts at column zero. Do not salvage nested fields from a
        # truncated object; shell prefixes may precede a complete JSON document.
        end = 0
        for match in re.finditer(r'(?m)^[\[{]', value):
            if match.start() < end:
                continue
            try:
                parsed, length = decoder.raw_decode(value[match.start():])
            except json.JSONDecodeError:
                continue
            end = match.start() + length
            yield from result_destinations(parsed)


# Recognize a direct capture CLI call (optionally after cd), not echoed metadata or unresolved helpers.
def capture_requests(arguments):
    command = arguments.get('command') if isinstance(arguments, dict) else None
    if not isinstance(command, str):
        return []
    lexer = shlex.shlex(command, posix=True, punctuation_chars=';&|()<>\n')
    lexer.whitespace = ' \t\r'
    try:
        tokens = list(lexer)
    except ValueError:
        return []  # Unsupported shell syntax is reported as unverified by the caller.
    segments = [[]]
    for token in tokens:
        if token in (';', '\n'):
            segments.append([])
        elif token and all(char in ';&|()<>' for char in token):
            return []
        else:
            segments[-1].append(token)
    segments = [segment for segment in segments if segment]
    if not segments or any(segment[0] != 'cd' for segment in segments[:-1]):
        return []
    call = segments[-1]
    if (len(call) != 3 or ntpath.basename(call[0]).casefold() not in ('cua-driver', 'cua-driver.exe')
            or call[1] not in ('get_window_state', 'get_desktop_state')):
        return []
    try:
        request = json.loads(call[2])
    except json.JSONDecodeError:
        return []
    path = request.get('screenshot_out_file') if isinstance(request, dict) else None
    return [path] if isinstance(path, str) and path and request.get('include_screenshot') is not False else []


# A changed existing destination plus a successful actual output is the failure boundary.
def audit_runtime_writes(calls: list[ToolCall], before, after):
    result = {'policy': 'direct-root-metadata-v1', 'outputs': [], 'unverified_calls': [],
              'changed_preexisting': [], 'coverage': 'unverified' if before is None or after is None else 'bounded'}
    if before is not None and after is not None:
        result['changed_preexisting'] = [path for path, info in before['files'].items()
                                         if after['files'].get(path) != info]
    shell_calls = 0
    for call in calls:
        if call['name'].casefold() not in ('bash', 'shell', 'unmatched'):
            continue
        call_id, arguments, body = call['id'], call['arguments'], call['result']
        failed = not call['matched'] or not call['completed'] or call['is_error'] is not False or call['truncated']
        shell_calls += 1
        requested = capture_requests(arguments)
        destinations = list(dict.fromkeys(result_destinations(body))) if not failed else []
        if not destinations:
            result['unverified_calls'].append({'call_id': call_id, 'reason': 'failed/missing/unmatched/truncated result' if failed else 'no complete runtime destination'})
        for raw in destinations:
            path = absolute_path(raw)
            source_verified = any(
                absolute_path(request) == path if absolute_path(request) else
                ntpath.basename(request).casefold() == ntpath.basename(raw).casefold()
                for request in requested)
            output = {'call_id': call_id, 'reported_path': raw, 'path': path, 'status': 'unverified',
                      'capture_request_verified': source_verified}
            if not source_verified:
                result['unverified_calls'].append({'call_id': call_id, 'reason': 'no matching direct capture request; helper/readback/shell provenance unresolved'})
            if path and before is not None and after is not None:
                parent = path.rsplit('/', 1)[0]
                covered = all(s['roots'].get(parent, {}).get('complete') and path not in s['errors'] for s in (before, after))
                old, new = before['files'].get(path), after['files'].get(path)
                output.update(before=old, after=new)
                if source_verified and covered and new is not None:
                    output['status'] = ('fresh' if old is None else
                                        'preexisting_changed' if old != new else 'preexisting_unchanged')
            result['outputs'].append(output)
    result['audited_shell_calls'] = shell_calls
    result['evidence_complete'] = shell_calls > 0 and not result['unverified_calls'] and all(
        output['status'] != 'unverified' for output in result['outputs'])
    return result
