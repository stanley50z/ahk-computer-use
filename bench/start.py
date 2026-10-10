"""Start one approved benchmark trial in the background without opening a terminal."""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bench.run import ARMS, ROOT, prepare, save_json


# Prepare a unique evidence directory, then launch an owned worker whose PID is recorded.
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--arm', choices=ARMS, default='pi-acu')
    parser.add_argument('--desktop-approved', action='store_true')
    parser.add_argument('--timeout', type=float, default=240)
    args = parser.parse_args()
    if not args.desktop_approved:
        parser.error('approval for this specific desktop run is required')
    run_dir = ROOT / '.pi/bench' / f'{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{args.arm}-{uuid4().hex[:6]}'
    prepare(args.arm, run_dir)
    command = [sys.executable, str(ROOT / 'bench/run.py'), 'run', '--arm', args.arm,
               '--run-dir', str(run_dir), '--desktop-approved', '--timeout', str(args.timeout)]
    options = {'creationflags': subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == 'nt' else {'start_new_session': True}
    environment = dict(os.environ, PYTHONUTF8='1')
    with (run_dir / 'worker.log').open('w', encoding='utf-8') as log:
        process = subprocess.Popen(command, cwd=ROOT, env=environment, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, **options)
    value = {'worker_pid': process.pid, 'run_dir': str(run_dir), 'command': command}
    save_json(run_dir / 'launch.json', value)
    print(json.dumps(value, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
