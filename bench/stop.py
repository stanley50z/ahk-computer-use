"""Request cancellation of one bench worker and wait for its cleanup; never kill unrelated processes."""

import argparse
import json
import time
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bench.run import cleanup_finished


# A run-local cancellation request lets the worker stop its child tree and perform owned-window cleanup.
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run_dir', type=Path)
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    launch = json.loads((run_dir / 'launch.json').read_text(encoding='utf-8'))
    if Path(launch['run_dir']).resolve() != run_dir:
        raise ValueError('launch record does not belong to this directory')
    if (run_dir / 'finished.json').exists():
        finished = json.loads((run_dir / 'finished.json').read_text(encoding='utf-8'))
        if not cleanup_finished(finished):
            raise RuntimeError('worker finished, but cleanup failed or is unverified; inspect cleanup.json')
        print('already finished; cleanup verified')
        return
    (run_dir / 'cancel.request').write_text('stop requested\n', encoding='utf-8')
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        if (run_dir / 'finished.json').exists():
            finished = json.loads((run_dir / 'finished.json').read_text(encoding='utf-8'))
            if not cleanup_finished(finished):
                raise RuntimeError('worker finished, but cleanup failed; inspect cleanup.json')
            print('worker finished cleanup')
            return
        time.sleep(0.25)
    raise TimeoutError(f"worker {launch['worker_pid']} has not acknowledged cleanup; inspect {run_dir / 'worker.log'}")


if __name__ == '__main__':
    main()
