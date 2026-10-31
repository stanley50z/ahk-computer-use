"""Shared launcher behavior through both command entrypoints."""

import json
from contextlib import contextmanager

import pytest

from acu import cli, run as launcher, tool
from fake_process import FakeProcessAdapter


def test_both_entrypoints_resolve_bundled_scripts_and_forward_literal_arguments(tmp_path, monkeypatch, capsys, process_adapter):
    """The low-level command must use the same resolution and argument split as acu run."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(launcher.time, "monotonic", lambda: 0)
    adapters = [FakeProcessAdapter("hello"), FakeProcessAdapter("hello")]
    pending = iter(adapters)
    monkeypatch.setattr(launcher, "Win32ProcessAdapter", lambda: next(pending))
    arguments = ["tree.ahk", "--timeout", "5", "--", "alpha beta", "--timeout", "--"]
    assert cli.main(["run", *arguments]) == 0
    response = json.loads(capsys.readouterr().out)
    assert launcher.main(arguments) == 0
    output = capsys.readouterr().out
    assert output == "hello\n[acu] ok 0ms\n"
    assert response["trailer"] == output.splitlines()[-1]
    for adapter in adapters:
        assert adapter.validation_command[5:] == [str(launcher.HERE / "tree.ahk"), "alpha beta", "--timeout", "--"]
        assert adapter.script_arguments[3] == str(launcher.HERE / "tree.ahk")
        assert adapter.script_arguments[6:] == ["alpha beta", "--timeout", "--"]
    rows = (launcher.acu_home() / "logs" / "runs.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(rows) == 2


@pytest.mark.parametrize("case, code, trailer", [
    ("ok", 0, "[acu] ok 0ms"),
    ("exit", 9, "[acu] exit 9 0ms"),
    ("exit-130", 130, "[acu] exit 130 0ms"),
    ("validation-error", 2, "[acu] exit 2 0ms"),
    ("validation-timeout", 124, "[acu] timeout 5s: validation"),
    ("closed", 124, "[acu] timeout 5s: closed on request"),
    ("killed", 124, "[acu] timeout 5s: killed"),
    ("interrupt", 130, "[acu] interrupted 0ms"),
    ("validation-interrupt", 130, "[acu] interrupted during validation 0ms"),
])
def test_entrypoints_preserve_exact_trailers(tmp_path, monkeypatch, capsys, process_adapter, case, code, trailer):
    script = tmp_path / "action.ahk"
    script.write_text("ExitApp\n", encoding="utf-8")
    monkeypatch.setattr(launcher.time, "monotonic", lambda: 0)

    def create():
        adapter = FakeProcessAdapter("captured\n")
        if case == "exit":
            adapter.script.code = 9
        elif case == "exit-130":
            adapter.script.code = 130
        elif case == "validation-error":
            adapter.validator.returncode = 2
        elif case == "validation-timeout":
            adapter.validator.timeout = True
        elif case in ("closed", "killed"):
            adapter.script.finish = False
            adapter.script.ignore_close = case == "killed"
        elif case == "interrupt":
            adapter.script.interrupt_wait = True
        elif case == "validation-interrupt":
            adapter.interrupt_creation = "validation"
        return adapter

    monkeypatch.setattr(launcher, "Win32ProcessAdapter", create)
    arguments = [str(script), "--timeout", "5"]
    assert cli.main(["run", *arguments]) == code
    response = json.loads(capsys.readouterr().out)
    assert launcher.main(arguments) == code
    output = capsys.readouterr().out
    assert output.splitlines()[-1] == response["trailer"] == trailer


def test_run_derives_trailer_from_facts():
    result = launcher.Run("", "ok", 0, 17)
    assert result.trailer == "[acu] ok 17ms"


def test_entrypoints_keep_explicit_lease_timeout_and_marker_differences(tmp_path, monkeypatch, capsys, process_adapter):
    script = tmp_path / "action.ahk"
    script.write_text("ExitApp\n", encoding="utf-8")
    folder = tmp_path / "snippets" / "Editor.exe"
    folder.mkdir(parents=True)
    (folder / "action.ahk").write_text("; does: Example\nExitApp\n", encoding="utf-8")
    monkeypatch.setenv("ACU_SNIPPETS_ROOT", str(folder.parent))
    monkeypatch.setenv("ACU_SETTINGS_FILE", str(tmp_path / "settings.json"))
    monkeypatch.chdir(tmp_path)
    adapters = []

    def create():
        adapter = FakeProcessAdapter("[acu:snippets] Editor.exe\n")
        adapters.append(adapter)
        return adapter

    monkeypatch.setattr(launcher, "Win32ProcessAdapter", create)
    assert cli.main(["run", str(script)]) == 0
    response = json.loads(capsys.readouterr().out)
    assert response["output"] == f"snippets {folder}\naction.ahk | args:  | does: Example\n"

    @contextmanager
    def busy():
        raise ValueError("busy: test lease held")
        yield

    monkeypatch.setattr(tool, "desktop_lease", busy)
    assert cli.main(["run", str(script)]) == 2
    assert "busy" in json.loads(capsys.readouterr().out)["error"]
    assert cli.main(["run", str(script), "--timeout", "301"]) == 2
    assert "300" in json.loads(capsys.readouterr().out)["error"]
    assert launcher.main([str(script), "--timeout", "301"]) == 0
    assert capsys.readouterr().out.startswith("[acu:snippets] Editor.exe\n[acu] ok ")
    assert len(adapters) == 2, "a rejected CLI request created a process"
    rows = [json.loads(line) for line in (launcher.acu_home() / "logs/runs.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [row["app"] for row in rows] == ["Editor.exe", "Editor.exe"]
    assert [row["timeout_s"] for row in rows] == [30, 301]


def test_logging_failure_does_not_replace_either_entrypoints_exit_code(tmp_path, monkeypatch, capsys, process_adapter):
    script = tmp_path / "action.ahk"
    script.write_text("ExitApp\n", encoding="utf-8")
    home = launcher.acu_home()
    home.mkdir()
    (home / "logs").write_text("obstructed", encoding="utf-8")

    def create():
        adapter = FakeProcessAdapter("error output\n")
        adapter.script.code = 9
        return adapter

    monkeypatch.setattr(launcher, "Win32ProcessAdapter", create)
    assert cli.main(["run", str(script)]) == 9
    response = json.loads(capsys.readouterr().out)
    assert response["log_error"] and response["output"] == "error output\n"
    assert launcher.main([str(script)]) == 9
    captured = capsys.readouterr()
    assert captured.out.startswith("error output\n[acu] exit 9 ")
    assert captured.err.startswith("[acu] log failed: ")
