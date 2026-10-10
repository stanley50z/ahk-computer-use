"""The public ACU CLI and MCP interfaces, without desktop execution unless marked."""

import json
import subprocess
import sys
from datetime import timedelta
from pathlib import Path

import pytest

from conftest import REPO


def cli(*args, stdin=None):
    """Call the real JSON CLI; every invocation has a process-level time limit."""
    return subprocess.run(
        [sys.executable, "-m", "acu", *args], cwd=REPO, input=stdin,
        capture_output=True, text=True, encoding="utf-8", timeout=20,
    )


def test_distributed_package_contains_scripts_library_and_discoverable_guides(tmp_path):
    import zipfile

    result = subprocess.run(["uv", "build", "--out-dir", str(tmp_path)], cwd=REPO,
                            capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    wheel = next(tmp_path.glob("*.whl"))
    with zipfile.ZipFile(wheel) as package:
        required = {"acu/__main__.py", "acu/cli.py", "acu/run.py", "acu/prelude.ahk", "acu/mcp_server.py",
                    "acu/windows.ahk", "acu/tree.ahk", "acu/screenshot.ahk", "acu/lib/UIA.ahk",
                    "acu/lib/UIA-LICENSE.txt", "acu/SKILL.md", "acu/capabilities.json", "acu/guides/scripting.md"}
        assert required <= set(package.namelist()), required - set(package.namelist())


def test_agent_discovers_scripts_and_instructions_then_loads_only_selected_guidance():
    result = cli("discover", "window")
    assert result.returncode == 0, result.stdout + result.stderr
    summaries = json.loads(result.stdout)["capabilities"]
    assert "windows.list" in {item["id"] for item in summaries}
    assert all("instructions" not in item for item in summaries)

    result = cli("describe", "windows.list")
    assert result.returncode == 0, result.stdout + result.stderr
    capability = json.loads(result.stdout)
    assert capability["runnable"] is True
    assert capability["engine"] == "ahk"
    assert "ahk_id" in capability["instructions"]
    assert capability["parameters"]["type"] == "object"

    result = cli("describe", "ahk.action-chain")
    assert result.returncode == 0, result.stdout + result.stderr
    capability = json.loads(result.stdout)
    assert capability["runnable"] is False
    assert "WinWaitActive" in capability["instructions"]


@pytest.mark.parametrize("args, message", [
    (("describe", "../run.py"), "unknown capability"),
    (("run", "ahk.action-chain"), "instructions only"),
    (("run", "windows.list", "--params", '{"surprise": true}'), "Additional properties"),
    (("execute", "--engine", "python", "--code", "print(1)"), "unsupported engine"),
    (("execute", "--code", ""), "non-empty"),
    (("execute", "--code", "ExitApp", "--timeout", "nan"), "finite"),
    (("execute", "--file", "missing.ahk"), "not found"),
    (("tree", ""), "non-empty"),
    (("screenshot", "--mode", "custom", "--rect", "0", "0", "0", "1"), "positive"),
])
def test_invalid_requests_fail_explicitly_without_execution(args, message, acu_home):
    result = cli(*args)
    assert result.returncode == 2, result.stdout + result.stderr
    assert message in json.loads(result.stdout)["error"]
    assert not (acu_home / "logs" / "runs.jsonl").exists()


def test_mcp_exposes_script_first_tools_and_discovery_over_project_config(acu_home):
    import anyio
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    async def scenario():
        config = json.loads((REPO / ".pi" / "mcp.json").read_text(encoding="utf-8"))["mcpServers"]["acu"]
        server = StdioServerParameters(command=config["command"], args=config["args"], cwd=str(REPO),
                                       env={"ACU_HOME": str(acu_home)})
        async with stdio_client(server) as (reader, writer):
            async with ClientSession(reader, writer, read_timeout_seconds=timedelta(seconds=15)) as session:
                initialized = await session.initialize()
                assert "action chain" in initialized.instructions
                tools = {item.name: item for item in (await session.list_tools()).tools}
                assert set(tools) == {"discover", "describe", "execute", "run", "tree", "screenshot"}
                assert tools["discover"].annotations.readOnlyHint is True
                assert tools["execute"].annotations.readOnlyHint is False
                assert tools["execute"].annotations.destructiveHint is True
                assert tools["screenshot"].annotations.readOnlyHint is False
                assert tools["screenshot"].annotations.destructiveHint is True
                assert "code" in tools["execute"].inputSchema["properties"]
                result = await session.call_tool("describe", {"id": "ahk.action-chain"})
                assert not result.isError
                assert result.structuredContent["runnable"] is False
                assert "WinWaitActive" in result.structuredContent["instructions"]
                result = await session.call_tool("run", {"id": "ahk.action-chain"})
                assert result.isError
                assert "instructions only" in result.structuredContent["error"]
                result = await session.call_tool("execute", {"engine": "python", "code": "print(1)"})
                assert result.isError
                assert "unsupported engine" in result.structuredContent["error"]

    anyio.run(scenario)


@pytest.mark.parametrize("blocked_root", [True, False])
def test_cli_reports_infrastructure_failure_even_when_crash_persistence_is_impossible(acu_home, tmp_path, monkeypatch, blocked_root):
    if blocked_root:
        occupied = tmp_path / "not-a-directory"
        occupied.write_text("occupied", encoding="utf-8")
        monkeypatch.setenv("ACU_HOME", str(occupied))
    else:
        acu_home.mkdir()
        (acu_home / "tmp").write_text("occupied", encoding="utf-8")
    result = cli("execute", "--code", 'FileAppend "never executed", "*"')
    assert result.returncode == 1, result.stdout + result.stderr
    facts = json.loads(result.stdout)
    assert facts["error"]
    if blocked_root:
        assert "could not persist crash report" in facts["diagnostic_error"]
    else:
        report = json.loads(Path(facts["artifacts"]["crash_report"]).read_text(encoding="utf-8"))
        assert "FileExistsError" in report["traceback"]
        assert "never executed" not in json.dumps(report)
    assert "Traceback" not in result.stderr


@pytest.mark.desktop
def test_cli_executes_inline_action_chain_with_arguments_and_removes_only_owned_scripts(acu_home, tmp_path):
    code = 'FileAppend "hello 你好|" A_Args[1] "|" A_Args[2] "`n", "*"'
    result = cli("execute", "--file", "-", "--args", "alpha beta", 'quote"; literal', stdin=code)
    assert result.returncode == 0, result.stdout + result.stderr
    facts = json.loads(result.stdout)
    assert facts["outcome"] == "ok"
    assert 'hello 你好|alpha beta|quote"; literal' in facts["output"]
    entries = [json.loads(line) for line in Path(facts["artifacts"]["run_log"]).read_text(encoding="utf-8").splitlines()]
    assert len(entries) == 1
    assert not Path(entries[0]["script"]).exists()
    assert not list((acu_home / "tmp").iterdir())
    assert "hello 你好" not in json.dumps(entries, ensure_ascii=False)

    script = tmp_path / "existing.ahk"
    script.write_text('FileAppend "existing script`n", "*"', encoding="utf-8")
    result = cli("execute", "--file", str(script))
    assert result.returncode == 0, result.stdout + result.stderr
    assert script.exists(), "ACU must preserve caller-owned scripts"


@pytest.mark.desktop
def test_cleanup_failure_preserves_execution_facts_and_reports_leftover_script(monkeypatch):
    import shutil
    from acu.tool import execute

    original = shutil.rmtree

    # A filesystem failure stands in for an antivirus/file-sharing lock; the script still runs for real.
    def locked(path, *args, **kwargs):
        raise PermissionError("script file is locked")

    with monkeypatch.context() as patch:
        patch.setattr(shutil, "rmtree", locked)
        result = execute(code='FileAppend "completed once", "*"')
    leftover = Path(result["artifacts"]["leftover_script"])
    try:
        assert result["outcome"] == "ok"
        assert result["exit_code"] == 0
        assert result["output"] == "completed once"
        assert "locked" in result["cleanup_error"]
        assert leftover.is_file()
    finally:
        original(leftover.parent)


@pytest.mark.desktop
@pytest.mark.parametrize("code, expected, text", [
    ('throw Error("ACU tool regression")', 1, "ACU tool regression"),
    ('this := (', 2, "==>"),
    ('Sleep 5000', 124, "timeout"),
])
def test_cli_reports_failure_with_persistent_crash_output_and_cleans_inline_script(code, expected, text, acu_home):
    result = cli("execute", "--code", code, "--timeout", "0.3")
    assert result.returncode == expected, result.stdout + result.stderr
    facts = json.loads(result.stdout)
    assert text in facts["output"] + facts["trailer"]
    report = json.loads(Path(facts["artifacts"]["crash_report"]).read_text(encoding="utf-8"))
    assert report["exit_code"] == expected
    assert report["output"] == facts["output"]
    assert not Path(report["script"]).exists()
    assert not list((acu_home / "tmp").iterdir())


@pytest.mark.desktop
def test_cli_rejects_overlapping_execution_and_releases_desktop_after_completion(tmp_path):
    import time

    ready = tmp_path / "ready.txt"
    process = subprocess.Popen(
        [sys.executable, "-m", "acu", "execute", "--code", 'FileAppend "ready", A_Args[1]\nSleep 2000',
         "--timeout", "5", "--args", str(ready)], cwd=REPO,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8",
    )
    try:
        deadline = time.monotonic() + 5
        while not ready.exists() and process.poll() is None and time.monotonic() < deadline:
            time.sleep(0.02)
        assert ready.exists(), "first script never reached its ready observation"
        result = cli("execute", "--code", 'FileAppend "second", "*"')
        assert result.returncode == 2, result.stdout + result.stderr
        assert "busy" in json.loads(result.stdout)["error"]
        output, error = process.communicate(timeout=10)
        assert process.returncode == 0, output + error
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=10)
    result = cli("execute", "--code", 'FileAppend "after", "*"')
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.desktop
def test_mcp_runs_maintained_inspection_and_returns_a_real_image(open_window, acu_home):
    import anyio
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    hwnd = open_window("ACU tool inspection fixture", 100, 100, script="uia_window.ahk")
    target = f"ahk_id {hwnd}"

    async def scenario():
        server = StdioServerParameters(command=sys.executable, args=["-m", "acu", "mcp"],
                                       cwd=str(REPO), env={"ACU_HOME": str(acu_home)})
        async with stdio_client(server) as (reader, writer):
            async with ClientSession(reader, writer, read_timeout_seconds=timedelta(seconds=15)) as session:
                await session.initialize()
                executed = await session.call_tool("execute", {"code": 'FileAppend "MCP action chain 你好`n", "*"'})
                assert not executed.isError
                assert "MCP action chain 你好" in executed.structuredContent["output"]
                failed = await session.call_tool("execute", {"code": 'throw Error("MCP failure")'})
                assert failed.isError
                assert failed.structuredContent["exit_code"] == 1
                assert Path(failed.structuredContent["artifacts"]["crash_report"]).is_file()
                windows = await session.call_tool("run", {"id": "windows.list"})
                assert not windows.isError
                assert "ACU tool inspection fixture" in windows.structuredContent["output"]
                tree = await session.call_tool("run", {"id": "uia.tree", "parameters": {"target": target}})
                assert not tree.isError
                assert "Button" in tree.structuredContent["output"]
                image = await session.call_tool("run", {"id": "screen.capture", "parameters": {"mode": "app", "target": target}})
                assert not image.isError
                assert any(block.type == "image" and block.mimeType == "image/png" for block in image.content)
                assert Path(image.structuredContent["screenshot"]["saved"]).is_file()
                assert "source" in image.structuredContent["screenshot"]
                assert not list((acu_home / "tmp").iterdir())

    anyio.run(scenario)
