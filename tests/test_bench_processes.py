"""Process-only lifecycle checks, with a small stand-in CLI rather than any desktop tool."""

import json
import sys

from bench.run import capture


def test_exited_agent_cannot_leave_descendant_holding_the_stream_open(tmp_path):
    program = 'import subprocess,sys,json; child=subprocess.Popen([sys.executable,"-c","import time; time.sleep(30)"]); print(json.dumps({"type":"child_started","pid":child.pid}),flush=True)'
    records, wall_s, exit_code = capture([sys.executable, '-u', '-c', program], tmp_path, None, tmp_path, timeout_s=10)
    assert records[0]['event']['type'] == 'child_started'
    state = json.loads((tmp_path / 'capture.json').read_text(encoding='utf-8'))
    assert not state['passed']
    assert state['process_tree_stopped']
    assert 'descendant held the stream open' in state['error']


def test_timeout_preserves_stream_measurements_and_records_terminal_failure(tmp_path):
    command = [sys.executable, '-u', '-c', 'import json,time; print(json.dumps({"type":"agent_start"}),flush=True); time.sleep(30)']
    records, wall_s, exit_code = capture(command, tmp_path, None, tmp_path, timeout_s=0.5)
    assert records[0]['event']['type'] == 'agent_start'
    assert wall_s >= 0.5
    assert exit_code != 0
    state = json.loads((tmp_path / 'capture.json').read_text(encoding='utf-8'))
    assert not state['passed']
    assert 'TimeoutError' in state['error']
    assert json.loads((tmp_path / 'state.json').read_text(encoding='utf-8'))['status'] == 'exited'
