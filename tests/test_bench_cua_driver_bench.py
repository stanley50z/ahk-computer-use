import base64
import json
import os
import shutil
import subprocess
import sys
import types

import pytest

from bench.cua_driver_bench import acu_mcp, run, score, session

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=="
)


def fake_acu(tmp_path, output):
    """A stand-in for the `acu` command that prints one result with OUTPUT and records its argv."""
    script = tmp_path / "fake_acu.py"
    script.write_text(
        "import json, sys\n"
        f"open({str(tmp_path / 'argv.json')!r}, 'w').write(json.dumps(sys.argv[1:]))\n"
        f"print(json.dumps({{'outcome': 'ok', 'exit_code': 0, 'output': {output!r}}}))\n",
        encoding="utf-8",
    )
    return [sys.executable, str(script)]


def test_script_is_written_to_a_new_file_and_run(tmp_path):
    acu = fake_acu(tmp_path, "hello\n")
    result = acu_mcp.call_run({"script": 'FileAppend "hello`n", "*"', "args": ["a"], "timeout": 5}, tmp_path, acu)
    argv = json.loads((tmp_path / "argv.json").read_text())
    assert argv[0] == "run" and argv[2:] == ["--timeout", "5", "--", "a"]
    assert (tmp_path / "acu-scripts" / "001.ahk").read_text(encoding="utf-8") == 'FileAppend "hello`n", "*"'
    assert argv[1] == str(tmp_path / "acu-scripts" / "001.ahk")
    assert not result["isError"] and json.loads(result["content"][0]["text"])["output"] == "hello\n"


def test_saved_screenshot_is_attached_as_an_image(tmp_path):
    png = tmp_path / "shot.png"
    png.write_bytes(PNG)
    result = acu_mcp.call_run({"file": "screenshot.ahk"}, tmp_path, fake_acu(tmp_path, f"saved={png}\nscale=1\n"))
    assert [c["type"] for c in result["content"]] == ["text", "image"]
    assert base64.b64decode(result["content"][1]["data"]) == PNG


def test_script_and_file_together_is_refused(tmp_path):
    assert acu_mcp.call_run({"script": "x", "file": "tree.ahk"}, tmp_path, ["acu"])["isError"]
    assert acu_mcp.call_run({}, tmp_path, ["acu"])["isError"]


# Claude Code cuts long server instructions short, so they carry only the tool mapping and send the agent to the skill.
def test_initialize_sends_the_tool_mapping_and_points_to_the_skill(tmp_path):
    reply = acu_mcp.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
                           tmp_path, ["acu"])
    text = reply["result"]["instructions"]
    assert text.startswith(acu_mcp.PREFACE) and "`acu` skill" in text and len(text) < 2000
    assert acu_mcp.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}, tmp_path, ["acu"]) is None
    assert acu_mcp.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, tmp_path, ["acu"])["result"]["tools"][0]["name"] == "run"


def test_agent_skill_is_the_whole_acu_skill_after_the_tool_mapping():
    skill = acu_mcp.SKILL.read_text(encoding="utf-8")
    text = acu_mcp.skill_file()
    front, body = skill.split("---", 2)[1:]
    assert text.startswith(f"---{front}---") and acu_mcp.PREFACE in text and text.rstrip().endswith(body.strip())


def test_ahk_scan_flags_side_doors_but_not_printing():
    script = "\n".join([
        'FileAppend "Run done, FileRead ok`n", "*"',  # printing to stdout, words inside a string
        'root := UIA.ElementFromHandle(WinExist("BenchLab"))',
        'Run "cmd.exe"',
        'text := FileRead("C:\\bench\\state.json")',
        'FileAppend "x", "C:\\out.txt"',
        'shell := ComObject("WScript.Shell")',
        '; Run "notepad" in a comment',
        'Download("http://127.0.0.1:4184/inspect?record=v", p)',  # an agent read the task's web app this way
        'http := ComObject("WinHttp.WinHttpRequest.5.1")',
    ])
    assert score.ahk_hits(script) == [
        'Run "cmd.exe"', 'text := FileRead("C:\\bench\\state.json")', 'FileAppend "x", "C:\\out.txt"',
        'shell := ComObject("WScript.Shell")', 'Download("http://127.0.0.1:4184/inspect?record=v", p)',
        'http := ComObject("WinHttp.WinHttpRequest.5.1")',
    ]


def test_file_append_counts_only_with_a_file_target():
    """Agents wrote FileAppend with no Filename (no file is written) and with commas inside calls and strings."""
    printing = ['FileAppend AcuTree("ahk_id 1")', 'FileAppend r.FindElement({Type:"ComboBox"}).Value "`n"',
                'FileAppend(x, "*")', 'FileAppend Foo(a, b), "*"', 'FileAppend "a, b", "**"']
    writing = ['FileAppend(x, "C:\\a.txt")', 'FileAppend x, A_Desktop "\\o.txt"']
    assert [line for line in printing if score.ahk_hits(line)] == []
    assert [line for line in writing if score.ahk_hits(line)] == writing


