"""The shared transcript record consumed by benchmark measurement and audits."""
from typing import Literal, NotRequired, TypedDict

type Json = str | int | float | bool | None | list[Json] | dict[str, Json]


# Each harness adapter maps its own tool names and parameters onto one of these requests; consumers read only these.
class ReadRequest(TypedDict):
    kind: Literal['read']


class WriteRequest(TypedDict):
    kind: Literal['write']
    path: str
    content: str


class Replacement(TypedDict):
    old: str
    new: str


# Every replacement matches the original file; replace_all lets one match several places.
class EditRequest(TypedDict):
    kind: Literal['edit']
    path: str
    edits: list[Replacement]
    replace_all: bool


class ShellRequest(TypedDict):
    kind: Literal['shell']
    command: str


# One cell run in a persistent JavaScript session such as node_repl.
class JavaScriptCellRequest(TypedDict):
    kind: Literal['javascript_cell']
    code: str


# A call that manages the JavaScript session without running a cell; resets is true when it drops session state.
class JavaScriptRuntimeRequest(TypedDict):
    kind: Literal['javascript_runtime']
    resets: bool


# The adapter cannot say what was requested: an unrecognised tool, arguments that do not fit the tool's
# parameters, or a result whose request never arrived. The raw name and arguments stay on the call as evidence.
class UnknownRequest(TypedDict):
    kind: Literal['unknown']


type Request = (ReadRequest | WriteRequest | EditRequest | ShellRequest
                | JavaScriptCellRequest | JavaScriptRuntimeRequest | UnknownRequest)


# Adapters retain incomplete evidence; consumers must not infer success from a missing result.
class ToolCall(TypedDict):
    id: str
    name: str
    arguments: Json
    request: Request
    text: str
    result: Json
    start_s: float | None
    end_s: float | None
    duration_s: float | None
    is_error: bool | None
    matched: bool
    completed: bool
    truncated: bool
    reported_duration_ms: NotRequired[float | None]
    status: NotRequired[str | None]
    error: NotRequired[Json]


# The node_repl MCP server's tools, which Pi and Codex both host under their own prefixes; each adapter strips its
# prefix and passes the bare tool name here.
def node_repl_request(tool: str, arguments: Json) -> Request:
    match tool, arguments:
        case 'js', {'code': str(code)}:
            return {'kind': 'javascript_cell', 'code': code}
        case 'js_add_node_module_dir', {'path': str()}:
            return {'kind': 'javascript_runtime', 'resets': False}
        case 'js_reset' | 'turn_ended', dict():
            return {'kind': 'javascript_runtime', 'resets': tool == 'js_reset'}
    return {'kind': 'unknown'}


# Route and conduct scans use decoded arguments, retaining real line breaks.
def argument_text(arguments: Json) -> str:
    if isinstance(arguments, dict):
        return '\n'.join(str(value) for value in arguments.values() if value is not None)
    return '' if arguments is None else str(arguments)


# Construct one serializable record without discarding missing timing or uncertain success.
def tool_call(call_id: str, name: str, arguments: Json, request: Request, start: float | None, end: float | None,
              result: Json, is_error: bool | None, *, matched=True, completed=True, truncated=False) -> ToolCall:
    return {'id': call_id, 'name': name, 'arguments': arguments, 'request': request, 'text': argument_text(arguments),
            'result': result, 'start_s': start, 'end_s': end,
            'duration_s': end - start if start is not None and end is not None else None,
            'is_error': is_error, 'matched': matched, 'completed': completed, 'truncated': truncated}


# Historical metrics, conduct scans and task grading include completed requests only.
def completed_calls(calls: list[ToolCall]) -> list[ToolCall]:
    return [call for call in calls if call.get('completed', True) and call.get('matched', True)]
