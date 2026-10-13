"""Adobe Illustrator Pen and Export preparation and grading boundaries; the native integration check is explicitly desktop-marked."""

import hashlib
import json
import subprocess
import sys
from uuid import uuid4

import pytest
from PIL import Image

from bench.run import ROOT, prepare


def test_lossless_reference_png_preserves_the_previous_reference_framing(tmp_path):
    from bench.illustrator_pen_export import shape_metrics, verify_outputs

    path = ROOT / 'bench/assets/illustrator-pen-export/Cloud9-Reference.png'
    with Image.open(path) as reference:
        assert reference.format == 'PNG'
        assert reference.mode == 'RGB' and reference.size == (800, 800)
        assert reference.getpixel((0, 0)) == (255, 255, 255)
        assert reference.getpixel((417, 230)) == (0, 174, 239)
        # Independent bounds recorded from the former reference; preparation must not change its framing.
        assert shape_metrics(reference, reference)['foreground_bounds'] == [143, 206, 693, 585]
    directory = tmp_path / 'trial'
    prepare('pi-acu', directory, scenario='illustrator-pen-export')
    (directory / 'workspace/Cloud9-Recreated.png').write_bytes(path.read_bytes())
    assert verify_outputs(directory)['passed'], 'the prepared reference must itself satisfy the PNG appearance/export checks'


def test_illustrator_pen_export_prepare_freezes_png_and_resolves_task_paths(tmp_path):
    skill = tmp_path / 'acu'
    skill.mkdir()
    (skill / 'SKILL.md').write_text('---\nname: acu\ndescription: fixture\n---\n', encoding='utf-8')
    directory = tmp_path / 'trial'
    plan = prepare('pi-acu', directory, skill=skill, scenario='illustrator-pen-export')
    assert plan['scenario'] == 'illustrator-pen-export'
    assert plan['grading']['shape_pass_threshold'] is None
    assert plan['grading']['registration'] == 'none'
    assert plan['grading']['mode'] == 'image-only'
    assert plan['actor_deliverables'] == ['Cloud9-Recreated.png']
    assert plan['trial_policy'] == {'attempts_per_configuration': 3, 'aggregation': 'all-successes',
                                    'replace_failed_attempts': False}
    assert sorted(p.name for p in (directory / 'workspace').iterdir()) == [
        'Cloud9-Pen-Starter.ai', 'Cloud9-Reference.png', 'scratch']
    assert (directory / 'workspace/scratch').is_dir()
    for name in ('Cloud9-Pen-Starter.ai', 'Cloud9-Reference.png'):
        data = (ROOT / 'bench/assets/illustrator-pen-export' / name).read_bytes()
        assert (directory / 'workspace' / name).read_bytes() == data
        assert plan['assets'][name] == hashlib.sha256(data).hexdigest()
    reference = directory / 'grading/reference.png'
    assert reference.read_bytes() == (directory / 'workspace/Cloud9-Reference.png').read_bytes()
    prompt = (directory / 'prompt.txt').read_text(encoding='utf-8')
    assert '#00AEEF' in prompt and '72 ppi' in prompt
    assert '800 × 800' in prompt and 'opaque white background' in prompt and 'non-interlaced' in prompt
    for widget in ('Export As', 'Use Artboards', 'Art Optimized', 'Interlaced off'):
        assert widget not in prompt, 'specify output properties, not a sequence of GUI controls'
    assert 'Pen tool' in prompt and 'then export' in prompt
    assert 'Use the supplied computer-use tool for every interaction with Adobe Illustrator.' in prompt
    assert 'c9.gg' not in prompt and 'guidelines' not in prompt.lower()
    for removed in ('visually', 'by eye', 'parametric', 'literal positions', 'Image Trace',
                    'no stroke', 'opacity', 'rename', 'Keep all task-created', '800 × 800-point'):
        assert removed not in prompt
    workspace = (directory / 'workspace').as_posix()
    assert f'Workspace: {workspace}\nScratch folder: {workspace}/scratch\nFinal output: {workspace}/Cloud9-Recreated.png' in prompt
    assert prompt.endswith('Only the PNG is required. Stop after exporting.\n')
    assert '<WORKSPACE>' not in prompt
    assert prompt in plan['command']
    template = (directory / 'prompt-template.txt').read_text(encoding='utf-8')
    assert '<WORKSPACE>' in template
    assert plan['prompt_template_sha256'] == hashlib.sha256(template.encode('utf-8')).hexdigest()
    assert plan['prompt_sha256'] == hashlib.sha256(prompt.encode('utf-8')).hexdigest()
    assert 'Color Picker' not in prompt, 'do not prescribe an appearance-control route'
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
    assert plan['scenario_version'] == 'Adobe Illustrator Pen and Export v0.7'
    # The blank starter is unchanged; the new reference is derived from the official lossless PNG.
    assert plan['prompt_sha256'] != 'b6b38f65c7675f11b27fd94fa0fcbef75d38208c441a6914727ef97a6f3c254b'
    assert plan['assets'] == {
        'Cloud9-Pen-Starter.ai': 'd2197b639dd7c9d4528962f8252bdbb0e6d250551f16675324ea95e2e0d99445',
        'Cloud9-Reference.png': '03dd860809cbfa143c35b50bd78fbdb8e43346e47d76e9aba5afc94a4e00a32c',
    }
    assert not (directory / 'state.json').exists()


