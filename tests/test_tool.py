"""The installed script-file CLI; desktop execution requires approval."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import REPO, SCRIPTS


def cli(*args):
    """Call the real JSON CLI with a process-level time limit."""
    executable = Path(sys.executable).with_name("acu.exe" if sys.platform == "win32" else "acu")
    return subprocess.run([str(executable), *args], cwd=REPO,
                          capture_output=True, text=True, encoding="utf-8", timeout=20)


def test_distributed_package_contains_the_launcher_and_ordinary_inspection_scripts(tmp_path):
    import zipfile

    result = subprocess.run(["uv", "build", "--out-dir", str(tmp_path)], cwd=REPO,
                            capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    with zipfile.ZipFile(next(tmp_path.glob("*.whl"))) as package:
        required = {"acu/__main__.py", "acu/cli.py", "acu/run.py", "acu/prelude.ahk",
                    "acu/tree.ahk", "acu/screenshot.ahk", "acu/lib/UIA.ahk", "acu/lib/UIA-LICENSE.txt", "acu/SKILL.md"}
        names = set(package.namelist())
        assert required <= names, required - names
        assert "acu/capabilities.json" not in names
        assert "acu/mcp_server.py" not in names
        metadata = package.read(next(name for name in names if name.endswith(".dist-info/METADATA"))).decode("utf-8")
        assert "Requires-Dist:" not in metadata, "the CLI must have no runtime package dependencies"


@pytest.mark.parametrize("command", ["discover", "describe", "execute", "tree", "screenshot", "mcp"])
def test_only_script_run_is_advertised_and_removed_commands_are_rejected(command, acu_home):
    help_result = cli("--help")
    assert help_result.returncode == 0, help_result.stdout + help_result.stderr
    assert command not in help_result.stdout
    result = cli(command)
    assert result.returncode == 2, result.stdout + result.stderr
    assert "invalid choice" in json.loads(result.stdout)["error"]
    assert not (acu_home / "logs" / "runs.jsonl").exists()


@pytest.mark.parametrize("args, message", [
    (("run", ""), "non-empty"),
    (("run", "missing.ahk"), "not found"),
    (("run", "missing.ahk", "--timeout", "nan"), "finite"),
    (("run", "missing.ahk", "--params", "{}"), "unrecognized arguments"),
    (("run", "--code", "ExitApp"), "unrecognized arguments"),
])
def test_invalid_requests_fail_before_launching_ahk(args, message, acu_home):
    result = cli(*args)
    assert result.returncode == 2, result.stdout + result.stderr
    assert message in json.loads(result.stdout)["error"]
    assert not (acu_home / "logs" / "runs.jsonl").exists()


def test_run_help_exposes_only_the_script_timeout_and_argument_separator():
    result = cli("run", "--help")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "script" in result.stdout and "--timeout" in result.stdout
    assert "--code" not in result.stdout and "--engine" not in result.stdout


@pytest.mark.desktop
def test_cli_runs_an_existing_script_with_literal_arguments_and_preserves_the_file(tmp_path):
    script = tmp_path / "action.ahk"
    script.write_text('FileAppend "hello 你好|" A_Args[1] "|" A_Args[2] "`n", "*"', encoding="utf-8")
    original = script.read_bytes()
    result = cli("run", str(script), "--timeout", "5", "--", "alpha beta", 'quote"; literal')
    assert result.returncode == 0, result.stdout + result.stderr
    facts = json.loads(result.stdout)
    assert 'hello 你好|alpha beta|quote"; literal' in facts["output"]
    assert facts["outcome"] == "ok"
    assert script.read_bytes() == original
    entries = [json.loads(line) for line in Path(facts["artifacts"]["run_log"]).read_text(encoding="utf-8").splitlines()]
    assert entries[0]["script"] == str(script)
    assert "hello 你好" not in json.dumps(entries, ensure_ascii=False)


@pytest.mark.desktop
def test_cli_exposes_persistent_failure_output():
    result = cli("run", str(SCRIPTS / "runtime_error.ahk"))
    assert result.returncode == 1, result.stdout + result.stderr
    facts = json.loads(result.stdout)
    assert facts["exit_code"] == 1
    report = json.loads(Path(facts["artifacts"]["crash_report"]).read_text(encoding="utf-8"))
    assert report["output"] == facts["output"]
    assert Path(report["script"]).is_file()
