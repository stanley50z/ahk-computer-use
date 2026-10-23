"""Adobe Illustrator Pen Tool preparation and grading boundaries; the native integration check is explicitly desktop-marked."""

import hashlib
import json
import subprocess
import sys
from uuid import uuid4

import pytest
from PIL import Image

import bench.run
from bench.run import ROOT, prepare
from conftest import needs_cloud9_reference


@needs_cloud9_reference
def test_lossless_reference_png_preserves_the_previous_reference_framing(tmp_path):
    from bench.illustrator_pen_tool import shape_metrics, verify_outputs

    path = ROOT / 'bench/assets/illustrator-pen-tool/Cloud9-Reference.png'
    with Image.open(path) as reference:
        assert reference.format == 'PNG'
        assert reference.mode == 'RGB' and reference.size == (800, 800)
        assert reference.getpixel((0, 0)) == (255, 255, 255)
        assert reference.getpixel((417, 230)) == (0, 174, 239)
        # Independent bounds recorded from the former reference; preparation must not change its framing.
        assert shape_metrics(reference, reference)['foreground_bounds'] == [143, 206, 693, 585]
    directory = tmp_path / 'trial'
    prepare('pi-acu', directory, scenario='illustrator-pen-tool')
    (directory / 'grading/Cloud9-Recreated.png').write_bytes(path.read_bytes())
    assert verify_outputs(directory)['passed'], 'the prepared reference must itself satisfy the PNG appearance/export checks'


def test_illustrator_pen_tool_prepare_freezes_png_and_resolves_task_paths(tmp_path):
    skill = tmp_path / 'acu'
    skill.mkdir()
    (skill / 'SKILL.md').write_text('---\nname: acu\ndescription: fixture\n---\n', encoding='utf-8')
    directory = tmp_path / 'trial'
    plan = prepare('pi-acu', directory, skill=skill, scenario='illustrator-pen-tool')
    assert plan['scenario'] == 'illustrator-pen-tool'
    assert plan['grading']['shape_pass_threshold'] is None
    assert plan['grading']['registration'] == 'none'
    assert plan['grading']['mode'] == 'live-drawing'
    assert plan['actor_deliverables'] == []
    assert plan['export_policy'] == {
        'owner': 'maintainer-cleanup', 'attempts': 2, 'output': 'grading/Cloud9-Recreated.png',
        'dimensions': [800, 800], 'background': 'opaque-white', 'dpi': 72,
        'interlaced': False, 'failure_classification': 'infrastructure'}
    assert plan['trial_policy'] == {'attempts_per_configuration': 3, 'aggregation': 'all-successes',
                                    'replace_failed_attempts': False}
    assert sorted(p.name for p in (directory / 'workspace').iterdir()) == [
        '.ahk-computer-use', 'Cloud9-Pen-Starter.ai', 'Cloud9-Reference.png', 'scratch']
    assert (directory / 'workspace/scratch').is_dir()
    for name, source in (('Cloud9-Pen-Starter.ai', ROOT / 'bench/assets/illustrator-pen-tool/Cloud9-Pen-Starter.ai'),
                         ('Cloud9-Reference.png', bench.run.ILLUSTRATOR_REFERENCE)):
        data = source.read_bytes()
        assert (directory / 'workspace' / name).read_bytes() == data
        assert plan['assets'][name] == hashlib.sha256(data).hexdigest()
    reference = directory / 'grading/reference.png'
    assert reference.read_bytes() == (directory / 'workspace/Cloud9-Reference.png').read_bytes()
    prompt = (directory / 'prompt.txt').read_text(encoding='utf-8')
    assert 'Set the fill color to #00AEEF. Set the stroke to None (no stroke).' in prompt
    assert 'genuine Bézier curves' in prompt and "Pen tool's direction handles" in prompt
    assert 'Do not approximate curves with many short straight-line segments.' in prompt
    assert '72 ppi' not in prompt and '800 × 800' not in prompt and 'Final output:' not in prompt
    assert 'Pen tool' in prompt and 'then export' not in prompt
    assert 'Use the supplied computer-use tool for every interaction with Adobe Illustrator.' in prompt
    assert 'c9.gg' not in prompt and 'guidelines' not in prompt.lower()
    for removed in ('visually', 'by eye', 'parametric', 'literal positions', 'Image Trace',
                    'opacity', 'rename', 'Keep all task-created', '800 × 800-point'):
        assert removed not in prompt
    from pathlib import Path
    workspace = prompt.split('Workspace: ', 1)[1].split('\n', 1)[0]
    assert Path(workspace).expanduser().resolve() == (directory / 'workspace').resolve()
    assert f'Workspace: {workspace}\nScratch folder: {workspace}/scratch' in prompt
    assert prompt.endswith('Stop when the drawing is finished, leaving it open.\n')
    assert '<WORKSPACE>' not in prompt
    assert prompt in plan['command']
    template = (directory / 'prompt-template.txt').read_text(encoding='utf-8')
    assert '<WORKSPACE>' in template
    assert plan['prompt_template_sha256'] == hashlib.sha256(template.encode('utf-8')).hexdigest()
    assert plan['prompt_sha256'] == hashlib.sha256(prompt.encode('utf-8')).hexdigest()
    assert 'Color Picker' not in prompt, 'do not prescribe an appearance-control route'
    assert 'result.json' not in prompt and 'Cloud9-Recreated.ai' not in prompt
    assert 'Cloud9-Recreated.png' not in prompt
    assert not (directory / 'agent-home/auth.json').exists()
    assert json.loads((directory / 'plan.json').read_text(encoding='utf-8')) == plan


