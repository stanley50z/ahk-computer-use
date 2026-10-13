"""Adobe Illustrator Pen and Export PNG grading and maintainer-only Illustrator preparation/inspection.

The lossless PNG fixes reference shape, scale, placement and #00AEEF color.
No registration or numeric shape threshold is applied to actor submissions.
"""

from array import array
import hashlib
import json
import os
import re
import uuid
from pathlib import Path
import shutil

from PIL import Image, UnidentifiedImageError


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


# Grading and aggregation share the requested basename and ordinary artboard suffixes, case-insensitively.
def is_requested_png(path):
    name = Path(path).name.casefold()
    return name == 'cloud9-recreated.png' or (name.startswith('cloud9-recreated-')
            and name.endswith('.png') and len(name) > len('cloud9-recreated-.png'))


# The exported PNG is the only actor deliverable; shape quality is measured, never a pass threshold.
def verify_outputs(run_dir):
    run_dir = Path(run_dir)
    plan = json.loads((run_dir / 'plan.json').read_text(encoding='utf-8'))
    reference_path = run_dir / 'grading/reference.png'
    if hashlib.sha256(reference_path.read_bytes()).hexdigest() != plan['grading']['reference_sha256']:
        raise ValueError('frozen grading reference fingerprint changed')
    png = run_dir / 'workspace/Cloud9-Recreated.png'
    report = {'passed': False, 'output': str(png), 'problems': [], 'checks': {}, 'quality': None}
    if not png.is_file():
        exports = sorted(path for path in png.parent.iterdir() if path.is_file() and is_requested_png(path))
        if len(exports) > 1:
            report['problems'].append('Ambiguous artboard-suffixed PNG exports')
            return report
        if exports:
            png = exports[0]
            report['output'] = str(png)
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
    from bench.run import ROOT

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
    from bench.run import ROOT, save_json

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


# Inspect a copy of the saved AI, not the actor's potentially unsaved in-memory document.
def inspect_native(run_dir, observer):
    from bench.run import save_json

    run_dir = Path(run_dir)
    source = run_dir / 'workspace/Cloud9-Recreated.ai'
    if not source.is_file():
        return
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    inspection = run_dir / 'grading/saved-copy.ai'
    shutil.copyfile(source, inspection)
    result = native_observer(run_dir, observer, 'verify', inspection=str(inspection),
                             render=str(run_dir / 'grading/native-render.png'))
    if hashlib.sha256(source.read_bytes()).hexdigest() != digest:
        raise ValueError('saved AI changed during native inspection')
    result['ai_sha256'] = digest
    save_json(run_dir / 'native-verification.json', result)


# Cancel recognized dialogs only when they were absent before preparation, preserving every pre-existing handle.
def dismiss_task_dialogs(run_dir, observer):
    from bench.run import ROOT

    run_dir = Path(run_dir)
    identity = json.loads((run_dir / 'illustrator-identity.json').read_text(encoding='utf-8'))
    observer(run_dir, ROOT / 'bench/illustrator/dismiss-dialogs.ahk', identity['hwnd'], identity['pid'],
             run_dir / 'observer-probe-before.log')


# Close only independently attributed task documents; close the application only if this task started it.
def cleanup_desktop(run_dir, observer):
    from bench.run import ROOT, save_json

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
    after = native_observer(run_dir, observer, 'cleanup', before=before, close=close, restore_preferences=preferences)['documents']
    if owned_documents(before, after, run_dir / 'workspace'):
        raise RuntimeError('Owned Illustrator documents remain after cleanup')
    if identity['started']:
        if after:
            raise RuntimeError('Task-started Illustrator still has documents; refusing application close')
        observer(run_dir, ROOT / 'bench/illustrator/close.ahk', identity['hwnd'], identity['pid'])
    result = {'passed': True, 'closed_documents': close, 'preserved_documents': after,
              'application_closed': bool(identity['started'])}
    save_json(run_dir / 'illustrator-cleanup.json', result)
    return result
