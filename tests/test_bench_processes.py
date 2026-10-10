"""Process-only lifecycle checks, using ordinary Python rather than desktop tools."""

import json
import subprocess
import sys
import threading
import time

from bench.run import capture
from conftest import REPO


def test_benchmark_entry_points_do_not_offer_an_overall_deadline():
    for entry in ("start.py", "run.py"):
        result = subprocess.run([sys.executable, str(REPO / "bench" / entry), "--help"],
                                capture_output=True, text=True, encoding="utf-8", timeout=10)
        assert result.returncode == 0, result.stdout + result.stderr
        assert "--timeout" not in result.stdout


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