@needs_cloud9_reference
def test_cli_prepares_illustrator_pen_tool_without_desktop_approval(tmp_path):
    directory = tmp_path / 'cli-trial'
    completed = subprocess.run(
        [sys.executable, str(ROOT / 'bench/run.py'), 'prepare', '--scenario', 'illustrator-pen-tool',
         '--arm', 'pi-acu', '--run-dir', str(directory)],
        capture_output=True, text=True, encoding='utf-8', timeout=20)
    assert completed.returncode == 0, completed.stderr
    plan = json.loads(completed.stdout)
    assert plan['scenario'] == 'illustrator-pen-tool'
    assert plan['scenario_version'] == 'Adobe Illustrator Pen Tool v0.11'
    # The blank starter is unchanged; the new reference is derived from the official lossless PNG.
    assert plan['prompt_sha256'] != 'b6b38f65c7675f11b27fd94fa0fcbef75d38208c441a6914727ef97a6f3c254b'
    assert plan['assets'] == {
        'Cloud9-Pen-Starter.ai': 'd2197b639dd7c9d4528962f8252bdbb0e6d250551f16675324ea95e2e0d99445',
        'Cloud9-Reference.png': '03dd860809cbfa143c35b50bd78fbdb8e43346e47d76e9aba5afc94a4e00a32c',
    }
    assert not (directory / 'state.json').exists()


def test_preparation_leaves_export_settings_untouched_until_post_actor_cleanup(tmp_path, monkeypatch):
    from bench.illustrator_pen_tool import prepare_desktop

    programs = tmp_path / 'programs'
    executable = programs / 'Adobe/Adobe Illustrator Fixture/Support Files/Contents/Windows/Illustrator.exe'
    executable.parent.mkdir(parents=True)
    executable.touch()
    monkeypatch.setenv('ProgramFiles', str(programs))
    directory = tmp_path / 'trial'
    plan = prepare('pi-acu', directory, scenario='illustrator-pen-tool')
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


