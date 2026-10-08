#!/usr/bin/env python3
"""Pull, generate, validate, commit and push a project's nested GitHub Wiki.

Copy this file and openwiki-sync into <project>/.githooks/. The launcher starts
a detached worker from post-commit. Requires Python 3.10+, Git and OpenWiki on PATH.
"""

import argparse
import json
import os
from pathlib import Path
import posixpath
import re
import shutil
import signal
import stat
import subprocess
import sys
from urllib.parse import quote, unquote, urlsplit


PROVIDER = 'openai-chatgpt'
MODEL = 'gpt-5.6-luna'
NO_WINDOW = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0


class SyncError(Exception):
    """An actionable sync failure that must leave the project commit intact."""


def save_diagnostics(path, output):
    """Keep diagnostics in Git-private storage, redacting common credential formats."""
    text = output.decode('utf-8', errors='replace') if isinstance(output, bytes) else output
    text = re.sub(r'(?i)(bearer\s+)\S+', r'\1[redacted]', text)
    text = re.sub(r'\bsk-[A-Za-z0-9_-]+', '[redacted]', text)
    text = re.sub(r'(?i)((?:[\w]*token|[\w]*api_key)["\x27]?\s*[:=]\s*["\x27]?)[^\s"\x27,}]+', r'\1[redacted]', text)
    text = re.sub(r'(https?://)[^/\s@]+@', r'\1[redacted]@', text)
    if path.is_symlink():
        raise SyncError('Refusing to follow a symlink for the private sync log.')
    descriptor = os.open(path, os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
        stream.write(text + '\n')
    path.chmod(0o600)


def git(cwd, *args, env, timeout=120):
    """Run noninteractive Git without triggering hooks in either repository."""
    result = subprocess.run(['git', '-c', f'core.hooksPath={os.devnull}', '-C', str(cwd), *args], env=env,
                            capture_output=True, text=True, encoding='utf-8', timeout=timeout,
                            creationflags=NO_WINDOW)
    if result.returncode:
        # Do not echo remote URLs or credential-bearing diagnostics into terminal output.
        detail = 'inspect this repository manually'
        if env.get('SZ_OPENWIKI_LOG'):
            path = Path(env['SZ_OPENWIKI_LOG'])
            save_diagnostics(path, result.stdout + result.stderr)
            detail = f'see {path}'
        raise SyncError(f'Git {args[0]} failed (exit {result.returncode}); {detail}.')
    return result.stdout.rstrip('\r\n')


def clean_git_env():
    """Detach nested Git commands from the committing process's repository/index."""
    env = os.environ.copy()
    keys = subprocess.run(['git', 'rev-parse', '--local-env-vars'], check=True,
                          capture_output=True, text=True, timeout=10, creationflags=NO_WINDOW).stdout.splitlines()
    for key in keys:
        env.pop(key, None)
    env.pop('SZ_OPENWIKI_LOG', None)
    env['GIT_TERMINAL_PROMPT'] = '0'
    env['GCM_INTERACTIVE'] = 'never'
    return env


def changed_paths(root, env):
    """List staged, unstaged and untracked files without Git's display quoting."""
    changed = set(git(root, 'diff', '--name-only', '-z', 'HEAD', env=env).split('\0'))
    changed.update(git(root, 'ls-files', '--others', '--exclude-standard', '-z', env=env).split('\0'))
    return changed - {''}


def github_repo(url):
    """Resolve the GitHub repository identity without conflating Wiki and project."""
    match = re.fullmatch(r'(?:https://github\.com/|git@github\.com:|ssh://git@github\.com/)([^/]+/[^/]+?)(?:\.git)?/?', url)
    if not match:
        raise SyncError('Expected a GitHub origin remote.')
    return match[1]


PRIVATE_FILES = {'INSTRUCTIONS.md', '_plan.md'}


def is_page(name):
    """Restrict publication to Markdown pages, excluding generator state and prompts."""
    path = Path(name)
    return (path.suffix == '.md' and path.name not in PRIVATE_FILES
            and not any(part.startswith('.') for part in path.parts))


def exclude_generator_state(git_dir):
    """Keep local generator state out of Wiki commits and clean-tree checks."""
    path = git_dir / 'info' / 'exclude'
    path.parent.mkdir(exist_ok=True)
    text = path.read_text(encoding='utf-8') if path.exists() else ''
    for rule in ['.*', 'INSTRUCTIONS.md', '_plan.md']:
        if rule not in text.splitlines():
            text = text.rstrip('\n') + '\n' + rule + '\n'
    path.write_text(text, encoding='utf-8', newline='\n')


def rewrite_links(text, resolve):
    """Rewrite Markdown inline/reference destinations without editing code examples."""
    inline = re.compile(r'(\!?\[[^\]\n]*\]\(\s*)(<[^>\n]+>|[^\s()]+(?:\([^()\n]*\)[^\s()]*)*)(\s+(?:"[^"\n]*"|\x27[^\x27\n]*\x27))?(\s*\))')
    reference = re.compile(r'^( {0,3}\[[^\]\n]+\]:\s*)(<[^>\n]+>|\S+)', re.MULTILINE)
    fence = None
    output = []
    for line in text.splitlines(keepends=True):
        marker = re.match(r'^ {0,3}(`{3,}|~{3,})', line)
        if marker:
            token = marker[1]
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = None
            output.append(line)
            continue
        if fence or line.startswith(('    ', '\t')):
            output.append(line)
            continue
        # A link may contain code in its label; protect matches *starting* in code.
        for pattern in [inline, reference]:
            spans = [(m.start(), m.end()) for m in re.finditer(r'(`+).*?\1(?!`)', line)]
            def replace(match):
                if any(start <= match.start() < end for start, end in spans):
                    return match[0]
                suffix = ''.join(group or '' for group in match.groups()[2:])
                return match[1] + resolve(match[2]) + suffix
            line = pattern.sub(replace, line)
        # HTML links need a real HTML parser; fail instead of publishing broken paths.
        prose = re.sub(r'(`+).*?\1(?!`)', '', line)
        for match in re.finditer(r'(?:href|src)\s*=\s*["\x27]([^"\x27]+)', prose, re.IGNORECASE):
            if not urlsplit(match[1]).scheme and not match[1].startswith(('#', '//')):
                raise SyncError('Relative HTML links are unsupported; use Markdown links.')
        output.append(line)
    return ''.join(output)


def prepare_pages(root, wiki, git_dir, project, source_ref):
    """Flatten pages in place, repair links and build a sidebar before staging anything."""
    mapping_file = git_dir / 'openwiki-page-map.json'
    previous = json.loads(mapping_file.read_text(encoding='utf-8')) if mapping_file.exists() else {}
    if not isinstance(previous, dict) or any(
        not isinstance(k, str) or not isinstance(v, str) or '/' in v or '\\' in v
        or v.startswith('.') or not v.endswith('.md') for k, v in previous.items()
    ):
        raise SyncError('Invalid local Wiki page mapping.')
    sources = []
    for directory, dirs, files in os.walk(wiki, followlinks=False):
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        for name in dirs + files:
            entry = Path(directory) / name
            reparse_point = (os.name == 'nt' and os.lstat(entry).st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)
            if entry.is_symlink() or reparse_point or not entry.resolve().is_relative_to(wiki):
                raise SyncError('Symlinks and junctions in the Wiki are unsupported for automatic publication.')
        sources.extend((Path(directory) / f).relative_to(wiki).as_posix()
                       for f in files if is_page((Path(directory) / f).relative_to(wiki)))
    mapping = dict(previous)
    selected = {}
    for source in sorted(sources):
        target = previous.get(source, source.replace('/', '-'))
        if re.search(r'[\\/:*?"<>|\[\]#]', target) or target.endswith((' .md', '..md')):
            raise SyncError(f'Unsafe Wiki page name: {source}')
        key = target.casefold()
        if key in selected:
            other = selected[key]
            # A generator may recreate a previously flattened source path.
            if previous.get(source) == other:
                selected[key] = source
            elif previous.get(other) != source:
                raise SyncError(f'Wiki page filename collision: {source}')
        else:
            selected[key] = source
        mapping[source] = target
    targets = {mapping[s] for s in selected.values()}
    if 'Home.md' not in targets:
        raise SyncError('Home.md is missing; initialize the Wiki before installing the hook.')
    for target in targets:
        mapping[target] = target

    def destination(source, value):
        wrapped = value.startswith('<') and value.endswith('>')
        url = value[1:-1] if wrapped else value
        parsed = urlsplit(url)
        if parsed.scheme or url.startswith(('#', '//')):
            return value
        path = unquote(parsed.path)
        relative = posixpath.normpath(posixpath.join(posixpath.dirname(source), path))
        if path.startswith('/openwiki/'):
            relative = posixpath.normpath(path[len('/openwiki/'):])
        page = mapping.get(relative) or mapping.get(relative + '.md')
        suffix = ('?' + parsed.query if parsed.query else '') + ('#' + parsed.fragment if parsed.fragment else '')
        if page in targets:
            result = quote(page[:-3]) + suffix
        else:
            candidate = ((root / path.lstrip('/')) if path.startswith('/') else (wiki / relative)).resolve()
            if not candidate.is_relative_to(root) or candidate.is_relative_to(wiki) or not candidate.exists():
                raise SyncError(f'Unresolved local link in {source}: {url}')
            kind = 'tree' if candidate.is_dir() else 'blob'
            result = f'https://github.com/{project}/{kind}/{quote(source_ref, safe="")}/' + quote(candidate.relative_to(root).as_posix()) + suffix
        return '<' + result + '>' if wrapped else result

    rendered = {}
    for source in selected.values():
        if mapping[source] == '_Sidebar.md':
            continue
        rendered[mapping[source]] = rewrite_links(
            (wiki / source).read_text(encoding='utf-8'), lambda value: destination(source, value))
    rendered['_Sidebar.md'] = ''.join(
        f'- [{Path(name).stem}]({quote(Path(name).stem)})\n'
        for name in sorted(targets, key=lambda n: (n != 'Home.md', n.casefold()))
        if not name.startswith('_'))
    # Validate the entire transformation before editing any page.
    for name, content in rendered.items():
        (wiki / name).write_text(content, encoding='utf-8', newline='\n')
    for source in sources:
        if source not in rendered:
            (wiki / source).unlink()
    mapping_file.write_text(json.dumps(mapping, indent=2) + '\n', encoding='utf-8')
    return list(rendered)


def generate(executable, root, env, timeout):
    """Bound generation and terminate its descendants on timeout or interruption."""
    options = ({'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP | NO_WINDOW} if os.name == 'nt'
               else {'start_new_session': True})
    process = subprocess.Popen([executable, 'code', '--update', '--print'], cwd=root,
                               env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, **options)
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except BaseException:
        if os.name == 'nt':
            subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                           capture_output=True, timeout=30, creationflags=NO_WINDOW)
        else:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass  # The process group exited between the timeout and the signal.
        process.communicate(timeout=30)
        raise
    return subprocess.CompletedProcess(process.args, process.returncode, stdout, stderr)


def sync(root, generation_timeout):
    """Synchronize only the Wiki repository; the main project is never committed."""
    env = clean_git_env()
    root = root.resolve()
    wiki = root / 'openwiki'
    if not (wiki / '.git').exists() or Path(git(wiki, 'rev-parse', '--show-toplevel', env=env)).resolve() != wiki:
        raise SyncError('openwiki/ must be the separate GitHub Wiki clone.')
    project = github_repo(git(root, 'config', '--get', 'remote.origin.url', env=env))
    # Check every literal fetch/push URL, before Git's trusted transport rewrites.
    origins = git(wiki, 'config', '--get-regexp', r'^remote\.origin\.(url|pushurl)$', env=env)
    for setting in origins.splitlines():
        if github_repo(setting.split(' ', 1)[1]).casefold() != (project + '.wiki').casefold():
            raise SyncError('openwiki/ origin is not this project\'s GitHub Wiki.')
    if git(root, 'ls-files', '--', 'openwiki', env=env):
        raise SyncError('The main repository still tracks openwiki/; migrate it first.')
    git_dir = Path(git(wiki, 'rev-parse', '--absolute-git-dir', env=env))
    exclude_generator_state(git_dir)
    if git(root, 'status', '--porcelain', env=env) or git(wiki, 'status', '--porcelain', env=env):
        print('OpenWiki sync skipped: project or Wiki has uncommitted changes.')
        return
    lock = git_dir / 'openwiki-sync.lock'
    try:
        lock.mkdir()
    except FileExistsError:
        print('OpenWiki sync skipped: another sync is already running; inspect the lock if a previous run was interrupted.')
        return
    try:
        publish(root, wiki, git_dir, project, env, generation_timeout)
    finally:
        lock.rmdir()


def publish(root, wiki, git_dir, project, env, generation_timeout):
    """Run the pull-to-push sequence while holding the Wiki clone's exclusive lock."""
    log = git_dir / 'openwiki-sync.log'
    if log.is_symlink():
        raise SyncError('Refusing to follow a symlink for the private sync log.')
    log.unlink(missing_ok=True)
    env = dict(env, SZ_OPENWIKI_LOG=str(log))
    branch = git(wiki, 'branch', '--show-current', env=env)
    remote_head = git(wiki, 'ls-remote', '--symref', 'origin', 'HEAD', env=env)
    if not branch or f'ref: refs/heads/{branch}\tHEAD' not in remote_head.splitlines():
        raise SyncError('Wiki must be on the remote default branch.')
    git(wiki, 'pull', '--ff-only', 'origin', branch, env=env)
    wiki_head = git(wiki, 'rev-parse', 'HEAD', env=env)
    remote_commit = git(wiki, 'rev-parse', 'FETCH_HEAD', env=env)
    pending_file = git_dir / 'openwiki-pending.json'
    pending = json.loads(pending_file.read_text(encoding='utf-8')) if pending_file.exists() else None
    if wiki_head != remote_commit and pending != {'base': remote_commit, 'head': wiki_head}:
        raise SyncError('Unrecognized unpublished Wiki commits; review and push them manually before automatic sync.')
    config = git(wiki, 'config', '--local', '--null', '--list', env=env)
    tracked = git(wiki, 'ls-files', '-z', env=env).split('\0')
    project_head = git(root, 'rev-parse', 'HEAD', env=env)
    source_ref = git(root, 'branch', '--show-current', env=env) or project_head
    executable = shutil.which('openwiki')
    if not executable:
        raise SyncError('OpenWiki CLI is missing from PATH.')
    generation_env = dict(env, OPENWIKI_PROVIDER=PROVIDER, OPENWIKI_MODEL_ID=MODEL)
    generation_env.pop('OPENWIKI_DEBUG', None)
    workflows = [root / '.github/workflows' / name for name in ['openwiki-update.yml', 'openwiki-update.yaml']]
    created_workflows = [path for path in workflows if not path.exists()]
    try:
        result = generate(executable, root, generation_env, generation_timeout)
        save_diagnostics(log, result.stdout + result.stderr)
    except subprocess.TimeoutExpired as error:
        save_diagnostics(log, (error.stdout or b'') + (error.stderr or b''))
        raise SyncError(f'OpenWiki generation timed out; see {log}.') from error
    finally:
        for path in created_workflows:
            if path.is_file() and path.resolve().is_relative_to(root):
                path.unlink()
    if result.returncode:
        raise SyncError(f'OpenWiki generation failed (exit {result.returncode}); see {log}.')
    if git(root, 'rev-parse', 'HEAD', env=env) != project_head or git(wiki, 'rev-parse', 'HEAD', env=env) != wiki_head:
        raise SyncError('Project or Wiki HEAD changed during generation; inspect before publishing.')
    verify_wiki_config(wiki, config, branch, env)
    if changed_paths(root, env) - {'AGENTS.md', 'CLAUDE.md'}:
        raise SyncError('Unexpected project changes from generation; inspect them before publishing.')
    if any(not is_page(p) for p in changed_paths(wiki, env)):
        raise SyncError('Unexpected Wiki changes outside publishable Markdown pages; inspect before publishing.')
    pages = prepare_pages(root, wiki, git_dir, project, source_ref)
    git(wiki, 'add', '--', *sorted(set(pages) | {p for p in tracked if is_page(p)}), env=env)
    if any(not is_page(p) for p in git(wiki, 'diff', '--cached', '--name-only', '-z', env=env).split('\0') if p):
        raise SyncError('Unexpected Wiki changes in the index; inspect before publishing.')
    git(wiki, 'diff', '--cached', '--check', env=env)
    if git(wiki, 'diff', '--cached', '--name-only', env=env):
        git(wiki, 'commit', '-m', 'docs: update project wiki', env=env)
        pending_file.write_text(json.dumps({'base': remote_commit, 'head': git(wiki, 'rev-parse', 'HEAD', env=env)}), encoding='utf-8')
    verify_wiki_config(wiki, config, branch, env)
    git(wiki, 'push', '--no-force', '--no-follow-tags', 'origin', f'HEAD:refs/heads/{branch}', env=env)
    if git(wiki, 'rev-parse', 'HEAD', env=env) != git(wiki, 'ls-remote', 'origin', f'refs/heads/{branch}', env=env).split()[0]:
        raise SyncError('Wiki remote advanced during synchronization; inspect before retrying.')
    pending_file.unlink(missing_ok=True)
    print('Wiki synced.')
    if git(root, 'status', '--porcelain', env=env):
        print('Project instruction changes remain uncommitted for review.')


def verify_wiki_config(wiki, config, branch, env):
    """Recheck the publication destination after generation and immediately before push."""
    if (git(wiki, 'config', '--local', '--null', '--list', env=env) != config
            or git(wiki, 'branch', '--show-current', env=env) != branch):
        raise SyncError('Wiki configuration or branch changed during synchronization; inspect before publishing.')


def start_background(root, generation_timeout):
    """Detach Wiki work from Git's process, console and pipes; retain private diagnostics."""
    root = root.resolve()
    env = clean_git_env()
    wiki = root / 'openwiki'
    if not (wiki / '.git').exists():
        raise SyncError('openwiki/ must be the separate GitHub Wiki clone.')
    git_dir = Path(git(wiki, 'rev-parse', '--absolute-git-dir', env=env))
    log = git_dir / 'openwiki-background.log'
    if log.is_symlink():
        raise SyncError('Refusing to follow a symlink for the private background log.')
    descriptor = os.open(log, os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o600)
    options = ({'creationflags': subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP}
               if os.name == 'nt' else {'start_new_session': True})
    with os.fdopen(descriptor, 'ab') as stream:
        log.chmod(0o600)
        process = subprocess.Popen(
            [sys.executable, '-u', str(Path(__file__).resolve()), '--root', str(root),
             '--generation-timeout', str(generation_timeout)],
            cwd=root, env=env, stdin=subprocess.DEVNULL, stdout=stream, stderr=stream,
            close_fds=True, **options)
    print(f'OpenWiki sync started in background (PID {process.pid}); see {log}.')


def main():
    """Expose detached hook startup and a synchronous manual retry command."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path.cwd())
    parser.add_argument('--background', action='store_true',
                        help='Start a detached Wiki job and return immediately.')
    parser.add_argument('--generation-timeout', type=float, default=1800,
                        help='Maximum generation time in seconds (default: 1800).')
    args = parser.parse_args()
    if not 0 < args.generation_timeout < float('inf'):
        parser.error('--generation-timeout must be positive and finite')
    try:
        if args.background:
            start_background(args.root, args.generation_timeout)
        else:
            sync(args.root, args.generation_timeout)
    except KeyboardInterrupt:
        print('OpenWiki sync interrupted; generated work was preserved.', file=sys.stderr)
        return 130
    except (SyncError, OSError, ValueError, subprocess.SubprocessError) as error:
        message = str(error) if isinstance(error, SyncError) else type(error).__name__
        print(f'OpenWiki sync failed: {message} No project commit was amended or rolled back by this script.', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    status = main()
    print(f'OpenWiki sync process {os.getpid()} finished (exit {status}).')
    raise SystemExit(status)
