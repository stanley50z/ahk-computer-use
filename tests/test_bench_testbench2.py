"""TB2 preparation and grading boundaries; the native integration check is explicitly desktop-marked."""

import hashlib
import json
import subprocess
import sys
from uuid import uuid4

import pytest
from PIL import Image

from bench.run import ROOT, prepare


def test_tb2_prepare_freezes_only_actor_assets_and_jpeg_grading_reference(tmp_path):
    skill = tmp_path / 'acu'
    skill.mkdir()
    (skill / 'SKILL.md').write_text('---\nname: acu\ndescription: fixture\n---\n', encoding='utf-8')
    directory = tmp_path / 'trial'
    plan = prepare('pi-acu', directory, skill=skill, scenario='testbench-2')
    assert plan['scenario'] == 'testbench-2'
    assert plan['grading']['shape_pass_threshold'] is None
    assert plan['grading']['registration'] == 'none'
    assert sorted(p.name for p in (directory / 'workspace').iterdir()) == [
        'Cloud9-Pen-Starter.ai', 'Cloud9-Reference.jpg']
    for name in ('Cloud9-Pen-Starter.ai', 'Cloud9-Reference.jpg'):
        data = (ROOT / 'bench/assets/testbench-2' / name).read_bytes()
        assert (directory / 'workspace' / name).read_bytes() == data
        assert plan['assets'][name] == hashlib.sha256(data).hexdigest()
    reference = directory / 'grading/reference.jpg'
    assert reference.read_bytes() == (directory / 'workspace/Cloud9-Reference.jpg').read_bytes()
    prompt = (directory / 'prompt.txt').read_text(encoding='utf-8')
    assert '#00AEEF' in prompt and '72 ppi' in prompt
    assert 'Pen tool' in prompt and 'remove' in prompt
    assert 'c9.gg' not in prompt and 'guidelines' not in prompt.lower()
    assert 'Image Trace' in prompt and 'scripting' in prompt
    assert not (directory / 'agent-home/auth.json').exists()
    assert json.loads((directory / 'plan.json').read_text(encoding='utf-8')) == plan


def test_cli_prepares_tb2_without_desktop_approval(tmp_path):
    directory = tmp_path / 'cli-trial'
    completed = subprocess.run(
        [sys.executable, str(ROOT / 'bench/run.py'), 'prepare', '--scenario', 'testbench-2',
         '--arm', 'pi-acu', '--run-dir', str(directory)],
        capture_output=True, text=True, encoding='utf-8', timeout=20)
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)['scenario'] == 'testbench-2'
    assert not (directory / 'state.json').exists()


