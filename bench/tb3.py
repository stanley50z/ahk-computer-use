"""TB3.1-TB3.7: live GUI-360 Office tasks in GUI-360's environment, graded by a programmatic check of the saved file.

GUI-360 (arXiv 2511.04307) collected these tasks with UFO's dataflow: copy a template, open it in Office, let the
agent act, take a final screenshot, save through COM, quit Office. TB3 repeats that environment with an ACU/CUA actor.
Grading differs by the user's 2026-10-20 decision: GUI-360 asked an LLM judge, TB3 reads the saved OOXML and checks
the request literally. UFO's 30-step limit is applied after the run to tool calls.
"""

import ctypes
import json
import os
import re
import subprocess
import time
import traceback
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
from ctypes import wintypes
from pathlib import Path

GUI360_REVISION = '1c46362efaae836c601004e77b98a1aba89a530f'
OFFICE_DIR = Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'Microsoft Office/root/Office16'
# GUI-360 ran Office maximized on a 1024x768 Windows 11 VM; its window frame was 1024x720 logical pixels.
WINDOW_DIPS = (1024, 720)
STEP_LIMIT = 30  # UFO dataflow MAX_STEPS
APPS = {
    'excel': {'exe': 'EXCEL.EXE', 'class': 'XLMAIN', 'name': 'Microsoft Excel', 'noun': 'workbook'},
    'word': {'exe': 'WINWORD.EXE', 'class': 'OpusApp', 'name': 'Microsoft Word', 'noun': 'document'},
    'ppt': {'exe': 'POWERPNT.EXE', 'class': 'PPTFrameClass', 'name': 'Microsoft PowerPoint', 'noun': 'presentation'},
}
TASKS = {
    'tb3.1': {'gui360_id': 'excel_4s_1666', 'app': 'excel', 'template': 'adult_sexual_behaviors.xlsx',
              'request': 'Delete columns B, D, and F in the Excel spreadsheet.'},
    'tb3.2': {'gui360_id': 'excel_4s_13432', 'app': 'excel', 'template': 'adult_sexual_behaviors.xlsx',
              'request': "Apply conditional formatting to the 'Age' column in Excel to highlight cells with values greater than 30."},
    'tb3.3': {'gui360_id': 'word_4s_1023', 'app': 'word', 'template': 'template1.docx',
              'request': "Highlight the text from 'An agent is a broad concept' to 'and autonomous systems.' in the Word document."},
    'tb3.4': {'gui360_id': 'word_4_16741', 'app': 'word', 'template': 'template1.docx',
              'request': "Add Arabic text 'مرحبا' to the Word document and align it to the right."},
    'tb3.5': {'gui360_id': 'ppt_4s_1846', 'app': 'ppt', 'template': 'template6.pptx',
              'request': 'Draw a straight line on Slide 1 in PowerPoint by holding the Shift key while drawing the line.'},
    'tb3.6': {'gui360_id': 'ppt_1_113', 'app': 'ppt', 'template': 'template6.pptx',
              'request': 'Draw a speech bubble on Slide 1 in the PowerPoint presentation.'},
    'tb3.7': {'gui360_id': 'ppt_4s_9417', 'app': 'ppt', 'template': 'template6.pptx',
              'request': 'Add a shape with rounded corners to Slide 1 in the PowerPoint presentation and adjust its corner properties.'},
}
OFFICE_EXES = [app['exe'] for app in APPS.values()]

def is_tb3(scenario):
    return str(scenario).startswith('tb3.')


# Actor prompt: where the document is, the verbatim GUI-360 request, and the shared open-document ending.
def prompt(scenario):
    task = TASKS[scenario]
    app = APPS[task['app']]
    return f"{app['name']} has {task['template']} open.\n\n{task['request']}\n\nStop when the task is done, leaving the {app['noun']} open.\n"


def office_processes():
    listing = subprocess.run(['tasklist', '/fo', 'csv', '/nh'], capture_output=True, text=True, errors='replace').stdout
    return [(row[0], int(row[1])) for row in (line.strip('"').split('","') for line in listing.splitlines())
            if len(row) > 1 and row[0].upper() in OFFICE_EXES]


