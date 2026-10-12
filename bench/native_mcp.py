"""Stdio MCP adapter for Pi: answer only preauthorized scenario-app form elicitations.

Tool calls/results are forwarded unchanged to the installed vendor node_repl. This
is not a desktop protocol implementation and never talks to the native helper.
"""

import json
import sys
import threading
import traceback
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bench.processes import OwnedProcessTree


# Only low-risk app-use approval for the exact scenario allowlist uses the user's standing authorization.
def approval(params, approved_apps):
    meta = params.get('_meta', {})
    app = meta.get('tool_params', {}).get('app')
    schema = params.get('requestedSchema', {})
    recognized_schema = (schema.get('type') == 'object' and not schema.get('properties')
                         and not schema.get('required') and set(schema) <= {'type', 'properties', 'required', 'additionalProperties'})
    accepted = (params.get('mode', 'form') == 'form' and recognized_schema
                and set(params) <= {'mode', 'message', 'requestedSchema', '_meta'}
                and meta.get('connector_id') == 'computer-use'
                and meta.get('codex_approval_kind') == 'mcp_tool_call'
                and meta.get('riskLevel') == 'low'
                and meta.get('tool_params') == {'app': app}
                and not meta.get('codex_request_type') and not meta.get('tool_name')
                and isinstance(app, str) and app.casefold() in {value.casefold() for value in approved_apps})
    return {'action': 'accept' if accepted else 'decline', 'content': {}}


# Relay one isolated native server, persisting every approval decision and crash without exposing credentials.
def main():
    config = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    log_path = Path(config['log_path'])
    tree = OwnedProcessTree()
    lock = threading.Lock()
    errors = []
    closing = threading.Event()
    try:
        process = tree.spawn([config['command'], *config['args']], stdin=-1, stdout=-1, stderr=sys.stderr,
                             text=True, encoding='utf-8')

        def send(message):
            with lock:
                if closing.is_set():
                    return False  # Client EOF cancels late server requests; do not approve after disconnect.
                process.stdin.write(json.dumps(message, ensure_ascii=False) + '\n')
                process.stdin.flush()
                return True

        def forward_client():
            try:
                for line in sys.stdin:
                    message = json.loads(line)
                    if message.get('method') == 'initialize':
                        message.setdefault('params', {}).setdefault('capabilities', {})['elicitation'] = {'form': {}}
                    send(message)
                with lock:
                    closing.set()
                    process.stdin.close()
            except (BrokenPipeError, OSError):
                if process.poll() is None:
                    errors.append(traceback.format_exc())
                    process.terminate()
            except Exception:
                errors.append(traceback.format_exc())
                process.terminate()

        reader = threading.Thread(target=forward_client, daemon=True)
        reader.start()
        for line in process.stdout:
            if closing.is_set():
                break
            message = json.loads(line)
            if message.get('method') == 'elicitation/create' and 'id' in message:
                params = message.get('params', {})
                result = approval(params, config['approved_apps'])
                record = {'ts': datetime.now(timezone.utc).isoformat(), 'action': result['action'],
                          'app': params.get('_meta', {}).get('tool_params', {}).get('app'),
                          'mode': params.get('mode', 'form'), 'metadata': params.get('_meta', {}),
                          'requested_schema': params.get('requestedSchema'),
                          'authorization': 'standing user approval; scenario app only'}
                with log_path.open('a', encoding='utf-8') as log:
                    log.write(json.dumps(record, ensure_ascii=False) + '\n')
                send({'jsonrpc': '2.0', 'id': message['id'], 'result': result})
            else:
                sys.stdout.write(line)
                sys.stdout.flush()
        if closing.is_set():
            return
        code = process.wait(timeout=10)
        if errors:
            raise RuntimeError('\n'.join(errors))
        if code:
            raise RuntimeError(f'native MCP server exited {code}')
    except Exception:
        log_path.with_suffix('.crash.txt').write_text(traceback.format_exc(), encoding='utf-8')
        raise
    finally:
        tree.stop()


if __name__ == '__main__':
    sys.stdin.reconfigure(encoding='utf-8')
    sys.stdout.reconfigure(encoding='utf-8')
    main()