def test_pilot_reports_exact_match_and_translation_without_an_overall_pass(tmp_path):
    from bench.testbench2 import shape_metrics, verify_outputs

    reference = Image.new('RGB', (40, 40), 'white')
    for x in range(10, 20):
        for y in range(12, 24):
            reference.putpixel((x, y), (0, 174, 239))
    metrics = shape_metrics(reference, reference)
    assert metrics['foreground_iou'] == 1.0
    assert metrics['boundary_mean_manhattan_px'] == 0
    moved = Image.new('RGB', (40, 40), 'white')
    moved.paste(reference.crop((10, 12, 20, 24)), (15, 12))
    shifted = shape_metrics(moved, reference)
    assert shifted['foreground_iou'] == pytest.approx(1 / 3)
    assert shifted['foreground_bounds'] == [15, 12, 25, 24]
    assert shifted['boundary_mean_manhattan_px'] > 0

    directory = tmp_path / 'trial'
    plan = prepare('pi-acu', directory, scenario='testbench-2')
    workspace = directory / 'workspace'
    supplied = Image.open(directory / 'grading/reference.jpg').convert('RGB')
    image = Image.new('RGB', supplied.size, 'white')
    image.putdata([(0, 174, 239) if r < 128 and g > 100 and b > 150 else (255, 255, 255)
                   for r, g, b in zip(supplied.tobytes()[::3], supplied.tobytes()[1::3], supplied.tobytes()[2::3])])
    image.save(workspace / 'Cloud9-Recreated.png', dpi=(72, 72))
    (workspace / 'Cloud9-Recreated.ai').write_bytes(b'%PDF-1.5 saved fixture')
    (workspace / 'result.json').write_text(json.dumps({
        'status': 'completed', 'ai_file': 'Cloud9-Recreated.ai', 'png_file': 'Cloud9-Recreated.png',
        'input_method': 'fixture', 'hiccups': []}), encoding='utf-8')
    native = {'checks': {'editable_paths': True, 'appearance': True, 'artboard': True},
              'ai_sha256': hashlib.sha256(b'%PDF-1.5 saved fixture').hexdigest()}
    (directory / 'native-verification.json').write_text(json.dumps(native), encoding='utf-8')
    verdict = verify_outputs(directory)
    assert verdict['export']['passed'] is True
    assert verdict['vector']['passed'] is True
    assert verdict['shape']['foreground_iou'] == 1.0
    assert verdict['shape']['passed'] is None
    assert verdict['method']['status'] == 'review_required'
    assert verdict['passed'] is None
    (workspace / 'result.json').write_text('{"status":"completed"}', encoding='utf-8')
    assert verify_outputs(directory)['passed'] is False, 'required manifest fields cannot be omitted'
    (workspace / 'result.json').write_text(json.dumps({
        'status': 'completed', 'ai_file': 'wrong.ai', 'png_file': 'Cloud9-Recreated.png',
        'input_method': 'fixture', 'hiccups': []}), encoding='utf-8')
    assert verify_outputs(directory)['passed'] is False, 'manifest must name the inspected outputs'
    (workspace / 'result.json').write_text(json.dumps({
        'status': 'completed', 'ai_file': 'Cloud9-Recreated.ai', 'png_file': 'Cloud9-Recreated.png',
        'input_method': 'fixture', 'hiccups': []}), encoding='utf-8')
    image.convert('RGBA').save(workspace / 'Cloud9-Recreated.png')
    assert verify_outputs(directory)['export']['passed'] is True, 'opaque RGBA is valid'
    transparent = image.convert('RGBA')
    transparent.putalpha(0)
    transparent.save(workspace / 'Cloud9-Recreated.png')
    bad = verify_outputs(directory)
    assert not bad['export']['passed'] and bad['passed'] is False
    assert bad['export']['checks']['opaque'] is False
    Image.new('RGB', (400, 400), 'white').save(workspace / 'Cloud9-Recreated.png')
    assert not verify_outputs(directory)['export']['checks']['dimensions']
    (workspace / 'Cloud9-Recreated.png').unlink()
    assert verify_outputs(directory)['passed'] is False


def test_pilot_refuses_modified_frozen_reference_and_stale_native_evidence(tmp_path):
    from bench.testbench2 import verify_outputs

    directory = tmp_path / 'trial'
    prepare('pi-acu', directory, scenario='testbench-2')
    workspace = directory / 'workspace'
    (workspace / 'Cloud9-Recreated.ai').write_bytes(b'%PDF-1.5 edited')
    (workspace / 'result.json').write_text('{"status":"completed"}', encoding='utf-8')
    (directory / 'native-verification.json').write_text(
        json.dumps({'ai_sha256': 'stale', 'checks': {'editable_paths': True}}), encoding='utf-8')
    with pytest.raises(ValueError, match='saved AI changed'):
        verify_outputs(directory)
    (directory / 'grading/reference.jpg').write_bytes(b'changed')
    with pytest.raises(ValueError, match='reference'):
        verify_outputs(directory)


def test_tb2_cleanup_protects_existing_documents_and_refuses_unclaimed_work(tmp_path):
    from bench.testbench2 import owned_documents

    workspace = tmp_path / 'workspace'
    workspace.mkdir()
    existing = {'path': 'C:/Users/13982/Downloads/Cloud9 Icon.ai', 'name': 'Cloud9 Icon.ai', 'saved': False}
    owned = {'path': str(workspace / 'Cloud9-Recreated.ai'), 'name': 'Cloud9-Recreated.ai', 'saved': True}
    assert owned_documents([existing], [existing, owned], workspace) == [owned['path']]
    assert owned_documents([owned], [owned], workspace) == [], 'even a workspace path is protected when pre-existing'
    with pytest.raises(ValueError, match='pre-existing'):
        owned_documents([existing], [owned], workspace)
    unsaved = {'path': '', 'name': 'Untitled-2', 'saved': False}
    with pytest.raises(ValueError, match='unclaimed'):
        owned_documents([existing], [existing, owned, unsaved], workspace)
    foreign = dict(owned, path=str(tmp_path / 'outside.ai'))
    with pytest.raises(ValueError, match='unclaimed'):
        owned_documents([existing], [existing, foreign], workspace)