def _windows(window_class, stem):
    import win32gui
    import win32process
    found = []

    def visit(hwnd, _):
        if win32gui.IsWindowVisible(hwnd) and win32gui.GetClassName(hwnd) == window_class and stem.casefold() in win32gui.GetWindowText(hwnd).casefold():
            found.append((hwnd, win32process.GetWindowThreadProcessId(hwnd)[1]))
    win32gui.EnumWindows(visit, None)
    return found


# Restore and place the window so its visible frame is 1024x720 logical pixels at the primary work area's corner.
def size_window(hwnd):
    import win32api
    import win32con
    import win32gui
    user32 = ctypes.windll.user32
    previous = user32.SetThreadDpiAwarenessContext(ctypes.c_void_p(-4))
    try:
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        work = win32api.GetMonitorInfo(win32api.MonitorFromPoint((0, 0), win32con.MONITOR_DEFAULTTOPRIMARY))['Work']
        for _ in range(3):
            scale = user32.GetDpiForWindow(hwnd) / 96
            outer, frame = win32gui.GetWindowRect(hwnd), wintypes.RECT()
            ctypes.windll.dwmapi.DwmGetWindowAttribute(hwnd, 9, ctypes.byref(frame), ctypes.sizeof(frame))
            left, top = frame.left - outer[0], frame.top - outer[1]
            right, bottom = outer[2] - frame.right, outer[3] - frame.bottom
            width, height = round(WINDOW_DIPS[0] * scale), round(WINDOW_DIPS[1] * scale)
            win32gui.SetWindowPos(hwnd, 0, work[0] - left, work[1] - top, width + left + right, height + top + bottom,
                                  win32con.SWP_NOZORDER | win32con.SWP_NOACTIVATE)
            time.sleep(0.5)
        ctypes.windll.dwmapi.DwmGetWindowAttribute(hwnd, 9, ctypes.byref(frame), ctypes.sizeof(frame))
        return {'scale': scale, 'frame': [frame.left, frame.top, frame.right - frame.left, frame.bottom - frame.top]}
    finally:
        user32.SetThreadDpiAwarenessContext(ctypes.c_void_p(previous))


# Bind the open document through its Running Object Table file moniker; None when it is no longer open.
def bind_document(path):
    import pythoncom
    import win32com.client
    rot, context = pythoncom.GetRunningObjectTable(), pythoncom.CreateBindCtx(0)
    for moniker in rot:
        if moniker.GetDisplayName(context, None).casefold() == str(path).casefold():
            return win32com.client.Dispatch(rot.GetObject(moniker).QueryInterface(pythoncom.IID_IDispatch))
    return None


def screenshot(run_dir, observer, hwnd, name):
    from bench.run import ROOT
    path = Path(run_dir) / 'grading' / name
    observer(run_dir, ROOT / 'acu/screenshot.ahk', 'app', f'ahk_id {hwnd}', '--out', path, '--max', '0', suffix='-' + path.stem)
    return path


# UFO's environment preparation: open the copied template in a fresh Office instance the bench owns.
def prepare_desktop(plan, observer):
    from bench.run import ROOT, save_json
    run_dir = Path(plan['run_dir'])
    task, document = plan['tb3'], Path(plan['workspace']) / plan['tb3']['template']
    app = APPS[task['app']]
    running = office_processes()
    if running:
        raise RuntimeError(f'Office is already running {running}; TB3 owns a fresh instance and will not share user documents')
    (run_dir / 'grading').mkdir(exist_ok=True)
    process = subprocess.Popen([str(OFFICE_DIR / app['exe']), str(document)])
    identity = {'launched_pid': process.pid, 'document': str(document), 'exe': app['exe']}
    save_json(run_dir / 'office-identity.json', identity)
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        windows = _windows(app['class'], Path(task['template']).stem)
        if len(windows) == 1 and bind_document(document) is not None:
            break
        time.sleep(1)
    else:
        raise RuntimeError(f'{app["exe"]} did not show exactly one window for {document.name}')
    time.sleep(3)  # first paint and add-in load
    identity.update(hwnd=windows[0][0], pid=windows[0][1], window=size_window(windows[0][0]))
    save_json(run_dir / 'office-identity.json', identity)
    observer(run_dir, ROOT / 'bench/office/window.ahk', 'activate', identity['hwnd'], identity['pid'], suffix='-activate')
    screenshot(run_dir, observer, identity['hwnd'], 'initial.png')
    return identity


