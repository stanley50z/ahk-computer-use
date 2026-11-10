"""Token and runtime scoring uses generated payloads, not model-response or end-to-end latency."""

import json
from pathlib import Path

import pytest

from bench.efficiency import measure_efficiency
from bench.tool_calls import tool_call


# Measurement reads only the adapter's request; the raw name and arguments are evidence the tests leave generic.
def call(identity, request, start, end, arguments=None):
    return tool_call(identity, f"raw-{request['kind']}", arguments, request, start, end, None, False)


def write(path, content):
    return {'kind': 'write', 'path': path, 'content': content}


def edit(path, *replacements, replace_all=False):
    return {'kind': 'edit', 'path': path, 'edits': [{'old': old, 'new': new} for old, new in replacements],
            'replace_all': replace_all}


def shell(command):
    return {'kind': 'shell', 'command': command}


def cell(code):
    return {'kind': 'javascript_cell', 'code': code}


def metrics(tools, output=1000, complete=True):
    return {'tools': tools, 'tokens': {'input_uncached': 100, 'cache_read': 200, 'cache_write': 0,
            'output_including_reasoning': output, 'reasoning_subset': 100, 'total': 300+output},
            'agent_completed': complete, 'token_counts_complete': complete}


# The public measurement follows route facts supplied by the arm table.
def test_arm_table_route_controls_direct_and_captured_helper_attribution(monkeypatch):
    from dataclasses import replace
    from bench.arms import ARM_TABLE

    arm = ARM_TABLE['pi-acu']
    route = replace(arm.route, executable='desktop-tool', subcommand='execute')
    monkeypatch.setattr('bench.efficiency.ARM_TABLE', {'pi-acu': replace(arm, route=route)})
    tools = [
        call('source', write('draw.ahk', 'Click(1, 2)'), 1, 2),
        call('direct', shell('desktop-tool.exe execute draw.ahk'), 3, 4),
        call('helper', write('helper.py', "import subprocess\nsubprocess.run(['desktop-tool', 'execute', 'draw.ahk'])\n"), 5, 6),
        call('indirect', shell('python helper.py'), 7, 8),
        call('old-route', shell('acu run draw.ahk'), 9, 10),
        call('quoted', shell('echo "desktop-tool execute draw.ahk"'), 11, 12),
    ]
    result = measure_efficiency(metrics(tools), 'pi-acu')
    assert [item['id'] for item in result['computer_use']['calls']] == ['direct', 'indirect']
    assert {item['call_id'] for item in result['code_tokens']['payloads']} == {'source', 'direct', 'helper', 'indirect'}


# A shared namespace change applies to direct calls and remembered JavaScript helpers.
def test_arm_table_namespace_controls_javascript_attribution(monkeypatch):
    from dataclasses import replace
    from bench.arms import ARM_TABLE

    arm = ARM_TABLE['pi-computer-use']
    route = replace(arm.route, javascript_namespace='desktop')
    monkeypatch.setattr('bench.efficiency.ARM_TABLE', {arm.id: replace(arm, route=route)})
    tools = [
        call('define', cell('globalThis.tap=async()=>{await desktop.click()}; await tap()'), 1, 2),
        call('repeat', cell('await tap()'), 3, 4),
        call('old-route', cell('await sky.click()'), 5, 6),
        call('quoted', cell('console.log("desktop.click()")'), 7, 8),
    ]
    result = measure_efficiency(metrics(tools), arm.id)
    assert [item['id'] for item in result['computer_use']['calls']] == ['define', 'repeat']


# Action exclusions come from the route in both direct commands and captured shell helpers.
def test_arm_table_exclusions_control_shell_helper_attribution(monkeypatch):
    from dataclasses import replace
    from bench.arms import ARM_TABLE

    arm = ARM_TABLE['pi-cua']
    route = replace(arm.route, executable='desktop-driver', excluded_subcommands=('inspect-help',))
    monkeypatch.setattr('bench.efficiency.ARM_TABLE', {arm.id: replace(arm, route=route)})
    tools = [
        call('source', write('helper.sh', 'desktop-driver.exe click {}'), 1, 2),
        call('indirect', shell('bash helper.sh'), 3, 4),
        call('direct', shell('desktop-driver click {}'), 5, 6),
        call('help', shell('desktop-driver inspect-help'), 7, 8),
        call('help-source', write('help.sh', 'desktop-driver inspect-help'), 9, 10),
        call('help-indirect', shell('bash help.sh'), 11, 12),
    ]
    result = measure_efficiency(metrics(tools), arm.id)
    assert [item['id'] for item in result['computer_use']['calls']] == ['indirect', 'direct']
    assert {item['call_id'] for item in result['code_tokens']['payloads']} == {'source', 'indirect', 'direct'}