def test_maintainer_png_quality_is_observational_and_requires_no_actor_ai_or_manifest(tmp_path):
    from bench.illustrator_pen_tool import shape_metrics, verify_outputs

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
    prepare('pi-acu', directory, scenario='illustrator-pen-tool')
    workspace = directory / 'workspace'
    # PNG inspection is separate from native Bézier/method verification; numeric quality is not a pass threshold.
    image = Image.new('RGB', (800, 800), 'white')
    image.paste((0, 174, 239), (100, 100, 200, 200))
    image.save(directory / 'grading/Cloud9-Recreated.png', dpi=(72, 72))
    verdict = verify_outputs(directory)
    assert verdict['passed'] is True and verdict['problems'] == []
    assert verdict['quality']['foreground_iou'] < .1
    assert 'vector' not in verdict and 'method' not in verdict and 'claim' not in verdict
    assert not (workspace / 'Cloud9-Recreated.ai').exists()
    assert not (workspace / 'result.json').exists()
    (workspace / 'result.json').write_text('invalid and irrelevant JSON', encoding='utf-8')
    assert verify_outputs(directory)['passed'], 'an unsolicited report file must not trip PNG grading'
    image.convert('RGBA').save(directory / 'grading/Cloud9-Recreated.png', dpi=(72, 72))
    assert verify_outputs(directory)['passed'], 'opaque RGBA with the requested density is valid'
    image.save(directory / 'grading/Cloud9-Recreated.png')
    assert verify_outputs(directory)['checks']['resolution_metadata'] is False, '72 ppi is a requested final-file property'
    image.save(directory / 'grading/Cloud9-Recreated.png', dpi=(144, 144))
    assert verify_outputs(directory)['checks']['resolution_metadata'] is False
    transparent = image.convert('RGBA')
    transparent.putalpha(0)
    transparent.save(directory / 'grading/Cloud9-Recreated.png')
    assert verify_outputs(directory)['checks']['opaque'] is False
    Image.new('RGB', (400, 400), 'white').save(directory / 'grading/Cloud9-Recreated.png')
    assert verify_outputs(directory)['checks']['dimensions'] is False
    (directory / 'grading/Cloud9-Recreated.png').write_bytes(b'not a PNG')
    assert verify_outputs(directory)['passed'] is False
    (directory / 'grading/Cloud9-Recreated.png').unlink()
    assert verify_outputs(directory)['passed'] is False


def test_png_grading_ignores_unsolicited_actor_exports_and_requires_maintainer_output(tmp_path):
    from bench.illustrator_pen_tool import verify_outputs

    directory = tmp_path / 'trial'
    prepare('pi-acu', directory, scenario='illustrator-pen-tool')
    image = Image.new('RGB', (800, 800), 'white')
    image.paste((0, 174, 239), (100, 100, 200, 200))
    for suffix in ('', '-01', '-Drawing'):
        image.save(directory / f'workspace/Cloud9-Recreated{suffix}.png', dpi=(72, 72))
    assert not verify_outputs(directory)['passed'], 'actor exports are not maintainer evidence'
    output = directory / 'grading/Cloud9-Recreated.png'
    image.save(output, dpi=(72, 72))
    verdict = verify_outputs(directory)
    assert verdict['passed'] and verdict['output'] == str(output)


def test_image_grading_refuses_a_modified_frozen_reference(tmp_path):
    from bench.illustrator_pen_tool import verify_outputs

    directory = tmp_path / 'trial'
    prepare('pi-acu', directory, scenario='illustrator-pen-tool')
    (directory / 'grading/reference.png').write_bytes(b'changed')
    with pytest.raises(ValueError, match='reference'):
        verify_outputs(directory)


def test_illustrator_pen_tool_cleanup_protects_existing_documents_and_refuses_unclaimed_work(tmp_path):
    from bench.illustrator_pen_tool import owned_documents

    workspace = tmp_path / 'workspace'
    workspace.mkdir()
    existing = {'path': str(tmp_path / 'user-root/Downloads/Cloud9 Icon.ai'), 'name': 'Cloud9 Icon.ai', 'saved': False}
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



