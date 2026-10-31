"""Run-record attribution and privacy without starting AutoHotkey."""

import hashlib
import json

import pytest

from acu.run import Run, record


@pytest.mark.parametrize("output, app", [
    ("before\n[acu:snippets] notepad++.exe\nafter\n", "notepad++.exe"),
    ("[acu:snippets] Editor.exe\r\n[acu:snippets] EDITOR.EXE\r\n", "EDITOR.EXE"),
    ("[acu:snippets] ApplicationFrameHost.EXE\n", None),
    ("[acu:snippets] ApplicationFrameHost.exe\n[acu:snippets] Editor.exe\n", "Editor.exe"),
    ("[acu:snippets] Editor.exe\n[acu:snippets] Browser.exe\n", None),
    ("ordinary output\n", None),
    ("[acu:snippets] C:\\Apps\\Editor.exe\n", None),
])
def test_record_uses_marker_process_without_logging_script_text(tmp_path, acu_home, output, app):
    script = tmp_path / "action.ahk"
    source = b'; private script contents\nExitApp\n'
    script.write_bytes(source)
    run = Run(output, "error", 1, 7)

    report = record(script, run, 30)

    entry = json.loads((acu_home / "logs" / "runs.jsonl").read_text(encoding="utf-8"))
    assert entry["app"] == app
    assert entry["sha256"] == hashlib.sha256(source).hexdigest()
    assert entry["script"] == str(script)
    assert "private script contents" not in json.dumps(entry)
    assert "output" not in entry
    crash = json.loads(report.read_text(encoding="utf-8"))
    assert crash["app"] == app
    assert crash["output"] == output
