"""The tray recorder on a real desktop: clicks and typing become steps whose targets match the captured trees."""

import json
import os
import subprocess
from types import SimpleNamespace

import pytest

from conftest import REPO, run_launcher, user32, wait_until
from acu.recording import summarize
from acu.run import plain_ahk_exe, request_close

pytestmark = pytest.mark.desktop

RECORDER = REPO / "acu" / "recorder.ahk"


def read_steps(folder):
    path = folder / "steps.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] if path.is_file() else []


@pytest.fixture
def start_recorder(tmp_path):
    """Factory for a recorder that starts recording at once and has captured step 0; killed if the test leaves it running."""
    processes = []

    def start():
        home = tmp_path / "home"
        processes.append(process := subprocess.Popen([str(plain_ahk_exe()), str(RECORDER), f"--acu-home={home}", "--record"]))
        root = home / "recordings"
        wait_until(lambda: any(read_steps(folder) for folder in root.glob("*")), 15, "the recorder never captured step 0")
        return SimpleNamespace(folder=next(root.glob("*")), process=process)

    yield start
    for process in processes:
        if process.poll() is None:
            process.kill()
        process.wait()


def test_recorder_captures_each_action_with_its_target_and_the_tree_after_it(open_window, start_recorder, tmp_path):
    title = f"ACU recorder window {os.getpid()}"
    open_window(title, 200, 200, script="uia_window.ahk", ACU_TEST_COUNT_FILE=str(tmp_path / "hits.txt"),
                ACU_TEST_EDIT_FILE=str(tmp_path / "edits.txt"))
    wait_until(lambda: user32.GetForegroundWindow() == user32.FindWindowW(None, title), 5, "the stand-in window never took the foreground")
    recorder = start_recorder()
    script = tmp_path / "act.ahk"
    script.write_text(f'''
hwnd := WinExist("{title}")
WinActivate hwnd
WinWaitActive hwnd, , 3
root := UIA.ElementFromHandle(hwnd)
center(element) => (r := element.Location, [r.x + r.w // 2, r.y + r.h // 2])
hit := center(root.FindElement({{Type: "Button", Name: "hit"}}))
Click hit[1], hit[2]
Sleep 1500
city := center(root.FindElement({{Type: "Edit", Name: "City"}}))
Click city[1], city[2]
Send "^a"
Send "xyz"
''', encoding="utf-8")
    result = run_launcher(script, "--timeout", "30")
    assert result.returncode == 0, result.stdout
    wait_until(lambda: any(a["kind"] == "type" for s in read_steps(recorder.folder) for a in s["actions"]), 10,
               "the typing step was never captured")
    request_close(recorder.process.pid)
    recorder.process.wait(15)

    steps = read_steps(recorder.folder)
    assert steps[0]["actions"] == [] and steps[-1].get("final") is True
    assert [s["step"] for s in steps] == list(range(len(steps)))
    actions = [a for s in steps for a in s["actions"]]
    clicks = [a for a in actions if a["kind"] == "click"]
    assert len(clicks) == 2 and all(a["button"] == "left" and a["count"] == 1 for a in clicks)
    path, rest = clicks[0]["target"]["line"].split(" ", 1)
    assert rest.startswith('Button "hit"')
    tree0 = (recorder.folder / steps[0]["tree"]).read_text(encoding="utf-8")
    assert f'\n{path} Button "hit"' in tree0, "a click's target path must find the same element in the captured tree"
    assert any(a["kind"] == "hotkey" and a["keys"] == "^a" for a in actions)
    typed = next(a for a in actions if a["kind"] == "type")
    assert typed["text"] == "xyz" and ' Edit "City"' in typed["target"]["line"]
    typing_step = next(s for s in steps if typed in s["actions"])
    after = (recorder.folder / typing_step["tree"]).read_text(encoding="utf-8")
    city_path = typed["target"]["line"].split(" ", 1)[0]
    assert f'\n{city_path} Edit "City" id="5" value="xyz"' in after
    assert (recorder.folder / typing_step["screenshot"]["file"]).is_file()

    timeline = summarize(str(recorder.folder))
    assert 'type "xyz" into' in timeline and '+ 3 Edit "City" id="5" value="xyz"' in timeline
