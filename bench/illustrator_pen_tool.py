"""Live Pen drawing verification, as-is maintainer export and owned Illustrator cleanup.

The lossless reference fixes shape, scale, placement and #00AEEF color.
Numeric drawing quality is observational, without registration or a pass threshold.
"""

from array import array
from copy import deepcopy
import hashlib
import json
import os
import re
import shutil
import traceback
import uuid
from pathlib import Path

from bench.common import ROOT, TRIAL_POLICY, load_actor_json, save_json
from bench.scenario import Scenario

from PIL import Image, UnidentifiedImageError

# Third-party artwork built locally from Cloud9's official icon; see bench/build_reference.py.
ILLUSTRATOR_REFERENCE = ROOT / 'bench/assets/illustrator-pen-tool/Cloud9-Reference.png'


EXPORT_POLICY = {
    'owner': 'maintainer-cleanup', 'attempts': 2, 'output': 'grading/Cloud9-Recreated.png',
    'dimensions': [800, 800], 'background': 'opaque-white', 'dpi': 72,
    'interlaced': False, 'failure_classification': 'infrastructure'}


# Shared mask classification includes antialiased blue edges in references and exported drawings.
def foreground(image):
    data = image.convert('RGBA').tobytes()
    return bytearray(r < 128 and g > 100 and b > 150 and a > 127
                     for r, g, b, a in zip(data[::4], data[1::4], data[2::4], data[3::4]))


# Boundaries are foreground pixels touching background in the four-neighbor grid.
def boundary(mask, width, height):
    points = []
    for i, filled in enumerate(mask):
        if filled and (i < width or i >= width * (height - 1) or i % width == 0 or i % width == width - 1
                       or not mask[i - 1] or not mask[i + 1] or not mask[i - width] or not mask[i + width]):
            points.append(i)
    return points


# Two passes give exact Manhattan distance to a boundary without extra numerical dependencies.
def distances(points, width, height):
    far = width + height
    values = array('I', [far]) * (width * height)
    for i in points:
        values[i] = 0
    for i in range(len(values)):
        if i >= width:
            values[i] = min(values[i], values[i - width] + 1)
        if i % width:
            values[i] = min(values[i], values[i - 1] + 1)
    for i in range(len(values) - 1, -1, -1):
        if i + width < len(values):
            values[i] = min(values[i], values[i + width] + 1)
        if i % width < width - 1:
            values[i] = min(values[i], values[i + 1] + 1)
    return values