def test_direct_calls_use_output_denominator_and_union_of_call_intervals():
    tools = [call('a', shell('acu run a.ahk'), 10, 12),
             call('b', shell('acu run b.ahk'), 11, 14),
             call('c', write('result.json', '{"input_method":"acu run"}'), 15, 16)]
    result = measure_efficiency(metrics(tools), 'pi-acu')
    assert result['api_tokens']['total'] == 1300
    assert result['code_tokens']['denominator_output_including_reasoning'] == 1000
    assert result['code_tokens']['output_share_percent_estimate'] == pytest.approx(result['code_tokens']['estimated_tokens'] / 10)
    assert result['computer_use']['call_count'] == 2
    assert result['computer_use']['busy_seconds'] == 4
    assert result['computer_use']['sum_call_seconds'] == 5
    assert [x['duration_s'] for x in result['computer_use']['calls']] == [2, 3]
    assert result['code_tokens']['encoding'] == 'o200k_base'
    assert 'task_s' not in result and 'model_response_s' not in result


def test_generated_script_is_counted_once_when_replayed_and_removed_before_analysis():
    tools = [call('write-script', write('draw.ahk', 'SendText "hello"'), 1, 2),
             call('first', shell('acu run draw.ahk'), 4, 5),
             call('second', shell('acu run draw.ahk'), 6, 7),
             call('cleanup', shell('rm draw.ahk'), 8, 9)]
    result = measure_efficiency(metrics(tools), 'claude-acu')
    payloads = result['code_tokens']['payloads']
    assert len([p for p in payloads if p['call_id'] == 'write-script']) == 1
    assert {p['call_id'] for p in payloads} == {'write-script', 'first', 'second'}
    assert result['computer_use']['call_count'] == 2


def test_result_json_mention_is_not_a_computer_use_call():
    tools = [call('actual', shell('cua-driver get_window_state \'{"pid":12}\''), 1, 3),
             call('evidence', shell('cat > result.json <<\'EOF\'\n{"input_method":"cua-driver click"}\nEOF\npython -m json.tool result.json'), 8, 10)]
    result = measure_efficiency(metrics(tools), 'claude-cua')
    assert result['computer_use']['call_count'] == 1
    assert result['computer_use']['busy_seconds'] == 2
    assert {p['call_id'] for p in result['code_tokens']['payloads']} == {'actual'}


def test_codex_computer_use_follows_repl_helpers_but_excludes_evidence_writes():
    tools = [call('define', cell('globalThis.tap=async()=>{await sky.click({window:w,x:1,y:2})}; await tap()'), 1, 2),
             call('replay', cell('await tap()'), 5, 7),
             call('evidence', cell('await fs.writeFile("result.json", JSON.stringify({input_method:"sky.click"}))'), 8, 9)]
    result = measure_efficiency(metrics(tools), 'pi-computer-use')
    assert result['runtime'] == 'Codex computer use'
    assert result['computer_use']['call_count'] == 2
    assert result['computer_use']['busy_seconds'] == 3
    assert {p['call_id'] for p in result['code_tokens']['payloads']} == {'define', 'replay'}


def test_incomplete_or_unknown_output_usage_has_no_percentage():
    tools = [call('a', shell('acu run a.ahk'), 1, 2)]
    assert measure_efficiency(metrics(tools, complete=False), 'pi-acu')['code_tokens']['output_share_percent_estimate'] is None
    assert measure_efficiency(metrics(tools, output=0), 'pi-acu')['code_tokens']['output_share_percent_estimate'] is None
    unknown = metrics(tools); unknown['tokens'] = None
    assert measure_efficiency(unknown, 'pi-acu')['api_tokens'] is None
    assert measure_efficiency(unknown, 'pi-acu')['code_tokens']['output_share_percent_estimate'] is None