def _com_retry(action, what, log, escape):
    for attempt in range(1, 6):
        try:
            return action()
        except Exception as error:  # noqa: BLE001 - COM raises pywintypes.com_error
            log.append(f'{what} attempt {attempt}: {error}')
            if attempt == 2:
                escape()
            time.sleep(2)
    raise RuntimeError(f'{what} failed; see collection.json')


# UFO's post-execution: final screenshot, save the document through COM, quit the owned Office instance.
def collect(run_dir, plan, observer):
    from bench.run import ROOT, save_json
    run_dir = Path(run_dir)
    identity = json.loads((run_dir / 'office-identity.json').read_text(encoding='utf-8'))
    record = {'interventions': [], 'log': []}

    def escape():
        observer(run_dir, ROOT / 'bench/office/window.ahk', 'escape', identity['hwnd'], identity['pid'], suffix='-escape')
        record['interventions'].append('sent Escape twice to the owned window so COM could save')
    try:
        try:
            record['final_screenshot'] = str(screenshot(run_dir, observer, identity['hwnd'], 'final.png'))
        except Exception:  # noqa: BLE001
            record['final_screenshot'] = None
            record['log'].append('final screenshot failed: ' + traceback.format_exc())
        document = bind_document(identity['document'])
        record['document_open'] = document is not None
        if document is not None:
            _com_retry(document.Save, 'save', record['log'], escape)
            record['saved'] = True
            application = document.Application
            app = plan['tb3']['app']
            if app == 'excel':
                application.DisplayAlerts = False
                _com_retry(application.Quit, 'quit', record['log'], escape)
            elif app == 'word':
                _com_retry(lambda: application.Quit(0), 'quit', record['log'], escape)
            else:
                presentations = list(application.Presentations)
                for presentation in presentations:
                    presentation.Saved = True
                    presentation.Close()
                record['log'].append(f'closed {len(presentations)} presentation(s)')
                presentations = presentation = None
                _com_retry(application.Quit, 'quit', record['log'], escape)
            record['log'].append('quit requested')
            # PowerPoint stays alive while any client reference remains, so release them before waiting for exit.
            document = application = None
            import gc
            gc.collect()
    finally:
        record['office_exit'] = stop_office(identity)
        save_json(run_dir / 'collection.json', record)
    snapshot = run_dir / 'grading' / plan['tb3']['template']
    snapshot.write_bytes(Path(identity['document']).read_bytes())
    record['graded_document'] = str(snapshot)
    save_json(run_dir / 'collection.json', record)
    return record


# Wait for the owned Office processes to exit; terminate only those this trial launched or attached to.
def stop_office(identity, timeout_s=30):
    owned = {identity.get('pid'), identity.get('launched_pid')} - {None}
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        remaining = [pid for _, pid in office_processes() if pid in owned]
        if not remaining:
            return {'exited': True, 'terminated': []}
        time.sleep(1)
    for pid in remaining:
        subprocess.run(['taskkill', '/PID', str(pid), '/F'], capture_output=True)
    return {'exited': not [pid for _, pid in office_processes() if pid in owned], 'terminated': remaining}


# Recognizes Office automation in actor tool calls; GUI-360 allows COM, so this is reported, not a failure.
COM_PATTERN = r'(?:Excel|Word|PowerPoint)\.Application|win32com|ComObj(?:Get|Active|ect)\b|GetObject\(|New-Object\s+-ComObject'


# Task success is the saved-file check within the step limit; COM use is an observation.
def grade(run_dir, plan, tools):
    from bench.run import ROOT
    task = plan['tb3']
    graded = Path(run_dir) / 'grading' / task['template']
    check = check_document(plan['scenario'], graded, ROOT / 'bench/assets/gui360' / task['template']) if graded.is_file() \
        else {'passed': False, 'sub_scores': {}, 'error': 'no saved document to check'}
    com = sorted({m.group(0) for t in tools for m in re.finditer(COM_PATTERN, t.get('text', ''))})
    within = len(tools) <= STEP_LIMIT
    return {'passed': check['passed'] and within, 'file_check': check,
            'tool_calls': len(tools), 'step_limit': STEP_LIMIT, 'within_step_limit': within,
            'office_com_used': bool(com), 'office_com_evidence': com}


