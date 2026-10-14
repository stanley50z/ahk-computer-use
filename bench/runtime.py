"""Select the project's dependency environment before a benchmark CLI does work."""

import importlib
import os
import subprocess
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


# CLI entry points call this after argument/approval checks, before preparing any trial.
def ensure_project_runtime(script):
    environment = ROOT / '.venv'
    python = environment / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    setup = f'Run uv sync --project "{ROOT}" to install the benchmark dependencies.'
    try:
        if not python.is_file():
            raise RuntimeError(f'Benchmark project Python is missing: {python}. {setup}')
        if Path(sys.prefix).resolve() != environment.resolve() or sys.flags.no_site:
            options = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}
            result = subprocess.run([str(python), str(script), *sys.argv[1:]],
                                    stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr,
                                    env=dict(os.environ, PYTHONUTF8='1'), **options)
            raise SystemExit(result.returncode)
        try:
            for module in ('tiktoken', 'PIL.Image'):
                importlib.import_module(module)
        except ImportError as error:
            raise RuntimeError(f'Benchmark project dependencies are incomplete. {setup}') from error
    except Exception:
        log = ROOT / '.pi/bench/runtime-preflight.log'
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open('a', encoding='utf-8') as output:
            output.write(f'\n{datetime.now(timezone.utc).isoformat()} {script}\n{traceback.format_exc()}')
        raise
