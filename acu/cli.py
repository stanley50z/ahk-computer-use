"""JSON CLI for ACU; stdout is reserved for the result."""

import argparse
import json
import sys

from . import tool
from .diagnostics import failure


# Return parse errors in the same JSON format as operation validation errors.
class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError(message)


def main(argv=None) -> int:
    """Dispatch CLI operations; runtime script failures retain their exit code."""
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stdin.reconfigure(encoding="utf-8")
    parser = Parser(prog="acu", description="Script-first computer use: batch an action chain in one execution")
    commands = parser.add_subparsers(dest="command", required=True)
    discovery = commands.add_parser("discover", help="Find bundled scripts and instructions")
    discovery.add_argument("query", nargs="?", default="")
    discovery.add_argument("--limit", type=int, default=10)
    description = commands.add_parser("describe", help="Read a capability contract and instructions")
    description.add_argument("id")
    execution = commands.add_parser("execute", help="Execute a whole script under ACU protections")
    source = execution.add_mutually_exclusive_group(required=True)
    source.add_argument("--code", help="Inline code; prefer --file - for secrets or multiline scripts")
    source.add_argument("--file", help="Script path, or - to read code from stdin")
    execution.add_argument("--engine", default="ahk")
    execution.add_argument("--args", nargs=argparse.REMAINDER, default=[], help="Arguments forwarded literally to A_Args (put last)")
    maintained = commands.add_parser("run", help="Run a maintained capability implementation")
    maintained.add_argument("id")
    maintained.add_argument("--params", default="{}", help="JSON object of capability parameters")
    tree = commands.add_parser("tree", help="Inspect an observed window's controls")
    tree.add_argument("target")
    tree.add_argument("--find", default="")
    tree.add_argument("--type", default="")
    tree.add_argument("--depth", type=int, default=25)
    tree.add_argument("--max", type=int, default=300)
    screenshot = commands.add_parser("screenshot", help="Capture a display, a window, or a rectangle")
    screenshot.add_argument("--mode", choices=("fullscreen", "app", "custom"), default="fullscreen")
    screenshot.add_argument("--target")
    screenshot.add_argument("--monitor", type=int, default=1)
    screenshot.add_argument("--rect", nargs=4, type=int)
    screenshot.add_argument("--out")
    screenshot.add_argument("--max", type=int, default=1280)
    for command in (execution, maintained, tree, screenshot):
        command.add_argument("--timeout", type=float, default=30)
    commands.add_parser("mcp", help="Serve MCP tools over stdio (no desktop session between calls)")

    try:
        args = vars(parser.parse_args(argv))
        command = args.pop("command")
        if command == "mcp":
            from .mcp_server import serve
            serve()
            return 0
        if command == "execute" and args["file"] == "-":
            args["code"] = sys.stdin.read()
            args["file"] = None
        if command == "run":
            args["parameters"] = json.loads(args.pop("params"))
        result = getattr(tool, command)(**args)
    except ValueError as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False))
        return 2
    except Exception as error:
        print(json.dumps(failure(error), ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return result.get("exit_code", 0)