# Leave no trial-owned Office running after a failure; never touches instances absent from office-identity.json.
def cleanup(run_dir):
    path = Path(run_dir) / 'office-identity.json'
    if not path.is_file():
        return {'passed': True, 'note': 'Office was not launched'}
    exit_state = stop_office(json.loads(path.read_text(encoding='utf-8')), timeout_s=5)
    return {'passed': exit_state['exited'], 'office_exit': exit_state}


# ---------------------------------------------------------------------------------------------------------------
# File checks: the request read literally against the saved OOXML, using only the standard library.

M = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
P = '{http://schemas.openxmlformats.org/presentationml/2006/main}'
A = '{http://schemas.openxmlformats.org/drawingml/2006/main}'
R = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
QUARTER_INCH_EMU = 228600


def _xml(archive, name):
    return ET.fromstring(archive.read(name))


def _target(archive, rels, rid, base):
    for rel in _xml(archive, rels):
        if rel.get('Id') == rid:
            target = rel.get('Target')
            return target.lstrip('/') if target.startswith('/') else base + target
    raise KeyError(rid)


# First worksheet's non-empty cell values by reference and its conditional-format blocks.
def xlsx_sheet(path):
    archive = zipfile.ZipFile(path)
    shared = []
    if 'xl/sharedStrings.xml' in archive.namelist():
        shared = [''.join(t.text or '' for t in si.iter(M + 't')) for si in _xml(archive, 'xl/sharedStrings.xml').findall(M + 'si')]
    first = _xml(archive, 'xl/workbook.xml').find(f'{M}sheets/{M}sheet')
    sheet = _xml(archive, _target(archive, 'xl/_rels/workbook.xml.rels', first.get(R + 'id'), 'xl/'))
    cells = {}
    for cell in sheet.iter(M + 'c'):
        kind, value = cell.get('t'), cell.find(M + 'v')
        if kind == 's':
            text = shared[int(value.text)]
        elif kind == 'inlineStr':
            text = ''.join(t.text or '' for t in cell.iter(M + 't'))
        else:
            text = value.text if value is not None else None
        if text not in (None, ''):
            cells[cell.get('r')] = text
    formats = [{'sqref': cf.get('sqref'),
                'rules': [{**rule.attrib, 'formulas': [f.text for f in rule.findall(M + 'formula')]} for rule in cf.findall(M + 'cfRule')]}
               for cf in sheet.findall(M + 'conditionalFormatting')]
    return cells, formats


def _ref(ref):
    column, row = re.fullmatch(r'([A-Z]+)(\d+)', ref).groups()
    return column, int(row)


def _check_delete_columns(saved, template):
    before, _ = xlsx_sheet(template)
    after, _ = xlsx_sheet(saved)
    expected = {'ABCD'['ACEG'.index(_ref(ref)[0])] + str(_ref(ref)[1]): value for ref, value in before.items() if _ref(ref)[0] in 'ACEG'}
    header = {ref: value for ref, value in after.items() if _ref(ref)[1] == 1}
    return {'Columns B, D and F deleted (header is Name, Gender, Gender identification, Country)':
                header == {ref: value for ref, value in expected.items() if _ref(ref)[1] == 1},
            'Remaining data shifted intact in all rows': all(after.get(ref) == value for ref, value in expected.items()),
            'No other columns or cells changed': after == expected}


def _covers_age_column(sqref):
    rows = set()
    for part in sqref.split():
        start, _, end = part.partition(':')
        (c1, r1), (c2, r2) = _ref(start), _ref(end or start)
        if c1 != 'B' or c2 != 'B':
            return False
        rows.update(range(r1, min(r2, 100) + 1))
    return set(range(2, 22)) <= rows


