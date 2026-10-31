"""Leaf paths and evidence IO shared by the controller and scenario adapters."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


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
