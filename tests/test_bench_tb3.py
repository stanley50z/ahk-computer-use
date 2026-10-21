"""TB3 GUI-360 Office scenarios: offline preparation, OOXML checks and the file-check verdict; no Office or desktop."""

import hashlib
import shutil
import zipfile
from xml.sax.saxutils import escape

import pytest

from bench.run import ROOT, prepare
from bench.tb3 import SENTENCES, STEP_LIMIT, TASKS, check_document, docx_paragraphs, grade, prompt

ASSETS = ROOT / 'bench/assets/gui360'


def test_every_tb3_scenario_prepares_its_request_and_unmodified_template(tmp_path):
    for scenario, task in TASKS.items():
        plan = prepare('pi-acu', tmp_path / scenario, scenario=scenario)
        scenario_file = (ROOT / f'bench/scenarios/{scenario}.md').read_text(encoding='utf-8')
        assert scenario_file.partition('\n')[2] == prompt(scenario), 'regenerate the scenario file from bench.tb3'
        sent = (tmp_path / scenario / 'prompt.txt').read_text(encoding='utf-8')
        assert task['request'] in sent and task['template'] in sent
        copied = tmp_path / scenario / 'workspace' / task['template']
        assert copied.read_bytes() == (ASSETS / task['template']).read_bytes()
        assert plan['assets'] == {task['template']: hashlib.sha256(copied.read_bytes()).hexdigest()}
        assert plan['tb3']['gui360_id'] == task['gui360_id'] and plan['grading'] == {'mode': 'ooxml-file-check-v1', 'llm_judge': None}


# Rewrite one archive member, standing in for the document Office saves after a correct or partial actor run.
def edited(template, tmp_path, member, old, new):
    target = tmp_path / f'{len(list(tmp_path.iterdir()))}-{template}'
    with zipfile.ZipFile(ASSETS / template) as source, zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as output:
        for item in source.infolist():
            data = source.read(item)
            if item.filename == member:
                text = data.decode('utf-8')
                assert old in text
                data = text.replace(old, new, 1).encode('utf-8')
            output.writestr(item, data)
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


def test_verdict_is_the_saved_file_check_within_the_step_limit_and_com_is_only_reported(tmp_path):
    plan = prepare('pi-acu', tmp_path / 'trial', scenario='tb3.2')
    run_dir = tmp_path / 'trial'
    (run_dir / 'grading').mkdir()
    shutil.copyfile(highlighted_docx(tmp_path, SENTENCES), run_dir / 'grading/template1.docx')
    com_call = {'text': 'ComObjActive("Word.Application").ActiveDocument.Paragraphs(4)'}
    result = grade(run_dir, plan, [com_call])
    assert result['passed'] is True and result['file_check']['passed'] is True
    assert result['office_com_used'] is True, 'GUI-360 allows COM, so it is reported without failing the task'
    assert grade(run_dir, plan, [{'text': 'acu run step.ahk'}] * (STEP_LIMIT + 1))['passed'] is False
    (run_dir / 'grading/template1.docx').unlink()
    missing = grade(run_dir, plan, [])
    assert missing['passed'] is False and missing['file_check']['error'] == 'no saved document to check'