def test_preparation_leaves_export_settings_and_artifact_creation_to_the_actor(tmp_path, monkeypatch):
    from bench.illustrator_pen_export import prepare_desktop

    programs = tmp_path / 'programs'
    executable = programs / 'Adobe/Adobe Illustrator Fixture/Support Files/Contents/Windows/Illustrator.exe'
    executable.parent.mkdir(parents=True)
    executable.touch()
    monkeypatch.setenv('ProgramFiles', str(programs))
    directory = tmp_path / 'trial'
    plan = prepare('pi-acu', directory, scenario='illustrator-pen-export')
    preferences = {'ResolutionR': 144, 'AntiAlias': 2, 'BackgroundTransparent': True, 'Interlaced': True}

    # Only the external desktop boundary is simulated; the real preparation code and files are used.
    def observer(run_dir, script, *args, **kwargs):
        if script.name == 'ensure.ahk':
            return 'illustrator=10\npid=20\nstarted=1\n'
        if script.name == 'window.ahk':
            args[2].write_text('{"maximized":true,"monitor":1,"bounds":[-8,-8,1936,1056],"work_area":[0,0,1920,1040]}', encoding='utf-8')
            return ''
        if script.name == 'run-jsx.ahk':
            config = json.loads(args[0].read_text(encoding='utf-8').split('\n', 1)[0].removeprefix('var config = ').removesuffix(';'))
            result = {'documents': [], 'png_preferences': preferences} if config['phase'] == 'snapshot' else {
                'documents': [{'path': str(directory / 'workspace/Cloud9-Pen-Starter.ai')}], 'zoom': 1}
            args[1].write_text(json.dumps(result), encoding='utf-8')
            return ''
        if script.name == 'input-state.ahk':
            return ''
        pytest.fail(f'Normal preparation must not export or modify export options: {script.name}')

    prepared = prepare_desktop(plan, observer)
    assert prepared['window']['maximized'] is True
    assert json.loads((directory / 'illustrator-preferences-before.json').read_text(encoding='utf-8')) == preferences
    assert not (directory / 'grading/blank-calibration.png').exists()
    assert not (directory / 'workspace/Cloud9-Recreated.png').exists()
    assert not (directory / 'illustrator-export-options.json').exists()


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
    image.convert('RGBA').save(workspace / 'Cloud9-Recreated.png', dpi=(72, 72))
    assert verify_outputs(directory)['passed'], 'opaque RGBA with the requested density is valid'
    image.save(workspace / 'Cloud9-Recreated.png')
    assert verify_outputs(directory)['checks']['resolution_metadata'] is False, '72 ppi is a requested final-file property'
    image.save(workspace / 'Cloud9-Recreated.png', dpi=(144, 144))
    assert verify_outputs(directory)['checks']['resolution_metadata'] is False
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


@pytest.mark.parametrize('suffix', ['-01', '-Drawing'])
def test_image_grading_accepts_a_unique_artboard_suffix_without_renaming(tmp_path, suffix):
    from bench.illustrator_pen_export import verify_outputs

    directory = tmp_path / 'trial'
    prepare('pi-acu', directory, scenario='illustrator-pen-export')
    output = directory / f'workspace/Cloud9-Recreated{suffix}.png'
    image = Image.new('RGB', (800, 800), 'white')
    image.paste((0, 174, 239), (100, 100, 200, 200))
    image.save(output, dpi=(72, 72))
    verdict = verify_outputs(directory)
    assert verdict['passed'] is True, verdict
    assert verdict['output'] == str(output)
    assert output.is_file()
    assert not (directory / 'workspace/Cloud9-Recreated.png').exists(), 'verification must not repair/rename actor work'
    image.save(directory / 'workspace/Cloud9-Recreated-Other.png')
    ambiguous = verify_outputs(directory)
    assert ambiguous['passed'] is False
    assert 'ambiguous' in ' '.join(ambiguous['problems']).lower()


