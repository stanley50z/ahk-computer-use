"""Bench copy of cua-driver's autostart task, which starts the daemon in a chosen working directory.

cua-driver resolves a relative screenshot_out_file against the daemon's working directory, and the installed
autostart task pins that to the home folder. The bench copy runs the same command with the same elevation, without
the logon trigger, and takes its working directory from CWD_FILE, which restart_cua_daemon writes before each trial.

    python bench/cua_bench_task.py install     # once per machine; asks for UAC approval
    python bench/cua_bench_task.py uninstall
"""

import ctypes
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALLED_TASK = r'\cua-driver-serve'
BENCH_TASK = r'\ahk-computer-use-bench-cua-serve'
CWD_FILE = ROOT / '.pi/bench/cua-serve-cwd.txt'
NS = 'http://schemas.microsoft.com/windows/2004/02/mit/task'


def start_command():
    return ['schtasks', '/run', '/tn', BENCH_TASK]


def installed(task=BENCH_TASK):
    return subprocess.run(['schtasks', '/query', '/tn', task], capture_output=True).returncode == 0


# The installed task's XML with the logon trigger removed and its fixed -WorkingDirectory read from CWD_FILE.
def bench_task_xml():
    source = subprocess.run(['schtasks', '/query', '/tn', INSTALLED_TASK, '/xml'], capture_output=True, text=True, check=True).stdout
    ET.register_namespace('', NS)
    task = ET.fromstring(re.sub(r'^\s*<\?xml[^>]*\?>', '', source.replace('\r\n', '\n')))
    for triggers in task.findall(f'{{{NS}}}Triggers'):
        task.remove(triggers)
    info = task.find(f'{{{NS}}}RegistrationInfo')
    for name, text in (('URI', BENCH_TASK), ('Description', 'ahk-computer-use bench: cua-driver serve in the trial workspace')):
        element = info.find(f'{{{NS}}}{name}')
        (element if element is not None else ET.SubElement(info, f'{{{NS}}}{name}')).text = text
    arguments = task.find(f'{{{NS}}}Actions/{{{NS}}}Exec/{{{NS}}}Arguments')
    replaced, count = re.subn(r"-WorkingDirectory '[^']*'", lambda _: f"-WorkingDirectory (Get-Content -LiteralPath '{CWD_FILE}' -Raw).Trim()", arguments.text)
    if count != 1:
        raise RuntimeError(f'unexpected autostart arguments in {INSTALLED_TASK}: {arguments.text}')
    arguments.text = replaced
    return ET.tostring(task, encoding='unicode')


def main(command):
    if command not in ('install', 'uninstall'):
        raise SystemExit(__doc__)
    if not ctypes.windll.shell32.IsUserAnAdmin():
        script = f"Start-Process -Verb RunAs -Wait -FilePath '{sys.executable}' -ArgumentList '\"{Path(__file__)}\"','{command}'"
        subprocess.run(['powershell.exe', '-NoProfile', '-Command', script], check=True)
    elif command == 'install':
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'task.xml'
            path.write_text(bench_task_xml(), encoding='utf-16')
            subprocess.run(['schtasks', '/create', '/tn', BENCH_TASK, '/xml', str(path), '/f'], check=True)
    else:
        subprocess.run(['schtasks', '/delete', '/tn', BENCH_TASK, '/f'], check=True)
    state = installed()
    print(f'{BENCH_TASK} installed: {state}')
    if state != (command == 'install'):
        raise SystemExit(1)


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else '')