# Simulate only the external AHK/Illustrator boundary; cleanup, ownership, encoding and grading run normally.
def drawing_cleanup_fixture(tmp_path, *, export_errors=0, straight=False, wrong_fill=False,
                            render_size=(800, 800), export_mutates_drawing=False, flat_loop=False,
                            native_fill_unknown=False, export_marks_dirty=False):
    directory = tmp_path / 'trial'
    prepare('pi-acu', directory, scenario='illustrator-pen-tool')
    existing = {'path': str(tmp_path / 'existing.ai'), 'name': 'existing.ai', 'saved': False,
                'artwork_signature': 'protected'}
    drawing = {'path': str(directory / 'workspace/Cloud9-Pen-Starter.ai'),
               'name': 'Cloud9-Pen-Starter.ai', 'saved': False, 'artwork_signature': 'unchanged'}
    documents = [existing, drawing]
    preferences = {'ResolutionR': 144}
    (directory / 'illustrator-identity.json').write_text('{"hwnd":10,"pid":20,"started":0}', encoding='utf-8')
    (directory / 'illustrator-before.json').write_text(json.dumps([existing]), encoding='utf-8')
    (directory / 'illustrator-preferences-before.json').write_text(json.dumps(preferences), encoding='utf-8')
    state = {'documents': documents, 'export_attempts': 0, 'png_preferences': {'ResolutionR': 72}}
    points = [dict(anchor=[100, 100], left=[100, 100], right=[100, 100] if straight else [100, 200]),
              dict(anchor=[300, 100], left=[300, 100] if straight else [300, 200], right=[300, 100])]
    if flat_loop:
        points = [dict(anchor=[100, 100], left=[100, 100], right=[100, 200]),
                  dict(anchor=[100, 100], left=[100, 300], right=[100, 100])]
    image = Image.new('RGB', render_size, 'white')
    image.paste((255, 0, 0) if wrong_fill else (0, 174, 239), (100, 100, 200, 200))

    def observer(run_dir, script, *args, **kwargs):
        if script.name == 'dismiss-dialogs.ahk':
            return ''
        assert script.name == 'run-jsx.ahk'
        config = json.loads(args[0].read_text(encoding='utf-8').split('\n', 1)[0].removeprefix('var config = ').removesuffix(';'))
        phase = config['phase']
        if phase == 'snapshot':
            result = {'documents': state['documents'], 'png_preferences': state['png_preferences']}
        elif phase == 'drawing':
            result = {'document': drawing, 'checks': {'artboard': True, 'editable_paths': True,
                                                     'blue_fill': None if native_fill_unknown else not wrong_fill},
                      'paths': [{'closed': True, 'points': points}]}
        elif phase == 'export':
            state['export_attempts'] += 1
            original = dict(drawing)
            if export_marks_dirty:
                drawing['saved'] = False
            if state['export_attempts'] <= export_errors:
                result = {'error': 'fixture export failed', 'stack': 'fixture native stack'}
            else:
                image.save(config['render'])  # Metadata encoding belongs to the maintainer, not the drawing.
                if export_mutates_drawing:
                    drawing['artwork_signature'] = 'changed-by-export'
                result = {'document_before': original, 'document_after': drawing}
        elif phase in ('cleanup', 'restore-preferences'):
            if phase == 'cleanup' and config['close']:
                output = directory / 'grading/Cloud9-Recreated.png'
                assert output.is_file(), 'never close an unexported drawing'
                with Image.open(output) as saved:
                    assert saved.size == (800, 800) and saved.info.get('dpi') == pytest.approx((72, 72), abs=.1)
                state['documents'] = [existing]
            state['png_preferences'] = config['restore_preferences']
            result = {'documents': state['documents'], 'png_preferences': state['png_preferences']}
        else:
            pytest.fail(f'Unexpected native operation: {phase}')
        args[1].write_text(json.dumps(result), encoding='utf-8')
        return ''
    return directory, observer, state, image


