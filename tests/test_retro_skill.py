"""Pin the user-only retro contract and distribution of the sibling skill."""

import re
import tomllib

from conftest import REPO


def test_retro_requires_history_and_approval_before_store_changes():
    text = (REPO / "retro-acu" / "SKILL.md").read_text(encoding="utf-8")
    metadata = dict(line.split(": ", 1) for line in text.split("---\n", 2)[1].strip().splitlines())
    assert metadata["name"] == "retro-acu"
    assert metadata["disable-model-invocation"] == "true"
    assert metadata["description"]
    for requirement in (
        'acu history "<session file>"',
        "Do not read raw logs or session files",
        "List every snippet history reports changed during the session",
        "For every frequently failing snippet",
        "Wait for the user's explicit approval before writing, modifying, or deleting any snippet",
        "Delete only the exact snippets whose deletion the user approved",
        "~/.ahk-computer-use/snippets/<exe name>/",
        "ACU_SNIPPETS_ROOT",
        "A_Args",
        "Implement the `needs` check before acting",
        "Implement a result check last",
        "error that names the missing need",
        "error if the action had no effect",
    ):
        assert requirement in text
    assert re.findall(r"^  ; (\w+):", text, re.MULTILINE) == [
        "does", "args", "needs", "effect", "check", "tested",
    ]
    assert not re.search(r"\b[\w-]+\.exe\b|Illustrator|Calculator|Notepad|Adobe", text, re.IGNORECASE)


def test_distributions_include_the_sibling_skill():
    config = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))
    targets = config["tool"]["hatch"]["build"]["targets"]
    assert "retro-acu" in targets["sdist"]["only-include"]
    assert targets["wheel"]["force-include"]["retro-acu"] == "retro-acu"
