import base64
import json
import sys

from bench.cua_driver_bench import acu_mcp, run, score

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
    ])
    assert score.ahk_hits(script) == [
        'Run "cmd.exe"', 'text := FileRead("C:\\bench\\state.json")', 'FileAppend "x", "C:\\out.txt"',
        'shell := ComObject("WScript.Shell")',
    ]


def test_file_append_counts_only_with_a_file_target():
    """Agents wrote FileAppend with no Filename (no file is written) and with commas inside calls and strings."""
    printing = ['FileAppend AcuTree("ahk_id 1")', 'FileAppend r.FindElement({Type:"ComboBox"}).Value "`n"',
                'FileAppend(x, "*")', 'FileAppend Foo(a, b), "*"', 'FileAppend "a, b", "**"']
    writing = ['FileAppend(x, "C:\\a.txt")', 'FileAppend x, A_Desktop "\\o.txt"']
    assert [line for line in printing if score.ahk_hits(line)] == []
    assert [line for line in writing if score.ahk_hits(line)] == writing


def test_schedule_runs_each_benchlab_task_in_its_manifest_conditions(tmp_path):
    manifest = tmp_path / "cdb" / "taskpack" / "v2-taskset.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({"tasks": [
        {"id": "CDB-G02", "conditions": ["foreground", "background"], "apps": ["Mail", "Calc"], "os": ["windows"]},
        {"id": "MB-10", "conditions": ["foreground"], "apps": ["BenchLab"], "os": ["windows"]},
        {"id": "IR-02", "conditions": ["foreground", "background"], "apps": ["BenchLab"], "os": ["windows"]},
    ]}))
    bench = tmp_path / "cdb" / "automated-eval" / "macos_bench"
    plan = run.schedule(bench, None, ["foreground", "background"], 2)
    assert plan == [("MB-10", "foreground", 0), ("IR-02", "foreground", 0), ("IR-02", "background", 0),
                    ("MB-10", "foreground", 1), ("IR-02", "foreground", 1), ("IR-02", "background", 1)]