def test_imported_cua_helpers_survive_moves_and_cli_aliases():
    source = 'import subprocess\nDRIVER = "cua-driver"\ndef act():\n    return subprocess.run([DRIVER, "click", "{}"])\n'
    tools = [
        call('ui', shell("cat > ui.py <<'PY'\n" + source + "PY\n"), 1, 2),
        call('pen', write('pen.py', 'from ui import act\nact()\n'), 3, 4),
        call('draw', shell('python pen.py'), 5, 9),
        call('again', shell("python -c 'from pen import act; act()'"), 11, 13),
        call('move', shell('mkdir evidence; mv ui.py pen.py evidence/'), 14, 15),
    ]
    result = measure_efficiency(metrics(tools), 'pi-cua')
    assert result['computer_use']['call_count'] == 2
    assert result['computer_use']['busy_seconds'] == 6
    assert {p['call_id'] for p in result['code_tokens']['payloads']} == {'ui', 'pen', 'draw', 'again'}


def test_nested_python_subprocess_helper_is_attributed_without_executing_dynamic_arguments():
    tools = [
        call('ui', write('scratch/act.py', "import subprocess,sys\nsubprocess.run(['cua-driver',sys.argv[1],sys.argv[2]])\n"), 1, 2),
        call('pen', write('scratch/pen.py', "import subprocess,sys,json\nsubprocess.run([sys.executable,'scratch/act.py',tool,json.dumps(args)])\n"), 3, 4),
        call('draw', shell('python scratch/pen.py 0'), 5, 8),
        call('again', shell('python scratch/pen.py 1'), 9, 11),
    ]
    result = measure_efficiency(metrics(tools), 'pi-cua')
    assert result['computer_use']['attribution_complete']
    assert result['computer_use']['call_count'] == 2
    assert result['computer_use']['busy_seconds'] == 5
    assert {p['call_id'] for p in result['code_tokens']['payloads']} == {'ui', 'pen', 'draw', 'again'}


def test_shell_substitution_keeps_quoted_python_source_separate_from_closing_parenthesis():
    command = 'id=$(cua-driver call get_window_state \'{}\' | python -I -c "import json,sys;print(json.load(sys.stdin)[\'capture_id\'])"); echo "$id"'
    result = measure_efficiency(metrics([call('capture', shell(command), 1, 4)]), 'claude-cua')
    assert result['computer_use']['attribution_complete']
    assert result['computer_use']['call_count'] == 1
    assert result['computer_use']['busy_seconds'] == 3


def test_shell_helpers_environment_prefixes_and_loop_bodies_are_attributed_once_per_host_call():
    tools = [
        call('shot', write('shot.sh', "cua-driver call get_window_state '{}'\n"), 1, 2),
        call('ui', write('ui.py', "import subprocess\nsubprocess.run(['cua-driver','click','{}'])\n"), 3, 4),
        call('capture', shell('sh shot.sh'), 5, 7),
        call('loop', shell('for i in 1 2; do WIN=10 python ui.py; done; sh shot.sh'), 8, 12),
    ]
    result = measure_efficiency(metrics(tools), 'claude-cua')
    assert result['computer_use']['attribution_complete']
    assert result['computer_use']['call_count'] == 2
    assert result['computer_use']['busy_seconds'] == 6
    assert {p['call_id'] for p in result['code_tokens']['payloads']} == {'shot', 'ui', 'capture', 'loop'}


@pytest.mark.parametrize('replacement', ['cua-driver', 'echo'])
def test_literal_python_helper_copy_preserves_provenance_and_follows_replaced_runtime(replacement):
    tools = [
        call('source', write('act.py', "import subprocess\nsubprocess.run(['cua-driver','click','{}'])\n"), 1, 2),
        call('copy', shell('python -c "from pathlib import Path;p=Path(\'act.py\').read_text();Path(\'dlg.py\').write_text(p.replace(\'cua-driver\',\'' + replacement + '\'))"'), 3, 4),
        call('run', shell('python dlg.py'), 5, 8),
    ]
    result = measure_efficiency(metrics(tools), 'pi-cua')
    assert result['computer_use']['attribution_complete']
    if replacement == 'cua-driver':
        assert result['computer_use']['call_count'] == 1
        assert result['computer_use']['busy_seconds'] == 3
        assert {p['call_id'] for p in result['code_tokens']['payloads']} == {'source', 'copy', 'run'}
    else:
        assert result['computer_use']['call_count'] == 0
        assert result['code_tokens']['payloads'] == []


