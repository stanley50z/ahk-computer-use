"""Settings resolution without desktop access or the user's global settings."""

import json
from pathlib import Path

import pytest

from acu import settings


@pytest.fixture
def global_settings(tmp_path, monkeypatch):
    path = tmp_path / "global" / "settings.json"
    monkeypatch.setenv("ACU_SETTINGS_FILE", str(path))
    return path


# Write settings only inside the test's temporary directories.
def write_settings(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def test_defaults_global_and_nearest_project_override(tmp_path, global_settings):
    project = tmp_path / "project"
    working = project / "nested" / "work"
    working.mkdir(parents=True)
    assert settings.snippets_enabled(working) is True
    assert not global_settings.exists()
    write_settings(global_settings, {"snippets": {"enabled": False}})
    assert settings.snippets_enabled(working) is False
    write_settings(project / ".ahk-computer-use/settings.json", {"snippets": {"enabled": True}})
    assert settings.snippets_enabled(working) is True
    write_settings(working.parent / ".ahk-computer-use/settings.json", {"snippets": {"enabled": False}})
    assert settings.snippets_enabled(working) is False


@pytest.mark.parametrize("value", [{}, {"snippets": {}}, {"unrelated": True}])
def test_missing_project_value_keeps_global_default(tmp_path, global_settings, value):
    write_settings(global_settings, {"snippets": {"enabled": False}})
    write_settings(tmp_path / ".ahk-computer-use/settings.json", value)
    assert settings.snippets_enabled(tmp_path) is False


@pytest.mark.parametrize("text", ['{', '[]', 'null', '{"snippets": false}', '{"snippets": null}',
                                  '{"snippets": {"enabled": "false"}}', '{"snippets": {"enabled": 0}}',
                                  '{"snippets": {"enabled": null}}'])
@pytest.mark.parametrize("scope", ["global", "project"])
def test_invalid_settings_name_the_file(tmp_path, global_settings, text, scope):
    path = global_settings if scope == "global" else tmp_path / ".ahk-computer-use/settings.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError) as error:
        settings.snippets_enabled(tmp_path)
    assert str(path) in str(error.value)


def test_global_override_does_not_rediscover_home_settings_as_project(tmp_path, monkeypatch, global_settings):
    home = tmp_path / "home"
    working = home / "project"
    working.mkdir(parents=True)
    monkeypatch.setattr(Path, "home", lambda: home)
    write_settings(home / ".ahk-computer-use/settings.json", {"snippets": {"enabled": False}})
    assert settings.snippets_enabled(working) is True


def test_default_global_location_is_independent_of_acu_home(tmp_path, monkeypatch):
    monkeypatch.delenv("ACU_SETTINGS_FILE", raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    monkeypatch.setenv("ACU_HOME", str(tmp_path / "diagnostics"))
    write_settings(tmp_path / "home/.ahk-computer-use/settings.json", {"snippets": {"enabled": False}})
    assert settings.snippets_enabled(tmp_path / "project") is False
