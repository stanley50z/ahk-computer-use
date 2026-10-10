"""Finding controls by name: the tree script, and UI Automation available to every script through the prelude."""

import os
import re
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from conftest import REPO, reported, run_launcher, visible_frame, wait_until

pytestmark = pytest.mark.desktop

TREE = REPO / "acu" / "tree.ahk"
# A name, id, or value as the dump prints it: AutoHotkey string contents between double quotes.
QUOTED = r'"(?:[^"`]|`.)*"'
LINE = re.compile(
    rf"^(?P<path>\d+(?:,\d+)*) (?P<type>\w+)(?: (?P<name>{QUOTED}))?(?: id=(?P<id>{QUOTED}))?(?: value=(?P<value>{QUOTED}))?"
    r" @(?P<x>-?\d+),(?P<y>-?\d+) (?P<w>\d+)x(?P<h>\d+)(?P<flags>(?: \w+)*)$"
)


def elements(stdout):
    """Every element line of a tree dump as a dict. Quoted fields keep their escaping; flags become a set."""
    found = []
    for line in stdout.splitlines():
        if match := LINE.match(line):
            entry = match.groupdict()
            for key in ("name", "id", "value"):
                if entry[key] is not None:
                    entry[key] = entry[key][1:-1]
            entry["flags"] = set(entry["flags"].split())
            found.append(entry)
    return found


def dump(title, *options):
    """Run tree.ahk on a window through the launcher."""
    return run_launcher(TREE, "--timeout", "15", "--", title, *options)


def run_script(tmp_path, body):
    """Run an agent-style script, plain AutoHotkey with no include, through the launcher."""
    script = tmp_path / "agent.ahk"
    script.write_text(body, encoding="utf-8")
    return run_launcher(script, "--timeout", "20")


def calculator_pids():
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq CalculatorApp.exe", "/FO", "CSV", "/NH"], capture_output=True, text=True).stdout
    return {int(line.split('","')[1]) for line in out.splitlines() if line.startswith('"CalculatorApp.exe"')}


@pytest.fixture
def uia_window(open_window, tmp_path):
    """A window with a button, two named edits, and a quoted check box, plus the files its handlers write."""
    count, edits = tmp_path / "hits.txt", tmp_path / "edits.txt"
    title = f"ACU uia window {os.getpid()}"
    hwnd = open_window(title, 200, 200, script="uia_window.ahk", ACU_TEST_COUNT_FILE=str(count), ACU_TEST_EDIT_FILE=str(edits))
    return SimpleNamespace(title=title, hwnd=hwnd, count=count, edits=edits)


@pytest.fixture
def calculator_cleanup():
    """Terminate only the Calculator processes a test started; a closed UWP window leaves its process suspended."""
    before = calculator_pids()
    yield
    for pid in calculator_pids() - before:
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)


def test_tree_lists_each_control_with_path_name_id_bounds_and_actions(uia_window):
    result = dump(uia_window.title)

    assert result.returncode == 0, result.stdout + result.stderr
    assert reported(result.stdout, "window").startswith(f'{uia_window.hwnd} "{uia_window.title}"')
    found = elements(result.stdout)
    by_name = {e["name"]: e for e in found if e["name"]}
    button, check = by_name["hit"], by_name['agree `"fully`"']
    assert button["type"] == "Button" and "invoke" in button["flags"] and button["id"]
    assert check["type"] == "CheckBox" and "toggle" in check["flags"]
    city, street = by_name["City"], by_name["Street"]
    assert (city["type"], city["value"]) == ("Edit", "Boston") and "value" in city["flags"]
    assert (street["type"], street["value"]) == ("Edit", "Main St")
    notes, memo = by_name["Notes"], by_name["Memo"]
    assert notes["value"] == "read only" and "value" not in notes["flags"], "value means writable"
    assert memo["type"] == "Document"
    assert memo["value"] == "0" * 100, "Document values must print in full"
    tabs = {e["name"]: e for e in found if e["type"] == "TabItem"}
    assert "selected" in tabs["One"]["flags"] and "selected" not in tabs["Two"]["flags"]
    fx, fy, fw, fh = visible_frame(uia_window.hwnd)
    for e in (button, check, city, street):
        x, y, w, h = (int(e[k]) for k in "xywh")
        assert fx <= x and fy <= y and x + w <= fx + fw and y + h <= fy + fh, f"{e['name']} lies outside the window"
    assert reported(result.stdout, "elements") == str(len(found))
    assert reported(result.stdout, "truncated") == "no"