@pytest.mark.parametrize('operands', [
    "'s/, 0)/, 1600)/' s.ahk",
    "-e 's/, 0)/, 1600)/' -- s.ahk",
    "--expression='s/, 0)/, 1600)/' s.ahk",
])
def test_sed_expression_operands_do_not_include_a_filename_starting_with_s(operands):
    tools = [
        call('source', write('s.ahk', 'Click(1, 0)\n'), 1, 2),
        call('patch', shell('sed -i ' + operands), 3, 4),
        call('run', shell('acu run s.ahk'), 5, 6),
    ]
    result = measure_efficiency(metrics(tools), 'claude-acu')
    assert result['computer_use']['attribution_complete']
    assert result['code_tokens']['output_share_percent_estimate'] is not None
    assert {p['call_id'] for p in result['code_tokens']['payloads']} == {'source', 'patch', 'run'}


@pytest.mark.parametrize(('operands', 'expected_calls'), [
    ("s.sh -e 's/cua-driver/echo/'", 0),
    ("'s/cua-driver/echo/' -e 's/noop/noop/' s.sh", 1),
])
def test_sed_explicit_program_options_determine_bare_operands_even_when_they_come_later(operands, expected_calls):
    tools = [
        call('source', write('s.sh', 'cua-driver click {}\n'), 1, 2),
        call('patch', shell('sed -i ' + operands), 3, 4),
        call('run', shell('bash s.sh'), 5, 6),
    ]
    result = measure_efficiency(metrics(tools), 'claude-cua')
    assert result['computer_use']['attribution_complete']
    assert result['computer_use']['call_count'] == expected_calls


def test_literal_sed_replacement_removes_the_old_runtime_route_from_helper_state():
    tools = [
        call('source', write('ui.py', "import subprocess\nsubprocess.run(['cua-driver','click','{}'])\n"), 1, 2),
        call('patch', shell("sed -i 's/cua-driver/echo/g' ui.py"), 3, 4),
        call('run', shell('python ui.py'), 5, 6),
    ]
    result = measure_efficiency(metrics(tools), 'pi-cua')
    assert result['computer_use']['attribution_complete']
    assert result['computer_use']['call_count'] == 0
    assert result['code_tokens']['payloads'] == []


def test_captured_shell_patches_keep_the_follow_on_host_execution_and_source_provenance():
    tools = json.loads((Path(__file__).parent / 'fixtures/estimator-source-patches.json').read_text(encoding='utf-8'))
    result = measure_efficiency(metrics(tools), 'claude-cua')
    assert [c['id'] for c in result['computer_use']['calls']] == [
        'toolu_01PLfvUr7aK4BHrzmk7N2TSi',
        'toolu_01Ddh3RCetRDbHmZbcC2SZz7',
        'toolu_01W5s3uSaNhUiCjFfJbDJdaS',
    ]
    assert result['computer_use']['busy_seconds'] == pytest.approx(65.4358812)
    assert result['computer_use']['attribution_complete']
    assert result['code_tokens']['estimated_tokens'] == 805
    assert [(p['call_id'], p['estimated_tokens']) for p in result['code_tokens']['payloads']] == [
        ('toolu_01Ddh3RCetRDbHmZbcC2SZz7', 129),
        ('toolu_01PLfvUr7aK4BHrzmk7N2TSi', 587),
        ('toolu_01W5s3uSaNhUiCjFfJbDJdaS', 89),
    ]


@pytest.mark.parametrize('program', [
    's/^cua-driver.*/echo removed/',
    's/cua-driver click {}$/echo/; s/echo/printf/',
    's/cua-driver/echo/g',
])
def test_supported_sed_program_rechecks_the_route_after_replacing_it(program):
    tools = [
        call('source', write('s.sh', 'cua-driver click {}\n'), 1, 2),
        call('patch', shell(f"sed -i '{program}' s.sh; bash s.sh"), 3, 4),
    ]
    result = measure_efficiency(metrics(tools), 'claude-cua')
    assert result['computer_use']['attribution_complete']
    assert result['computer_use']['call_count'] == 0
    assert result['code_tokens']['payloads'] == []


