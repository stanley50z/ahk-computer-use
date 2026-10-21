"""TB3 Office scenarios: offline preparation, OOXML checks, recorded-input checks and the verdict; no Office or desktop."""

import hashlib
import json
import shutil
import zipfile
from xml.sax.saxutils import escape

from bench.run import ROOT, actor_path, prepare
from bench.tb3 import SENTENCES, TASKS, check_document, check_input, docx_paragraphs, grade, prompt, template_path

ASSETS = ROOT / 'bench/assets/gui360'


def test_every_tb3_scenario_prepares_its_request_and_unmodified_template(tmp_path):
    for scenario, task in TASKS.items():
        plan = prepare('pi-acu', tmp_path / scenario, scenario=scenario)
        scenario_file = (ROOT / f'bench/scenarios/{scenario}.md').read_text(encoding='utf-8')
        assert scenario_file.partition('\n')[2] == prompt(scenario), 'regenerate the scenario file from bench.tb3'
        sent = (tmp_path / scenario / 'prompt.txt').read_text(encoding='utf-8')
        assert task['request'] in sent and task['template'] in sent
        assert f"Your working directory is {actor_path(tmp_path / scenario / 'workspace')}." in sent and '<WORKSPACE>' not in sent
        copied = tmp_path / scenario / 'workspace' / task['template']
        assert copied.read_bytes() == template_path(task['template']).read_bytes()
        assert plan['assets'] == {task['template']: hashlib.sha256(copied.read_bytes()).hexdigest()}
        assert plan['tb3']['gui360_id'] == task['gui360_id'] and plan['grading'] == {'mode': 'ooxml-file-check-v1', 'llm_judge': None}


# Rewrite archive members, standing in for the document Office saves after a correct or partial actor run.
def edited(template, tmp_path, member, old, new, *more, added=None):
    target = tmp_path / f'{len(list(tmp_path.iterdir()))}-{template}'
    changes = [(member, old, new), *zip(more[::3], more[1::3], more[2::3])]
    with zipfile.ZipFile(template_path(template)) as source, zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as output:
        for item in source.infolist():
            data = source.read(item)
            for name, before, after in changes:
                if item.filename == name:
                    text = data.decode('utf-8')
                    assert before in text
                    data = text.replace(before, after, 1).encode('utf-8')
            output.writestr(item, data)
        for name, data in (added or {}).items():
            output.writestr(name, data)
    return target


# The Word template's text unchanged, with each given span in its own highlighted run.
def highlighted_docx(tmp_path, spans):
    paragraphs = []
    for paragraph in docx_paragraphs(ASSETS / 'template1.docx'):
        text, runs, position = paragraph['text'], [], 0
        for start, span in sorted((text.find(span), span) for span in spans if span in text):
            runs.append(f'<w:r><w:t xml:space="preserve">{escape(text[position:start])}</w:t></w:r>')
            runs.append(f'<w:r><w:rPr><w:highlight w:val="yellow"/></w:rPr><w:t xml:space="preserve">{escape(span)}</w:t></w:r>')
            position = start + len(span)
        runs.append(f'<w:r><w:t xml:space="preserve">{escape(text[position:])}</w:t></w:r>')
        paragraphs.append('<w:p>' + ''.join(runs) + '</w:p>')
    body = ('<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
            + ''.join(paragraphs) + '</w:body></w:document>')
    source = zipfile.ZipFile(ASSETS / 'template1.docx').read('word/document.xml').decode('utf-8')
    return edited('template1.docx', tmp_path, 'word/document.xml', source, body)


def test_conditional_format_check_needs_the_age_column_rule(tmp_path):
    template = ASSETS / 'adult_sexual_behaviors.xlsx'
    rule = '<conditionalFormatting sqref="{}:{}"><cfRule type="cellIs" dxfId="0" priority="1" operator="greaterThan"><formula>30</formula></cfRule></conditionalFormatting></worksheet>'
    assert check_document('tb3.1', template, template)['passed'] is False
    wrong = edited(template.name, tmp_path, 'xl/worksheets/sheet1.xml', '</worksheet>', rule.format('C1', 'C1048576'))
    assert check_document('tb3.1', wrong, template)['passed'] is False
    right = edited(template.name, tmp_path, 'xl/worksheets/sheet1.xml', '</worksheet>', rule.format('B1', 'B1048576'))
    result = check_document('tb3.1', right, template)
    assert result['passed'] is True and set(result['sub_scores'].values()) == {'yes'}