def test_dumped_name_pastes_into_a_script_as_it_is(uia_window, tmp_path):
    printed = next(e["name"] for e in elements(dump(uia_window.title).stdout) if e["type"] == "CheckBox")

    result = run_script(tmp_path, f'root := UIA.ElementFromHandle("{uia_window.title}")\nFileAppend "name=" root.FindElement({{Type:"CheckBox", Name:"{printed}"}}).Name "`n", "*"\n')

    assert result.returncode == 0, result.stdout + result.stderr
    assert reported(result.stdout, "name") == 'agree "fully"'


def test_tree_path_resolves_to_the_same_element(uia_window, tmp_path):
    path = next(e["path"] for e in elements(dump(uia_window.title).stdout) if e["name"] == "hit")

    result = run_script(tmp_path, f'root := UIA.ElementFromHandle("{uia_window.title}")\nFileAppend "name=" root.ElementFromPath("{path}").Name "`n", "*"\n')

    assert result.returncode == 0, result.stdout + result.stderr
    assert reported(result.stdout, "name") == "hit"


def test_acu_tree_returns_the_same_dump_from_inside_a_script(uia_window, tmp_path):
    result = run_script(tmp_path, f'FileAppend AcuTree("{uia_window.title}", {{type: "Button", find: "hit"}}), "*"\n')

    assert result.returncode == 0, result.stdout + result.stderr
    assert reported(result.stdout, "window").startswith(f'{uia_window.hwnd} "{uia_window.title}"')
    found = elements(result.stdout)
    assert [e["name"] for e in found] == ["hit"] and "invoke" in found[0]["flags"]
    assert reported(result.stdout, "truncated") == "no"


def test_acu_tree_waits_for_a_fresh_chromium_window_to_answer(tmp_path):
    """A Chromium window exists before its UI Automation provider is ready; the first dump used to fail with UIA_E_TIMEOUT."""
    edge = next((p for p in (Path(os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)')) / 'Microsoft/Edge/Application/msedge.exe',
                             Path(os.environ.get('ProgramFiles', r'C:\Program Files')) / 'Microsoft/Edge/Application/msedge.exe') if p.is_file()), None)
    if edge is None:
        pytest.skip('Microsoft Edge is not installed')
    profile = tmp_path / 'edge-profile'
    command = f'"{edge}" --user-data-dir="{profile}" --no-first-run --no-default-browser-check --new-window --app=about:blank'
    body = (f"window := AcuLaunch('{command}', 'ahk_exe msedge.exe', 20000)\n"
            'FileAppend "hwnd=" window.hwnd "`n", "*"\n'
            'FileAppend AcuTree("ahk_id " window.hwnd, {type: "Document", max: 5}), "*"\n'
            'WinClose "ahk_id " window.hwnd\n'
            'WinWaitClose "ahk_id " window.hwnd, , 5\n')
    try:
        result = run_script(tmp_path, body)
    finally:
        # Only the Edge processes started with the throwaway profile; the user's own browser is never touched.
        for proc in subprocess.run(["wmic", "process", "where", f"name='msedge.exe' and commandline like '%{profile.name}%'", "get", "processid"], capture_output=True, text=True).stdout.split():
            if proc.isdigit():
                subprocess.run(["taskkill", "/F", "/PID", proc], capture_output=True)

    assert result.returncode == 0, result.stdout + result.stderr
    assert reported(result.stdout, "window").startswith(reported(result.stdout, "hwnd"))
    assert reported(result.stdout, "truncated") in ("no", "max")


def test_tree_honours_max_and_says_so(uia_window):
    result = dump(uia_window.title, "--max", "2")

    assert result.returncode == 0, result.stdout + result.stderr
    assert len(elements(result.stdout)) == 2
    assert reported(result.stdout, "truncated") == "max"


def test_tree_reports_a_depth_cut_as_truncation(uia_window):
    result = dump(uia_window.title, "--depth", "1")

    assert result.returncode == 0, result.stdout + result.stderr
    found = elements(result.stdout)
    assert found and all("," not in e["path"] for e in found)
    assert reported(result.stdout, "truncated") == "depth", "the title bar's buttons were cut off"