def test_tb2_conduct_accepts_illustrator_not_a_new_calculator(tmp_path):
    from bench.run import conduct_audit

    plan = {'scenario': 'testbench-2', 'run_dir': str(tmp_path), 'workspace': str(tmp_path), 'skill_path': str(ROOT / 'acu/SKILL.md')}
    before = 'window=1 pid=5\n'
    clean = conduct_audit(plan, before, 'window=1 pid=5\nwindow=9 pid=8\nwindow=10 pid=8\nillustrator=9\npid=8\n', {}, {}, [])
    assert clean['passed']
    stray = conduct_audit(plan, before, 'window=1 pid=5\nwindow=9 pid=8\ncalculator=9\npid=8\n', {}, {}, [])
    assert not stray['passed']
    shadow_before = 'window=1 pid=5\nwindow=2 pid=8\nwindow=3 pid=8\nclass=2 SysShadow\nclass=3 illustrator\nillustrator=3\npid=8\n'
    shadow_after = 'window=1 pid=5\nwindow=3 pid=8\nillustrator=3\npid=8\n'
    assert conduct_audit(plan, shadow_before, shadow_after, {}, {}, [])['passed'], 'Illustrator menu/tooltip shadows are not user windows'
    assert not conduct_audit(plan, shadow_before, 'window=1 pid=5\n', {}, {}, [])['passed'], 'the actual main frame stays protected'


