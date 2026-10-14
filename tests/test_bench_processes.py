"""Process-only lifecycle checks, using ordinary Python rather than desktop tools."""

import json
import shutil
import subprocess
import sys
import threading
import time
import venv

import pytest

from bench.run import capture
from conftest import REPO


def test_benchmark_entry_points_do_not_offer_an_overall_deadline():
    for entry in ("start.py", "run.py"):
        result = subprocess.run([sys.executable, str(REPO / "bench" / entry), "--help"],
                                capture_output=True, text=True, encoding="utf-8", timeout=10)
        assert result.returncode == 0, result.stdout + result.stderr
        assert "--timeout" not in result.stdout


@pytest.mark.parametrize('entry, arguments', [
    ('start.py', ['--desktop-approved']),
    ('run.py', ['run', '--desktop-approved']),
])
@pytest.mark.parametrize('environment', ['missing', 'without-dependencies'])
def test_benchmark_setup_failure_stops_before_creating_a_trial(tmp_path, entry, arguments, environment):
    checkout = tmp_path / 'checkout'
    bench = checkout / 'bench'
    bench.mkdir(parents=True)
    for name in ('__init__.py', 'start.py', 'run.py', 'intervals.py', 'runtime.py'):
        shutil.copyfile(REPO / 'bench' / name, bench / name)
    if environment == 'without-dependencies':
        venv.EnvBuilder(with_pip=False).create(checkout / '.venv')
    result = subprocess.run([sys._base_executable, '-S', str(bench / entry), *arguments],
                            capture_output=True, text=True, encoding='utf-8', timeout=20)
    assert result.returncode != 0
    assert 'uv sync --project' in result.stderr
    evidence = checkout / '.pi/bench'
    assert {path.name for path in evidence.iterdir()} == {'runtime-preflight.log'}
    log = (evidence / 'runtime-preflight.log').read_text(encoding='utf-8')
    assert 'Traceback' in log
    assert ('project Python is missing' if environment == 'missing' else "No module named 'tiktoken'") in log


def test_capture_can_finish_after_more_than_240_measured_seconds(tmp_path, monkeypatch):
    clock = time.perf_counter
    monkeypatch.setattr(time, "perf_counter", lambda: clock() * 1000)
    program = 'import json,time; print(json.dumps({"type":"agent_start"}),flush=True); time.sleep(0.4); print(json.dumps({"type":"completed"}),flush=True)'
    records, wall_s, exit_code = capture([sys.executable, '-u', '-c', program], tmp_path, None, tmp_path)
    assert wall_s > 240
    assert exit_code == 0
    assert records[-1]['event']['type'] == 'completed'
    assert json.loads((tmp_path / 'capture.json').read_text(encoding='utf-8'))['passed']


def test_exited_agent_cannot_leave_descendant_holding_the_stream_open(tmp_path):
    program = 'import subprocess,sys,json; child=subprocess.Popen([sys.executable,"-c","import time; time.sleep(30)"]); print(json.dumps({"type":"child_started","pid":child.pid}),flush=True)'
    records, wall_s, exit_code = capture([sys.executable, '-u', '-c', program], tmp_path, None, tmp_path)
    assert records[0]['event']['type'] == 'child_started'
    state = json.loads((tmp_path / 'capture.json').read_text(encoding='utf-8'))
    assert not state['passed']
    assert state['process_tree_stopped']
    assert 'descendant held the stream open' in state['error']


def test_manual_cancellation_preserves_evidence_and_stops_owned_processes(tmp_path):
    ready = tmp_path / 'ready'
    program = 'import json,time,pathlib,sys; print(json.dumps({"type":"agent_start"}),flush=True); pathlib.Path(sys.argv[1]).touch(); time.sleep(30)'

    def cancel_when_ready():
        deadline = time.monotonic() + 5
        while not ready.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        (tmp_path / 'cancel.request').write_text('stop requested\n', encoding='utf-8')

    controller = threading.Thread(target=cancel_when_ready)
    controller.start()
    try:
        records, wall_s, exit_code = capture([sys.executable, '-u', '-c', program, str(ready)], tmp_path, None, tmp_path)
    finally:
        controller.join(timeout=6)
    assert records[0]['event']['type'] == 'agent_start'
    assert exit_code != 0
    state = json.loads((tmp_path / 'capture.json').read_text(encoding='utf-8'))
    assert not state['passed']
    assert state['process_tree_stopped']
    assert 'bench stop requested' in state['error']
    assert json.loads((tmp_path / 'state.json').read_text(encoding='utf-8'))['status'] == 'exited'