# Report unaligned mask overlap and symmetric boundary distances; an empty drawing is explicit.
def shape_metrics(image, reference):
    if image.size != reference.size:
        raise ValueError('shape comparison requires equal canvas dimensions; resizing is not allowed')
    width, height = image.size
    submitted, expected = foreground(image), foreground(reference)
    indices = [i for i, value in enumerate(submitted) if value]
    union = sum(a or b for a, b in zip(submitted, expected))
    if not any(expected):
        raise ValueError('grading reference has no foreground')
    result = {'foreground_iou': sum(a and b for a, b in zip(submitted, expected)) / union,
              'foreground_pixels': len(indices), 'foreground_bounds': None,
              'boundary_mean_manhattan_px': None, 'boundary_p95_manhattan_px': None}
    if indices:
        xs, ys = [i % width for i in indices], [i // width for i in indices]
        result['foreground_bounds'] = [min(xs), min(ys), max(xs) + 1, max(ys) + 1]
        actual_edge, expected_edge = boundary(submitted, width, height), boundary(expected, width, height)
        to_actual, to_expected = distances(actual_edge, width, height), distances(expected_edge, width, height)
        errors = sorted([to_expected[i] for i in actual_edge] + [to_actual[i] for i in expected_edge])
        result['boundary_mean_manhattan_px'] = sum(errors) / len(errors)
        result['boundary_p95_manhattan_px'] = errors[min(len(errors) - 1, int(len(errors) * .95))]
    return result


# Inspect a maintainer-rendered PNG; quality is an observation, never a numeric completion threshold.
def verify_outputs(run_dir, *, output=None):
    run_dir = Path(run_dir)
    plan = json.loads((run_dir / 'plan.json').read_text(encoding='utf-8'))
    reference_path = run_dir / 'grading/reference.png'
    if hashlib.sha256(reference_path.read_bytes()).hexdigest() != plan['grading']['reference_sha256']:
        raise ValueError('frozen grading reference fingerprint changed')
    png = Path(output) if output is not None else run_dir / EXPORT_POLICY['output']
    report = {'passed': False, 'output': str(png), 'problems': [], 'checks': {}, 'quality': None}
    if not png.is_file():
        report['problems'].append('Cloud9-Recreated.png missing')
        return report
    try:
        with Image.open(png) as opened:
            checks = {'png': opened.format == 'PNG', 'dimensions': opened.size == (800, 800)}
            report['checks'] = checks
            if all(checks.values()):
                opened.load()
                pixels = opened.convert('RGBA')
                mask = foreground(pixels)
                data = pixels.tobytes()
                colors = list(zip(data[::4], data[1::4], data[2::4], data[3::4]))
                background = [p for p, filled in zip(colors, mask) if not filled]
                blue = [p[:3] for p, filled in zip(colors, mask) if filled]
                solid = sum(p == (0, 174, 239) for p in blue)
                checks.update(opaque=pixels.getchannel('A').getextrema() == (255, 255),
                              white_background=bool(background) and sum(p == (255, 255, 255, 255) for p in background) / len(background) >= .99,
                              blue_fill=bool(blue) and solid / len(blue) >= .95,
                              non_interlaced=not opened.info.get('interlace', 0))
                dpi = opened.info.get('dpi')
                checks['resolution_metadata'] = dpi is not None and all(abs(value - 72) < .1 for value in dpi)
                report['dpi'] = dpi
                with Image.open(reference_path) as reference:
                    report['quality'] = shape_metrics(pixels, reference)
                report['quality']['registration'] = 'none'
        report['sha256'] = hashlib.sha256(png.read_bytes()).hexdigest()
        report['problems'] = [f'PNG check failed: {name}' for name, passed in checks.items() if not passed]
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
        report['problems'].append(f'Cannot read exported PNG: {error}')
    report['passed'] = not report['problems']
    return report


# Attribute only known task files, and refuse cleanup if a pre-existing document disappeared or an unknown one appeared.
def owned_documents(before, after, workspace):
    def key(document):
        return ('path', str(Path(document['path']).resolve()).casefold()) if document['path'] else ('unsaved', document['name'])

    protected = {key(document) for document in before}
    current = {key(document) for document in after}
    if len(protected) != len(before) or len(current) != len(after):
        raise ValueError('ambiguous document identity; refusing cleanup')
    if not protected <= current:
        raise ValueError('a pre-existing Illustrator document disappeared or was renamed; refusing cleanup')
    allowed = {str((Path(workspace) / name).resolve()).casefold()
               for name in ('Cloud9-Pen-Starter.ai', 'Cloud9-Recreated.ai')}
    owned = []
    for document in after:
        if key(document) in protected:
            continue
        if not document['path'] or key(document)[1] not in allowed:
            raise ValueError(f'unclaimed Illustrator document: {document["name"]}; refusing cleanup')
        owned.append(document['path'])
    return owned


# Execute trusted observer code outside actor timing, retaining generated scripts and native crash stacks.
def native_observer(run_dir, observer, phase, **values):

    run_dir = Path(run_dir)
    identity = json.loads((run_dir / 'illustrator-identity.json').read_text(encoding='utf-8'))
    stem = f'illustrator-{phase}-{uuid.uuid4().hex[:6]}'
    result_path, script = run_dir / f'{stem}.json', run_dir / f'{stem}.jsx'
    config = dict(values, phase=phase, result=str(result_path))
    script.write_text('var config = ' + json.dumps(config) + ';\n' +
                      (ROOT / 'bench/illustrator/observer.jsx').read_text(encoding='utf-8'), encoding='utf-8')
    observer(run_dir, ROOT / 'bench/illustrator/run-jsx.ahk', script, result_path,
             identity['hwnd'], identity['pid'], suffix=f'-{stem}', timeout=40)
    result = json.loads(result_path.read_text(encoding='utf-8-sig'))
    if 'error' in result:
        raise RuntimeError(f'Illustrator {phase} failed; native stack: {result_path}: {result["error"]}')
    return result


# Establish the shared initial document/viewport/input state, preserving a baseline before opening task artwork.
def prepare_desktop(plan, observer):

    run_dir = Path(plan['run_dir'])
    candidates = list((Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'Adobe').glob(
        'Adobe Illustrator*/Support Files/Contents/Windows/Illustrator.exe'))
    if len(candidates) != 1:
        raise RuntimeError(f'Expected exactly one installed Illustrator, found: {candidates}')
    output = observer(run_dir, ROOT / 'bench/illustrator/ensure.ahk', candidates[0], run_dir / 'illustrator-identity.json', timeout=60)
    identity = {key: int(re.search(rf'^{key}=(\d+)$', output, re.MULTILINE).group(1))
                for key in ('illustrator', 'pid', 'started')}
    identity['hwnd'] = identity.pop('illustrator')
    save_json(run_dir / 'illustrator-identity.json', identity)
    snapshot = native_observer(run_dir, observer, 'snapshot')
    before = snapshot['documents']
    save_json(run_dir / 'illustrator-before.json', before)
    save_json(run_dir / 'illustrator-preferences-before.json', snapshot['png_preferences'])
    plan['protected_document_files'] = [doc['path'] for doc in before if doc['path'] and Path(doc['path']).is_file()]
    save_json(run_dir / 'plan.json', plan)
    window_state = run_dir / 'illustrator-window.json'
    observer(run_dir, ROOT / 'bench/illustrator/window.ahk', identity['hwnd'], identity['pid'], window_state)
    prepared = native_observer(run_dir, observer, 'prepare', starter=str(run_dir / 'workspace/Cloud9-Pen-Starter.ai'))
    prepared['window'] = json.loads(window_state.read_text(encoding='utf-8'))
    save_json(run_dir / 'illustrator-prepared.json', prepared)
    observer(run_dir, ROOT / 'bench/illustrator/input-state.ahk', identity['hwnd'], identity['pid'])
    return prepared


# Cancel recognized dialogs only when they were absent before preparation, preserving every pre-existing handle.
def dismiss_task_dialogs(run_dir, observer):

    run_dir = Path(run_dir)
    identity = json.loads((run_dir / 'illustrator-identity.json').read_text(encoding='utf-8'))
    observer(run_dir, ROOT / 'bench/illustrator/dismiss-dialogs.ahk', identity['hwnd'], identity['pid'],
             run_dir / 'observer-probe-before.log')



# Count actual noncollinear cubic segments, not merely nonzero handles that still lie on a straight chord.
def segment_counts(paths):
    curved = straight = 0
    for path in paths:
        points = path['points']
        count = len(points) if path['closed'] else len(points) - 1
        for index in range(max(0, count)):
            start, end = points[index], points[(index + 1) % len(points)]
            a, b = start['anchor'], end['anchor']
            dx, dy = b[0] - a[0], b[1] - a[1]
            handles = (start['right'], end['left'])
            if dx == 0 and dy == 0:
                first, second = handles
                bent = abs((first[0] - a[0]) * (second[1] - a[1]) -
                           (first[1] - a[1]) * (second[0] - a[0])) > 1e-6
            else:
                bent = any(abs(dx * (handle[1] - a[1]) - dy * (handle[0] - a[0])) > 1e-6 for handle in handles)
            curved += bent
            straight += not bent
    return {'curved_segments': curved, 'straight_segments': straight}


# Render/encode one frozen live drawing; artifact/IO retries are bounded, integrity refusals stop immediately.
def _export_live_drawing(run_dir, observer, before, document, expected_document):

    output = run_dir / EXPORT_POLICY['output']
    if output.exists():
        raise FileExistsError(f'Maintainer output already exists; refusing overwrite: {output}')
    attempts = []
    for attempt in range(1, EXPORT_POLICY['attempts'] + 1):
        raw = run_dir / f'grading/native-export-{uuid.uuid4().hex[:6]}.png'
        encoded = run_dir / f'grading/encoded-export-{uuid.uuid4().hex[:6]}.png'
        try:
            exported = native_observer(run_dir, observer, 'export', before=before, document=document, render=str(raw))
            # Illustrator can mark unchanged artwork dirty, even on a failed export.
            # Accept that flag on retry too; identity and all other metadata must still match.
            expected_dirty = dict(expected_document, saved=False)
            expected_before = (expected_document,) if attempt == 1 else (expected_document, expected_dirty)
            expected_after = (exported['document_before'], expected_dirty)
            if (exported['document_before'] not in expected_before
                    or exported['document_after'] not in expected_after):
                raise ValueError('Drawing changed during maintainer export; refusing cleanup')
            with Image.open(raw) as image:
                image.load()
                image.save(encoded, format='PNG', dpi=(72, 72))
                with Image.open(encoded) as saved:
                    if saved.convert('RGBA').tobytes() != image.convert('RGBA').tobytes():
                        raise ValueError('Maintainer PNG encoding changed drawing pixels')
            verification = verify_outputs(run_dir, output=encoded)
            # Invalid dimensions/decoding omit appearance fields: reject format before indexing those fields.
            format_properties = ('png', 'dimensions', 'opaque', 'non_interlaced', 'resolution_metadata')
            export_checks = {key: verification['checks'].get(key) for key in format_properties}
            if not all(passed is True for passed in export_checks.values()):
                raise RuntimeError(f'Maintainer PNG properties failed: {verification["problems"]}')
            appearance_checks = {key: verification['checks'][key] for key in ('blue_fill', 'white_background')}
            encoded.rename(output)
            verification.update(output=str(output), passed=True, problems=[], checks=export_checks,
                                appearance_checks=appearance_checks)
            attempts.append({'attempt': attempt, 'passed': True, 'native_output': str(raw)})
            break
        except (RuntimeError, OSError, ValueError) as error:
            crash = run_dir / f'export-attempt-{attempt}-crash.txt'
            crash.write_text(traceback.format_exc(), encoding='utf-8')
            attempts.append({'attempt': attempt, 'passed': False, 'error': str(error), 'crash': str(crash),
                             'native_output': str(raw), 'encoded_output': str(encoded),
                             'retryable': not isinstance(error, ValueError)})
            if isinstance(error, ValueError):
                break  # Integrity/data refusals are terminal: never retry against changed or untrusted evidence.
    if not attempts[-1]['passed']:
        verification = {'passed': False, 'output': None, 'quality': None, 'checks': {}, 'attempts': attempts,
                        'problems': [record['error'] for record in attempts]}
        failure = {'kind': 'maintainer_export_failure', 'errors': verification['problems'], 'attempts': attempts}
        save_json(run_dir / 'export.json', verification)
        save_json(run_dir / 'infrastructure-failure.json', failure)
        return {'export': verification, 'infrastructure_failure': failure}
    verification['attempts'] = attempts
    save_json(run_dir / 'export.json', verification)
    return {'export': verification, 'infrastructure_failure': None}


# Export only the live owned document, then encode the same pixels with the frozen PNG density/encoding policy.
def collect_drawing(run_dir, observer, before, owned):

    plan = json.loads((run_dir / 'plan.json').read_text(encoding='utf-8'))
    if plan.get('export_policy') != EXPORT_POLICY:
        raise ValueError('Maintainer export policy changed; refusing collection')
    if not owned:
        drawing = {'passed': False, 'problems': ['Owned drawing is not open; leave the finished drawing open'],
                   'checks': {'open_drawing': False}, 'paths': [], 'curved_segments': 0, 'straight_segments': 0}
        export = {'passed': False, 'output': None, 'quality': None, 'checks': {}, 'attempts': [],
                  'problems': ['No drawing to export; task input is missing, not an exporter failure']}
        save_json(run_dir / 'drawing-verification.json', drawing)
        save_json(run_dir / 'export.json', export)
        return {'drawing_verification': drawing, 'export': export, 'infrastructure_failure': None}
    if len(owned) != 1:
        raise RuntimeError('Drawing collection requires exactly one independently owned document')
    drawing = native_observer(run_dir, observer, 'drawing', before=before, document=owned[0])
    drawing['native_checks'] = dict(drawing['checks'])
    drawing['rendered_checks'] = None
    drawing['assessment_source'] = 'native-only'
    drawing.update(segment_counts(drawing['paths']))
    drawing['checks']['bezier_curves'] = drawing['curved_segments'] > 0
    drawing['problems'] = [f'Drawing check failed: {key}' for key, passed in drawing['checks'].items() if passed is False]
    if not drawing['checks']['bezier_curves']:
        drawing['problems'].append('No genuine Bézier curves; straight-line approximation is not allowed')
    drawing['passed'] = False if drawing['problems'] else (None if None in drawing['checks'].values() else True)
    save_json(run_dir / 'drawing-verification.json', drawing)
    rendering = _export_live_drawing(run_dir, observer, before, owned[0], drawing['document'])
    if rendering['infrastructure_failure']:
        return {'drawing_verification': drawing, **rendering}
    verification = rendering['export']
    appearance_checks = verification['appearance_checks']
    drawing['rendered_checks'] = appearance_checks
    drawing['assessment_source'] = 'native-and-rendered'
    # Effective rendered color resolves non-RGB fill uncertainty; a proven wrong native RGB fill is not excused.
    drawing['checks']['blue_fill'] = appearance_checks['blue_fill'] and drawing['native_checks']['blue_fill'] is not False
    drawing['checks']['white_background'] = appearance_checks['white_background']
    for key in appearance_checks:
        problem = f'Drawing check failed: {key}'
        if not drawing['checks'][key] and problem not in drawing['problems']:
            drawing['problems'].append(problem)
    drawing['passed'] = not drawing['problems']
    save_json(run_dir / 'drawing-verification.json', drawing)
    return {'drawing_verification': drawing, **rendering}


# Collect optional drawing evidence before closing owned documents; never repair artwork or close protected resources.
def cleanup_desktop(run_dir, observer, *, export_drawing=False):

    run_dir = Path(run_dir)
    identity = json.loads((run_dir / 'illustrator-identity.json').read_text(encoding='utf-8'))
    dismiss_task_dialogs(run_dir, observer)
    snapshot = native_observer(run_dir, observer, 'snapshot')
    current = snapshot['documents']
    baseline_path = run_dir / 'illustrator-before.json'
    if not baseline_path.is_file():
        # No task document is opened until the baseline is persisted. Preserve every currently open document.
        if current:
            raise RuntimeError('Preparation baseline missing and Illustrator has documents; refusing cleanup')
        before = []
    else:
        before = json.loads(baseline_path.read_text(encoding='utf-8'))
    close = owned_documents(before, current, run_dir / 'workspace')
    preferences_path = run_dir / 'illustrator-preferences-before.json'
    preferences = json.loads(preferences_path.read_text(encoding='utf-8')) if baseline_path.is_file() else snapshot['png_preferences']
    collection = collect_drawing(run_dir, observer, before, close) if export_drawing else {}
    if collection.get('infrastructure_failure'):
        failed_state = native_observer(run_dir, observer, 'snapshot')
        owned_documents(before, failed_state['documents'], run_dir / 'workspace')
        restored = native_observer(run_dir, observer, 'restore-preferences', restore_preferences=preferences)
        if restored['documents'] != failed_state['documents'] or restored['png_preferences'] != preferences:
            raise RuntimeError('Preferences restoration changed documents or did not restore PNG preferences')
        result = {'passed': False, 'closed_documents': [], 'preserved_documents': restored['documents'],
                  'application_closed': False, **collection}
        save_json(run_dir / 'illustrator-cleanup.json', result)
        return result  # Explicit failed cleanup: preserve the unexported drawing and stop subsequent trials.
    cleaned = native_observer(run_dir, observer, 'cleanup', before=before, close=close, restore_preferences=preferences)
    after = cleaned['documents']
    if cleaned['png_preferences'] != preferences:
        raise RuntimeError('PNG preferences were not restored during cleanup')
    if owned_documents(before, after, run_dir / 'workspace'):
        raise RuntimeError('Owned Illustrator documents remain after cleanup')
    if identity['started']:
        if after:
            raise RuntimeError('Task-started Illustrator still has documents; refusing application close')
        observer(run_dir, ROOT / 'bench/illustrator/close.ahk', identity['hwnd'], identity['pid'])
    result = {'passed': True, 'closed_documents': close, 'preserved_documents': after,
              'application_closed': bool(identity['started']), **collection}
    save_json(run_dir / 'illustrator-cleanup.json', result)
    return result


# One attempt's adapter retains collection state so a refused export is never repeated by final cleanup.
class IllustratorScenario(Scenario):
    application = 'illustrator'
    group_process_windows = True

    def __init__(self):
        self.collection_started = False
        self.collection = None

    def validate_assets(self):
        if not ILLUSTRATOR_REFERENCE.is_file():
            raise SystemExit(f'{ILLUSTRATOR_REFERENCE} is not redistributed; build it once with bench/build_reference.py')

    def prepare_files(self, plan):
        run_dir, workspace = Path(plan['run_dir']), Path(plan['workspace'])
        (workspace / 'scratch').mkdir()
        assets = ROOT / 'bench/assets/illustrator-pen-tool'
        plan['assets'] = {}
        for name, source in (('Cloud9-Pen-Starter.ai', assets / 'Cloud9-Pen-Starter.ai'),
                             ('Cloud9-Reference.png', ILLUSTRATOR_REFERENCE)):
            shutil.copyfile(source, workspace / name)
            plan['assets'][name] = hashlib.sha256((workspace / name).read_bytes()).hexdigest()
        (run_dir / 'grading').mkdir()
        shutil.copyfile(ILLUSTRATOR_REFERENCE, run_dir / 'grading/reference.png')
        plan['grading'] = {'reference_sha256': plan['assets']['Cloud9-Reference.png'],
                           'registration': 'none', 'shape_pass_threshold': None, 'mode': 'live-drawing'}
        plan['actor_deliverables'] = []
        plan['export_policy'] = deepcopy(EXPORT_POLICY)
        plan['skill_guidance_policy'] = 'benchmark-neutral-v1'
        plan['trial_policy'] = dict(TRIAL_POLICY)

    def approved_apps(self):
        apps = ['Illustrator.exe']
        adobe = Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'Adobe'
        for executable in adobe.glob('Adobe Illustrator*/Support Files/Contents/Windows/Illustrator.exe'):
            apps.extend([str(executable), 'process:' + str(executable)])
        return apps

    def prepare_desktop(self, trial):
        prepare_desktop(trial.plan, trial.observer)

    def guarded_roots(self, plan):
        run_dir = Path(plan['run_dir'])
        return [run_dir / name for name in ('grading/reference.png', 'illustrator-identity.json',
                'illustrator-before.json', 'illustrator-preferences-before.json', 'prompt.txt',
                'prompt-template.txt', 'scenario.md')] + [Path(path) for path in plan.get('protected_document_files', [])]

    def audit(self, trial, conduct):
        documents = native_observer(trial.run_dir, trial.observer, 'snapshot')['documents']
        protected = load_actor_json(trial.run_dir / 'illustrator-before.json')
        changed = [doc for doc in protected if doc not in documents]
        conduct['preexisting_documents_changed'] = changed
        if changed:
            conduct['passed'] = False
            conduct['problems'].append('pre-existing Illustrator documents changed')

    def collect_and_grade(self, trial, tools):
        self.collection_started = True
        self.collection = cleanup_desktop(trial.run_dir, trial.observer, export_drawing=True)
        return self.collection['drawing_verification']

    def cleanup(self, trial):
        if self.collection is not None:
            return self.collection
        if self.collection_started:
            failure = {'kind': 'maintainer_collection_failure', 'errors': [traceback.format_exc()]}
            save_json(trial.run_dir / 'infrastructure-failure.json', failure)
            return {'passed': False, 'error': failure['errors'][0], 'infrastructure_failure': failure,
                    'note': 'Collection was already attempted and refused; not repeating export or close'}
        if (trial.run_dir / 'illustrator-identity.json').is_file():
            return cleanup_desktop(trial.run_dir, trial.observer, export_drawing=trial.actor_started)
        return {'passed': False, 'note': 'Illustrator ownership was not recorded; preparation cleanup is unverified'}

    def summarize(self, summary, plan, verification, conduct, isolation):
        rendering = self.collection['export']
        failure = self.collection['infrastructure_failure']
        summary.update(scenario='illustrator-pen-tool', output_image=rendering['output'],
                       quality=rendering['quality'], problems=verification['problems'],
                       drawing_passed=verification['passed'], infrastructure_failure=failure,
                       safeguard_violations=conduct['problems'] + isolation['problems'])
        if failure:
            summary['passed'] = False
        for field in ('isolation_passed', 'task_passed', 'conduct_passed', 'conduct_problems'):
            summary.pop(field)

    def finalize_summary(self, summary, cleanup, *, failed=False):
        passed = not failed and cleanup.get('passed') is True and cleanup.get('cursor_scheme_restored') is True
        if failed:
            summary.setdefault('safeguard_violations', []).append('worker or cleanup failed; inspect crash.txt')
        elif not passed and not cleanup.get('infrastructure_failure'):
            summary['safeguard_violations'].append('cleanup failed or is unverified')
        if not passed:
            summary['passed'] = False
