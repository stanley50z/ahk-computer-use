"""Stdio MCP server that offers ACU to an agent that has no shell or file tools.

Cua Driver Bench gives the agent only its driver's MCP server, so this adapter stands in for the
shell call that `acu/SKILL.md` describes. Claude Code starts it from the trial's MCP config:

    python acu_mcp.py

It offers one tool, `run`. Script text is written to a new `.ahk` file under `acu-scripts/` in the
working directory and run with `acu run`; a bundled script or an existing file runs by name. The
result is the JSON `acu run` prints, with every PNG named on a `saved=` output line attached as an
image, because the agent cannot open files. The server instructions are a short note that maps the
skill's shell calls onto this tool and points to the `acu` skill; `skill_file()` builds that skill
(the ACU skill unmodified after the same note), which agent.py installs for the agent.

Every request, its outcome and any crash traceback are appended to `acu-mcp.log` in the working
directory.
"""

from __future__ import annotations

import base64
import json
import re
import shutil
import subprocess
import sys
import time
import traceback
from pathlib import Path

SKILL = Path(__file__).resolve().parents[2] / "acu" / "SKILL.md"
DEFAULT_TIMEOUT = 30
SAVED_LINE = re.compile(r"^saved=(.+\.png)\s*$", re.MULTILINE | re.IGNORECASE)

PREFACE = """\
In this session ACU is the `run` tool of this MCP server, not a shell command; there is no shell or file tool.
Where the manual below writes a script file and calls `acu run`, pass the AutoHotkey v2 source as `script`
instead: the tool writes it to a new .ahk file in the working directory and runs it, in one call. For
`acu run <file> -- <arguments>`, pass `file` (a bundled script such as `tree.ahk` or `screenshot.ahk`, or an
existing .ahk path) and `args`. `timeout` is the `--timeout` in seconds. The result is the JSON `acu run`
prints; each PNG a screenshot saves is attached to the result as an image, so you do not need to open it.
`acu snippets list` has no tool here; snippet listings still appear where the manual says ACU prints them.

"""

TOOL = {
    "name": "run",
    "description": "Run one AutoHotkey v2 script through ACU (`acu run`) and return its JSON result, "
    "with any saved screenshot attached as an image. Pass `script` (source text) or `file` (a bundled "
    "script such as tree.ahk or screenshot.ahk, or an existing .ahk path), not both.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "script": {"type": "string", "description": "AutoHotkey v2 source to write to a new .ahk file and run."},
            "file": {"type": "string", "description": "A bundled script name (tree.ahk, screenshot.ahk) or an existing .ahk path."},
            "args": {"type": "array", "items": {"type": "string"}, "description": "Arguments after `--`, received as A_Args."},
            "timeout": {"type": "number", "description": f"Seconds, more than 0 and at most 300 (default {DEFAULT_TIMEOUT})."},
        },
        "additionalProperties": False,
    },
}


SERVER_NOTE = "The full ACU manual is the `acu` skill: load it with the Skill tool before your first `run` call.\n"


# The server instructions: the mapping note and a pointer to the skill. Claude Code cuts long server instructions short
# (the skill's text stopped two sections in), so the manual itself travels as a skill, as the bench's Cua Driver arm does.
def instructions() -> str:
    return PREFACE + SERVER_NOTE


# The agent's `acu` project skill: the ACU skill's front matter, the mapping note, then its body unchanged.
def skill_file(skill: Path = SKILL) -> str:
    _, front, body = skill.read_text(encoding="utf-8").split("---", 2)
    return f"---{front}---\n\n" + PREFACE + body.strip() + "\n"


# Runs one `run` tool call; `acu` is the command prefix, `workdir` holds the written scripts.
def call_run(arguments: dict, workdir: Path, acu: list[str]) -> dict:
    script, file = arguments.get("script"), arguments.get("file")
    if (script is None) == (file is None):
        return error_result("pass exactly one of `script` or `file`")
    timeout = arguments.get("timeout", DEFAULT_TIMEOUT)
    if script is not None:
        folder = workdir / "acu-scripts"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{len(list(folder.glob('*.ahk'))) + 1:03d}.ahk"
        path.write_text(script, encoding="utf-8")
        file = str(path)
    command = [*acu, "run", file, "--timeout", str(timeout), "--", *map(str, arguments.get("args", []))]
    done = subprocess.run(
        command, cwd=workdir, capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=float(timeout) + 30,
    )
    text = done.stdout.strip() or done.stderr.strip() or f"acu exited {done.returncode} with no output"
    content = [{"type": "text", "text": text}]
    try:
        output = json.loads(done.stdout).get("output", "")
    except (json.JSONDecodeError, AttributeError):
        output = ""
    for saved in SAVED_LINE.findall(output):
        png = Path(saved.strip())
        if png.is_file():
            content.append({"type": "image", "mimeType": "image/png",
                            "data": base64.b64encode(png.read_bytes()).decode("ascii")})
    return {"content": content, "isError": done.returncode != 0}


def error_result(message: str) -> dict:
    return {"content": [{"type": "text", "text": message}], "isError": True}


# Answers one JSON-RPC message; returns None for notifications.
def handle(message: dict, workdir: Path, acu: list[str]) -> dict | None:
    method, rid = message.get("method"), message.get("id")
    if rid is None:
        return None
    if method == "initialize":
        version = (message.get("params") or {}).get("protocolVersion", "2025-06-18")
        result = {"protocolVersion": version, "capabilities": {"tools": {}},
                  "serverInfo": {"name": "acu", "version": "0.1.0"}, "instructions": instructions()}
    elif method == "tools/list":
        result = {"tools": [TOOL]}
    elif method == "tools/call":
        params = message.get("params") or {}
        if params.get("name") != TOOL["name"]:
            result = error_result(f"unknown tool {params.get('name')!r}")
        else:
            result = call_run(params.get("arguments") or {}, workdir, acu)
    elif method == "ping":
        result = {}
    else:
        return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": f"unknown method {method}"}}
    return {"jsonrpc": "2.0", "id": rid, "result": result}


def main() -> None:
    workdir = Path.cwd()
    log = (workdir / "acu-mcp.log").open("a", encoding="utf-8", buffering=1)
    found = shutil.which("acu")
    acu = [found] if found else ["acu"]
    sys.stdout.reconfigure(encoding="utf-8")
    for line in sys.stdin.buffer:
        if not line.strip():
            continue
        started = time.monotonic()
        message: dict = {}
        try:
            message = json.loads(line)
            reply = handle(message, workdir, acu)
        except Exception:  # noqa: BLE001 - a crash is logged and answered, never fatal to the trial
            log.write(f"{time.strftime('%H:%M:%S')} crash\n{traceback.format_exc()}\n")
            reply = {"jsonrpc": "2.0", "id": message.get("id"), "error": {"code": -32603, "message": "adapter error, see acu-mcp.log"}}
        log.write(json.dumps({"t": time.strftime("%H:%M:%S"), "method": message.get("method"),
                              "ms": round((time.monotonic() - started) * 1000),
                              "error": bool(reply and (reply.get("error") or (reply.get("result") or {}).get("isError")))}) + "\n")
        if reply is not None and reply.get("id") is not None:
            sys.stdout.write(json.dumps(reply) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
