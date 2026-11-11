"""Reading a recording back: each step's actions, its target lines, and the tree changes since the same window's last capture."""

import json

from acu import recording
from acu.cli import main


def write_recording(folder, steps, trees):
    folder.mkdir(parents=True)
    for name, lines in trees.items():
        (folder / name).write_text(f'window=1 "t" app.exe\n' + "".join(line + "\n" for line in lines) + "elements=0\ntruncated=no\n", encoding="utf-8")
    (folder / "steps.jsonl").write_text("".join(json.dumps(step) + "\n" for step in steps), encoding="utf-8")


EDITOR = {"hwnd": 1, "title": "Editor", "exe": "app.exe"}
DIALOG = {"hwnd": 2, "title": "Save As", "exe": "app.exe"}
SHOT = {"file": "000.png", "source": [0, 0, 1920, 1080], "scale": 1.5}


def test_timeline_diffs_each_window_against_its_own_last_capture(tmp_path):
    field = '2 Edit "Name" @10,10 100x20 value'
    write_recording(tmp_path / "r", [
        {"step": 0, "ms": 0, "actions": [], "window": EDITOR, "tree": "000-tree.txt", "screenshot": SHOT},
        {"step": 1, "ms": 2000, "window": DIALOG, "tree": "001-tree.txt", "screenshot": SHOT, "actions": [
            {"kind": "hotkey", "keys": "^s", "count": 1, "ms": 1500, "target": {"line": '1 Document "Text"', "window": EDITOR}}]},
        {"step": 2, "ms": 5000, "window": DIALOG, "tree": "002-tree.txt", "screenshot": SHOT, "input_during_capture": 2, "actions": [
            {"kind": "click", "button": "left", "count": 2, "ms": 3000, "x": 60, "y": 20, "target": {"line": field, "window": DIALOG}},
            {"kind": "type", "text": "report", "backspaces": 1, "ms": 3500, "target": {"line": field, "window": DIALOG}}]},
        {"step": 3, "ms": 6000, "final": True, "window": EDITOR, "tree": "003-tree.txt", "screenshot": SHOT, "actions": []},
    ], {
        "000-tree.txt": ['1 Document "Text"'],
        "001-tree.txt": ['1 Text "File name"', field],
        "002-tree.txt": ['1 Text "File name"', '2 Edit "Name" value="report" @10,10 100x20 value'],
        "003-tree.txt": ['1 Document "Text"', '2 Text "Saved"'],
    })

    timeline = recording.summarize(str(tmp_path / "r"))

    assert "4 steps." in timeline
    assert 'hotkey ^s, focus 1 Document "Text" in "Editor" app.exe' in timeline
    assert "first capture of this window: 2 elements" in timeline
    assert f'left double-click at 60,20 on {field} in "Save As" app.exe' in timeline
    assert f'type "report" after erasing 1 characters into {field}' in timeline
    assert f"- {field}\n" in timeline and '+ 2 Edit "Name" value="report"' in timeline
    assert "input arrived during this capture" in timeline
    final = timeline.split("Step 3", 1)[1]
    assert "tree changes since step 0" in final and '+ 2 Text "Saved"' in final, "the editor diffs against step 0, not the dialog"


def test_unchanged_paths_shift_without_counting_as_changes():
    before = ['1 Button "A"', '2 Button "B"']
    after = ['1 Text "New"', '2 Button "A"', '3 Button "B"']

    assert recording.tree_changes(before, after) == ['+ 1 Text "New"']


def test_long_changes_are_counted_and_point_to_the_tree_files(tmp_path):
    lines = [f'{i} Text "row {i}"' for i in range(1, 60)]
    write_recording(tmp_path / "r", [
        {"step": 0, "ms": 0, "actions": [], "window": EDITOR, "tree": "000-tree.txt", "screenshot": SHOT},
        {"step": 1, "ms": 900, "window": EDITOR, "tree": "001-tree.txt", "screenshot": SHOT, "actions": [
            {"kind": "scroll", "axis": "vertical", "delta": -360, "ms": 500, "x": 5, "y": 5, "target": {"line": '1 List "rows"', "window": EDITOR}}]},
    ], {"000-tree.txt": [], "001-tree.txt": lines})

    timeline = recording.summarize(str(tmp_path / "r"))

    assert "scroll vertical -3 notches at 5,5" in timeline
    assert f"... {59 - recording.MAX_CHANGES} more; compare 000-tree.txt with 001-tree.txt" in timeline
    assert "no final step" in timeline


def test_masked_typing_shows_only_its_length(tmp_path):
    write_recording(tmp_path / "r", [
        {"step": 0, "ms": 0, "actions": [], "window": EDITOR, "screenshot": SHOT, "tree_error": "gone"},
        {"step": 1, "ms": 900, "window": EDITOR, "screenshot": SHOT, "tree_error": "gone", "final": True, "actions": [
            {"kind": "type", "masked": True, "length": 8, "backspaces": 0, "ms": 500, "target": {"line": '1 Edit "Password"', "window": EDITOR}}]},
    ], {})

    timeline = recording.summarize(str(tmp_path / "r"))

    assert 'type 8 masked characters into 1 Edit "Password"' in timeline
    assert "tree failed: gone" in timeline


def test_cli_reads_the_newest_recording_by_default(acu_home, capsys):
    root = acu_home / "recordings"
    for name in ("20261101-090000", "20261102-090000"):
        write_recording(root / name, [{"step": 0, "ms": 0, "actions": [], "window": EDITOR, "tree": "000-tree.txt", "screenshot": SHOT}],
                        {"000-tree.txt": []})

    assert main(["recording"]) == 0

    assert "20261102-090000" in capsys.readouterr().out


def test_cli_reports_a_folder_that_is_not_a_recording(tmp_path, capsys):
    assert main(["recording", str(tmp_path)]) == 2

    assert "not a recording" in json.loads(capsys.readouterr().out)["error"]