@pytest.mark.desktop
def test_tb2_real_illustrator_preparation_and_owned_document_cleanup(tmp_path):
    from bench.run import acu_observer
    from bench.testbench2 import prepare_desktop, inspect_native, verify_outputs, cleanup_desktop

    directory = ROOT / '.pi/tb2-validation' / f'native-check-{uuid4().hex[:8]}'
    plan = prepare('pi-acu', directory, scenario='testbench-2')
    acu_observer(directory, ROOT / 'bench/probe.ahk', suffix='-before')
    try:
        prepared = prepare_desktop(plan, acu_observer)
        assert prepared['zoom'] == 1
        assert prepared['png_preferences']['ResolutionR'] == 72
        assert prepared['export_options']['anti_aliasing'] == 'Art Optimized (Supersampling)'
        assert prepared['png_preferences']['AntiAlias'] == 1
        assert prepared['workspace'] == 'Getting Started'
        assert any(d['name'] == 'Cloud9-Pen-Starter.ai' for d in prepared['documents'])
        identity = json.loads((directory / 'illustrator-identity.json').read_text(encoding='utf-8'))
        workspace = directory / 'workspace'
        screenshot = directory / 'blank-desktop.png'
        acu_observer(directory, ROOT / 'acu/screenshot.ahk', 'fullscreen', '--max', 0, '--out', screenshot)
        with Image.open(screenshot) as desktop:
            rgb = desktop.convert('RGB')
            # Find the blank artboard from its longest white row/column, not hard-coded screen coordinates.
            from itertools import groupby
            # Register the visible blank artboard independently of the gesture implementation.
            def white_span(values):
                spans = [list(group) for white, group in groupby(enumerate(values), lambda item: item[1] == (255, 255, 255)) if white]
                longest = max(spans, key=len)
                return longest[0][0], longest[-1][0] + 1
            left, right = white_span([rgb.getpixel((x, rgb.height // 2)) for x in range(rgb.width)])
            top, bottom = white_span([rgb.getpixel(((left + right) // 2, y)) for y in range(rgb.height)])
        # Map these literal fixture points into the observed artboard, not a guessed viewport.
        def screen(x, y):
            return round(left + x * (right - left) / 800), round(top + y * (bottom - top) / 800)
        start, handle, second, third = [screen(x, y) for x, y in ((200, 200), (350, 200), (600, 200), (600, 600))]
        gesture_script = directory / 'paced-pen.ahk'
        target = f'ahk_id {identity["hwnd"]}'
        gesture_script.write_text(
            'SendMode "Input"\nSetKeyDelay 7,9\nSetMouseDelay 11\n'
            f'target := "{target}"\n'
            'AcuKeys(target, "{Esc}p")\n'
            f'AcuDrag(target, {start[0]}, {start[1]}, {handle[0]}, {handle[1]})\n'
            f'AcuClick(target, {second[0]}, {second[1]})\n'
            f'AcuClick(target, {third[0]}, {third[1]})\n'
            f'AcuClick(target, {start[0]}, {start[1]})\n'
            'AcuKeys(target, "{Esc}v")\n'
            'if A_SendMode != "Input" || A_KeyDelay != 7 || A_KeyDuration != 9 || A_MouseDelay != 11\n'
            '    throw Error("Helper changed native input settings")\n'
            'if GetKeyState("LButton")\n    throw Error("Helper left a button held")\n', encoding='utf-8')
        acu_observer(directory, gesture_script)
        result = directory / 'fixture-result.txt'
        config = {'starter': str(workspace / 'Cloud9-Pen-Starter.ai'),
                  'ai': str(workspace / 'Cloud9-Recreated.ai'), 'png': str(workspace / 'Cloud9-Recreated.png'),
                  'result': str(result)}
        script = directory / 'saved-fixture.jsx'
        script.write_text('var config = ' + json.dumps(config) + ';\n' +
                          (ROOT / 'tests/scripts/tb2_saved_fixture.jsx').read_text(encoding='utf-8'), encoding='utf-8')
        acu_observer(directory, ROOT / 'bench/illustrator/run-jsx.ahk', script, result,
                     identity['hwnd'], identity['pid'], timeout=40)
        assert result.read_text(encoding='utf-8') == 'SUCCESS'
        (workspace / 'result.json').write_text(json.dumps({
            'status': 'completed', 'ai_file': 'Cloud9-Recreated.ai', 'png_file': 'Cloud9-Recreated.png',
            'input_method': 'paced Pen fixture', 'hiccups': []}), encoding='utf-8')
        inspect_native(directory, acu_observer)
        verification = verify_outputs(directory)
        assert verification['export']['passed']
        assert verification['vector']['passed']
        first = verification['vector']['native']['paths'][0]['points'][0]
        assert first['anchor'] == pytest.approx([200, 600], abs=.75)
        assert first['right'] == pytest.approx([350, 600], abs=.75)
        assert verification['vector']['png_consistency']['foreground_iou'] == 1
        assert verification['passed'] is None
        # A provider interruption may leave Save As open; cleanup cancels this new dialog without touching documents.
        dialog_script = directory / 'leave-save-as.ahk'
        dialog_script.write_text(
            'WinActivate "ahk_id ' + str(identity['hwnd']) + '"\n'
            'if !WinWaitActive("ahk_id ' + str(identity['hwnd']) + '", , 3)\n'
            '    throw Error("Fixture did not activate")\n'
            'SetKeyDelay 30,30\nSendEvent "^+s"\n'
            'if !AcuWaitUntil(() => WinExist("Save As ahk_exe Illustrator.exe"), 5000)\n'
            '    throw Error("Fixture Save As did not open")\n', encoding='utf-8')
        acu_observer(directory, dialog_script)
        refusal_script = directory / 'refuse-main-with-dialog.ahk'
        refusal_script.write_text(
            f'target := "{target}"\n'
            'refused := false\ntry AcuActivate(target)\ncatch Error as failure {\n'
            '    if !InStr(failure.Message, "dialog")\n        throw failure\n'
            '    refused := true\n}\n'
            'if !refused\n    throw Error("Helper activated a frame with an owned dialog")\n'
            'dialog := WinExist("Save As ahk_exe Illustrator.exe")\n'
            'AcuActivate("ahk_id " dialog)\n', encoding='utf-8')
        acu_observer(directory, refusal_script)
        menu_script = directory / 'export-menu-recipe.ahk'
        menu_script.write_text(
            'dialog := WinExist("Save As ahk_exe Illustrator.exe")\n'
            'AcuKeys("ahk_id " dialog, "{Esc}")\n'
            'if !WinWaitClose("ahk_id " dialog, , 3)\n    throw Error("Save As did not cancel")\n'
            f'AcuKeys("{target}", "!fe{{Right}}{{Down}}{{Enter}}")\n'
            'opened := AcuWaitUntil(() => WinExist("Export ahk_class #32770 ahk_exe Illustrator.exe"), 5000)\n'
            'if !opened || WinGetTitle("ahk_id " opened) != "Export"\n'
            '    throw Error("Export As menu recipe did not open Export As")\n', encoding='utf-8')
        acu_observer(directory, menu_script)
    finally:
        if (directory / 'illustrator-identity.json').exists():
            try:
                cleanup = cleanup_desktop(directory, acu_observer)
                assert cleanup['passed']
            finally:
                acu_observer(directory, ROOT / 'bench/restore_cursor.ahk')


def test_unknown_scenario_is_rejected_before_creating_a_workspace(tmp_path):
    with pytest.raises(ValueError, match='scenario'):
        prepare('pi-acu', tmp_path / 'unknown', scenario='unknown')
    assert not (tmp_path / 'unknown').exists()
