"""The agent of one Cua Driver Bench trial on Windows: Claude Code `claude -p` with ACU's MCP server and skill.

The Windows counterpart of the bench's `launch/xfce/agent.sh`, with the system prompt its Windows notes
name. `launch/windows_session.py` runs it as the trial's COMMAND from the trial directory and sets
`CDB_BRIEF_FILE`; `run.py` builds that command:

    python agent.py [--model claude-sonnet-5-5] [--effort medium] [--max-turns 45]

It writes `mcp.json` and the `acu` project skill (`work/.claude/skills/acu/SKILL.md`, the manual the
bench's Cua Driver arm also gets as a skill), runs the agent in `work/` with no built-in tool but Skill
and an empty ACU snippet store, and the bench's system prompt plus its GUI-only rule. It
leaves `agent-transcript.jsonl` (stream-json, read by the bench's GUI-only scan) and
`agent-stderr.log` in the trial directory. The ACU adapter logs to `work/acu-mcp.log`.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ADAPTER = Path(__file__).resolve().with_name("acu_mcp.py")
sys.path.insert(0, str(ADAPTER.parent))
from acu_mcp import skill_file  # noqa: E402
# The bench's MACOS_SYSTEM_PROMPT (claude_arms.py) with the platform words its Windows notes give, then the
# bench's GUI-only rule. The bench never states the rule because its own drivers can't leave the GUI; an ACU
# script can run programs, read files and fetch URLs, so the prompt has to say it.
SYSTEM_PROMPT = (
    "You are an autonomous computer-use agent operating a Windows desktop through the tools provided. "
    "No human is available to answer questions or confirm actions; every action the task requires is "
    "pre-approved. Operate only the applications the task names. Do not use the network. When the task "
    "is done, reply with the single word DONE. If you cannot finish, reply BLOCKED and the reason.\n\n"
    "This is a GUI-only run: do the task through the windows of the applications it names. Your scripts may "
    "look at and drive windows (screenshots, accessibility trees, keyboard, mouse, clipboard) and print to "
    "stdout. A script that starts a program, reads or writes a file or the registry, or fetches a URL fails "
    "the task."
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="claude-sonnet-5-5")
    parser.add_argument("--effort", default="medium")
    parser.add_argument("--max-turns", default="45")
    args = parser.parse_args()
    trial = Path.cwd()
    brief = Path(os.environ["CDB_BRIEF_FILE"]).read_text(encoding="utf-8")
    work = trial / "work"
    snippets = trial / "empty-snippets"
    skill = work / ".claude" / "skills" / "acu" / "SKILL.md"
    skill.parent.mkdir(parents=True, exist_ok=True)
    skill.write_text(skill_file(), encoding="utf-8")
    snippets.mkdir(exist_ok=True)
    env = {**os.environ, "ACU_SNIPPETS_ROOT": str(snippets), "MAX_THINKING_TOKENS": "16000",
           "DISABLE_AUTOUPDATER": "1", "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1",
           "CLAUDE_CODE_DISABLE_CLAUDE_MDS": "1", "DISABLE_TELEMETRY": "1"}
    config = trial / "mcp.json"
    config.write_text(json.dumps({"mcpServers": {"acu": {
        "command": sys.executable, "args": ["-I", "-B", str(ADAPTER)],
        "env": {"ACU_SNIPPETS_ROOT": str(snippets)}}}}), encoding="utf-8")
    claude = shutil.which("claude") or "claude"
    command = [
        claude, "-p", brief, "--model", args.model, "--effort", args.effort, "--system-prompt", SYSTEM_PROMPT,
        "--mcp-config", str(config), "--strict-mcp-config", "--tools", "Skill", "--allowed-tools", "mcp__acu,Skill",
        "--permission-mode", "bypassPermissions", "--setting-sources", "project", "--max-turns", args.max_turns,
        "--output-format", "stream-json", "--verbose",
    ]
    with (trial / "agent-transcript.jsonl").open("wb") as out, (trial / "agent-stderr.log").open("wb") as err:
        return subprocess.run(command, cwd=work, env=env, stdout=out, stderr=err).returncode


if __name__ == "__main__":
    sys.exit(main())
