"""The native MCP approval bridge grants only the scenario's explicit app-use permission."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from bench.native_mcp import approval

from bench.run import ROOT


# A stdio MCP fixture checks the real bridge boundary without launching Windows automation.
def test_native_bridge_advertises_form_support_and_limits_approvals(tmp_path):
    server = tmp_path / 'server.py'
    server.write_text('''import json, sys
request=json.loads(sys.stdin.readline())
assert request['params']['capabilities']['elicitation']['form']=={}
print(json.dumps({'jsonrpc':'2.0','id':request['id'],'result':{'protocolVersion':'2025-06-18','capabilities':{},'serverInfo':{'name':'fixture','version':'1'}}}),flush=True)
for i,(app,connector,method) in enumerate([('calc.exe','computer-use','elicitation/create'),('passwords.exe','computer-use','elicitation/create'),('calc.exe','other','elicitation/create'),('calc.exe','computer-use','elicitation/create')]):
    meta={'connector_id':connector,'codex_approval_kind':'mcp_tool_call','riskLevel':'low','tool_params':{'app':app}}
    params={'mode':'form','message':'Allow app use','requestedSchema':{'type':'object'},'_meta':meta}
    if i==3: params['mode']='url'
    print(json.dumps({'jsonrpc':'2.0','id':100+i,'method':method,'params':params}),flush=True)
    response=json.loads(sys.stdin.readline())
    assert response['result']['action']==('accept' if i==0 else 'decline'),response
    print(json.dumps({'jsonrpc':'2.0','method':'notifications/message','params':{'data':str(i)}}),flush=True)
''',encoding='utf-8')
    config = tmp_path / 'bridge.json'
    config.write_text(json.dumps({'command':sys.executable,'args':[str(server)],'approved_apps':['calc.exe'],
                                 'log_path':str(tmp_path/'approvals.jsonl')}),encoding='utf-8')
    process = subprocess.Popen([sys.executable,str(ROOT/'bench/native_mcp.py'),str(config)],
                               stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8')
    try:
        process.stdin.write(json.dumps({'jsonrpc':'2.0','id':1,'method':'initialize','params':{'capabilities':{}}})+'\n')
        process.stdin.flush()
        reply=json.loads(process.stdout.readline())
        assert reply['id']==1 and reply['result']['serverInfo']['name']=='fixture'
        for i in range(4):
            assert json.loads(process.stdout.readline())['params']['data']==str(i)
        process.wait(timeout=10)
        assert process.returncode==0, process.stderr.read()
        log=[json.loads(line) for line in (tmp_path/'approvals.jsonl').read_text(encoding='utf-8').splitlines()]
        assert [r['action'] for r in log]==['accept','decline','decline','decline']
        assert log[0]['authorization']=='standing user approval; scenario app only'
    finally:
        if process.poll() is None:
            process.kill();process.wait(timeout=5)
        process.stdin.close();process.stdout.close();process.stderr.close()


# The classifier is the permission boundary used by the stdio bridge, including future SDK shape drift.
@pytest.mark.parametrize('change', ['missing-risk', 'high-risk', 'audio', 'other-request', 'extra-params', 'form-fields', 'missing-schema'])
def test_native_app_approval_fails_closed_on_unknown_or_sensitive_requests(change):
    params = {'mode': 'form', 'requestedSchema': {'type': 'object', 'properties': {}},
              '_meta': {'connector_id': 'computer-use', 'codex_approval_kind': 'mcp_tool_call',
                        'riskLevel': 'low', 'tool_params': {'app': 'calc.exe'}}}
    assert approval(params, ['calc.exe'])['action'] == 'accept'
    if change == 'missing-risk':
        del params['_meta']['riskLevel']
    elif change == 'high-risk':
        params['_meta']['riskLevel'] = 'high'
    elif change == 'audio':
        params['_meta']['tool_name'] = 'start_audio_recording'
    elif change == 'other-request':
        params['_meta']['codex_request_type'] = 'approval_request'
    elif change == 'extra-params':
        params['_meta']['tool_params']['operation'] = 'delete'
    elif change == 'form-fields':
        params['requestedSchema']['properties']['password'] = {'type': 'string'}
    elif change == 'missing-schema':
        del params['requestedSchema']
    assert approval(params, ['calc.exe'])['action'] == 'decline'


def test_native_bridge_cancels_late_server_elicitation_after_client_eof(tmp_path):
    server = tmp_path / 'late-server.py'
    server.write_text(
        'import json,sys,time\n'
        'for line in sys.stdin: pass\n'
        'print(json.dumps({"jsonrpc":"2.0","id":99,"method":"elicitation/create","params":{}}),flush=True)\n'
        'time.sleep(60)\n', encoding='utf-8')
    config = tmp_path / 'bridge.json'
    config.write_text(json.dumps({'command': sys.executable, 'args': [str(server)], 'approved_apps': ['calc.exe'],
                                 'log_path': str(tmp_path / 'approvals.jsonl')}), encoding='utf-8')
    result = subprocess.run([sys.executable, str(ROOT / 'bench/native_mcp.py'), str(config)],
                            input='', capture_output=True, text=True, encoding='utf-8', timeout=10)
    assert result.returncode == 0, result.stderr
    assert not result.stdout
    assert not (tmp_path / 'approvals.jsonl').exists(), 'disconnected clients must not authorize more work'
    assert not (tmp_path / 'approvals.crash.txt').exists()