def test_schedule_runs_each_windows_task_in_its_manifest_conditions(tmp_path):
    manifest = tmp_path / "cdb" / "taskpack" / "v2-taskset.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({"tasks": [
        {"id": "CDB-G02", "conditions": ["foreground", "background"], "apps": ["Mail", "Calc"], "os": ["windows"]},
        {"id": "MAC-01", "conditions": ["foreground"], "apps": ["Finder"], "os": ["macos"]},
        {"id": "MB-10", "conditions": ["foreground"], "apps": ["BenchLab"], "os": ["windows"]},
    ]}))
    bench = tmp_path / "cdb" / "automated-eval" / "macos_bench"
    plan = run.schedule(bench, None, ["foreground", "background"], 2)
    assert plan == [("CDB-G02", "foreground", 0), ("MB-10", "foreground", 0), ("CDB-G02", "background", 0),
                    ("CDB-G02", "foreground", 1), ("MB-10", "foreground", 1), ("CDB-G02", "background", 1)]
    assert run.schedule(bench, ["MB-10"], ["foreground", "background"], 1) == [("MB-10", "foreground", 0)]


# A stand-in for the bench's windows/cdb.py: CDB-G04's descriptor, whose by-name cleanup stops every chrome.exe.
def fake_cdb(workspace):
    class CdbTask:
        def __init__(self):
            self.workspace = workspace
            self.descriptor = {"apps": [{"id": "cases", "window": {"bounds": {"x": 20, "y": 30, "width": 980}}},
                                        {"id": "archive", "kind": "service"}]}

        def clear_leftovers(self):
            pass

    return types.SimpleNamespace(CdbTask=CdbTask, process_names=lambda d: {"chrome.exe", "rillwatch cases.exe"})


def test_task_windows_move_onto_the_chosen_display(tmp_path):
    cdb = fake_cdb(tmp_path)
    session.move_task_windows(cdb, 3840, -200)
    assert cdb.CdbTask().descriptor["apps"][0]["window"]["bounds"] == {"x": 3860, "y": -170, "width": 980}


def test_making_a_display_primary_moves_every_display_by_its_offset():
    from bench.cua_driver_bench import display
    layout = [{"display": "D1", "position": [0, 0]}, {"display": "D2", "position": [3840, 116]}]
    assert display.primary_positions(layout, "D2") == {"D1": (-3840, -116), "D2": (0, 0)}


@pytest.mark.skipif(sys.platform != "win32", reason="Windows processes")
def test_abort_finds_a_session_and_the_script_loop_that_started_it():
    from bench.cua_driver_bench import abort
    session_py = str(abort.HERE / "session.py")
    # A loop script (python -c) whose child names session.py, as a trial's process would.
    loop = subprocess.Popen([sys.executable, "-c", "import subprocess, sys; subprocess.run([sys.executable, '-c', "
                             f"'import time; time.sleep(60)', {session_py!r}, '--bench', 'B'])"])
    try:
        for _ in range(50):
            procs, benches = abort.bench_processes()
            if procs:
                break
            subprocess.run(["ping", "-n", "1", "-w", "100", "192.0.2.1"], capture_output=True)
        assert "B" in benches
        for proc in procs:
            abort.kill_tree(proc.pid)
        assert loop.wait(timeout=10) is not None  # the loop is stopped too, not only its current child
    finally:
        abort.kill_tree(loop.pid)


def test_abort_reads_the_task_workspaces_from_the_launch_descriptors(tmp_path, monkeypatch):
    from bench.cua_driver_bench import abort
    descriptor = tmp_path / "cdb" / "taskpack" / "tasks" / "shared" / "cdb-s02" / "platform" / "launch.windows.json"
    descriptor.parent.mkdir(parents=True)
    descriptor.write_text(json.dumps({"workspace_root": "${USERPROFILE}\\cdb-s02"}))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    assert abort.workspaces(tmp_path / "cdb" / "automated-eval" / "macos_bench") == [tmp_path / "cdb-s02"]


@pytest.mark.skipif(sys.platform != "win32", reason="Windows process cleanup")
def test_g04_cleanup_stops_the_task_chrome_and_spares_the_users(tmp_path):
    """The bench stops every chrome.exe of the session by name, which closed the user's own browser."""
    chrome = tmp_path / "bin" / "chrome.exe"
    chrome.parent.mkdir()
    shutil.copy(os.path.join(os.environ["SystemRoot"], "System32", "cmd.exe"), chrome)
    workspace = tmp_path / "cdb-s04"

    def start(profile):
        return subprocess.Popen([str(chrome), "/d", "/c", f"ping -n 60 127.0.0.1 >nul & rem --user-data-dir={profile}"],
                                creationflags=subprocess.CREATE_NO_WINDOW)

    task, users = start(f"{workspace}/.runtime/browser"), start(tmp_path / "User Data")
    try:
        cdb = fake_cdb(workspace)
        session.spare_users_chrome(cdb)
        assert cdb.process_names(None) == {"rillwatch cases.exe"}
        cdb.CdbTask().clear_leftovers()
        assert task.wait(timeout=10) is not None and users.poll() is None
    finally:
        for proc in (task, users):
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True)