def test_highlight_check_needs_all_three_sentences_and_nothing_else(tmp_path):
    template = ASSETS / 'template1.docx'
    paragraphs = docx_paragraphs(template)
    assert [sum(s in p['text'] for p in paragraphs) for s in SENTENCES] == [1, 1, 1]
    assert not any(any(p['highlighted']) for p in paragraphs), 'the template starts with no highlight'
    assert check_document('tb3.2', template, template)['passed'] is False
    assert check_document('tb3.2', highlighted_docx(tmp_path, SENTENCES[:2]), template)['passed'] is False
    whole = next(p['text'] for p in paragraphs if SENTENCES[0] in p['text'])
    overreach = check_document('tb3.2', highlighted_docx(tmp_path, [whole, *SENTENCES[1:]]), template)
    assert overreach['passed'] is False and overreach['sub_scores']['No other text highlighted'] == 'no'
    with_space = check_document('tb3.2', highlighted_docx(tmp_path, [s + ' ' for s in SENTENCES]), template)
    assert with_space['passed'] is True, 'a trailing space selected with a sentence is not extra text'
    result = check_document('tb3.2', highlighted_docx(tmp_path, SENTENCES), template)
    assert result['passed'] is True and set(result['sub_scores'].values()) == {'yes'}


def test_verdict_is_the_saved_file_check_and_step_count_and_com_are_only_reported(tmp_path):
    plan = prepare('pi-acu', tmp_path / 'trial', scenario='tb3.2')
    run_dir = tmp_path / 'trial'
    (run_dir / 'grading').mkdir()
    shutil.copyfile(highlighted_docx(tmp_path, SENTENCES), run_dir / 'grading/template1.docx')
    (run_dir / 'office-identity.json').write_text(json.dumps({'hwnd': 7}), encoding='utf-8')
    (run_dir / 'input-log.jsonl').write_text(json.dumps({'kind': 'mouse', 'button': 'left', 'action': 'down', 'x': 1, 'y': 1, 'window': 7, 'foreground': 7}), encoding='utf-8')
    com_call = {'text': 'ComObjActive("Word.Application").ActiveDocument.Paragraphs(4)'}
    result = grade(run_dir, plan, [com_call])
    assert result['passed'] is True and result['file_check']['passed'] is True
    assert result['office_com_used'] is True, 'GUI-360 allows COM, so it is reported without failing the task'
    many = grade(run_dir, plan, [{'text': 'acu run step.ahk'}] * 80)
    assert many['passed'] is True and many['tool_calls'] == 80, 'a correct end product passes however many steps it took'
    (run_dir / 'grading/template1.docx').unlink()
    missing = grade(run_dir, plan, [])
    assert missing['passed'] is False and missing['file_check']['error'] == 'no saved document to check'


SHEET = 'xl/worksheets/sheet1.xml'


def test_fill_formatting_check_needs_exactly_b3_to_b10_restyled_with_values_kept(tmp_path):
    template = template_path('budget.xlsx')
    rows = [f'<c r="B{row}">' for row in range(3, 11)]
    restyle = lambda refs: [part for ref in refs for part in (SHEET, ref, ref.replace('">', '" s="2">'))]
    assert check_document('tb3.3', template, template)['passed'] is False
    short = edited('budget.xlsx', tmp_path, *restyle(rows[:-1]))
    assert check_document('tb3.3', short, template)['sub_scores']["B3:B10 have B2's formatting"] == 'no'
    overwritten = edited('budget.xlsx', tmp_path, *restyle(rows), SHEET, '<v>185.4</v>', '<v>1200</v>')
    assert check_document('tb3.3', overwritten, template)['sub_scores']['No cell values changed'] == 'no'
    result = check_document('tb3.3', edited('budget.xlsx', tmp_path, *restyle(rows)), template)
    assert result['passed'] is True and set(result['sub_scores'].values()) == {'yes'}


def test_sheet_copy_check_needs_an_identical_budget_2_sheet(tmp_path):
    template = template_path('budget.xlsx')
    sheet = zipfile.ZipFile(template).read(SHEET)
    copy = ('xl/workbook.xml', '</sheets>', '<sheet name="Budget (2)" sheetId="2" r:id="rId99"/></sheets>',
            'xl/_rels/workbook.xml.rels', '</Relationships>',
            '<Relationship Id="rId99" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
            'Target="worksheets/sheet2.xml"/></Relationships>')
    assert check_document('tb3.4', template, template)['passed'] is False
    altered = edited('budget.xlsx', tmp_path, *copy, added={'xl/worksheets/sheet2.xml': sheet.replace(b'<v>185.4</v>', b'<v>1</v>')})
    assert check_document('tb3.4', altered, template)['sub_scores']['Copy has the same values and formatting'] == 'no'
    result = check_document('tb3.4', edited('budget.xlsx', tmp_path, *copy, added={'xl/worksheets/sheet2.xml': sheet}), template)
    assert result['passed'] is True and set(result['sub_scores'].values()) == {'yes'}


# A recorder log of button presses and releases on window 7 (the owned Excel window) or elsewhere.
def input_run(tmp_path, scenario, events):
    plan = prepare('pi-acu', tmp_path / scenario, scenario=scenario)
    run_dir = tmp_path / scenario
    (run_dir / 'office-identity.json').write_text(json.dumps({'hwnd': 7}), encoding='utf-8')
    lines = []
    for kind, name, action, x, y, window in events:
        event = {'kind': kind, 'action': action, 'x': x, 'y': y, 'window': window, 'foreground': window}
        event.update({'button': name} if kind == 'mouse' else {'vk': name})
        lines.append(json.dumps(event))
    (run_dir / 'input-log.jsonl').write_text('\n'.join(lines), encoding='utf-8')
    return check_input(run_dir, plan)


