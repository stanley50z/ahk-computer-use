# ACU on Cua Driver Bench

These scripts run [Cua Driver Bench](https://github.com/trycua/cua/tree/main/libs/cua-driver-bench), Cua's benchmark of computer-use drivers, with ACU as the driver. They use the bench's Windows launcher (`launch/windows_session.py`) unchanged. The bench gives the agent no shell, file or read tools, only its driver's MCP server. ACU needs a shell, so `acu_mcp.py` stands in for it. Everything here is ordinary bench tooling: nothing in `acu/` changes, and the agent's guidance is the ACU skill as written.

| File | What it does |
| --- | --- |
| `acu_mcp.py` | Stdio MCP server with one tool, `run`. It writes script text to `acu-scripts/NNN.ahk` and runs it with `acu run`, or runs a bundled or existing file by name. It returns `acu run`'s JSON with saved screenshots attached as images. Its instructions are a short note mapping the skill's shell calls onto the tool, plus a pointer to the `acu` skill. |
| `agent.py` | The trial's agent: `claude -p` with that server and the `acu` project skill (`acu/SKILL.md` unmodified after the same note), the Skill tool as its only built-in, an empty snippet store, and the bench's system prompt with "a Windows desktop". The Windows counterpart of the bench's `launch/xfce/agent.sh`. |
| `session.py` | Runs `windows_session.py` with its four fixed screen positions moved onto another display, and with the launcher per-monitor DPI aware. |
| `display.py` | Shows, switches and restores a display's resolution and scaling. |
| `run.py` | The trial loop: every BenchLab task in its manifest conditions, run indexes 0 to 4. It resumes, and retries harness errors with the same seed. |
| `score.py` | Full-pass counts with Wilson intervals, per condition and task. It also runs the AutoHotkey GUI-only scan described below. |

## Setup

1. Check out [trycua/cua](https://github.com/trycua/cua). The bench lives at `libs/cua-driver-bench/automated-eval/macos_bench`.
2. Give the bench a Python 3.12 that is a full interpreter, not a venv. The launcher copies `pythonw.exe` as `BenchLab.exe` and `BenchSentinel.exe`, and a venv's launcher hands the window to a child process. Copy a standalone build, for example `uv python install 3.12`, then `cp -r` its folder. Then run `uv pip install --python <copy>\python.exe wxPython pywinauto pytest`.
3. Install `acu` (see the repository README) and Claude Code, logged in.
4. The bench assumes a 1920 x 1080 display at 100%. If no display runs that way, switch one for the run. Use PowerShell, since Git Bash rewrites `\\.\` paths:

   ```powershell
   python display.py show
   python display.py set '\\.\DISPLAY2' 1920 1080 --scale 100 --save C:\cdb\display-state.json
   # ... the run ...
   python display.py restore C:\cdb\display-state.json
   ```

5. Validate the machine before spending model calls. The bench's scripted oracle must pass every task through `session.py` (the bench's `tests/test_windows_desktop.py` does the same for the primary display). A do-nothing background trial must keep all eight undisturbed criteria.

## Run

```powershell
python run.py --bench "<cua>\libs\cua-driver-bench\automated-eval\macos_bench" `
  --python C:\cdb\python\python.exe --out C:\cdb\results\acu-sonnet-5-5 `
  --display '\\.\DISPLAY2' --tool-exe "Cua Spaces.exe"
python score.py C:\cdb\results\acu-sonnet-5-5 --json C:\cdb\results\acu-sonnet-5-5\scores.json
```

The default plan is the seven BenchLab tasks: 35 foreground and 25 background trials. Nobody may use the mouse or keyboard during the run. The sentinel counts real input as a disturbance, and pointer input from ACU lands wherever the user's windows are. Create `<out>\STOP` to stop after the current trial.

`--tool-exe` exempts shells started by named background programs from the GUI-only guard. The guard counts any new PowerShell or cmd in the desktop session outside the trial's own process tree, so a program on the machine that polls through PowerShell fails every trial. Name only programs unrelated to the agent, and record them with the results. Never name AutoHotkey or `acu`.

## Logs and evidence

Each trial directory, `<out>\<condition>\<task>-r<index>\`, holds these files:

| File | Contents |
| --- | --- |
| `row.json` | The bench's verdict: checker, GUI-only, the eight undisturbed criteria |
| `agent-transcript.jsonl` | The agent's stream-json |
| `agent-stderr.log` | Claude Code's stderr |
| `brief.md` | The task brief |
| `sentinel.jsonl` | The sentinel's log |
| `events.jsonl`, `state.json` | BenchLab's event log and final state |
| `work\acu-mcp.log` | Every MCP request and any adapter crash traceback |
| `work\acu-scripts\` | Every script the agent ran |

The loop's progress is in `<out>\run.log`. ACU's own run log and crash reports are in `%LOCALAPPDATA%\ACU\logs\` and `%LOCALAPPDATA%\ACU\crashes\`.

## Scoring notes

- **The skill goes in as a skill, not as server instructions.** Claude Code cuts long MCP server instructions short: with the whole skill there, the agent saw nothing after "Reuse snippets". The bench's Cua Driver arm gets its skill the same way, through the Skill tool, which the GUI-only rules allow.

- **The bench's guard doesn't know AutoHotkey.** It scans tool inputs for shell, Node and Python patterns only, and it ignores processes under the trial, which includes anything AutoHotkey starts. `score.py` therefore fails a trial whose scripts use AutoHotkey's process, file or registry commands, or `WScript.Shell`, `Shell.Application`, or `CreateProcess`-style `DllCall`s, and lists the evidence. `FileAppend ..., "*"` (printing to stdout) is allowed.
- **The multi-app tasks are not in the default plan.** CDB-G02 and G03 need LibreOffice and GnuCash. CDB-G04's cleanup kills `chrome.exe` by name in the desktop session, which closes the user's own Chrome. Run them only on a machine dedicated to the bench, with `--tasks`.