@pytest.mark.parametrize('operands', [
    "'s/^cua-driver.*$/echo removed/' s.sh",
    "-E 's/cua-driver/echo/' s.sh",
    "-f rules.sed s.sh",
    "--file=rules.sed s.sh",
    "-e 's/cua-driver/echo/; 1d' s.sh",
    "'s/^cua-driver.*/echo\n/' s.sh",
])
def test_unsupported_sed_mutations_leave_an_unresolved_execution_not_a_stale_route(operands):
    tools = [
        call('source', write('s.sh', 'cua-driver click {}\n'), 1, 2),
        call('patch', shell('sed -i ' + operands), 3, 4),
        call('run', shell('bash s.sh'), 5, 6),
    ]
    result = measure_efficiency(metrics(tools), 'claude-cua')
    assert result['computer_use']['call_count'] == 0
    assert not result['computer_use']['attribution_complete']
    assert result['code_tokens']['output_share_percent_estimate'] is None
    assert any(note['call_id'] == 'patch' and 'unsupported in-place' in note['reason']
               for note in result['code_tokens']['review_notes'])
    assert any(note['call_id'] == 'run' and 'source unavailable' in note['reason']
               for note in result['code_tokens']['review_notes'])


def test_uncaptured_nested_helper_keeps_attribution_explicitly_unknown():
    tools = [
        call('source', write('pen.py', "import subprocess,sys\nsubprocess.run([sys.executable,'missing.py'])\n"), 1, 2),
        call('run', shell('python pen.py'), 3, 4),
    ]
    result = measure_efficiency(metrics(tools), 'pi-cua')
    assert not result['computer_use']['attribution_complete']
    assert 'captured source unavailable' in result['code_tokens']['review_notes'][0]['reason']
    assert result['code_tokens']['output_share_percent_estimate'] is None


@pytest.mark.parametrize('mutation', [
    'python -c "with open(\'ui.py\',\'w\') as f: f.write(\'print(1)\')"',
    "sed -i '2d' ui.py",
])
def test_unreplayed_source_mutation_invalidates_stale_helper_attribution(mutation):
    tools = [
        call('source', write('ui.py', "import subprocess\nsubprocess.run(['cua-driver','click','{}'])\n"), 1, 2),
        call('patch', shell(mutation), 3, 4),
        call('run', shell('python ui.py'), 5, 6),
    ]
    result = measure_efficiency(metrics(tools), 'pi-cua')
    assert not result['computer_use']['attribution_complete']
    assert result['computer_use']['call_count'] == 0
    assert result['code_tokens']['output_share_percent_estimate'] is None


def test_shell_helper_with_generated_child_source_requires_review():
    tools = [
        call('ui', write('ui.py', "import subprocess\nsubprocess.run(['cua-driver','click','{}'])\n"), 1, 2),
        call('wrapper', write('wrapper.sh', "cat > ui.py <<'PY'\nprint(1)\nPY\npython ui.py\n"), 3, 4),
        call('run', shell('sh wrapper.sh'), 5, 6),
    ]
    result = measure_efficiency(metrics(tools), 'pi-cua')
    assert not result['computer_use']['attribution_complete']


def test_shell_helper_inline_python_rewrite_does_not_certify_a_stale_child():
    tools = [
        call('ui', write('ui.py', "import subprocess\nsubprocess.run(['cua-driver','click','{}'])\n"), 1, 2),
        call('wrapper', write('wrapper.sh', 'python -c "from pathlib import Path;Path(\'ui.py\').write_text(\'print(1)\')"\npython ui.py\n'), 3, 4),
        call('run', shell('sh wrapper.sh'), 5, 6),
    ]
    result = measure_efficiency(metrics(tools), 'pi-cua')
    assert not result['computer_use']['attribution_complete']
    assert result['computer_use']['call_count'] == 0


def test_python_shell_string_and_condition_prefix_preserve_helper_routes():
    tools = [
        call('ui', write('ui.py', "import subprocess\nsubprocess.run(['cua-driver','click','{}'])\n"), 1, 2),
        call('outer', write('outer.py', "import subprocess\nsubprocess.run('python ui.py',shell=True)\n"), 3, 4),
        call('run', shell('if python outer.py; then echo ok; fi'), 5, 8),
    ]
    result = measure_efficiency(metrics(tools), 'pi-cua')
    assert result['computer_use']['attribution_complete']
    assert result['computer_use']['call_count'] == 1
    assert {p['call_id'] for p in result['code_tokens']['payloads']} == {'ui','outer','run'}


