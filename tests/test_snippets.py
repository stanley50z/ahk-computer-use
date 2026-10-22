"""Snippet discovery through the CLI, without AutoHotkey or desktop input."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from acu import snippets
from test_tool import cli


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("ACU_SETTINGS_FILE", str(tmp_path / "global-settings.json"))


@pytest.mark.parametrize("scope", ["global", "project"])
def test_cli_respects_settings_from_working_folder(tmp_path, monkeypatch, scope):
    store = tmp_path / "snippets" / "Editor.exe"
    store.mkdir(parents=True)
    (store / "open.ahk").write_text("; does: Open\nExitApp\n", encoding="utf-8")
    monkeypatch.setenv("ACU_SNIPPETS_ROOT", str(store.parent))
    working = tmp_path / "project" / "nested"
    working.mkdir(parents=True)
    settings_file = (tmp_path / "global-settings.json" if scope == "global"
                     else working.parent / ".ahk-computer-use/settings.json")
    settings_file.parent.mkdir(parents=True, exist_ok=True)
    executable = Path(sys.executable).with_name("acu.exe")

    def listing():
        return subprocess.run([str(executable), "snippets", "list", "editor"], cwd=working,
                              capture_output=True, text=True, encoding="utf-8", timeout=20)

    settings_file.write_text('{"snippets": {"enabled": false}}', encoding="utf-8")
    result = listing()
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == "Snippets are off."
    settings_file.write_text('{"snippets": {"enabled": true}}', encoding="utf-8")
    assert "open.ahk" in listing().stdout
    settings_file.write_text('{', encoding="utf-8")
    result = listing()
    assert result.returncode == 2, result.stdout + result.stderr
    assert str(settings_file) in json.loads(result.stdout)["error"]


def test_cli_lists_snippets_and_marks_missing_headers(tmp_path, monkeypatch):
    monkeypatch.setenv("ACU_SNIPPETS_ROOT", str(tmp_path))
    folder = tmp_path / "Editor.exe"
    folder.mkdir()
    (folder / "open.ahk").write_text(
        '; DOES: Open a document\n; args: path\n; needs: editor\nMsgBox A_Args[1]\n',
        encoding="utf-8-sig",
    )
    (folder / "bare.ahk").write_text('ExitApp\n; does: Not a header\n', encoding="utf-8")
    (folder / "notes.txt").write_text("ignored", encoding="utf-8")
    result = cli("snippets", "list", "EDITOR")
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.splitlines() == [
        f"snippets {folder}", "bare.ahk | no header",
        "open.ahk | args: path | does: Open a document",
    ]


def test_keywords_rank_distinct_hits_search_header_and_name_only(tmp_path, monkeypatch):
    monkeypatch.setenv("ACU_SNIPPETS_ROOT", str(tmp_path))
    folder = tmp_path / "Editor.exe"
    folder.mkdir()
    sources = {
        "z-masks.ahk": "; does: Set MASKS\n; args: color\nExitApp\n",
        "b.ahk": "; needs: Masks masks masks\nExitApp\n",
        "a.ahk": "; check: MASKS ready\nExitApp\n",
        "c.ahk": "; tested: COLOR verified\nExitApp\n",
        "body.ahk": '; does: Nothing relevant\nMsgBox "mask color"\n',
        "mask-bare.ahk": "ExitApp\n",
    }
    for name, source in sources.items():
        (folder / name).write_text(source, encoding="utf-8")
    result = cli("snippets", "list", "editor.exe", "MASK", "color", "mask")
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.splitlines()[1:] == [
        "z-masks.ahk | args: color | does: Set MASKS",
        "a.ahk | args:  | does: ",
        "b.ahk | args:  | does: ",
        "c.ahk | args:  | does: ",
        "mask-bare.ahk | no header",
    ]
    assert cli("snippets", "list", "editor", "absent").stdout.splitlines() == [f"snippets {folder}"]


def test_app_description_matching_and_ambiguous_or_unknown_apps(tmp_path, monkeypatch):
    monkeypatch.setenv("ACU_SNIPPETS_ROOT", str(tmp_path))
    for name in ("Writer.exe", "Draw.exe", "Unresolved.exe"):
        (tmp_path / name).mkdir()
    descriptions = {"Writer.exe": "Acme Document Editor", "Draw.exe": "Acme Drawing Editor", "Unresolved.exe": ""}
    monkeypatch.setattr(snippets, "exe_description", descriptions.__getitem__)
    assert snippets.list_for_app("DOCUMENT", []) == f"snippets {tmp_path / 'Writer.exe'}"
    assert snippets.list_for_app("writer.EXE", []) == f"snippets {tmp_path / 'Writer.exe'}"
    ambiguous = snippets.list_for_app("editor", [])
    assert "choose one" in ambiguous
    assert "Draw.exe" in ambiguous and "Writer.exe" in ambiguous
    assert "Unresolved.exe" not in ambiguous
    unknown = snippets.list_for_app("absent", [])
    assert "No snippet folder matches" in unknown
    assert all(name in unknown for name in descriptions)
    assert snippets.list_for_app("unresolved", []) == f"snippets {tmp_path / 'Unresolved.exe'}"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows process/version metadata")
def test_running_executable_description_without_desktop():
    assert snippets.exe_description(Path(sys.executable).name) == "Python"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows version metadata")
def test_description_uses_app_paths_only_when_no_process_path(monkeypatch):
    calls = []
    monkeypatch.setattr(snippets, "running_executable", lambda name: Path(sys.executable))
    monkeypatch.setattr(snippets, "registered_executable", lambda name: calls.append(name) or Path(sys.executable))
    assert snippets.exe_description("registered.exe") == "Python"
    assert calls == []
    monkeypatch.setattr(snippets, "running_executable", lambda name: None)
    assert snippets.exe_description("registered.exe") == "Python"
    assert calls == ["registered.exe"]
    monkeypatch.setattr(snippets, "registered_executable", lambda name: None)
    assert snippets.exe_description("unresolved.exe") == ""


def test_missing_store_and_unknown_app_are_clear_and_read_only(tmp_path, monkeypatch):
    root = tmp_path / "missing"
    monkeypatch.setenv("ACU_SNIPPETS_ROOT", str(root))
    result = cli("snippets", "list", "editor")
    assert result.returncode == 0
    assert result.stdout.strip() == f"Snippets folder not found: {root}"
    assert not root.exists()
    root.mkdir()
    result = cli("snippets", "list", "editor")
    assert result.returncode == 0
    assert "Existing folders: (none)" in result.stdout
    (root / "Editor.exe").mkdir()
    result = cli("snippets", "list", "unknown")
    assert result.returncode == 0
    assert "Existing folders: Editor.exe" in result.stdout


@pytest.mark.skipif(sys.platform != "win32", reason="Windows session-local lease")
def test_cli_lists_while_desktop_lease_is_held_without_ahk(tmp_path, monkeypatch, acu_home):
    from acu.tool import _desktop_lease

    monkeypatch.setenv("ACU_SNIPPETS_ROOT", str(tmp_path))
    monkeypatch.setenv("ACU_AHK", str(tmp_path / "not-installed.exe"))
    folder = tmp_path / "Editor.exe"
    folder.mkdir()
    (folder / "hello.ahk").write_text('; does: Hello\nExitApp\n', encoding="utf-8")
    with _desktop_lease():
        result = cli("snippets", "list", "editor")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "hello.ahk | args:  | does: Hello" in result.stdout
    assert not (acu_home / "logs").exists()
    assert not (acu_home / "crashes").exists()


def test_snippets_root_is_independent_of_diagnostics_home(tmp_path, monkeypatch):
    monkeypatch.delenv("ACU_SNIPPETS_ROOT", raising=False)
    monkeypatch.setenv("ACU_HOME", str(tmp_path / "diagnostics"))
    assert snippets.snippets_root() == Path.home() / ".ahk-computer-use" / "snippets"
    monkeypatch.setenv("ACU_SNIPPETS_ROOT", str(tmp_path / "snippets"))
    assert snippets.snippets_root() == tmp_path / "snippets"
