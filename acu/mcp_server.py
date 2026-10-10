"""Thin stdio MCP transport: the shared operations own execution and capability discovery."""

import base64
import json
from functools import partial
from pathlib import Path

import anyio
from mcp.server.fastmcp import FastMCP
from mcp.types import CallToolResult, ImageContent, TextContent, ToolAnnotations

from . import tool
from .diagnostics import configure_mcp_logging, failure

server = FastMCP(
    "ACU",
    instructions=(
        "Script-first computer use: execute one predictable action chain per call, not one call per button. "
        "Discover maintained scripts and instructions, describe the selected capability, then run it or "
        "draft a script and execute it. Inspect tree or screenshot when states are unknown. "
        "Execution success is not verified effect; print and observe the user's postcondition. "
        "Only AHK is currently supported. Desktop calls are serialized; a busy error means inspect before retrying. "
        "Discovery is read-only and grants no permission to operate the desktop."
    ),
)
READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
EXECUTION = ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=False, openWorldHint=True)
OBSERVATION = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=False, openWorldHint=True)


def _call(operation, **arguments) -> CallToolResult:
    """Return matching structured/text facts, plus a screenshot image; failures set isError."""
    try:
        result = operation(**arguments)
        failed = "error" in result or result.get("exit_code", 0) != 0
        content = [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]
        if not failed and "screenshot" in result:
            image = Path(result["screenshot"]["saved"]).read_bytes()
            content.append(ImageContent(type="image", data=base64.b64encode(image).decode("ascii"), mimeType="image/png"))
        return CallToolResult(content=content, structuredContent=result, isError=failed)
    except ValueError as error:
        result = {"error": str(error)}
    except Exception as error:
        result = failure(error)
    return CallToolResult(content=[TextContent(type="text", text=json.dumps(result, ensure_ascii=False))],
                          structuredContent=result, isError=True)


async def _invoke(operation, **arguments) -> CallToolResult:
    """Keep stdio responsive while the launcher waits; cancellation waits for its bounded execution."""
    return await anyio.to_thread.run_sync(partial(_call, operation, **arguments))


@server.tool(annotations=READ_ONLY, structured_output=False)
async def discover(query: str = "", limit: int = 10) -> CallToolResult:
    """Find compact summaries of bundled scripts and instruction-only capabilities."""
    return await _invoke(tool.discover, query=query, limit=limit)


@server.tool(annotations=READ_ONLY, structured_output=False)
async def describe(id: str) -> CallToolResult:
    """Read one capability's instructions, prerequisites and parameter contract."""
    return await _invoke(tool.describe, id=id)


@server.tool(annotations=EXECUTION, structured_output=False)
async def execute(code: str | None = None, file: str | None = None, engine: str = "ahk",
                  timeout: float = 30, args: list[str] | None = None) -> CallToolResult:
    """Execute a whole AHK action chain, inline or from a file, under ACU's launcher protections."""
    return await _invoke(tool.execute, code=code, file=file, engine=engine, timeout=timeout, args=args)


@server.tool(annotations=EXECUTION, structured_output=False)
async def run(id: str, parameters: dict | None = None, timeout: float = 30) -> CallToolResult:
    """Run a maintained script by capability ID and parameters; never generate code as a fallback."""
    return await _invoke(tool.run, id=id, parameters=parameters, timeout=timeout)


@server.tool(annotations=OBSERVATION, structured_output=False)
async def tree(target: str, find: str = "", type: str = "", depth: int = 25,
               max: int = 300, timeout: float = 30) -> CallToolResult:
    """Inspect an observed window's controls, full values, supported actions and screen bounds."""
    return await _invoke(tool.tree, target=target, find=find, type=type, depth=depth, max=max, timeout=timeout)


@server.tool(annotations=EXECUTION, structured_output=False)
async def screenshot(mode: str = "fullscreen", target: str | None = None, monitor: int = 1,
                     rect: list[int] | None = None, out: str | None = None, max: int = 1280,
                     timeout: float = 30) -> CallToolResult:
    """Capture a display, window or rectangle and return the PNG; an explicit out path can overwrite a file."""
    return await _invoke(tool.screenshot, mode=mode, target=target, monitor=monitor,
                         rect=rect, out=out, max=max, timeout=timeout)


def serve() -> None:
    """Let the calling harness own the stdio server lifetime; no independently launched daemon."""
    configure_mcp_logging()
    server.run(transport="stdio")
