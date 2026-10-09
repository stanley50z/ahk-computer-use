"""The agent skill: valid Agent Skills frontmatter, and an installer that links it where the harnesses look."""

import re
import sys

from conftest import REPO

sys.path.insert(0, str(REPO))
from install_skill import ROOTS, install, is_link  # noqa: E402

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


def test_skill_names_only_files_that_exist_beside_it():
    for script in ("run.py", "screenshot.ahk"):
        assert script in SKILL_FILE.read_text(encoding="utf-8")
        assert (SKILL_DIR / script).is_file()


def test_installer_links_the_skill_into_every_harness_root_and_removes_cleanly(tmp_path):
    first = install(tmp_path)
    second = install(tmp_path)

    assert len(first) == len(ROOTS) and all(line.startswith("installed") for line in first)
    assert all(line.startswith("already installed") for line in second)
    for root in ROOTS:
        link = tmp_path / root / "acu"
        assert is_link(link)
        assert (link / "SKILL.md").read_text(encoding="utf-8") == SKILL_FILE.read_text(encoding="utf-8")
        assert (link / "run.py").is_file()

    removed = install(tmp_path, remove=True)

    assert all(line.startswith("removed") for line in removed)
    assert not any((tmp_path / root / "acu").exists() for root in ROOTS)
    assert SKILL_FILE.is_file(), "removing links must leave the checkout alone"
