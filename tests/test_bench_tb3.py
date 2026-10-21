"""TB3 GUI-360 Office scenarios: offline preparation, OOXML checks and the file-check verdict; no Office or desktop."""

import hashlib
import shutil
import zipfile

import pytest

from bench.run import ROOT, prepare
from bench.tb3 import STEP_LIMIT, TASKS, check_document, grade, prompt

ASSETS = ROOT / 'bench/assets/gui360'


def test_every_tb3_scenario_prepares_its_verbatim_request_and_unmodified_template(tmp_path):
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


@pytest.mark.parametrize(('scenario', 'member', 'old', 'passing', 'partial'), [
    ('tb3.2', 'xl/worksheets/sheet1.xml', '</worksheet>',
     '<conditionalFormatting sqref="B1:B1048576"><cfRule type="cellIs" dxfId="0" priority="1" operator="greaterThan"><formula>30</formula></cfRule></conditionalFormatting></worksheet>',
     '<conditionalFormatting sqref="C1:C1048576"><cfRule type="cellIs" dxfId="0" priority="1" operator="greaterThan"><formula>30</formula></cfRule></conditionalFormatting></worksheet>'),
    ('tb3.4', 'word/document.xml', '<w:sectPr',
     '<w:p><w:pPr><w:jc w:val="right"/></w:pPr><w:r><w:t>مرحبا</w:t></w:r></w:p><w:sectPr',
     '<w:p><w:r><w:t>مرحبا</w:t></w:r></w:p><w:sectPr'),
    ('tb3.6', 'ppt/slides/slide1.xml', '</p:spTree>',
     '<p:sp><p:nvSpPr><p:cNvPr id="2" name="Bubble"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr><p:spPr><a:xfrm><a:off x="1270000" y="1270000"/>'
     '<a:ext cx="2540000" cy="1270000"/></a:xfrm><a:prstGeom prst="wedgeEllipseCallout"><a:avLst/></a:prstGeom></p:spPr></p:sp></p:spTree>',
     '<p:sp><p:nvSpPr><p:cNvPr id="2" name="Oval"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr><p:spPr><a:xfrm><a:off x="1270000" y="1270000"/>'
     '<a:ext cx="2540000" cy="1270000"/></a:xfrm><a:prstGeom prst="ellipse"><a:avLst/></a:prstGeom></p:spPr></p:sp></p:spTree>'),
])
def test_file_checks_pass_the_requested_result_and_reject_the_template_and_near_misses(tmp_path, scenario, member, old, passing, partial):
    template = ASSETS / TASKS[scenario]['template']
    assert check_document(scenario, template, template)['passed'] is False
    assert check_document(scenario, edited(template.name, tmp_path, member, old, partial), template)['passed'] is False
    result = check_document(scenario, edited(template.name, tmp_path, member, old, passing), template)
    assert result['passed'] is True and set(result['sub_scores'].values()) == {'yes'}


def test_verdict_is_the_saved_file_check_within_the_step_limit_and_com_is_only_reported(tmp_path):
    plan = prepare('pi-acu', tmp_path / 'trial', scenario='tb3.6')
    run_dir = tmp_path / 'trial'
    (run_dir / 'grading').mkdir()
    bubble = ('<p:sp><p:nvSpPr><p:cNvPr id="2" name="Bubble"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr><p:spPr><a:xfrm><a:off x="1270000" y="1270000"/>'
              '<a:ext cx="2540000" cy="1270000"/></a:xfrm><a:prstGeom prst="wedgeEllipseCallout"><a:avLst/></a:prstGeom></p:spPr></p:sp></p:spTree>')
    shutil.copyfile(edited('template6.pptx', tmp_path, 'ppt/slides/slide1.xml', '</p:spTree>', bubble), run_dir / 'grading/template6.pptx')
    com_call = {'text': 'ComObjActive("PowerPoint.Application").ActivePresentation.Slides(1)'}
    result = grade(run_dir, plan, [com_call])
    assert result['passed'] is True and result['file_check']['passed'] is True
    assert result['office_com_used'] is True, 'GUI-360 allows COM, so it is reported without failing the task'
    assert grade(run_dir, plan, [{'text': 'acu run step.ahk'}] * (STEP_LIMIT + 1))['passed'] is False
    (run_dir / 'grading/template6.pptx').unlink()
    missing = grade(run_dir, plan, [])
    assert missing['passed'] is False and missing['file_check']['error'] == 'no saved document to check'