def test_image_grading_refuses_a_modified_frozen_reference(tmp_path):
    from bench.illustrator_pen_export import verify_outputs

    directory = tmp_path / 'trial'
    prepare('pi-acu', directory, scenario='illustrator-pen-export')
    (directory / 'grading/reference.png').write_bytes(b'changed')
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
    outside = [{'name': 'write', 'text': str(tmp_path.parent / 'helper.py') + '\nprint(1)'}]
    scratch = conduct_audit(plan, before, 'window=1 pid=5\nwindow=9 pid=8\nillustrator=9\npid=8\n', {}, {}, outside)
    assert scratch['passed'], 'the scratch-folder hint is not a location restriction'
    assert scratch['writes_outside_workspace'], 'retain diagnostic evidence without a hidden disqualifier'
    guarded = conduct_audit(plan, before, before, {'protected': 'original'}, {'protected': 'changed'}, outside)
    assert not guarded['passed'] and guarded['problems'] == ['guarded files changed']
    stray = conduct_audit(plan, before, 'window=1 pid=5\nwindow=9 pid=8\ncalculator=9\npid=8\n', {}, {}, [])
    assert not stray['passed']
    shadow_before = 'window=1 pid=5\nwindow=2 pid=8\nwindow=3 pid=8\nclass=2 SysShadow\nclass=3 illustrator\nillustrator=3\npid=8\n'
    shadow_after = 'window=1 pid=5\nwindow=3 pid=8\nillustrator=3\npid=8\n'
    assert conduct_audit(plan, shadow_before, shadow_after, {}, {}, [])['passed'], 'Illustrator menu/tooltip shadows are not user windows'
    assert not conduct_audit(plan, shadow_before, 'window=1 pid=5\n', {}, {}, [])['passed'], 'the actual main frame stays protected'