@pytest.mark.parametrize('initial_saved', [False, True])
def test_cleanup_exports_unchanged_artwork_when_export_marks_document_dirty(tmp_path, initial_saved):
    from bench.illustrator_pen_tool import cleanup_desktop

    directory, observer, state, native_image = drawing_cleanup_fixture(tmp_path, export_marks_dirty=True)
    state['documents'][-1]['saved'] = initial_saved
    # An unsolicited actor file is not the new protocol's export evidence.
    Image.new('RGB', (400, 400), 'red').save(directory / 'workspace/Cloud9-Recreated.png')
    result = cleanup_desktop(directory, observer, export_drawing=True)
    assert result['passed'] and result['drawing_verification']['passed']
    assert result['export']['passed'] and result['infrastructure_failure'] is None
    assert result['drawing_verification']['curved_segments'] == 1
    output = directory / 'grading/Cloud9-Recreated.png'
    with Image.open(output) as saved:
        assert saved.convert('RGBA').tobytes() == native_image.convert('RGBA').tobytes()
        assert saved.info['dpi'] == pytest.approx((72, 72), abs=.1)
    assert result['export']['output'] == str(output)
    assert state['documents'] == result['preserved_documents']
    assert len(state['documents']) == 1 and state['documents'][0]['artwork_signature'] == 'protected'
    assert not (directory / 'workspace/Cloud9-Recreated.ai').exists()


@pytest.mark.parametrize('flat_loop', [False, True])
def test_cleanup_detects_straight_segment_approximation_without_repairing_the_drawing(tmp_path, flat_loop):
    from bench.illustrator_pen_tool import cleanup_desktop

    directory, observer, state, native_image = drawing_cleanup_fixture(tmp_path, straight=True, flat_loop=flat_loop)
    result = cleanup_desktop(directory, observer, export_drawing=True)
    assert result['passed'] and result['export']['passed']
    assert not result['drawing_verification']['passed']
    assert result['drawing_verification']['curved_segments'] == 0
    assert 'genuine Bézier' in ' '.join(result['drawing_verification']['problems'])
    assert result['infrastructure_failure'] is None
    with Image.open(result['export']['output']) as saved:
        assert saved.convert('RGBA').tobytes() == native_image.convert('RGBA').tobytes()



@pytest.mark.parametrize('export_errors', [0, 2])
def test_cleanup_uses_rendered_fill_for_other_native_color_types_without_inventing_a_failure(tmp_path, export_errors):
    from bench.illustrator_pen_tool import cleanup_desktop

    directory, observer, state, _ = drawing_cleanup_fixture(tmp_path, native_fill_unknown=True, export_errors=export_errors)
    result = cleanup_desktop(directory, observer, export_drawing=True)
    drawing = result['drawing_verification']
    assert drawing['native_checks']['blue_fill'] is None
    if export_errors:
        assert drawing['passed'] is None, 'unknown effective fill is not a failed actor drawing'
        assert result['infrastructure_failure']['kind'] == 'maintainer_export_failure'
    else:
        assert drawing['passed'] is True and drawing['rendered_checks']['blue_fill'] is True
        assert result['passed'] and result['infrastructure_failure'] is None


def test_cleanup_records_missing_drawing_as_task_failure_without_reopening_or_exporting_a_blank(tmp_path):
    from bench.illustrator_pen_tool import cleanup_desktop

    directory, observer, state, _ = drawing_cleanup_fixture(tmp_path)
    state['documents'] = state['documents'][:1]  # Actor no longer left an owned drawing open.
    result = cleanup_desktop(directory, observer, export_drawing=True)
    assert result['passed'] and result['infrastructure_failure'] is None
    assert not result['drawing_verification']['passed']
    assert 'not open' in ' '.join(result['drawing_verification']['problems'])
    assert result['export']['output'] is None
    assert state['export_attempts'] == 0 and len(state['documents']) == 1
    assert not (directory / 'grading/Cloud9-Recreated.png').exists()


def test_cleanup_exports_wrong_fill_as_evidence_without_calling_it_an_export_failure(tmp_path):
    from bench.illustrator_pen_tool import cleanup_desktop

    directory, observer, state, native_image = drawing_cleanup_fixture(tmp_path, wrong_fill=True)
    result = cleanup_desktop(directory, observer, export_drawing=True)
    assert result['passed'] and result['export']['passed']
    assert result['infrastructure_failure'] is None
    assert not result['drawing_verification']['passed']
    assert not result['drawing_verification']['checks']['blue_fill']
    assert len(state['documents']) == 1
    with Image.open(result['export']['output']) as saved:
        assert saved.convert('RGBA').tobytes() == native_image.convert('RGBA').tobytes()


