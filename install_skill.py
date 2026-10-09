"""Install the ACU skill where the coding harnesses look for skills.

Usage: python install_skill.py [--global] [--remove]

By default links acu/ (SKILL.md beside the launcher and scripts) into this repository, so only sessions
started inside it see the skill:

    .agents/skills/acu     Pi, Codex, and OpenCode
    .claude/skills/acu     Claude Code

Both links are gitignored; run this once per checkout. With --global the links go into the user-level
roots instead and every session on the machine sees the skill:

    ~/.agents/skills/acu            Pi and Codex
    ~/.claude/skills/acu            Claude Code
    ~/.config/opencode/skills/acu   OpenCode

Links are directory junctions on Windows, which need no elevation, or symlinks elsewhere, so the installed
skill always matches the checkout. --remove deletes the links for the chosen scope and nothing else.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent
SKILL = REPO / "acu"
PROJECT_ROOTS = {
    Path(".agents") / "skills": "Pi, Codex, and OpenCode",
    Path(".claude") / "skills": "Claude Code",
}
USER_ROOTS = {
    Path(".agents") / "skills": "Pi and Codex",
    Path(".claude") / "skills": "Claude Code",
    Path(".config") / "opencode" / "skills": "OpenCode",
}


def is_link(path: Path) -> bool:
    return path.is_symlink() or os.path.isjunction(path)


def make_link(target: Path, source: Path) -> None:
    if sys.platform == "win32":
        subprocess.run(["cmd", "/c", "mklink", "/J", str(target), str(source)], check=True, capture_output=True)
    else:
        os.symlink(source, target, target_is_directory=True)


def install(base: Path, roots: dict[Path, str], remove: bool = False) -> list[str]:
    """Create or remove the links under base for the given roots and return one report line per root."""
    report = []
    for root, harness in roots.items():
        target = base / root / SKILL.name
        if remove:
            if is_link(target):
                os.rmdir(target) if os.path.isjunction(target) else target.unlink()
                report.append(f"removed {target}")
            else:
                report.append(f"nothing to remove at {target}")
        elif is_link(target):
            if target.resolve() == SKILL:
                report.append(f"already installed for {harness}: {target}")
            else:
                raise SystemExit(f"{target} is a link to somewhere else; remove it first")
        elif target.exists():
            raise SystemExit(f"{target} exists and is not a link; move it aside first")
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            make_link(target, SKILL)
            report.append(f"installed for {harness}: {target}")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Link the ACU skill into the harness skill directories.")
    parser.add_argument("--global", dest="machine_wide", action="store_true", help="link into the user-level roots instead of this repository")
    parser.add_argument("--remove", action="store_true", help="delete the links instead of creating them")
    args = parser.parse_args()
    base, roots = (Path.home(), USER_ROOTS) if args.machine_wide else (REPO, PROJECT_ROOTS)
    for line in install(base, roots, remove=args.remove):
        print(line)


if __name__ == "__main__":
    main()
