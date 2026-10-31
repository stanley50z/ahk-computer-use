"""The acu command: run AHK scripts, or inspect snippets and history without desktop access."""

import argparse
import json
import sys

from . import history, snippets, tool
from .diagnostics import failure


# Return parse errors in the same JSON format as operation validation errors.
class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError(message)


def main(argv=None) -> int:
    """Dispatch read-only discovery or preserve the launcher's run/arguments contract."""
    sys.stdout.reconfigure(encoding="utf-8")
    parser = Parser(prog="acu", description="Run AutoHotkey v2 scripts or list saved app snippets")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="Run an existing AHK script file")
    run.add_argument("script", help="Path to the script file")
    run.add_argument("--timeout", type=float, default=30)

    snippet_command = commands.add_parser("snippets", help="Find saved app snippets without using the desktop")
    snippet_commands = snippet_command.add_subparsers(dest="snippet_command", required=True)
    listing = snippet_commands.add_parser("list", help="List snippets for an app, optionally ranked by keywords")
    listing.add_argument("app")
    listing.add_argument("keywords", nargs="*")

    history_command = commands.add_parser("history", help="Summarize ACU activity in a session",
                                          description=history.RULES)
    history_command.add_argument("session_file", help="Pi, Codex or Claude Code JSONL session file")

    try:
        arguments = list(sys.argv[1:] if argv is None else argv)
        forwarded = []
        if arguments[:1] == ["run"]:
            arguments, forwarded = tool.split_script_args(arguments)
        options = parser.parse_args(arguments)
        if options.command == "history":
            print(history.summarize(options.session_file))
            return 0
        if options.command == "snippets":
            print(snippets.list_for_app(options.app, options.keywords))
            return 0
        result = tool.run(options.script, options.timeout, forwarded)
    except ValueError as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False))
        return 2
    except Exception as error:
        print(json.dumps(failure(error), ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return result["exit_code"]
