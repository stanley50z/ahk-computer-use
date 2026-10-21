"""TB3.1-TB3.4: live Office tasks in GUI-360's environment, graded by a programmatic check of the saved file.

GUI-360 (arXiv 2511.04307) collected tasks with UFO's dataflow: copy a template, open it in Office, let the agent act,
take a final screenshot, save through COM, quit Office. TB3 repeats that environment with an ACU/CUA actor. TB3.1 is a
GUI-360 task, TB3.2 is adapted from one, TB3.3 and TB3.4 are the bench's own input tasks. Grading reads the saved OOXML
and checks the request literally; the number of tool calls is reported but never fails a task. Tasks that name an input
method are also graded on that input, observed by bench/input_recorder.py while the actor runs.
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
APPS = {
    'excel': {'exe': 'EXCEL.EXE', 'class': 'XLMAIN', 'name': 'Microsoft Excel', 'noun': 'workbook'},
    'word': {'exe': 'WINWORD.EXE', 'class': 'OpusApp', 'name': 'Microsoft Word', 'noun': 'document'},
}
# Middle sentences of body paragraphs 3, 6 and 10 of template1.docx; at the TB3 window size none is visible without scrolling.
SENTENCES = (
    'A software agent is a program that autonomously performs tasks on behalf of users or other programs.',
    'The study of philosophical agents involves questions about consciousness, moral responsibility, and the nature of decision-making.',
    'As autonomous agents assume greater roles in decision-making, questions about accountability, bias, and fairness arise.',
)
TASKS = {
    'tb3.1': {'gui360_id': 'excel_4s_13432', 'app': 'excel', 'template': 'adult_sexual_behaviors.xlsx', 'adapted': False,
              'request': "Apply conditional formatting to the 'Age' column in Excel to highlight cells with values greater than 30."},
    'tb3.2': {'gui360_id': 'word_4s_1023', 'app': 'word', 'template': 'template1.docx', 'adapted': True,
              'request': 'Highlight these three sentences in the Word document: '
                         + ', '.join(f"'{s}'" for s in SENTENCES[:2]) + f", and '{SENTENCES[2]}'"},
    'tb3.3': {'gui360_id': None, 'app': 'excel', 'template': 'budget.xlsx', 'adapted': False,
              'request': "Copy cell B2's formatting onto B3:B10 without changing their values. Do it by right-dragging "
                         "B2's fill handle down to B10 with the right mouse button, releasing it, and choosing Fill Formatting Only.",
              'required_input': 'right-button drag on the Excel window'},
    'tb3.4': {'gui360_id': None, 'app': 'excel', 'template': 'budget.xlsx', 'adapted': False,
              'request': 'Make a copy of the Budget sheet. Do it by holding Ctrl while dragging the Budget sheet tab to the right '
                         'with the left mouse button, and releasing it there.',
              'required_input': 'left-button drag on the Excel window with Ctrl held from press to release'},
}
OFFICE_EXES = [app['exe'] for app in APPS.values()]


def is_tb3(scenario):
    return str(scenario).startswith('tb3.')


# Actor prompt: where the document is, the task request, and the shared open-document ending.
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
            # Even the method lookup is a COM call that a busy Office rejects, so it must sit inside the retry.
            _com_retry(lambda: document.Save(), 'save', record['log'], escape)
            record['saved'] = True
            application = _com_retry(lambda: document.Application, 'application', record['log'], escape)
            if plan['tb3']['app'] == 'excel':
                application.DisplayAlerts = False
                _com_retry(lambda: application.Quit(), 'quit', record['log'], escape)
            else:
                _com_retry(lambda: application.Quit(0), 'quit', record['log'], escape)
            record['log'].append('quit requested')
            # Office can stay alive while a client reference remains, so release them before waiting for exit.
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
COM_PATTERN = r'(?:Excel|Word)\.Application|win32com|ComObj(?:Get|Active|ect)\b|GetObject\(|New-Object\s+-ComObject'


# GUI-360 templates and the bench's own templates live in separate asset folders.
def template_path(name):
    from bench.run import ROOT
    gui360 = ROOT / 'bench/assets/gui360' / name
    return gui360 if gui360.is_file() else ROOT / 'bench/assets/tb3' / name


# Start the Raw Input recorder for the actor's run; maintainer setup and collection stay outside its window.
def start_recorder(run_dir):
    import sys
    from bench.run import ROOT, save_json
    run_dir = Path(run_dir)
    process = subprocess.Popen([sys.executable, str(ROOT / 'bench/input_recorder.py'), str(run_dir / 'input-log.jsonl'),
                                str(run_dir / 'input-recorder.stop')], creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    save_json(run_dir / 'input-recorder.json', {'pid': process.pid})
    deadline = time.monotonic() + 10
    while not (run_dir / 'input-log.jsonl').is_file():
        if process.poll() is not None or time.monotonic() > deadline:
            raise RuntimeError('input recorder did not start; see input-log.crash.txt')
        time.sleep(0.1)
    return process


# Ask the recorder to stop through its stop file; a recorder that ignores it is killed.
def stop_recorder(run_dir, process):
    (Path(run_dir) / 'input-recorder.stop').touch()
    try:
        process.wait(5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(5)


CTRL_KEYS = {0x11, 0xA2, 0xA3}
MIN_DRAG_PX = 40


# Press/release pairs of one button with the Ctrl state at each, in recorder log order.
def drags(events, button):
    ctrl, pressed, found = False, None, []
    for event in events:
        if event.get('kind') == 'key' and event.get('vk') in CTRL_KEYS:
            ctrl = event['action'] == 'down'
        elif event.get('kind') == 'mouse' and event.get('button') == button:
            if event['action'] == 'down':
                pressed = dict(event, ctrl=ctrl)
            elif pressed is not None:
                found.append({'down': pressed, 'up': dict(event, ctrl=ctrl),
                              'dx': event['x'] - pressed['x'], 'dy': event['y'] - pressed['y']})
                pressed = None
    return found


# The input a task names, read from the recorder log; a task that names no method has no input requirement.
def check_input(run_dir, plan):
    run_dir, scenario = Path(run_dir), plan['scenario']
    if 'required_input' not in plan['tb3']:
        return None
    log = run_dir / 'input-log.jsonl'
    if not log.is_file():
        return {'passed': False, 'required': plan['tb3']['required_input'], 'error': 'no input log'}
    hwnd = json.loads((run_dir / 'office-identity.json').read_text(encoding='utf-8'))['hwnd']
    events = [json.loads(line) for line in log.read_text(encoding='utf-8').splitlines() if line.strip()]
    on_window = lambda drag: drag['down']['window'] == hwnd and drag['up']['window'] == hwnd
    if scenario == 'tb3.3':
        matches = [d for d in drags(events, 'right') if on_window(d) and abs(d['dy']) >= MIN_DRAG_PX]
    else:
        matches = [d for d in drags(events, 'left') if on_window(d) and abs(d['dx']) >= MIN_DRAG_PX and d['down']['ctrl'] and d['up']['ctrl']]
    return {'passed': bool(matches), 'required': plan['tb3']['required_input'], 'matching_drags': matches[:5],
            'recorded_events': sum(e.get('kind') in ('mouse', 'key', 'wheel', 'hwheel') for e in events)}


# Task success is the saved-file check and the named input when there is one; tool calls and COM use are observations.
def grade(run_dir, plan, tools):
    task = plan['tb3']
    graded = Path(run_dir) / 'grading' / task['template']
    check = check_document(plan['scenario'], graded, template_path(task['template'])) if graded.is_file() \
        else {'passed': False, 'sub_scores': {}, 'error': 'no saved document to check'}
    observed = check_input(run_dir, plan)
    com = sorted({m.group(0) for t in tools for m in re.finditer(COM_PATTERN, t.get('text', ''))})
    return {'passed': check['passed'] and (observed is None or observed['passed']), 'file_check': check,
            'input_check': observed, 'tool_calls': len(tools),
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
R = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'


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


# Paragraph text with a per-character flag for Word's text highlight color.
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
        paragraphs.append({'text': unicodedata.normalize('NFC', text), 'highlighted': marks})
    return paragraphs


def _texts(paragraphs):
    return [t for t in (p['text'].strip() for p in paragraphs) if t]


# Every visible character of each sentence highlighted, nothing else; whitespace next to a sentence may go either way.
def _check_highlight_sentences(saved, template):
    before, after = docx_paragraphs(template), docx_paragraphs(saved)
    allowed = [set() for _ in after]
    scores = {}
    for sentence in SENTENCES:
        hits = [(i, p['text'].find(sentence)) for i, p in enumerate(after) if sentence in p['text']]
        lit = False
        if len(hits) == 1:
            index, start = hits[0]
            span = range(start, start + len(sentence))
            allowed[index].update(span)
            lit = all(after[index]['highlighted'][k] or after[index]['text'][k].isspace() for k in span)
        scores[f"Highlighted: '{sentence[:40]}...'"] = lit
    scores['No other text highlighted'] = not any(
        on and not char.isspace() and k not in allowed[i]
        for i, p in enumerate(after) for k, (char, on) in enumerate(zip(p['text'], p['highlighted'])))
    scores['Document text unchanged'] = _texts(after) == _texts(before)
    return scores


# Every sheet by name in tab order, with cell values and each cell's formatting resolved to its XML definitions, so
# two cells match when they look the same even if Excel stored them under different style indexes.
def xlsx_book(path):
    archive = zipfile.ZipFile(path)
    shared = []
    if 'xl/sharedStrings.xml' in archive.namelist():
        shared = [''.join(t.text or '' for t in si.iter(M + 't')) for si in _xml(archive, 'xl/sharedStrings.xml').findall(M + 'si')]
    styles = _xml(archive, 'xl/styles.xml')
    pool = {name: [ET.tostring(item) for item in styles.find(M + name)] for name in ('fonts', 'fills', 'borders')}
    formats = {f.get('numFmtId'): f.get('formatCode') for f in styles.iter(M + 'numFmt')}
    looks = []
    for xf in styles.find(M + 'cellXfs'):
        alignment = xf.find(M + 'alignment')
        looks.append((formats.get(xf.get('numFmtId'), xf.get('numFmtId')), pool['fonts'][int(xf.get('fontId', 0))],
                      pool['fills'][int(xf.get('fillId', 0))], pool['borders'][int(xf.get('borderId', 0))],
                      ET.tostring(alignment) if alignment is not None else None))
    book = {}
    for sheet in _xml(archive, 'xl/workbook.xml').find(M + 'sheets'):
        data = _xml(archive, _target(archive, 'xl/_rels/workbook.xml.rels', sheet.get(R + 'id'), 'xl/'))
        values, look = {}, {}
        for cell in data.iter(M + 'c'):
            kind, value = cell.get('t'), cell.find(M + 'v')
            text = shared[int(value.text)] if kind == 's' else (value.text if value is not None else None)
            if text not in (None, ''):
                values[cell.get('r')] = text
            if int(cell.get('s', 0)):
                look[cell.get('r')] = looks[int(cell.get('s'))]
        book[sheet.get('name')] = {'values': values, 'looks': look}
    return book


FILL_TARGETS = [f'B{row}' for row in range(3, 11)]


def _check_fill_formatting(saved, template):
    before, after = xlsx_book(template)['Budget'], xlsx_book(saved)['Budget']
    source = after['looks'].get('B2')
    others = set(before['looks']) | set(after['looks'])
    return {"B3:B10 have B2's formatting": source is not None and all(after['looks'].get(ref) == source for ref in FILL_TARGETS),
            'B2 formatting unchanged': source == before['looks'].get('B2'),
            'No cell values changed': after['values'] == before['values'],
            'No other cell formatting changed': all(after['looks'].get(ref) == before['looks'].get(ref)
                                                    for ref in others if ref not in FILL_TARGETS)}


def _check_sheet_copy(saved, template):
    before, after = xlsx_book(template), xlsx_book(saved)
    copy = after.get('Budget (2)')
    return {"Sheets are 'Budget' and its copy 'Budget (2)'": sorted(after) == ['Budget', 'Budget (2)'],
            'Copy has the same values and formatting': copy == before['Budget'],
            'Original sheet unchanged': after.get('Budget') == before['Budget']}


CHECKS = {'tb3.1': _check_conditional_format, 'tb3.2': _check_highlight_sentences,
          'tb3.3': _check_fill_formatting, 'tb3.4': _check_sheet_copy}


# An unreadable document fails explicitly instead of raising out of grading.
def check_document(scenario, saved, template):
    try:
        scores = CHECKS[scenario](saved, template)
    except Exception as error:  # noqa: BLE001
        return {'passed': False, 'sub_scores': {}, 'error': repr(error)}
    return {'passed': all(scores.values()), 'sub_scores': {name: 'yes' if value else 'no' for name, value in scores.items()}}