@pytest.mark.desktop
def test_illustrator_pen_export_real_illustrator_preparation_and_owned_document_cleanup(tmp_path):
    from bench.run import acu_observer
    from bench.illustrator_pen_export import prepare_desktop, inspect_native, verify_outputs, cleanup_desktop, dismiss_task_dialogs
    from concurrent.futures import ThreadPoolExecutor

    directory = ROOT / '.pi/illustrator-pen-export-validation' / f'native-check-{uuid4().hex[:8]}'
    plan = prepare('pi-acu', directory, scenario='illustrator-pen-export')
    acu_observer(directory, ROOT / 'bench/probe.ahk', suffix='-before')
    try:
        prepared = prepare_desktop(plan, acu_observer)
        assert prepared['zoom'] == 1
        assert prepared['window']['maximized'] is True
        before_preferences = json.loads((directory / 'illustrator-preferences-before.json').read_text(encoding='utf-8'))
        assert prepared['png_preferences'] == before_preferences
        assert not (directory / 'grading/blank-calibration.png').exists()
        assert not (directory / 'illustrator-export-options.json').exists()
        assert prepared['workspace'] == 'Getting Started'
        assert any(d['name'] == 'Cloud9-Pen-Starter.ai' for d in prepared['documents'])
        identity = json.loads((directory / 'illustrator-identity.json').read_text(encoding='utf-8'))
        workspace = directory / 'workspace'
        window_check = directory / 'check-initial-window.ahk'
        window_check.write_text(
            f'target := "ahk_id {identity["hwnd"]}"\n'
            'if WinGetMinMax(target) != 1\n    throw Error("Prepared Illustrator is not maximized")\n'
            'MonitorGetWorkArea MonitorGetPrimary(), &left, &top, &right, &bottom\n'
            'WinGetPos &x, &y, &width, &height, target\n'
            'if x > left || y > top || x+width < right || y+height < bottom\n'
            '    throw Error("Prepared Illustrator does not cover the primary work area")\n', encoding='utf-8')
        acu_observer(directory, window_check)
        # Optional maintainer fixture check, never part of normal trial preparation.
        calibration = directory / 'grading/blank-calibration.png'
        acu_observer(directory, ROOT / 'bench/illustrator/prepare-export.ahk', identity['hwnd'], identity['pid'],
                     calibration, directory / 'fixture-export-options.json', timeout=40)
        with Image.open(calibration) as blank:
            assert blank.size == (800, 800)
            assert blank.convert('RGBA').getextrema() == ((255, 255),) * 4
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
        dismiss_task_dialogs(directory, acu_observer)

        # Exercise the actual ownerless-picker failure, not a substitute owned Save As dialog.
        picker_result = directory / 'picker-result.json'
        picker_script = directory / 'picker-fixture.jsx'
        picker_script.write_text('var config = ' + json.dumps({'result': str(picker_result)}) + ';\n' +
            (ROOT / 'tests/scripts/illustrator_color_picker.jsx').read_text(encoding='utf-8'), encoding='utf-8')
        picker_state = directory / 'picker-state.json'
        picker_probe = directory / 'observe-ownerless-picker.ahk'
        picker_probe.write_text(
            f'pid := {identity["pid"]}\n'
            'dialog := AcuWaitUntil(() => WinExist("Color Picker ahk_class #32770 ahk_pid " pid), 10000)\n'
            'if !dialog\n    throw Error("Fixture Color Picker did not appear")\n'
            'owner := DllCall("GetWindow", "ptr", dialog, "uint", 4, "ptr")\n'
            'FileAppend \'{"hwnd":\' dialog \',"owner":\' owner \'}\', A_Args[1], "UTF-8-RAW"\n'
            'if owner != 0\n    throw Error("Fixture did not reproduce the ownerless Color Picker")\n', encoding='utf-8')
        with ThreadPoolExecutor(max_workers=1) as executor:
            opening = executor.submit(acu_observer, directory, ROOT / 'bench/illustrator/run-jsx.ahk',
                                      picker_script, picker_result, identity['hwnd'], identity['pid'],
                                      suffix='-picker-fixture', timeout=45)
            try:
                acu_observer(directory, picker_probe, picker_state, timeout=15)
                picker = json.loads(picker_state.read_text(encoding='utf-8'))
                protected = directory / 'protected-picker-probe.log'
                protected.write_text((directory / 'observer-probe-before.log').read_text(encoding='utf-8') +
                                     f'\nhiddenwindow={picker["hwnd"]} pid={identity["pid"]}\n', encoding='utf-8')
                with pytest.raises(RuntimeError, match='dismiss-dialogs'):
                    acu_observer(directory, ROOT / 'bench/illustrator/dismiss-dialogs.ahk',
                                 identity['hwnd'], identity['pid'], protected, suffix='-protected-picker')
                preserved = directory / 'check-picker-preserved.ahk'
                preserved.write_text(f'if !WinExist("ahk_id {picker["hwnd"]}")\n'
                                     '    throw Error("Pre-existing picker was cancelled")\n', encoding='utf-8')
                acu_observer(directory, preserved)
            finally:
                # The genuine baseline does not contain this fixture-created picker; cancel it, never accept it.
                try:
                    acu_observer(directory, ROOT / 'bench/illustrator/dismiss-dialogs.ahk',
                                 identity['hwnd'], identity['pid'], directory / 'observer-probe-before.log',
                                 suffix='-ownerless-picker')
                finally:
                    # Test-resource teardown also works when the production cancellation regresses.
                    # It cannot make the regression pass: the production cancelled= log is asserted below.
                    if picker_state.exists():
                        recorded = json.loads(picker_state.read_text(encoding='utf-8'))
                        release = directory / 'release-fixture-picker.ahk'
                        release.write_text(f'target := "ahk_id {recorded["hwnd"]}"\n'
                            f'if WinExist(target) && WinGetPID(target) = {identity["pid"]} && WinGetTitle(target) = "Color Picker" {{\n'
                            '    UIA.ElementFromHandle(target).FindElement({Type:"Button", Name:"Cancel"}).Invoke()\n'
                            '    if !WinWaitClose(target, , 3)\n        throw Error("Fixture picker remains open")\n}\n', encoding='utf-8')
                        acu_observer(directory, release)
                    opening.result(timeout=55)
        assert json.loads(picker_result.read_text(encoding='utf-8')) == {'closed': True}
        assert f'cancelled={picker["hwnd"]} Color Picker' in (directory / 'observer-dismiss-dialogs-ownerless-picker.log').read_text(encoding='utf-8')
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
