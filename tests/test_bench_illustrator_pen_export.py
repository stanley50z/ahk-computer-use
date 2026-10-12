"""Adobe Illustrator Pen and Export preparation and grading boundaries; the native integration check is explicitly desktop-marked."""

import hashlib
import json
import subprocess
import sys
from uuid import uuid4

import pytest
from PIL import Image

from bench.run import ROOT, prepare


def test_illustrator_pen_export_prepare_freezes_only_actor_assets_and_jpeg_grading_reference(tmp_path):
    skill = tmp_path / 'acu'
    skill.mkdir()
    (skill / 'SKILL.md').write_text('---\nname: acu\ndescription: fixture\n---\n', encoding='utf-8')
    directory = tmp_path / 'trial'
    plan = prepare('pi-acu', directory, skill=skill, scenario='illustrator-pen-export')
    assert plan['scenario'] == 'illustrator-pen-export'
    assert plan['grading']['shape_pass_threshold'] is None
    assert plan['grading']['registration'] == 'none'
    assert plan['grading']['mode'] == 'image-only-single-attempt'
    assert plan['actor_deliverables'] == ['Cloud9-Recreated.png']
    assert plan['trial_policy']['attempts_per_configuration'] == 5
    assert plan['trial_policy']['replace_failed_attempts'] is False
    assert sorted(p.name for p in (directory / 'workspace').iterdir()) == [
        'Cloud9-Pen-Starter.ai', 'Cloud9-Reference.jpg']
    for name in ('Cloud9-Pen-Starter.ai', 'Cloud9-Reference.jpg'):
        data = (ROOT / 'bench/assets/illustrator-pen-export' / name).read_bytes()
        assert (directory / 'workspace' / name).read_bytes() == data
        assert plan['assets'][name] == hashlib.sha256(data).hexdigest()
    reference = directory / 'grading/reference.jpg'
    assert reference.read_bytes() == (directory / 'workspace/Cloud9-Reference.jpg').read_bytes()
    prompt = (directory / 'prompt.txt').read_text(encoding='utf-8')
    assert '#00AEEF' in prompt and '72 ppi' in prompt
    assert 'Pen tool' in prompt and 'remove' in prompt
    assert 'c9.gg' not in prompt and 'guidelines' not in prompt.lower()
    assert 'Image Trace' in prompt and 'scripting' in prompt
    assert 'one drawing attempt' in prompt
    assert 'do not redraw' in prompt.lower()
    assert 'result.json' not in prompt and 'Cloud9-Recreated.ai' not in prompt
    assert 'Cloud9-Recreated.png' in prompt
    assert not (directory / 'agent-home/auth.json').exists()
    assert json.loads((directory / 'plan.json').read_text(encoding='utf-8')) == plan


def test_cli_prepares_illustrator_pen_export_without_desktop_approval(tmp_path):
    directory = tmp_path / 'cli-trial'
    completed = subprocess.run(
        [sys.executable, str(ROOT / 'bench/run.py'), 'prepare', '--scenario', 'illustrator-pen-export',
         '--arm', 'pi-acu', '--run-dir', str(directory)],
        capture_output=True, text=True, encoding='utf-8', timeout=20)
    assert completed.returncode == 0, completed.stderr
    plan = json.loads(completed.stdout)
    assert plan['scenario'] == 'illustrator-pen-export'
    assert plan['scenario_version'] == 'Adobe Illustrator Pen and Export v0.4 (single attempt)'
    # The task changed, but the prepared starter and separate reference bytes stay fixed.
    assert plan['prompt_sha256'] != 'b6b38f65c7675f11b27fd94fa0fcbef75d38208c441a6914727ef97a6f3c254b'
    assert plan['assets'] == {
        'Cloud9-Pen-Starter.ai': 'd2197b639dd7c9d4528962f8252bdbb0e6d250551f16675324ea95e2e0d99445',
        'Cloud9-Reference.jpg': '715a4a7e15cb0e5ecc3452ef53585971eb7cb9ca5e61334c10bf1de443333231',
    }
    assert not (directory / 'state.json').exists()