def test_dot_sourced_shell_helper_and_os_system_routes_are_captured():
    tools = [
        call('shot', write('shot.sh', "cua-driver call get_window_state '{}'\n"), 1, 2),
        call('outer', write('outer.py', "import os\nos.system('sh shot.sh')\n"), 3, 4),
        call('dot', shell('. shot.sh'), 5, 6),
        call('python', shell('python outer.py'), 7, 9),
    ]
    result = measure_efficiency(metrics(tools), 'pi-cua')
    assert result['computer_use']['attribution_complete']
    assert result['computer_use']['call_count'] == 2
    assert result['computer_use']['busy_seconds'] == 3


@pytest.mark.parametrize('command', ['timeout 30 cua-driver click {}', 'uv run ui.py'])
def test_unresolved_execution_wrapper_requires_review_instead_of_a_certified_zero(command):
    result = measure_efficiency(metrics([call('wrapped',shell(command),1,2)]),'pi-cua')
    assert not result['computer_use']['attribution_complete']
    assert result['code_tokens']['output_share_percent_estimate'] is None


def test_unused_script_and_old_edit_match_text_do_not_inflate_executable_code():
    tools = [
        call('unused', write('unused.ahk', 'SendText "unused"'), 1, 2),
        call('script', write('draw.ahk', 'SendText "hello"'), 3, 4),
        call('edit', edit('draw.ahk', ('hello', 'world')), 5, 6),
        call('run', shell('acu run draw.ahk'), 7, 8),
    ]
    result = measure_efficiency(metrics(tools), 'pi-acu')
    ledger = result['code_tokens']['payloads']
    assert {p['call_id'] for p in ledger} == {'script', 'edit', 'run'}
    assert next(p for p in ledger if p['call_id'] == 'edit')['characters'] == 5


@pytest.mark.parametrize('python_runtime', ['project', 'bare-system'])
def test_cli_reanalysis_reports_new_metrics_without_rewriting_historical_measurements(tmp_path, python_runtime):
    import json
    import subprocess
    import sys
    from bench.run import ROOT

    workspace = tmp_path / 'workspace'
    workspace.mkdir()
    prior = '{"wall_s":9,"task":{"task_s":7}}'
    (tmp_path / 'metrics.json').write_text(prior, encoding='utf-8')
    (tmp_path / 'plan.json').write_text(json.dumps({'arm':'pi-acu', 'workspace':str(workspace)}), encoding='utf-8')
    message = {'role':'assistant','model':'gpt-6-astra','thinkingLevel':'low','stopReason':'toolUse',
               'durationMs':1000,'usage':{'input':10,'output':100,'cacheRead':20,'totalTokens':130}}
    records = [
        {'elapsed_s':1,'event':{'type':'agent_start'}},
        {'elapsed_s':2,'event':{'type':'message_start','message':{'role':'assistant'}}},
        {'elapsed_s':3,'event':{'type':'message_end','message':message}},
        {'elapsed_s':3,'event':{'type':'tool_execution_start','toolCallId':'t','toolName':'bash','args':{'command':'acu run a.ahk'}}},
        {'elapsed_s':5,'event':{'type':'tool_execution_end','toolCallId':'t','isError':False,'result':{}}},
        {'elapsed_s':8,'event':{'type':'agent_settled','aborted':False}},
    ]
    (tmp_path / 'events.jsonl').write_text('\n'.join(json.dumps(r) for r in records), encoding='utf-8')
    python = [sys.executable] if python_runtime == 'project' else [sys._base_executable, '-S']
    result = subprocess.run([*python,str(ROOT/'bench/run.py'),'analyse','--run-dir',str(tmp_path)],
                            capture_output=True,text=True,encoding='utf-8',timeout=20)
    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    score = output['benchmark']
    assert score['api_tokens']['total'] == 130
    assert score['computer_use']['busy_seconds'] == 2
    assert score['code_tokens']['estimated_tokens'] > 0
    assert score['code_tokens']['denominator_output_including_reasoning'] == 100
    assert 'task' not in output
    assert (tmp_path/'metrics.json').read_text(encoding='utf-8') == prior


def test_codex_helper_does_not_mark_an_unrelated_evidence_function_as_computer_use():
    tools = [
        call('setup', cell('globalThis.report=async()=>{await fs.writeFile("result.json","{}")}; await sky.list_apps()'), 1, 2),
        call('report', cell('await report()'), 3, 5),
        call('reset', {'kind': 'javascript_runtime', 'resets': True}, 6, 7, arguments={}),
    ]
    result = measure_efficiency(metrics(tools), 'pi-computer-use')
    assert [c['id'] for c in result['computer_use']['calls']] == ['setup','reset']
    assert result['computer_use']['busy_seconds'] == 2