def test_cleanup_stops_after_export_integrity_failure_without_retry_repair_or_close(tmp_path):
    from bench.illustrator_pen_tool import cleanup_desktop

    directory, observer, state, _ = drawing_cleanup_fixture(tmp_path, export_mutates_drawing=True)
    result = cleanup_desktop(directory, observer, export_drawing=True)
    assert not result['passed'] and result['drawing_verification']['passed']
    assert result['infrastructure_failure']['kind'] == 'maintainer_export_failure'
    assert state['export_attempts'] == 1, 'do not retry against changed artwork'
    assert len(state['documents']) == 2 and state['documents'][1]['artwork_signature'] == 'changed-by-export'
    assert state['png_preferences'] == {'ResolutionR': 144}
    assert (directory / 'export-attempt-1-crash.txt').is_file()
    assert not (directory / 'grading/Cloud9-Recreated.png').exists()


def test_cleanup_retains_invalid_sized_export_as_infrastructure_failure_with_logs_and_no_resize(tmp_path):
    from bench.illustrator_pen_tool import cleanup_desktop

    directory, observer, state, _ = drawing_cleanup_fixture(tmp_path, render_size=(400, 400))
    result = cleanup_desktop(directory, observer, export_drawing=True)
    assert not result['passed'] and result['drawing_verification']['passed']
    assert result['infrastructure_failure']['kind'] == 'maintainer_export_failure'
    assert state['export_attempts'] == 2 and len(state['documents']) == 2
    assert state['png_preferences'] == {'ResolutionR': 144}
    for attempt in (1, 2):
        assert (directory / f'export-attempt-{attempt}-crash.txt').is_file()
    for output in (directory / 'grading').glob('native-export-*.png'):
        with Image.open(output) as image:
            assert image.size == (400, 400), 'retain the failure, never resize it into a successful export'
    assert not (directory / 'grading/Cloud9-Recreated.png').exists()


@pytest.mark.parametrize('failures', [1, 2])
def test_cleanup_retries_only_export_and_classifies_exhaustion_as_infrastructure_failure(tmp_path, failures):
    from bench.illustrator_pen_tool import cleanup_desktop

    directory, observer, state, _ = drawing_cleanup_fixture(tmp_path, export_errors=failures, export_marks_dirty=True)
    state['documents'][-1]['saved'] = True
    result = cleanup_desktop(directory, observer, export_drawing=True)
    assert state['export_attempts'] == 2
    assert state['png_preferences'] == {'ResolutionR': 144}, 'restore preferences even when preserving an unexported drawing'
    assert result['drawing_verification']['passed'], 'export errors are not actor drawing failures'
    assert (directory / 'export-attempt-1-crash.txt').is_file()
    assert result['passed'] is (failures == 1)
    if failures == 2:
        assert result['infrastructure_failure']['kind'] == 'maintainer_export_failure'
        assert result['export']['passed'] is False
        assert len(state['documents']) == 2, 'preserve the unexported drawing rather than destroying it'
        assert not result['closed_documents']
    else:
        assert result['infrastructure_failure'] is None
        assert len(state['documents']) == 1

def test_illustrator_conduct_keeps_resource_tampering_gated_and_window_changes_diagnostic(tmp_path):
    from bench.run import conduct_audit

    plan = {'scenario': 'illustrator-pen-tool', 'run_dir': str(tmp_path), 'workspace': str(tmp_path), 'skill_path': str(ROOT / 'acu/SKILL.md')}
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
    assert stray['passed'] and stray['windows']['new_non_calculator'] == ['9']
    shadow_before = 'window=1 pid=5\nwindow=2 pid=8\nwindow=3 pid=8\nclass=2 SysShadow\nclass=3 illustrator\nillustrator=3\npid=8\n'
    shadow_after = 'window=1 pid=5\nwindow=3 pid=8\nillustrator=3\npid=8\n'
    assert conduct_audit(plan, shadow_before, shadow_after, {}, {}, [])['passed'], 'Illustrator menu/tooltip shadows are not user windows'
    disappeared = conduct_audit(plan, shadow_before, 'window=1 pid=5\n', {}, {}, [])
    assert disappeared['passed'] and '3' in disappeared['windows']['closed_preexisting'], 'window disappearance is diagnostic; document identity/cleanup checks remain separate'