def test_image_only_output_succeeds_without_an_ai_or_manifest_and_quality_is_observational(tmp_path):
    from bench.illustrator_pen_export import shape_metrics, verify_outputs

    reference = Image.new('RGB', (40, 40), 'white')
    for x in range(10, 20):
        for y in range(12, 24):
            reference.putpixel((x, y), (0, 174, 239))
    exact = shape_metrics(reference, reference)
    assert exact['foreground_iou'] == 1 and exact['boundary_mean_manhattan_px'] == 0
    moved = Image.new('RGB', (40, 40), 'white')
    moved.paste(reference.crop((10, 12, 20, 24)), (15, 12))
    assert shape_metrics(moved, reference)['foreground_iou'] == pytest.approx(1 / 3)

    directory = tmp_path / 'trial'
    prepare('pi-acu', directory, scenario='illustrator-pen-export')
    workspace = directory / 'workspace'
    # A crude blue rectangle is a completed export, not a good drawing. Quality must not become a hidden pass threshold.
    image = Image.new('RGB', (800, 800), 'white')
    image.paste((0, 174, 239), (100, 100, 200, 200))
    image.save(workspace / 'Cloud9-Recreated.png', dpi=(72, 72))
    verdict = verify_outputs(directory)
    assert verdict['passed'] is True and verdict['problems'] == []
    assert verdict['quality']['foreground_iou'] < .1
    assert 'vector' not in verdict and 'method' not in verdict and 'claim' not in verdict
    assert not (workspace / 'Cloud9-Recreated.ai').exists()
    assert not (workspace / 'result.json').exists()
    (workspace / 'result.json').write_text('invalid and irrelevant JSON', encoding='utf-8')
    assert verify_outputs(directory)['passed'], 'an unsolicited report file must not trip PNG grading'
    image.convert('RGBA').save(workspace / 'Cloud9-Recreated.png')
    assert verify_outputs(directory)['passed'], 'opaque RGBA is valid'
    transparent = image.convert('RGBA')
    transparent.putalpha(0)
    transparent.save(workspace / 'Cloud9-Recreated.png')
    assert verify_outputs(directory)['checks']['opaque'] is False
    Image.new('RGB', (400, 400), 'white').save(workspace / 'Cloud9-Recreated.png')
    assert verify_outputs(directory)['checks']['dimensions'] is False
    (workspace / 'Cloud9-Recreated.png').write_bytes(b'not a PNG')
    assert verify_outputs(directory)['passed'] is False
    (workspace / 'Cloud9-Recreated.png').unlink()
    assert verify_outputs(directory)['passed'] is False


def test_image_grading_refuses_a_modified_frozen_reference(tmp_path):
    from bench.illustrator_pen_export import verify_outputs

    directory = tmp_path / 'trial'
    prepare('pi-acu', directory, scenario='illustrator-pen-export')
    (directory / 'grading/reference.jpg').write_bytes(b'changed')
    with pytest.raises(ValueError, match='reference'):
        verify_outputs(directory)


def test_illustrator_pen_export_cleanup_protects_existing_documents_and_refuses_unclaimed_work(tmp_path):
    from bench.illustrator_pen_export import owned_documents

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


def test_illustrator_pen_export_conduct_accepts_illustrator_not_a_new_calculator(tmp_path):
    from bench.run import conduct_audit

    plan = {'scenario': 'illustrator-pen-export', 'run_dir': str(tmp_path), 'workspace': str(tmp_path), 'skill_path': str(ROOT / 'acu/SKILL.md')}
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
def test_illustrator_pen_export_real_illustrator_preparation_and_owned_document_cleanup(tmp_path):
    from bench.run import acu_observer
    from bench.illustrator_pen_export import prepare_desktop, inspect_native, verify_outputs, cleanup_desktop

    directory = ROOT / '.pi/illustrator-pen-export-validation' / f'native-check-{uuid4().hex[:8]}'
    plan = prepare('pi-acu', directory, scenario='illustrator-pen-export')
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
                          (ROOT / 'tests/scripts/illustrator_pen_export_saved_fixture.jsx').read_text(encoding='utf-8'), encoding='utf-8')
        acu_observer(directory, ROOT / 'bench/illustrator/run-jsx.ahk', script, result,
                     identity['hwnd'], identity['pid'], timeout=40)
        assert result.read_text(encoding='utf-8') == 'SUCCESS'
        inspect_native(directory, acu_observer)  # Maintainer-only geometry regression, not an actor deliverable.
        inspected = json.loads((directory / 'native-verification.json').read_text(encoding='utf-8'))
        assert all(inspected['checks'].values())
        first = inspected['paths'][0]['points'][0]
        assert first['anchor'] == pytest.approx([200, 600], abs=.75)
        assert first['right'] == pytest.approx([350, 600], abs=.75)
        assert verify_outputs(directory)['passed']
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


@pytest.mark.parametrize('scenario', ['unknown', 'testbench-2'])
def test_unknown_or_retired_scenario_is_rejected_before_creating_a_workspace(tmp_path, scenario):
    with pytest.raises(ValueError, match='scenario'):
        prepare('pi-acu', tmp_path / 'unknown', scenario=scenario)
    assert not (tmp_path / 'unknown').exists()