def _greater_than_30(rule, sqref):
    formulas = [f.strip().lstrip('=') for f in rule['formulas'] if f]
    if rule.get('type') == 'cellIs' and rule.get('operator') == 'greaterThan':
        return len(formulas) == 1 and re.fullmatch(r'30(?:\.0+)?', formulas[0]) is not None
    if rule.get('type') == 'expression':
        top = _ref(sqref.split()[0].partition(':')[0])[1]
        return len(formulas) == 1 and re.fullmatch(rf'\$?B\$?{top}\s*>\s*30', formulas[0]) is not None
    return False


def _check_conditional_format(saved, template):
    before, _ = xlsx_sheet(template)
    after, formats = xlsx_sheet(saved)
    matching = [(f['sqref'], rule) for f in formats for rule in f['rules'] if _greater_than_30(rule, f['sqref'])]
    return {'Rule highlights values greater than 30': bool(matching),
            'Rule applies to the Age column (B2:B21 covered, no other column)': any(_covers_age_column(sqref) for sqref, _ in matching),
            'Rule has a highlight format': any('dxfId' in rule for _, rule in matching),
            'No cell values changed': after == before}


# Paragraph text with per-character highlight flags and paragraph alignment.
def docx_paragraphs(path):
    body = _xml(zipfile.ZipFile(path), 'word/document.xml').find(W + 'body')
    paragraphs = []
    for paragraph in body.iter(W + 'p'):
        text, marks = '', []
        for run in paragraph.iter(W + 'r'):
            piece = ''.join(t.text or '' for t in run.findall(W + 't'))
            highlight = run.find(f'{W}rPr/{W}highlight')
            text += piece
            marks += [highlight is not None and highlight.get(W + 'val') not in (None, 'none')] * len(piece)
        alignment = paragraph.find(f'{W}pPr/{W}jc')
        paragraphs.append({'text': unicodedata.normalize('NFC', text), 'highlighted': marks,
                           'jc': alignment.get(W + 'val') if alignment is not None else None})
    return paragraphs


def _texts(paragraphs, remove=''):
    return [t for t in ((p['text'].replace(remove, '') if remove else p['text']).strip() for p in paragraphs) if t]


def _check_highlight_span(saved, template):
    before, after = docx_paragraphs(template), docx_paragraphs(saved)
    span = before[1]['text']  # the request's span is exactly the first body paragraph
    targets = [p for p in after if p['text'] == span]
    whole = len(targets) == 1 and all(on or c.isspace() for c, on in zip(span, targets[0]['highlighted']))
    others = [p for p in after if not (targets and p is targets[0]) and any(on and not c.isspace() for c, on in zip(p['text'], p['highlighted']))]
    return {"Whole span 'An agent is a broad concept' ... 'and autonomous systems.' highlighted": whole,
            'No text outside the span highlighted': whole and not others,
            'Document text unchanged': _texts(after) == _texts(before)}


ARABIC = unicodedata.normalize('NFC', 'مرحبا')


def _check_arabic_right(saved, template):
    before, after = docx_paragraphs(template), docx_paragraphs(saved)
    holders = [p for p in after if ARABIC in p['text']]
    return {"Arabic text 'مرحبا' added": bool(holders),
            'Its paragraph is right-aligned': any(p['jc'] == 'right' for p in holders),
            'Existing document text unchanged': _texts(after, ARABIC) == _texts(before)}


# Slide size and count, and slide 1 shapes with preset geometry, position, extent and adjustments.
def pptx_slide1(path):
    archive = zipfile.ZipFile(path)
    presentation = _xml(archive, 'ppt/presentation.xml')
    size, ids = presentation.find(P + 'sldSz'), presentation.find(P + 'sldIdLst').findall(P + 'sldId')
    slide = _xml(archive, _target(archive, 'ppt/_rels/presentation.xml.rels', ids[0].get(R + 'id'), 'ppt/'))
    shapes = []
    for element in slide.find(f'{P}cSld/{P}spTree').iter():
        if element.tag not in (P + 'sp', P + 'cxnSp', P + 'pic', P + 'graphicFrame'):
            continue
        geometry = element.find(f'{P}spPr/{A}prstGeom')
        offset, extent = element.find(f'{P}spPr/{A}xfrm/{A}off'), element.find(f'{P}spPr/{A}xfrm/{A}ext')
        shapes.append({'prst': geometry.get('prst') if geometry is not None else None,
                       'x': int(offset.get('x')) if offset is not None else None, 'y': int(offset.get('y')) if offset is not None else None,
                       'cx': int(extent.get('cx')) if extent is not None else None, 'cy': int(extent.get('cy')) if extent is not None else None,
                       'adjust': {gd.get('name'): gd.get('fmla') for gd in geometry.iter(A + 'gd')} if geometry is not None else {}})
    return {'width': int(size.get('cx')), 'height': int(size.get('cy')), 'slides': len(ids), 'shapes': shapes}


