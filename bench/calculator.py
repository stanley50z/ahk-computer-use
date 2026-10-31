"""Calculator ownership, verification and cleanup behind the scenario contract."""
import re

from bench.common import ROOT, load_actor_json
from bench.scenario import Scenario

EXPRESSION = '98765 * 432 / 1234 * 56 / 789 + 6543 - 4321'
EXPECTED = '4676.045886202710280949769213229720652488'  # normal precedence; the verifier compares to a millionth


# A claim never authorizes closing a pre-existing visible handle; current PID must also be checked by cleanup.ahk.
# Hidden pre-existing handles (probe lines `hiddenwindow=`) are not protected: on 2026-10-10 the frame host gave a new
# Calculator a hidden shell window it already owned, and the old rule refused to clean up the actor's own window.
def owned_window(before, claim):
    hwnd = str(claim.get('hwnd', ''))
    pid = str(claim.get('pid', ''))
    if not hwnd.isdigit() or not int(hwnd) or not pid.isdigit() or not int(pid):
        raise ValueError('missing or invalid window/process identity')
    protected = set(re.findall(r'^(?:window|calculator)=(\d+)', before, re.MULTILINE))
    if hwnd in protected:
        raise ValueError('refusing cleanup of a pre-existing window')
    return hwnd, int(pid)



# Bind a returned numeric window ID to observed Win32 identity; reject guesses, old windows and PID changes.
def bind_owned_window(before, claim, observed):
    if 'hwnd' in claim:
        raw_id = claim['hwnd']
    elif 'window_id' in claim:
        raw_id = claim['window_id']
    elif 'window' in claim and 'id' in claim['window']:
        raw_id = claim['window']['id']
    else:
        raise ValueError('the actor supplied no returned window identity')
    value = str(raw_id)
    if not re.fullmatch(r'(?:0x[0-9a-fA-F]+|[0-9]+)', value):
        raise ValueError(f'unsupported opaque window identity: {value}')
    hwnd = str(int(value, 16 if value.startswith('0x') else 10))
    pids = dict(re.findall(r'^window=(\d+) pid=(\d+)\s*$', observed, re.MULTILINE))
    if hwnd not in pids:
        raise ValueError('returned window was not observed by the independent inspector')
    pid = int(pids[hwnd])
    if 'pid' in claim and int(claim['pid']) != pid:
        raise ValueError('claimed process identity does not match the observed window')
    return owned_window(before, {'hwnd': hwnd, 'pid': pid})


# Scenario v1.1 asks the actor for the task and result.json only, so the bench finds the actor's window itself: the one
# visible Calculator present after the trial that was not there before, excluding independently observed XAML popups.
# Keep the raw probe intact for protection/cleanup checks. None or several main candidates is an error, never a guess.
def new_calculator_window(before, observed):
    old = set(re.findall(r'^calculator=(\d+)', before, re.MULTILINE))
    popups = set(re.findall(r'^class=(\d+) Xaml_WindowedPopupClass\s*$', observed, re.MULTILINE))
    new = sorted(set(re.findall(r'^calculator=(\d+)', observed, re.MULTILINE)) - old - popups)
    if len(new) != 1:
        raise ValueError(f'expected exactly one new Calculator window, observed {new}')
    pids = dict(re.findall(r'^window=(\d+) pid=(\d+)\s*$', observed, re.MULTILINE))
    if new[0] not in pids:
        raise ValueError('the new Calculator window has no observed process identity')
    return owned_window(before, {'hwnd': new[0], 'pid': pids[new[0]]})


# The actor's window: its own claim when it wrote one (ownership.json or result.json), else the observed new window.
def actor_window(before, claim, observed):
    if claim and any(key in claim for key in ('hwnd', 'window_id', 'window')):
        return bind_owned_window(before, claim, observed)
    return new_calculator_window(before, observed)


# Record which input routes a script used. Scenario v4 (2026-10-10) allows any input the tool offers, so this is
# evidence for the report, not a gate; v3 had failed keyboard/text and field-value injection.
def script_input_methods(text):
    patterns = {
        'keyboard/text input': r'\b(?:Send|SendText|SendInput|SendEvent|ControlSend|ControlSetText)\s*(?:\(|["\x27])|\.(?:type_text|press_key|hotkey|key_press|type)\s*\(|\b(?:type_text|press_key|key_press|hotkey)\b',
        'direct field value': r'\.Value\s*:=|\.(?:SetValue|set_value)\s*\(',
        'semantic action': r'\.(?:Invoke|Toggle|Select|Expand)\s*\(|\.Click\(\)|element_token|element_index',
        'pointer': r'\bClick\s*\(?\s*\d|\bMouseClick|\.Click\(\s*"|screenshotId|sky\.click\(',
    }
    return [name for name, pattern in patterns.items() if re.search(pattern, text, re.IGNORECASE)]