def test_tree_find_and_type_narrow_the_dump(uia_window):
    by_text = dump(uia_window.title, "--find", "AGREE")
    by_type = dump(uia_window.title, "--type", "Edit")

    assert by_text.returncode == 0, by_text.stdout + by_text.stderr
    assert [e["type"] for e in elements(by_text.stdout)] == ["CheckBox"]
    assert reported(by_text.stdout, "elements") == "1"
    assert by_type.returncode == 0, by_type.stdout + by_type.stderr
    assert sorted(e["name"] for e in elements(by_type.stdout)) == ["City", "Notes", "Street"]
    documents = dump(uia_window.title, "--type", "Document", "--find", "memo", "--max", "1")
    assert documents.returncode == 0, documents.stdout + documents.stderr
    assert [(e["name"], e["value"]) for e in elements(documents.stdout)] == [("Memo", "0" * 100)]
    assert reported(documents.stdout, "truncated") == "no"


def test_tree_rejects_an_empty_budget(uia_window):
    result = dump(uia_window.title, "--max", "0")

    assert result.returncode == 1, result.stdout + result.stderr
    assert "at least 1" in result.stdout


def test_tree_reports_a_missing_window():
    result = dump("ahk_class NoSuchWindowClass_ACU")

    assert result.returncode == 1, result.stdout + result.stderr
    assert "not found" in result.stdout.lower()


def test_script_acts_on_controls_by_name_and_reads_state_back(uia_window, tmp_path):
    result = run_script(
        tmp_path,
        f'root := UIA.ElementFromHandle("{uia_window.title}")\n'
        'root.FindElement({Type:"Button", Name:"hit"}).Invoke()\n'
        'root.FindElement({Type:"Edit", Name:"Street"}).Value := "typed by uia"\n'
        'box := root.FindElement({Type:"CheckBox", Name:"agree `"fully`""})\n'
        "box.Toggle()\n"
        "Loop 20 {  ; the pattern call returns before the control repaints\n"
        "    if box.ToggleState\n"
        "        break\n"
        "    Sleep 50\n"
        "}\n"
        'FileAppend "agree=" box.ToggleState "`n", "*"\n',
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert reported(result.stdout, "agree") == "1"
    wait_until(lambda: uia_window.count.is_file() and uia_window.count.read_text() == "1", 2, "the button's handler never ran")
    wait_until(lambda: uia_window.edits.is_file() and uia_window.edits.read_text() == "Street=typed by uia", 2, "the Street edit never changed")


def test_calculator_six_times_seven_by_name(tmp_path, calculator_cleanup):
    """The three-step flow an agent runs: open the window, dump its tree, act by path and by name."""
    opened = run_script(
        tmp_path,
        "existing := Map()\n"
        'for h in WinGetList("Calculator ahk_class ApplicationFrameWindow")\n'
        "    existing[h] := true\n"
        'Run "calc.exe"\n'
        "deadline := A_TickCount + 8000\n"
        "hwnd := 0\n"
        "while (!hwnd && A_TickCount < deadline) {\n"
        '    for h in WinGetList("Calculator ahk_class ApplicationFrameWindow")\n'
        "        if !existing.Has(h)\n"
        "            hwnd := h\n"
        "    Sleep 100\n"
        "}\n"
        'FileAppend "hwnd=" hwnd "`n", "*"\n',
    )
    assert opened.returncode == 0, opened.stdout + opened.stderr
    hwnd = reported(opened.stdout, "hwnd")
    if hwnd == "0":
        pytest.skip("Windows Calculator is not installed")

    tree = dump(f"ahk_id {hwnd}")
    assert tree.returncode == 0, tree.stdout + tree.stderr
    six = next(e for e in elements(tree.stdout) if e["name"] == "Six")
    assert six["type"] == "Button" and six["id"] == "num6Button" and "invoke" in six["flags"]

    acted = run_script(
        tmp_path,
        f"root := UIA.ElementFromHandle({hwnd})\n"
        "try {\n"
        f'    FileAppend "by_path=" root.ElementFromPath("{six["path"]}").Name "`n", "*"\n'
        '    for name in ["Six", "Multiply by", "Seven", "Equals"]\n'
        '        root.FindElement({Type:"Button", Name:name}).Invoke()\n'
        "    Sleep 250\n"
        '    FileAppend "display=" root.FindElement({AutomationId:"CalculatorResults"}).Name "`n", "*"\n'
        "} finally {\n"
        f"    WinClose {hwnd}\n"
        "}\n",
    )
    assert acted.returncode == 0, acted.stdout + acted.stderr
    assert reported(acted.stdout, "by_path") == "Six"
    assert reported(acted.stdout, "display") == "Display is 42"