# Every session call is computer use; only a reset forgets the helpers earlier cells defined.
@pytest.mark.parametrize('resets,replayed', [(True, False), (False, True)])
def test_javascript_session_calls_count_and_only_a_reset_forgets_helpers(resets, replayed):
    tools = [
        call('define', cell('globalThis.tap=async()=>{await sky.click({})}; await tap()'), 1, 2),
        call('session', {'kind': 'javascript_runtime', 'resets': resets}, 3, 4, arguments={'path': 'C:/modules'}),
        call('replay', cell('await tap()'), 5, 6),
    ]
    result = measure_efficiency(metrics(tools), 'pi-computer-use')
    assert [c['id'] for c in result['computer_use']['calls']] == ['define', 'session', *(['replay'] if replayed else [])]
    session, = (p for p in result['code_tokens']['payloads'] if p['call_id'] == 'session')
    assert session['characters'] == len('{"path":"C:/modules"}'), 'the generated session arguments are the charged payload'


def test_append_heredoc_retains_the_initial_helper_and_both_generated_payloads():
    tools = [
        call('first', shell("cat > ui.py <<'PY'\nimport subprocess\ndef act():\n    subprocess.run(['cua-driver', 'click', '{}'])\nPY"), 1, 2),
        call('append', shell("cat >> ui.py <<'PY'\nact()\nPY"), 3, 4),
        call('run', shell('python ui.py'), 5, 8),
    ]
    result = measure_efficiency(metrics(tools), 'pi-cua')
    assert result['computer_use']['call_count'] == 1
    assert {p['call_id'] for p in result['code_tokens']['payloads']} == {'first','append','run'}


def test_python_acu_list_invocation_and_redirect_after_heredoc():
    tools = [
        call('source', shell("cat <<'EOF' > helper.py\nimport subprocess\nsubprocess.run(['acu', 'run', 'draw.ahk'])\nEOF"), 1, 2),
        call('run', shell('python helper.py'), 3, 5),
    ]
    result = measure_efficiency(metrics(tools), 'pi-acu')
    assert result['computer_use']['call_count'] == 1
    assert {p['call_id'] for p in result['code_tokens']['payloads']} == {'source','run'}
    assert not result['code_tokens']['review_notes']


def test_failed_edit_does_not_change_replayed_source_or_charge_unapplied_replacements():
    source = 'Click 1,1\nClick 2,2'
    failed = call('failed', edit('draw.ahk', ('Click 1,1', 'Click 3,3'), ('Click', 'AcuClick')), 3, 4)
    failed['is_error'] = True
    rejected = call('rejected', write('draw.ahk', 'Click 9,9'), 4, 5)
    rejected['is_error'] = True
    tools = [
        call('source', write('draw.ahk', source), 1, 2),
        failed,
        rejected,
        call('fix', edit('draw.ahk', (source, 'Click 4,4')), 5, 6),
        call('run', shell('acu run draw.ahk'), 7, 8),
    ]
    result = measure_efficiency(metrics(tools), 'pi-acu')
    assert result['computer_use']['attribution_complete']
    assert {p['call_id'] for p in result['code_tokens']['payloads']} == {'source', 'fix', 'run'}


def test_successful_batch_edits_match_the_original_source_not_earlier_replacements():
    tools = [
        call('source', write('draw.ahk', 'one\ntwo'), 1, 2),
        call('edit', edit('draw.ahk', ('one', 'two'), ('two', 'three')), 3, 4),
        call('run', shell('acu run draw.ahk'), 5, 6),
    ]
    result = measure_efficiency(metrics(tools), 'pi-acu')
    assert result['computer_use']['attribution_complete']
    assert len([p for p in result['code_tokens']['payloads'] if p['call_id'] == 'edit']) == 2