def _on_slide(shape, deck):
    return None not in (shape['x'], shape['cx']) and shape['x'] >= 0 and shape['y'] >= 0 \
        and shape['x'] + shape['cx'] <= deck['width'] and shape['y'] + shape['cy'] <= deck['height']


def _single(deck, kinds):
    return deck['shapes'][0] if len(deck['shapes']) == 1 and deck['shapes'][0]['prst'] in kinds else None


def _check_shift_line(saved, template):
    deck = pptx_slide1(saved)
    line = _single(deck, {'line', 'straightConnector1'})
    constrained = line is not None and (line['cx'] == 0 or line['cy'] == 0 or abs(line['cx'] - line['cy']) <= 0.01 * max(line['cx'], line['cy']))
    return {'One line on Slide 1 and nothing else': line is not None,
            'Line is constrained straight (horizontal, vertical or 45 degrees)': constrained,
            'Line has visible length and lies on the slide': line is not None and max(line['cx'], line['cy']) >= QUARTER_INCH_EMU and _on_slide(line, deck),
            'Slide count unchanged': deck['slides'] == pptx_slide1(template)['slides']}


def _check_speech_bubble(saved, template):
    deck = pptx_slide1(saved)
    bubble = _single(deck, {'wedgeRectCallout', 'wedgeRoundRectCallout', 'wedgeEllipseCallout'})
    return {'One speech-bubble shape on Slide 1 and nothing else': bubble is not None,
            'Bubble has visible size and lies on the slide': bubble is not None and min(bubble['cx'], bubble['cy']) >= QUARTER_INCH_EMU and _on_slide(bubble, deck),
            'Slide count unchanged': deck['slides'] == pptx_slide1(template)['slides']}


ROUNDED_DEFAULTS = {'roundRect': {'adj': 16667}, 'round1Rect': {'adj': 16667},
                    'round2SameRect': {'adj1': 16667, 'adj2': 0}, 'round2DiagRect': {'adj1': 16667, 'adj2': 0}}


def _check_rounded_corners(saved, template):
    deck = pptx_slide1(saved)
    shape = _single(deck, set(ROUNDED_DEFAULTS))
    adjusted = False
    for name, formula in (shape or {}).get('adjust', {}).items():
        value = re.fullmatch(r'val (-?\d+)', formula or '')
        adjusted |= value is not None and int(value.group(1)) != ROUNDED_DEFAULTS[shape['prst']].get(name)
    return {'One rounded-corner shape on Slide 1 and nothing else': shape is not None,
            'Corner roundness changed from the default': adjusted,
            'Shape has visible size and lies on the slide': shape is not None and min(shape['cx'], shape['cy']) >= QUARTER_INCH_EMU and _on_slide(shape, deck),
            'Slide count unchanged': deck['slides'] == pptx_slide1(template)['slides']}


CHECKS = {'tb3.1': _check_delete_columns, 'tb3.2': _check_conditional_format, 'tb3.3': _check_highlight_span,
          'tb3.4': _check_arabic_right, 'tb3.5': _check_shift_line, 'tb3.6': _check_speech_bubble, 'tb3.7': _check_rounded_corners}


# An unreadable document fails explicitly instead of raising out of grading.
def check_document(scenario, saved, template):
    try:
        scores = CHECKS[scenario](saved, template)
    except Exception as error:  # noqa: BLE001
        return {'passed': False, 'sub_scores': {}, 'error': repr(error)}
    return {'passed': all(scores.values()), 'sub_scores': {name: 'yes' if value else 'no' for name, value in scores.items()}}
