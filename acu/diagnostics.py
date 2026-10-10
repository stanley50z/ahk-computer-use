"""Persist transport failures without recording request arguments or script text."""

import json
import logging
import traceback
from datetime import datetime

from .run import acu_home


def failure(error: Exception) -> dict:
    """Return an explicit tool error with a persistent Python stack trace for diagnosis."""
    stamp = datetime.now().astimezone()
    reports = acu_home() / "crashes"
    report = reports / f"{stamp.strftime('%Y%m%d-%H%M%S-%f')}-tool.json"
    try:
        reports.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps({
            "ts": stamp.isoformat(timespec="milliseconds"),
            "error": str(error), "traceback": "".join(traceback.format_exception(error)),
        }, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as diagnostic_error:
        return {"error": str(error), "diagnostic_error": f"could not persist crash report at {report}: {diagnostic_error}"}
    return {"error": str(error), "artifacts": {"crash_report": str(report)}}


def configure_mcp_logging() -> None:
    """Keep SDK server diagnostics in a file as well as stderr; stdio stdout stays protocol-only."""
    logs = acu_home() / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(logs / "mcp.log", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    handler.setLevel(logging.INFO)
    logging.getLogger("mcp").addHandler(handler)
