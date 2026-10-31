"""Leaf paths and evidence IO shared by the controller and scenario adapters."""
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


# Resolve ordinary installed commands without changing their argument boundaries.
def executable_command(command):
    executable = shutil.which(command[0])
    if executable is None:
        raise FileNotFoundError(f'{command[0]} is not on PATH')
    return [executable, *command[1:]]


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


TRIAL_POLICY = {'attempts_per_configuration': 3, 'aggregation': 'all-successes', 'replace_failed_attempts': False}


# Resolve the home alias consistently in prompts and audits, using the current user's root.
def expand_user_root(path):
    path = Path(path)
    return Path.home().joinpath(*path.parts[1:]) if path.parts and path.parts[0] == '~' else path


# Bench-authored prompt references use the current user's home alias; internal paths stay resolved.
def actor_path(path):
    path = expand_user_root(path).absolute()
    home = Path.home().absolute()
    if not path.is_relative_to(home):
        path, home = path.resolve(), home.resolve()
    if path.is_relative_to(home):
        relative = path.relative_to(home)
        return '~' if not relative.parts else '~/' + relative.as_posix()
    return path.as_posix()  # A path outside the user root has no home-relative equivalent.