@pytest.mark.desktop
@pytest.mark.parametrize('initially_enabled', [False, True])
def test_real_preparation_enables_smart_guides_and_snap_to_point(initially_enabled):
    from bench.run import acu_observer
    from bench.illustrator_pen_tool import prepare_desktop, cleanup_desktop

    directory = ROOT / '.pi/illustrator-pen-tool-validation' / f'snapping-check-{uuid4().hex[:8]}'
    plan = prepare('pi-acu', directory, scenario='illustrator-pen-tool')
    acu_observer(directory, ROOT / 'bench/probe.ahk', suffix='-before')

    # Seed the real application immediately before production setup, not a simulated preference store.
    def seeded_observer(run_dir, script, *args, **kwargs):
        if script.name == 'run-jsx.ahk':
            content = args[0].read_text(encoding='utf-8')
            first, body = content.split('\n', 1)
            config = json.loads(first.removeprefix('var config = ').removesuffix(';'))
            if config['phase'] == 'prepare':
                seed = str(initially_enabled).lower()
                args[0].write_text(first + '\n' +
                    f'app.preferences.setBooleanPreference("showSnapping", {seed});\n' +
                    f'app.preferences.setBooleanPreference("snapToPoint", {seed});\n' + body, encoding='utf-8')
        return acu_observer(run_dir, script, *args, **kwargs)

    try:
        prepared = prepare_desktop(plan, seeded_observer)
        identity = json.loads((directory / 'illustrator-identity.json').read_text(encoding='utf-8'))
        result = directory / 'snapping-readback.json'
        check = directory / 'snapping-readback.jsx'
        check.write_text('(function () {\n' +
            'var values = [app.preferences.getBooleanPreference("showSnapping"), '
            'app.preferences.getBooleanPreference("snapToPoint")];\n' +
            'var report = new File(' + json.dumps(str(result)) + ');\n' +
            'report.encoding = "UTF-8"; report.open("w");\n'
            'report.write("[" + values.join(",") + "]"); report.close();\n}());\n', encoding='utf-8')
        acu_observer(directory, ROOT / 'bench/illustrator/run-jsx.ahk', check, result,
                     identity['hwnd'], identity['pid'], suffix='-snapping-readback', timeout=40)
        assert json.loads(result.read_text(encoding='utf-8-sig')) == [True, True]
        assert prepared['snapping'] == {'smart_guides': True, 'snap_to_point': True}
        assert json.loads((directory / 'illustrator-prepared.json').read_text(encoding='utf-8'))['snapping'] == prepared['snapping']
        prompt = (directory / 'prompt.txt').read_text(encoding='utf-8').lower()
        assert 'smart guides' not in prompt and 'snap to point' not in prompt
        menu_check = directory / 'snapping-menu.ahk'
        menu_check.write_text(f'target := "ahk_id {identity["hwnd"]}"\n'
            'AcuActivate(target)\nAcuKeys(target, "!v")\n'
            'try\n    AcuScreenshot({monitor:1}, A_ScriptDir "\\view-menu.png", 1600)\n'
            'finally\n    AcuKeys(target, "{Esc}")\n', encoding='utf-8')
        acu_observer(directory, menu_check)
    finally:
        if (directory / 'illustrator-before.json').exists():
            try:
                assert cleanup_desktop(directory, acu_observer)['passed']
            finally:
                acu_observer(directory, ROOT / 'bench/restore_cursor.ahk')