# Independently verify displayed arithmetic against a fixed decimal reference, and preserve a screenshot.
def verify_calculator(run_dir, before, observer):
    from decimal import Decimal
    result_file = run_dir / 'workspace/result.json'
    if not result_file.is_file():
        return {'passed': False, 'reason': 'agent did not write result.json'}
    claimed = load_actor_json(result_file)  # the task asks for result.json; the window itself is found by observation
    if claimed.get('status') == 'blocked':
        return {'passed': False, 'reason': 'actor reported blocked', 'claim': claimed}
    identity = observer(run_dir, ROOT / 'bench/probe.ahk', suffix='-bind')
    try:
        hwnd, pid = actor_window(before, claimed, identity)
    except ValueError as error:
        return {'passed': False, 'reason': str(error), 'claim': claimed}
    observed = observer(run_dir, ROOT / 'bench/calculator/verify.ahk', hwnd)
    displayed = re.search(r'^result=(.*)', observed, re.MULTILINE).group(1).strip()
    expression = re.search(r'^expression=(.*)', observed, re.MULTILINE).group(1).strip()
    number = re.search(r'[-−]?[\d,]+(?:\.\d+)?', displayed)
    if number is None:
        raise ValueError(f'cannot parse Calculator display: {displayed}')
    actual = Decimal(number.group().replace(',', '').replace('−', '-'))
    expected = Decimal(EXPECTED)
    screenshot = run_dir / 'calculator-result.png'
    observer(run_dir, ROOT / 'acu/screenshot.ahk', 'app', f'ahk_id {hwnd}', '--out', screenshot, '--max', '0')
    scripts = [path for path in (run_dir / 'workspace').rglob('*') if path.suffix.lower() in ('.ahk', '.py', '.js', '.mjs', '.ps1', '.sh')]
    methods = {str(script.relative_to(run_dir / 'workspace')): script_input_methods(script.read_text(encoding='utf-8-sig')) for script in scripts}
    return {'passed': abs(actual - expected) < Decimal('0.000001'),
            'hwnd': hwnd, 'observed_result': displayed, 'observed_expression': expression,
            'expected': str(expected), 'screenshot': str(screenshot), 'claim': claimed,
            'script_audit': {'input_methods_by_script': methods, 'note': 'Static screening of workspace scripts for the report; the scenario names no input route. Not a security boundary.'}}


# Calculator retains its existing window/PID ownership and cleanup policy.
def cleanup_calculator(run_dir, before, ownership_file, observer):
    claimed = load_actor_json(ownership_file) if ownership_file.is_file() else None
    identity = observer(run_dir, ROOT / 'bench/probe.ahk', suffix='-cleanup-bind')
    try:
        hwnd, pid = actor_window(before, claimed, identity)
    except ValueError as error:
        if re.search(r'^calculator=', identity, re.MULTILINE) and not re.search(r'^calculator=', before, re.MULTILINE):
            raise  # Calculator windows appeared and none can be attributed: refuse rather than guess
        hwnd = None  # the actor opened nothing, or closed its own window already
        (run_dir / 'cleanup-note.txt').write_text(f'no window to close: {error}\n', encoding='utf-8')
    if hwnd is not None:
        observer(run_dir, ROOT / 'bench/calculator/cleanup.ahk', hwnd, pid)
    after = observer(run_dir, ROOT / 'bench/probe.ahk', suffix='-after')
    old = set(re.findall(r'^calculator=(\d+)', before, re.MULTILINE))
    remaining = set(re.findall(r'^calculator=(\d+)', after, re.MULTILINE)) - old
    return {'passed': not remaining, 'remaining_new_calculator_windows': sorted(remaining)}


# Calculator verifies before conduct, preserving its original observer and artifact timing.
class CalculatorScenario(Scenario):
    application = 'calculator'
    prepares_desktop = False
    verify_before_audit = True
    fail_outside_writes = True
    cursor_verification = 'Saved Windows scheme reloaded and OS showing flag checked; not a pixel-level visibility proof.'

    def approved_apps(self):
        return ['calc.exe', 'Calculator.exe', 'CalculatorApp.exe',
                'Microsoft.WindowsCalculator_8wekyb3d8bbwe!App']

    def collect_and_grade(self, trial, tools):
        return verify_calculator(trial.run_dir, trial.before, trial.observer)

    def cleanup(self, trial):
        return cleanup_calculator(trial.run_dir, trial.before,
                                  trial.run_dir / 'workspace/ownership.json', trial.observer)

    def check_cleanup(self, cleanup):
        remaining = cleanup['remaining_new_calculator_windows']
        if remaining:
            raise RuntimeError(f'unclaimed Calculator windows remain; do not auto-close: {remaining}')
