"""Install the acu and retro-acu skills where the coding harnesses look for skills.

Usage: python install_skill.py [--global] [--remove]

By default links both acu/ and retro-acu/ into each repository-local root, so only sessions
started inside this repository see the skills:

    .agents/skills/     Pi, Codex, and OpenCode
    .claude/skills/     Claude Code

All four links are gitignored; run this once per checkout. With --global both skills are linked
into each user-level root instead and every session on the machine sees them:

    ~/.agents/skills/            Pi and Codex
    ~/.claude/skills/            Claude Code
    ~/.config/opencode/skills/   OpenCode

Links are directory junctions on Windows, which need no elevation, or symlinks elsewhere, so the installed
skills always match the checkout. --remove deletes the links for the chosen scope and nothing else.
"""

import argparse
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent
SKILLS = (REPO / "acu", REPO / "retro-acu")
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
    """Create a directory link without interpreting either path as a shell command."""
    if sys.platform == "win32":
        import _winapi

        _winapi.CreateJunction(str(source), str(target))
    else:
        os.symlink(source, target, target_is_directory=True)


def install(base: Path, roots: dict[Path, str], remove: bool = False) -> list[str]:
    """Link or unlink both skills under base; report each skill in each harness root."""
    report = []
    for root, harness in roots.items():
        for skill in SKILLS:
            target = base / root / skill.name
            if remove:
                if is_link(target):
                    os.rmdir(target) if os.path.isjunction(target) else target.unlink()
                    report.append(f"removed {target}")
                else:
                    report.append(f"nothing to remove at {target}")
            elif is_link(target):
                if target.resolve() == skill:
                    report.append(f"already installed for {harness}: {target}")
                else:
                    raise SystemExit(f"{target} is a link to somewhere else; remove it first")
            elif target.exists():
                raise SystemExit(f"{target} exists and is not a link; move it aside first")
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                make_link(target, skill)
                report.append(f"installed for {harness}: {target}")
    return report


def main() -> None:
    """Install or remove the selected links and report Unicode paths as UTF-8."""
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Link acu and retro-acu into the harness skill directories.")
    parser.add_argument("--global", dest="machine_wide", action="store_true", help="link into the user-level roots instead of this repository")
    parser.add_argument("--remove", action="store_true", help="delete the links instead of creating them")
    args = parser.parse_args()
    base, roots = (Path.home(), USER_ROOTS) if args.machine_wide else (REPO, PROJECT_ROOTS)
    for line in install(base, roots, remove=args.remove):
        print(line)


if __name__ == "__main__":
    main()