@pytest.mark.desktop
def test_illustrator_pen_tool_real_illustrator_preparation_and_owned_document_cleanup(tmp_path):
    from bench.run import acu_observer
    from bench.illustrator_pen_tool import prepare_desktop, cleanup_desktop
    from concurrent.futures import ThreadPoolExecutor

    directory = ROOT / '.pi/illustrator-pen-tool-validation' / f'native-check-{uuid4().hex[:8]}'
    plan = prepare('pi-acu', directory, scenario='illustrator-pen-tool')
    acu_observer(directory, ROOT / 'bench/probe.ahk', suffix='-before')
    cleanup_finished = False
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
        start, handle, second, third = [screen(x, y) for x, y in ((200, 200), (200, 350), (600, 200), (600, 600))]
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
                  'reference': str(workspace / 'Cloud9-Reference.png'), 'result': str(result)}
        script = directory / 'drawing-fixture.jsx'
        script.write_text('var config = ' + json.dumps(config) + ';\n' +
                          (ROOT / 'tests/scripts/illustrator_pen_drawing_fixture.jsx').read_text(encoding='utf-8'), encoding='utf-8')
        acu_observer(directory, ROOT / 'bench/illustrator/run-jsx.ahk', script, result,
                     identity['hwnd'], identity['pid'], timeout=40)
        assert result.read_text(encoding='utf-8') == 'SUCCESS'
        assert not (workspace / 'Cloud9-Recreated.ai').exists()
        assert not (workspace / 'Cloud9-Recreated.png').exists()

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
        export_attempts = 0
        # Inject one genuine native destination failure, then exercise the unchanged production retry/export pipeline.
        def failing_first_export(run_dir, script, *args, **kwargs):
            nonlocal export_attempts
            if script.name == 'run-jsx.ahk':
                content = args[0].read_text(encoding='utf-8')
                first_line, rest = content.split('\n', 1)
                config = json.loads(first_line.removeprefix('var config = ').removesuffix(';'))
                if config['phase'] == 'export':
                    export_attempts += 1
                    if export_attempts == 1:
                        config['render'] = str(directory / 'missing-directory/failure.png')
                        args[0].write_text('var config = ' + json.dumps(config) + ';\n' + rest, encoding='utf-8')
            return acu_observer(run_dir, script, *args, **kwargs)
        cleanup = cleanup_desktop(directory, failing_first_export, export_drawing=True)
        cleanup_finished = cleanup['passed']
        assert cleanup['passed'] and cleanup['drawing_verification']['passed']
        assert cleanup['export']['passed'] and cleanup['infrastructure_failure'] is None
        assert export_attempts == 2 and (directory / 'export-attempt-1-crash.txt').is_file()
        inspected = cleanup['drawing_verification']
        assert inspected['document']['saved'] is False
        assert inspected['curved_segments'] > 0
        assert inspected['item_types']['PlacedItem'] == 2, 'hidden and off-artboard references must not fail Pen output verification'
        first = inspected['paths'][0]['points'][0]
        assert first['anchor'] == pytest.approx([200, 600], abs=.75)
        assert first['right'] == pytest.approx([200, 450], abs=.75)
        output = directory / 'grading/Cloud9-Recreated.png'
        with Image.open(output) as image:
            assert image.size == (800, 800)
            assert image.info['dpi'] == pytest.approx((72, 72), abs=.1)
            assert image.convert('RGBA').getchannel('A').getextrema() == (255, 255)
            assert image.getpixel((0, 0))[:3] == (255, 255, 255)
            assert not image.info.get('interlace', 0)
        assert cleanup['preserved_documents'] == json.loads((directory / 'illustrator-before.json').read_text(encoding='utf-8'))

    finally:
        if (directory / 'illustrator-identity.json').exists():
            try:
                if not cleanup_finished:
                    cleanup = cleanup_desktop(directory, acu_observer)
                    assert cleanup['passed']
            finally:
                acu_observer(directory, ROOT / 'bench/restore_cursor.ahk')


@pytest.mark.parametrize('scenario', ['unknown', 'testbench-2'])
def test_unknown_or_retired_scenario_is_rejected_before_creating_a_workspace(tmp_path, scenario):
    with pytest.raises(ValueError, match='scenario'):
        prepare('pi-acu', tmp_path / 'unknown', scenario=scenario)
    assert not (tmp_path / 'unknown').exists()
