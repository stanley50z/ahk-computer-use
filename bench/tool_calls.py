"""The shared transcript record consumed by benchmark measurement and audits."""
from typing import NotRequired, TypedDict

type Json = str | int | float | bool | None | list[Json] | dict[str, Json]


# Adapters retain incomplete evidence; consumers must not infer success from a missing result.
class ToolCall(TypedDict):
    id: str
    name: str
    arguments: Json
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


# Route and conduct scans use decoded arguments, retaining real line breaks.
def argument_text(arguments: Json) -> str:
    if isinstance(arguments, dict):
        return '\n'.join(str(value) for value in arguments.values() if value is not None)
    return '' if arguments is None else str(arguments)


# Construct one serializable record without discarding missing timing or uncertain success.
def tool_call(call_id, name, arguments, start, end, result, is_error, *, matched=True, completed=True, truncated=False) -> ToolCall:
    return {'id': call_id, 'name': name, 'arguments': arguments, 'text': argument_text(arguments),
            'result': result, 'start_s': start, 'end_s': end,
            'duration_s': end - start if start is not None and end is not None else None,
            'is_error': is_error, 'matched': matched, 'completed': completed, 'truncated': truncated}


# Historical metrics, conduct scans and task grading include completed requests only.
def completed_calls(calls: list[ToolCall]) -> list[ToolCall]:
    return [call for call in calls if call.get('completed', True) and call.get('matched', True)]
