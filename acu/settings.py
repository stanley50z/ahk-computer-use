"""Resolve snippet discovery settings separately from diagnostic artifact locations."""

import json
import os
from pathlib import Path


# Read the optional value; absence leaves the preceding default unchanged.
def _enabled_value(path: Path) -> bool | None:
    try:
        text = path.read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        return None
    except (OSError, UnicodeError) as error:
        raise ValueError(f"Invalid settings file {path}: {error}") from error
    try:
        value = json.loads(text)
        if not isinstance(value, dict):
            raise ValueError("expected a JSON object")
        snippets = value.get("snippets", {})
        if not isinstance(snippets, dict):
            raise ValueError("snippets must be an object")
        if "enabled" in snippets and not isinstance(snippets["enabled"], bool):
            raise ValueError("snippets.enabled must be a boolean")
        return snippets.get("enabled")
    except ValueError as error:
        raise ValueError(f"Invalid settings file {path}: {error}") from error


# Shared by explicit listing and automatic discovery, using the caller's working folder.
def snippets_enabled(working_folder: str | Path | None = None) -> bool:
    home_file = (Path.home() / ".ahk-computer-use/settings.json").resolve()
    global_file = Path(os.environ.get("ACU_SETTINGS_FILE", home_file)).resolve()
    enabled = _enabled_value(global_file)
    folder = Path.cwd() if working_folder is None else Path(working_folder).resolve()
    for directory in (folder, *folder.parents):
        project_file = directory / ".ahk-computer-use/settings.json"
        # The home settings are global, even when tests relocate that global file.
        if project_file in (home_file, global_file) or not project_file.exists():
            continue
        project_enabled = _enabled_value(project_file)
        if project_enabled is not None:
            enabled = project_enabled
        break
    return True if enabled is None else enabled