def test_right_drag_requirement_rejects_clicks_and_other_windows(tmp_path):
    drag = [('mouse', 'right', 'down', 100, 100, 7), ('mouse', 'right', 'up', 100, 400, 7)]
    assert input_run(tmp_path / 'a', 'tb3.3', drag)['passed'] is True
    assert input_run(tmp_path / 'b', 'tb3.3', [('mouse', 'right', 'down', 100, 100, 7), ('mouse', 'right', 'up', 102, 101, 7)])['passed'] is False
    assert input_run(tmp_path / 'c', 'tb3.3', [('mouse', 'right', 'down', 100, 100, 9), ('mouse', 'right', 'up', 100, 400, 9)])['passed'] is False
    assert input_run(tmp_path / 'd', 'tb3.3', [('mouse', 'left', 'down', 100, 100, 7), ('mouse', 'left', 'up', 100, 400, 7)])['passed'] is False


def test_ctrl_drag_requirement_needs_ctrl_held_from_press_to_release(tmp_path):
    held = [('key', 17, 'down', 0, 0, 7), ('mouse', 'left', 'down', 100, 900, 7), ('mouse', 'left', 'up', 300, 900, 7), ('key', 17, 'up', 0, 0, 7)]
    assert input_run(tmp_path / 'a', 'tb3.4', held)['passed'] is True
    early = [held[0], held[1], held[3], held[2]]
    assert input_run(tmp_path / 'b', 'tb3.4', early)['passed'] is False, 'Ctrl released before the drop moves the sheet instead'
    assert input_run(tmp_path / 'c', 'tb3.4', held[1:3])['passed'] is False
    assert input_run(tmp_path / 'd', 'tb3.1', held) is None, 'a task that names no input method has no input requirement'


def test_recorder_reads_mouse_button_flags_at_the_windows_offset():
    import ctypes
    from bench.input_recorder import RAWINPUT, RAWINPUTHEADER, RAWMOUSE
    assert RAWMOUSE.usButtonFlags.offset == 4 and RAWMOUSE.lLastX.offset == 12 and ctypes.sizeof(RAWMOUSE) == 24
    assert RAWINPUT.data.offset == ctypes.sizeof(RAWINPUTHEADER)


# A busy Office rejects even the method lookup, so collection must retry it and send Escape instead of crashing.
def test_collection_retries_a_save_that_busy_office_rejects(tmp_path, monkeypatch):
    import bench.tb3 as tb3
    plan = prepare('pi-acu', tmp_path / 'trial', scenario='tb3.2')
    run_dir = tmp_path / 'trial'
    (run_dir / 'grading').mkdir()
    document_path = run_dir / 'workspace/template1.docx'
    (run_dir / 'office-identity.json').write_text(json.dumps({'hwnd': 7, 'pid': 70, 'launched_pid': 70, 'document': str(document_path)}), encoding='utf-8')

    class Busy:
        rejections = 2
        saved = quit = False

        def __getattr__(self, name):
            if name == 'Save' and Busy.rejections:
                Busy.rejections -= 1
                raise AttributeError('<unknown>.Save')  # what win32com raises for RPC_E_CALL_REJECTED on lookup
            if name == 'Save':
                return lambda: setattr(Busy, 'saved', True)
            if name == 'Application':
                return type('App', (), {'Quit': lambda self, *_: setattr(Busy, 'quit', True)})()
            raise AttributeError(name)
    observed = []
    monkeypatch.setattr(tb3, 'bind_document', lambda path: Busy())
    monkeypatch.setattr(tb3, 'screenshot', lambda *a: run_dir / 'grading/final.png')
    monkeypatch.setattr(tb3, 'stop_office', lambda identity, timeout_s=30: {'exited': True, 'terminated': []})
    monkeypatch.setattr(tb3.time, 'sleep', lambda s: None)
    record = tb3.collect(run_dir, plan, lambda run, script, *args, **kw: observed.append(args[0]))
    assert Busy.saved and Busy.quit and record['saved'] is True
    assert observed == ['escape'] and len(record['interventions']) == 1


def test_mouse_only_requirement_fails_any_key_press_in_word(tmp_path):
    clicks = [('mouse', 'left', 'down', 100, 100, 7), ('mouse', 'left', 'up', 300, 100, 7)]
    assert input_run(tmp_path / 'a', 'tb3.2', clicks)['passed'] is True
    assert input_run(tmp_path / 'b', 'tb3.2', clicks + [('key', 17, 'down', 0, 0, 7)])['passed'] is False
    assert input_run(tmp_path / 'c', 'tb3.2', clicks + [('key', 17, 'down', 0, 0, 9)])['passed'] is True, 'keys in another window do not count'
    assert input_run(tmp_path / 'd', 'tb3.2', [])['passed'] is False, 'no mouse use on Word fails'
