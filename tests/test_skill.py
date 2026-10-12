"""The agent skill: valid Agent Skills frontmatter, and an installer that links it where the harnesses look."""

import re
import sys
from pathlib import Path

import pytest

from conftest import REPO

sys.path.insert(0, str(REPO))
from install_skill import PROJECT_ROOTS, USER_ROOTS, install, is_link  # noqa: E402

SKILL_DIR = REPO / "acu"
SKILL_FILE = SKILL_DIR / "SKILL.md"


def frontmatter():
    """The key: value pairs between the opening and closing --- lines of SKILL.md."""
    text = SKILL_FILE.read_text(encoding="utf-8")
    assert text.startswith("---\n"), "SKILL.md must open with frontmatter"
    block = text.split("---\n", 2)[1]
    return dict(line.split(": ", 1) for line in block.strip().splitlines())


def test_frontmatter_follows_the_agent_skills_specification():
    fields = frontmatter()

    assert fields["name"] == SKILL_DIR.name, "name must match the directory, which some harnesses enforce"
    assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", fields["name"])
    assert 0 < len(fields["description"]) <= 1024
    assert fields["description"].startswith("Operate"), "front-load the verb the agent will route on"


def test_skill_teaches_window_discovery_before_control_lookup():
    """Guard the launch recipe against the process-only assumption seen in the Calculator trial."""
    text = SKILL_FILE.read_text(encoding="utf-8")
    discovery = text.split("### 1. Look", 1)[1].split('acu run ', 1)[0]

    for required in ("AcuLaunch(", "WinGetList()", "WinGetTitle", "WinGetClass", "WinGetProcessName", "ahk_id",
                     "CalculatorApp.exe", "ApplicationFrameHost.exe"):
        assert required in discovery, f"window discovery must explain {required} before tree lookup"
    assert "pre-existing window" in discovery, "new-window tasks must preserve pre-existing windows"
    assert "observed" in discovery, "window identity must be observed rather than guessed"
    for required in ('acu run "<absolute script.ahk>"', "whole scripted action chain"):
        assert required in text, f"skill must teach the script-first tool interface: {required}"
    assert "`discover`" not in text and "`describe`" not in text
    assert "MCP" not in text and "uv run" not in text and "python -m acu" not in text


def test_skill_is_self_contained_and_spends_turns_on_looking_not_ceremony():
    """Guard the Calculator benchmark findings: separate guide reads, write-then-run turns, blind sleeps, and the Click() claim."""
    text = SKILL_FILE.read_text(encoding="utf-8")

    assert "guides/" not in text, "everything an agent needs before its first script lives in the skill itself"
    for required in ("one shell call", "heredoc", "AcuLaunch(command, winTitle", "AcuWaitUntil(predicate", "AcuTree(target", "AcuScreenshot({app", "acu run tree.ahk",
                     "element.Click()", 'Click("left")', "screen-reader text", "truncated=", "scale=", "fullscreen [monitor]",
                     "PrintWindow", "on-screen", "popup", "repaint", "English keyboard", "no English keyboard"):
        assert required in text, f"skill must cover {required}"
    assert "AcuKeepForeground" not in text
    assert "restore skipped" not in text
    assert not re.search(r'Illustrator|Adobe|Cloud9|Pen[- ]tool', text, re.IGNORECASE), 'the skill must not coach a benchmark workflow'
    assert '!fe{Right}{Down}{Enter}' not in text, 'benchmark-specific menu recipes do not belong in ACU'


def test_skill_names_only_files_that_exist_beside_it():
    for script in ("run.py", "prelude.ahk", "tree.ahk", "screenshot.ahk"):
        assert script in SKILL_FILE.read_text(encoding="utf-8")
        assert (SKILL_DIR / script).is_file()


@pytest.mark.parametrize("roots", [PROJECT_ROOTS, USER_ROOTS], ids=["project", "global"])
def test_installer_links_the_skill_into_every_harness_root_and_removes_cleanly(tmp_path, roots):
    first = install(tmp_path, roots)
    second = install(tmp_path, roots)

    assert len(first) == len(roots) and all(line.startswith("installed") for line in first)
    assert all(line.startswith("already installed") for line in second)
    for root in roots:
        link = tmp_path / root / "acu"
        assert is_link(link)
        assert (link / "SKILL.md").read_text(encoding="utf-8") == SKILL_FILE.read_text(encoding="utf-8")
        assert (link / "run.py").is_file()

    removed = install(tmp_path, roots, remove=True)

    assert all(line.startswith("removed") for line in removed)
    assert not any((tmp_path / root / "acu").exists() for root in roots)
    assert SKILL_FILE.is_file(), "removing links must leave the checkout alone"


def test_project_roots_cover_the_four_harnesses_in_repo():
    assert set(PROJECT_ROOTS) == {Path(".agents") / "skills", Path(".claude") / "skills"}
