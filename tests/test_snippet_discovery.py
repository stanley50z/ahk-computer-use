"""Automatic discovery through the script-run boundary and real Calculator windows."""

import json
import subprocess
import sys
from contextlib import nullcontext
from pathlib import Path

import pytest

from acu import tool
from acu.run import Run


@pytest.fixture
def store(tmp_path, monkeypatch):
    """Isolate both discovery inputs from the user's store and settings."""
    root = tmp_path / "snippets"
    folder = root / "CalculatorApp.exe"
    folder.mkdir(parents=True)
    for index in range(305):
        (folder / f"action-{index:03}.ahk").write_text(
            f"; args: value\n; does: Temporary action {index}\nExitApp\n", encoding="utf-8")
    monkeypatch.setenv("ACU_SNIPPETS_ROOT", str(root))
    monkeypatch.setenv("ACU_SETTINGS_FILE", str(tmp_path / "global.json"))
    monkeypatch.chdir(tmp_path)
    return folder


def test_run_expands_full_list_and_preserves_other_output(store, tmp_path, monkeypatch):
    script = tmp_path / "action.ahk"
    script.touch()
    monkeypatch.setattr(tool, "_desktop_lease", nullcontext)
    monkeypatch.setattr(tool.launcher, "run_script", lambda *args: Run(
        "before\n[acu:snippets] calculatorapp.exe\nafter\n", "ok", 0, 1, "[acu] ok 1ms"))
    output = tool.run(str(script))["output"]
    assert output.startswith(f"before\nsnippets {store}\n")
    assert "action-000.ahk | args: value | does: Temporary action 0\n" in output
    assert output.endswith("action-304.ahk | args: value | does: Temporary action 304\nafter\n")


@pytest.mark.parametrize("case", ["missing-store", "unknown-app", "empty-folder", "disabled"])
def test_discovery_without_snippets_is_quiet(case, store, tmp_path, monkeypatch):
    script = tmp_path / "action.ahk"
    script.touch()
    monkeypatch.setattr(tool, "_desktop_lease", nullcontext)
    monkeypatch.setattr(tool.launcher, "run_script", lambda *args: Run(
        "before\n[acu:snippets] CalculatorApp.exe\nafter\n", "ok", 0, 1, "[acu] ok 1ms"))
    if case == "missing-store":
        monkeypatch.setenv("ACU_SNIPPETS_ROOT", str(tmp_path / "absent"))
    elif case == "unknown-app":
        store.rename(store.with_name("Other.exe"))
    elif case == "empty-folder":
        for path in store.iterdir():
            path.unlink()
    else:
        settings = tmp_path / ".ahk-computer-use" / "settings.json"
        settings.parent.mkdir()
        settings.write_text('{"snippets":{"enabled":false}}', encoding="utf-8")
        # Disabled discovery must not attempt to decode this file.
        (store / "invalid.ahk").write_bytes(b"\xff")
        child = tmp_path / "nested"
        child.mkdir()
        monkeypatch.chdir(child)
    output = tool.run(str(script))["output"]
    expected = f"before\nsnippets {store}\nafter\n" if case == "empty-folder" else "before\nafter\n"
    assert output == expected


# Run the installed CLI from the project's working folder, not the script's folder.
def call(cwd, *args):
    executable = Path(sys.executable).with_name("acu.exe")
    result = subprocess.run([str(executable), *args], cwd=cwd, capture_output=True,
                            text=True, encoding="utf-8", timeout=35)
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)["output"]


@pytest.mark.desktop
def test_calculator_launch_direct_tree_and_bundled_filters(store, tmp_path):
    launch = tmp_path / "launch.ahk"
    handle = tmp_path / "owned.txt"
    launch.write_text('window := AcuLaunch("calc.exe", "Calculator")\n'
                      'FileAppend window.hwnd, A_Args[1]\n', encoding="utf-8")
    try:
        output = call(tmp_path, "run", str(launch), "--", str(handle))
        assert f"snippets {store}\n" in output
        assert "action-304.ahk | args: value | does: Temporary action 304" in output
        target = "ahk_id " + handle.read_text(encoding="utf-8")
        direct = tmp_path / "direct.ahk"
        direct.write_text('FileAppend AcuTree(A_Args[1], {max: 1}), "*"', encoding="utf-8")
        for script, args in [(str(direct), []), ("tree.ahk", ["--max", "1"])]:
            output = call(tmp_path, "run", script, "--", target, *args)
            assert output.endswith("action-304.ahk | args: value | does: Temporary action 304\n")
            assert "ApplicationFrameHost.exe\n" not in output.split("snippets ")[-1]
        for args in [("--find", "num"), ("--type", "Button")]:
            output = call(tmp_path, "run", "tree.ahk", "--", target, *args)
            assert "snippets" not in output and "action-" not in output
        settings = tmp_path / ".ahk-computer-use" / "settings.json"
        settings.parent.mkdir()
        settings.write_text('{"snippets":{"enabled":false}}', encoding="utf-8")
        output = call(tmp_path, "run", str(direct), "--", target)
        assert "snippets" not in output and "action-" not in output
    finally:
        if handle.exists():
            cleanup = tmp_path / "close.ahk"
            cleanup.write_text('target := "ahk_id " A_Args[1]\n'
                               'if WinExist(target) {\n WinClose target\n'
                               ' if !WinWaitClose(target, , 5)\n  throw Error("Calculator did not close")\n}', encoding="utf-8")
            call(tmp_path, "run", str(cleanup), "--", handle.read_text(encoding="utf-8"))
