"""The acu command: run one AHK script file and return execution facts as JSON."""

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
    """Use the original launcher's script/timeout/arguments contract and preserve its exit code."""
    sys.stdout.reconfigure(encoding="utf-8")
    parser = Parser(prog="acu", description="Run one AutoHotkey v2 script file under ACU protections")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="Run an existing AHK script file")
    run.add_argument("script", help="Path to the script file")
    run.add_argument("--timeout", type=float, default=30)

    try:
        arguments = list(sys.argv[1:] if argv is None else argv)
        forwarded = []
        if "--" in arguments:
            boundary = arguments.index("--")
            forwarded = arguments[boundary + 1:]
            arguments = arguments[:boundary]
        options = parser.parse_args(arguments)
        result = tool.run(options.script, options.timeout, forwarded)
    except ValueError as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False))
        return 2
    except Exception as error:
        print(json.dumps(failure(error), ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return result["exit_code"]