def test_dynamic_subprocess_and_ambiguous_edits_require_review_not_a_silent_zero():
    tools = [
        call('source', write('helper.py', 'import subprocess\nsubprocess.run(get_command())\n'), 1, 2),
        call('run', shell('python helper.py'), 3, 5),
    ]
    result = measure_efficiency(metrics(tools), 'pi-cua')
    assert result['code_tokens']['review_required']
    assert result['code_tokens']['output_share_percent_estimate'] is None
    assert not result['computer_use']['attribution_complete']
    tools = [
        call('source', write('draw.ahk', 'Click 1,1\nClick 2,2'), 1, 2),
        call('edit', edit('draw.ahk', ('Click', 'AcuClick')), 3, 4),
        call('run', shell('acu run draw.ahk'), 5, 6),
    ]
    assert measure_efficiency(metrics(tools), 'pi-acu')['code_tokens']['review_required']


def test_replace_all_edit_applies_every_match_and_charges_its_replacement():
    tools = [
        call('source', write('draw.ahk', 'Click 1,1\nClick 2,2'), 1, 2),
        call('edit', edit('draw.ahk', ('Click', 'AcuClick'), replace_all=True), 3, 4),
        call('run', shell('acu run draw.ahk'), 5, 6),
    ]
    result = measure_efficiency(metrics(tools), 'claude-acu')
    assert result['computer_use']['attribution_complete']
    assert {p['call_id'] for p in result['code_tokens']['payloads']} == {'source', 'edit', 'run'}


# An unknown request is visible as such: it blocks a certified share instead of being skipped or guessed.
def test_unknown_request_requires_review_and_names_the_raw_tool():
    unknown = tool_call('glob', 'Glob', {'pattern': '*.ahk'}, {'kind': 'unknown'}, 1, 2, None, False)
    tools = [call('skill', {'kind': 'read'}, 0, 1), unknown, call('run', shell('acu run a.ahk'), 3, 4)]
    result = measure_efficiency(metrics(tools), 'claude-acu')
    assert result['code_tokens']['review_notes'] == [{'call_id': 'glob', 'reason': 'unknown request from tool Glob; attribution needs review'}]
    assert result['code_tokens']['output_share_percent_estimate'] is None
    assert result['computer_use']['call_count'] == 1


def test_opening_line_execution_and_script_rename_remain_attributable():
    tools = [
        call('make-run', shell("cat > draw.ahk <<'EOF'; acu run draw.ahk\nClick 1,1\nEOF"), 1, 3),
        call('source', write('ui.py', "import subprocess\nsubprocess.run(['cua-driver','click','{}'])"), 4, 5),
        call('move-run', shell('mv ui.py renamed.py; python renamed.py'), 6, 8),
    ]
    result = measure_efficiency(metrics(tools), 'pi-acu')
    assert [c['id'] for c in result['computer_use']['calls']] == ['make-run','move-run']


def test_same_basename_does_not_overwrite_a_different_script_and_js_reassignment_expires():
    tools = [
        call('a', write('a/ui.py', "import subprocess\nsubprocess.run(['cua-driver','click','{}'])"), 1, 2),
        call('b', write('b/ui.py', 'print("unrelated")'), 3, 4),
        call('run-a', shell('python a/ui.py'), 5, 6),
    ]
    result = measure_efficiency(metrics(tools), 'pi-cua')
    assert [c['id'] for c in result['computer_use']['calls']] == ['run-a']
    assert {p['call_id'] for p in result['code_tokens']['payloads']} == {'a','run-a'}
    tools = [
        call('define', cell('globalThis.tap=async()=>{await sky.click({})}; await tap()'), 1, 2),
        call('redefine', cell('globalThis.tap=async()=>{await fs.writeFile("result.json","{}")}'), 3, 4),
        call('evidence', cell('await tap()'), 5, 6),
    ]
    result = measure_efficiency(metrics(tools), 'pi-computer-use')
    assert [c['id'] for c in result['computer_use']['calls']] == ['define']


def test_codex_completion_without_start_has_unknown_duration_not_zero():
    from bench.run import analyse_codex

    events = [
        {'elapsed_s':4,'event':{'type':'item.completed','item':{'id':'t','type':'mcp_tool_call',
            'server':'node_repl','tool':'js','arguments':{'code':'await sky.list_apps()'}}}},
        {'elapsed_s':5,'event':{'type':'turn.completed','usage':{'input_tokens':10,'cached_input_tokens':0,'output_tokens':20}}},
    ]
    result = measure_efficiency(analyse_codex(events, 5), 'codex-computer-use')
    assert result['computer_use']['calls'][0]['duration_s'] is None
    assert result['computer_use']['busy_seconds'] is None
    assert not result['computer_use']['durations_complete']
