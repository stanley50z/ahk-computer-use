# Computer-use landscape for ACU

## Comparison

Surveyed on 2026-10-08 with Ketch search, scrape, and code. No repositories were cloned and no desktop actions were executed. Every scrape used `--trim` and a 6,000 or 8,000 character cap. Source code takes precedence over README promises. “Not verified” means this survey did not establish the claim, not that the feature is absent.

Size is approximate engineering scope, supplemented by visible file sizes or commit counts. Commit counts are history size, not lines of code or evidence of reliability. Repository byte sizes and complete LOC counts were not obtainable within this bounded, no-clone survey. Sources in each row support that row; the notes give narrower evidence and caveats.

| Project | Platforms and perception | Execution and action vocabulary | Agent integration | Safety, recovery, and takeover | Approximate scope and license |
|---|---|---|---|---|---|
| Anthropic computer use | Client-provided desktop; screenshot perception. Reference executor is Linux/X11. | 17 current members: mouse, keyboard, scroll, screenshot, zoom, wait. Reference uses xdotool. | Messages API client toolset; older dated `computer_*` tools remain documented. | Isolation and consent recommended; approval callback in SDK; per-call errors and ordered batches. | API plus a Python reference executor. Demo MIT; hosted service is separate. [Spec][anthropic] [Executor][anthropic-code] [License][anthropic-license] |
| OpenAI computer use / CUA | Client-provided browser or desktop; screenshots. | Nine structured action types; client chooses Playwright, PyAutoGUI, or another executor. | Responses API `computer`; generated-code function tools also documented. | Client enforces permissions and limits; pending safety checks in response schema. | API contract plus sample runtime, not an OS driver. Service licensing is separate from SDK code. [Guide][openai] [Schema][openai-actions] |
| Microsoft UFO / UFO2 | Windows; screenshot plus UI Automation. | pywinauto controls, Win32, WinCOM, and PyAutoGUI coordinate fallback. Click, type, drag, app-specific APIs. | Python agent framework and CLI; current repository also contains UFO3 orchestration and MCP integration. | Input fallback and error traces; controller explicitly disables PyAutoGUI failsafe. | Large framework, about 1,930 commits; MIT. [Repo][ufo] [Controller][ufo-controller] |
| Microsoft OmniParser / OmniTool | Screenshot parser; OmniTool targets a Windows 11 VM. | Detection, OCR, icon descriptions, bounding regions. Parser itself does not inject input. | Python, notebook, Gradio; separate OmniTool agent/VM integration. | VM separation in OmniTool. Parser has no cancellation or takeover responsibility. | Model stack plus demo, about 156 commits. Root CC-BY-4.0; detector and caption weight terms differ. [Repo][omni] |
| mediar-ai/terminator | Windows only in current README; accessibility tree, screenshots, browser DOM. | Rust Windows UIA and `SendInput`; element locators, click/type, apps, windows, workflows. | Rust, TypeScript, partial Python SDK, CLI, MCP. | Advertises background operation and AI recovery. Coordinate click source still moves the shared pointer. | Large multi-package project, about 2,941 commits; MIT. [Repo][terminator] [Input][terminator-input] |
| CursorTouch/Windows-Use | Windows; UIA, optional vision. Requested URL redirects to Jeomon. | Click, type, scroll, drag, shortcuts, windows, PowerShell, files, virtual desktops. | Python agent SDK and CLI; built using Windows-MCP. | CLI step limit, default 200. Exact user takeover behavior at this layer not verified. | Smaller agent package, about 62 commits; MIT. [Repo][windows-use] |
| CursorTouch/Windows-MCP | Windows; UIA, optional screenshots, browser accessibility extraction. | Native UIA bindings include `SendInput`; screenshot, snapshot, click, keyboard and system tools. | MCP stdio, SSE, Streamable HTTP, CLI. | Physical-input hooks, takeover chord, fail-open behavior, HTTP auth and tool filtering. | Substantial Windows server, about 762 commits; MIT. [Repo][windows-mcp] [Hooks][windows-hooks] [Bindings][windows-core] |
| simular-ai/Agent-S | Windows, macOS, Linux; current S3 uses screenshots, visual grounding and OCR. | Generated Python/PyAutoGUI; click/type/scroll and other agent actions. | Python `gui-agents` SDK and `agent_s` CLI. | README warns that generated Python runs on the computer; single-monitor restriction. Dedicated takeover not verified. | Research framework, about 357 commits; Apache-2.0. [Repo][agent-s] [Grounding][agent-s-grounding] |
| OpenInterpreter OS mode | Historical Python computer API; screenshots and text/icon matching. macOS-specific integrations also exist. | Generated Python, `computer.mouse`, keyboard, display, clipboard; PyAutoGUI underneath mouse operations. | Python and CLI. Current official main is a different Rust project. | Historical OS profile sets `auto_run=True`; no per-block approval guarantee. | Multi-module interpreter, not a small driver. Python continuation AGPL-3.0; new official main Apache-2.0. [Current][oi-current] [Profile][oi-profile] [Mouse][oi-mouse] [Python license][oi-license] |
| Self-Operating Computer | Windows, macOS, Linux/X11; screenshots, optional OCR and set-of-mark. | PyAutoGUI `write`, key down/up, move/click. | Python package and `operate` CLI. | Executor catches and prints exceptions. A dedicated takeover protocol was not verified. | Smaller agent application, about 645 commits; MIT. [Repo][soc] [Executor][soc-input] |
| bytebot | Containerized Ubuntu/XFCE desktop; screenshots. | nut.js wrapper; move, trace, click, press, drag, scroll, keys, text, paste, screenshot, wait, files/apps. | REST desktop/task APIs, web UI; MCP dependency also present. | Separate desktop and explicit takeover mode. | Multi-service TypeScript application, about 499 commits; root Apache-2.0. Package-level licensing caveat below. [Repo][bytebot] [Executor][bytebot-input] [Package][bytebot-package] |
| PyAutoGUI | Windows, macOS, Linux; screenshots and image matching, not an accessibility tree. | Windows cursor move uses `SetCursorPos`; click uses separate `mouse_event`. | Python library. | Corner failsafe and inter-call pause; not a transactional click guarantee. | Library with OS-specific backends; Windows backend declares BSD. [Docs][py-docs] [Windows source][py-win] |
| xdotool | X11 desktops; no screenshot or accessibility perception of its own. | XTEST/Xlib; move, click, key, type, window operations. | CLI and libxdo. | `--sync` waits for movement, not exclusive pointer ownership. | C utility/library; `xdo.c` about 2,243 lines; BSD-3-Clause. [Manual][xdo-man] [Source][xdo] [License][xdo-license] |
| spyoungtech/ahk-mcp | Windows; window/control metadata, screenshots and EasyOCR. | 33 advertised tools through Python AHK; source selects AHK v1. | FastMCP. | Daemon cleanup on shutdown; dedicated emergency stop not verified. | One main file, 380 lines; 5 commits. No clear project license found. [Repo][spyoung] [Source][spyoung-code] |
| Xeo786/AutohotkeyV2_MCPServer | Windows; active-window inspection, script/debugger state. | Validate/run AHK v2, search libraries, history, DBGp debugging. | Python MCP server. | Execution timeout, stdout/error capture, debugger break/step; not a screenshot-driven controller. | `server.py` 719 lines plus debugger/config/UI; 23 commits; GPL-3.0. [Repo][xeo] [Source][xeo-code] |
| TrueCrimeDev/ahk-mcp | Windows execution; read-only UIA inspection plus development context. | AHK v2 run/eval/validate, file tools, language-server navigation, debugger. | TypeScript MCP, stdio and Streamable HTTP. | Allowed directories, symlink restrictions, process tracking, read-only UIA toolset. | Development-tool suite, 180 commits; README says MIT, but linked LICENSE was not retrievable. [Repo][truecrime] |
| wizd/ahk-mcp | AHK authoring context; no desktop vision pipeline established. | Completion, diagnostics, analysis, prompts and resources. | TypeScript MCP. | Primarily authoring support; execution safety not established. | Older related code line, 7 commits, includes `node_modules`; license grant not verified. [Repo][wizd] [History][wizd-history] |
| sandraschi/autohotkey-mcp | Windows script execution; script metadata, source and running-process state. | List/run/stop/promote scriptlets, generate drafts, macros. | FastMCP stdio/HTTP, FastAPI and web UI; optional HTTP bridge. | Stop by script/PID, draft staging, visible activity HUD with e-stop. | Python service plus React UI, 54 commits; MIT. [Repo][sandra] |
| sandraschi/autohotkey-tools | Windows; scriptlet depot rather than a perception service. | AHK v2 utilities, recorder/replay, bridge list/run/stop. | Local HTTP bridge and dashboard; consumed by sibling MCP server. | Review-before-execution notice; promotion checks in sibling server. | README reports 64 utilities; 99 commits; MIT. [Repo][sandra-tools] [License][sandra-tools-license] |
| claude-did-this/MCPControl | Windows; screenshots and window metadata. | Mouse, keyboard, windows, clipboard; keysender default, optional AHK v2 and PowerShell providers. | TypeScript MCP, documented SSE/HTTPS and CLI. | Recommends VM and controlled environment; explicit dangerous-software warning. | Multi-provider server, 333 commits; MIT. [Repo][mcpcontrol] |

## Per-project notes

### Anthropic computer use

#### Current contract and dated contracts

Do not treat `computer_20241022` as the current specification. The official page now leads with `computer_toolset_20260801`. It exposes 17 member tools rather than one `computer` call containing an `action` discriminator. Calls carry `toolset_name: "computer"`; results must echo that field. The page still documents `computer_20251124` and `computer_20250124` as legacy model-specific tools. [Official specification][anthropic]

The current definition is `{"type":"computer_toolset_20260801"}`. Optional `configs` entries are keyed by member name and support `enabled` and `defer_loading`. All members, including zoom, default to enabled. The table also lists `cache_control` and `allowed_callers`, with only `["direct"]` accepted for this toolset. No beta header is required for the current toolset. [Official specification][anthropic]

The exact current member names and inputs are below. All coordinates are in the screenshot coordinate system. `coordinate` means `[x,y]`; `region` means `[x0,y0,x1,y1]`. [Official specification][anthropic]

| Member | Required inputs | Optional inputs and semantics |
|---|---|---|
| `screenshot` | None | `{}`; returns a full-display image. |
| `zoom` | `region` | Full-resolution crop fitted into the usual screenshot dimensions, preserving aspect ratio. |
| `left_click` | None | `coordinate`; `text` for held modifiers. Omitted coordinate means current cursor. |
| `right_click` | None | Same as `left_click`. |
| `middle_click` | None | Same as `left_click`. |
| `double_click` | None | Same as `left_click`. |
| `triple_click` | None | Same as `left_click`. |
| `left_click_drag` | `start_coordinate`, `coordinate` | `text` for held modifiers. |
| `mouse_move` | `coordinate` | Move without clicking. |
| `left_mouse_down` | None | Press at current cursor. |
| `left_mouse_up` | None | Release at current cursor. |
| `cursor_position` | None | Returns current coordinates as text. |
| `scroll` | `scroll_direction`, `scroll_amount` | Direction is `up`, `down`, `left`, or `right`. Amount is wheel clicks. Optional `coordinate` and modifier `text`. |
| `type` | `text` | Literal text at current keyboard focus. |
| `key` | `text` | Key or `+`-joined chord. Optional `repeat`, 1 through 100, default 1. |
| `hold_key` | `text`, `duration` | Duration in seconds, up to 300. |
| `wait` | `duration` | Seconds, up to 300. |

Table source: [Anthropic member input table][anthropic]. Modifier names are `shift`, `ctrl`, `alt`, `super`, or combinations such as `ctrl+shift`. They are not AHK's modifier syntax. [Specification][anthropic]

For the specifically requested dated `computer_*` format, `computer_20251124` requires `type`, `name: "computer"`, `display_width_px`, and `display_height_px`. Optional fields in the SDK include `display_number`, `enable_zoom`, `cache_control`, `defer_loading`, `allowed_callers`, `input_examples`, and `strict`. Its documented beta header is `computer-use-2025-11-24`. [SDK definition][anthropic-param] [Version table][anthropic]

The reference executor defines these dated action sets:

- `computer_20241022`: `key`, `type`, `mouse_move`, `left_click`, `left_click_drag`, `right_click`, `middle_click`, `double_click`, `screenshot`, `cursor_position`.
- `computer_20250124`: the previous ten plus `left_mouse_down`, `left_mouse_up`, `scroll`, `hold_key`, `wait`, `triple_click`.
- `computer_20251124`: the previous sixteen plus `zoom`. [Source action unions][anthropic-code]

There is a version-sensitive parameter trap. The dated reference handler accepts `action`, `text`, `coordinate`, `start_coordinate`, `scroll_direction`, `scroll_amount`, `duration`, `key`, and, for the 20251124 handler, `region`. Its click handler rejects `text` and uses `key` for held modifiers. The current toolset documentation instead specifies modifier `text`. The dated handler also rejects durations above 100 seconds, whereas the current toolset table says 300. Do not copy the old handler signature as the current public contract. [Reference handlers][anthropic-code] [Current inputs][anthropic]

#### Linux execution

The demo constructs `DISPLAY=:N xdotool` commands. Pointer motion uses `mousemove --sync x y`. Dragging chains move, `mousedown 1`, another move, and `mouseup 1`. Clicks use buttons 1, 2, and 3. Double/triple clicks use `--repeat` and a 10 ms inter-click delay. Scrolling maps directions to buttons 4 through 7. Typing is chunked into 50-character groups with a 12 ms typing delay. [Executor][anthropic-code]

Screenshots use `gnome-screenshot`, falling back to `scrot`; ImageMagick resizes or crops them. Ordinary shell actions wait two seconds before the follow-up screenshot. The executor returns command output, errors, and an image. That is an implementation choice, not a model/API requirement. [Executor][anthropic-code]

The API does not operate the machine itself. The application executes calls, in order, and supplies results. Anthropic recommends isolation, protection of sensitive data, user consent, and precautions against screenshot/webpage prompt injection. The current page also describes SDK approval callbacks. These are not an OS-level emergency stop. [Guide][anthropic]

### OpenAI computer use / CUA

The current guide documents both generated-code execution and the structured `computer` tool. It recommends code execution for the model identified on that page. A structured `computer_call` now supports an ordered `actions` array; the Python response type also retains a legacy optional singular `action`. The developer still owns the desktop runtime. [Guide][openai] [Response type][openai-call]

The complete action union in the current Python SDK is:

| `type` | Parameters |
|---|---|
| `click` | Required `x`, `y`, `button`. Button is `left`, `right`, `wheel`, `back`, or `forward`. Optional held `keys`. |
| `double_click` | Required `x`, `y`; optional held `keys`. No button field in this schema. |
| `drag` | Required `path`, an array of `{x,y}` objects; optional held `keys`. |
| `keypress` | Required `keys`, an array of key names. |
| `move` | Required `x`, `y`; optional held `keys`. |
| `screenshot` | No other fields. |
| `scroll` | Required `x`, `y`, `scroll_x`, `scroll_y`; optional held `keys`. |
| `type` | Required `text`. |
| `wait` | No duration field in this schema. |

Table source: [Generated SDK action schema][openai-actions]. Do not silently map Anthropic wheel-click amounts onto OpenAI's scroll distances, or invent an OpenAI `wait.duration` field. [OpenAI schema][openai-actions] [Anthropic inputs][anthropic]

`pending_safety_checks` contain an ID and optional code/message. The guide requires the client runtime to apply permission rules and execution limits, preserve the environment between calls, and return current screenshots. Those controls are separate from how Windows input is injected. [Response type][openai-call] [Guide][openai]

### Microsoft UFO / UFO2

UFO2 combines screenshots and UIA control detection. It uses a HostAgent/AppAgent structure and supports both GUI actions and application APIs. The same repository now leads with UFO3, which adds multi-device orchestration. Do not attribute all current UFO3 machinery to the original Windows agent. [Repository comparison and feature tables][ufo]

The controller imports pywinauto and `UIAWrapper`. It selects `click` or `click_input` from configuration. Coordinate clicks use `pyautogui.click`; dragging uses `moveTo` and `dragTo`. Text entry first tries control methods, then keyboard input, then a PyAutoGUI fallback. This is not a single universal Windows injection mechanism. [Controller source][ufo-controller]

Verified actions include `click_input`, `click_on_coordinates`, `drag_on_coordinates`, `set_edit_text`, and `keyboard_input`. The framework also exposes app APIs through its broader automation system. At the OS level, UIA/COM is verified; PyAutoGUI's Windows path is traced below. The exact lower-level pywinauto API for every control type was not traced here. [Controller][ufo-controller] [Framework][ufo]

Recovery is concrete in the text-entry fallback and exception trace capture. A caution for ACU: this controller sets `pyautogui.FAILSAFE = False`. Its `click_input` wrapper can also return an “executed” message after delegating to a helper that catches exceptions. I would not copy that success-reporting pattern. A separate global cancellation mechanism was not verified in the inspected code. [Controller][ufo-controller]

### Microsoft OmniParser and OmniTool

OmniParser converts screenshots into structured elements. It uses an interactive-region detector and an icon-caption model. The README separately introduces OmniTool, which controls a Windows 11 VM with a selected vision model. Perception and desktop execution are distinct components. [Repository][omni]

The parser's output is grounding information, not a click command. Its Python/notebook/Gradio interfaces are useful for experiments, but it brings model weights and inference dependencies. For ACU, I would keep this optional rather than require a local parser to take a screenshot. [Installation and examples][omni]

Licensing needs component-level review. GitHub identifies the root license as CC-BY-4.0. The current README says the newer YOLOv9-E detector is based on an MIT implementation, earlier Ultralytics detector weights retain AGPL terms, and caption models use MIT. Do not summarize the whole stack as MIT. [License and model-weight sections][omni]

The attempted OmniTool executor URL returned 404. This survey therefore does not claim a verified Win32 input API or cancellation protocol for OmniTool. Its documented VM architecture remains a useful isolation pattern. [Attempted executor](https://raw.githubusercontent.com/microsoft/OmniParser/master/omnitool/omnibox/api.py) [VM description][omni]

### mediar-ai/terminator

Current support is Windows only. The README lists Rust and TypeScript APIs, CLI, MCP, workflow recording, screenshots, UIA locators and browser integration; Python support is partial. It describes deterministic workflows with AI recovery. [Repository][terminator]

The important source-level correction is that “doesn't take over your cursor or keyboard” is not a universal property of the coordinate-click implementation. `send_mouse_click` saves the pointer optionally, builds move/down/up `INPUT` records, then calls `SendInput` three times, each with a one-element array. A double-click adds two more calls after a 50 ms sleep. Optional restoration uses `SetCursorPos`. [Input source][terminator-input]

That is not one non-interleaved move-and-click batch. The code also supports focus/caret restoration through UIA, but restoring state afterward is not the same as never disturbing it. Treat background operation as operation-dependent. I did not verify a global emergency-stop contract. [Input source][terminator-input] [README claim][terminator]

### CursorTouch/Windows-Use and Windows-MCP

Windows-Use is the agent; Windows-MCP is the tool server it builds on. The requested Windows-Use URL redirects to Jeomon/Windows-Use. Its README documents UIA perception without a vision requirement, optional screenshots, multiple model providers, Python sync/async entry points, and a CLI with a configurable step limit. [Windows-Use][windows-use] [Windows-MCP][windows-mcp]

Windows-MCP supports both UI state and screenshots. Its browser mode filters accessibility content and includes an IAccessible2 fallback for Firefox. Screenshot backends are documented as `dxcam`, `mss`, and Pillow, with configurable scaling. Its native UIA module contains `SendInput` bindings. This evidence does not establish that every mouse action uses one combined input batch. [README tables][windows-mcp] [Native module][windows-core]

Its input-ownership source is worth reading. Physical mouse and keyboard hooks ignore injected-event flags. Physical movement can block new agent input. A takeover chord uses Ctrl+Alt+Shift+Backspace. The hooks release suppression before notifying the coordinator and fail open on exceptions or expired deadlines. The desktop-health code rejects a non-default input desktop or inactive session, relevant to lock screens and UAC. [Hooks][windows-hooks] [Win32 coordinator bindings][windows-control]

The server documents bearer authentication, IP allowlists, CORS, TLS, tool allowlists/exclusions, and persistent server/error log paths. Those are network/runtime controls, not proof that arbitrary exposed PowerShell or registry actions are safe. Its screenshot scaling and explicit physical-input distinction are more relevant to ACU than its full tool catalog. [Configuration tables][windows-mcp]

### simular-ai/Agent-S

The current repository describes S3, with Windows, macOS and Linux support. It requires a grounding model in addition to the main reasoning model and warns that the agent executes Python on the user's machine. It also states a single-monitor assumption. [README][agent-s]

The S3 grounding source uses the screenshot to ask a visual model for coordinates and uses Tesseract for word-level text boxes. The repository's OSWorld integration demonstrates generated PyAutoGUI commands. This survey verified the current screenshot/OCR route, not a universal accessibility-tree requirement across all Agent-S generations. [Grounding][agent-s-grounding] [Integration example](https://github.com/simular-ai/Agent-S/blob/3aa272d23d2994c7bbde1acbbe0ef8e8d06b8693/osworld_setup/s2/OSWorld.md)

The agent framework includes more planning and model infrastructure than ACU needs. A dedicated physical-input takeover policy was not established from these sources. PyAutoGUI on Windows has the input behavior analyzed below; the presence of an agent planner does not change that backend guarantee. [README][agent-s] [Windows backend][py-win]

### OpenInterpreter OS mode

The project name now points at a different implementation. Official main describes a Rust coding agent based on Codex and directs readers seeking the original Python project to `endolith/open-interpreter`. The current project's QA skill uses browser/native tools; that is not the old `--os` implementation. [Current README][oi-current]

For historical OS mode, the Python profile enables vision, imports the computer API, loops, and sets `auto_run=True`. It exposes display viewing, text/icon-based mouse targeting, keyboard writing/hotkeys, clipboard reading and selected-text access. Some integrations are explicitly macOS-only. [OS profile][oi-profile]

The mouse implementation uses PyAutoGUI and resolves text/icon references through screenshot search. Ambiguous matches produce an annotated image and an error asking for disambiguation. This is a useful recovery pattern. The broad permission language and automatic execution in the profile are not suitable defaults for a minimal tool. A reliable global user-takeover path was not verified. [Mouse source][oi-mouse] [Profile][oi-profile]

The legacy documentation page did not yield usable content through the bounded scrape. The Python continuation source was used instead. Its license is AGPL-3.0; current official Rust main says Apache-2.0. Its current official commit count includes the new codebase and is not a meaningful estimate of historical OS-mode size. [Attempted OS docs](https://docs.openinterpreter.com/guides/os-mode) [Python license][oi-license] [Current repository][oi-current]

### Self-Operating Computer

The project supports macOS, Windows and Linux with an X server. It offers screenshot-based control, OCR coordinate lookup and set-of-mark experiments through the `operate` CLI. Some README model/provider guidance is visibly historical, so I would use source rather than its setup prose to assess execution behavior. [README][soc]

The small executor exposes `write`, `press`, and `mouse`. `write` sends characters through PyAutoGUI. `press` sends key-down events, waits, then sends key-up events. The click routine moves toward a percentage-derived coordinate, draws a circular pointer motion, then calls `pyautogui.click`. Exceptions are caught and printed. [Executor][soc-input]

I would not copy decorative pointer motion or error handling that hides failure from the caller. The inspected executor has no `finally` block around held-key release. That creates an obvious cleanup review point, not proof that a stuck key occurred in a test. No separate takeover protocol was verified. [Executor][soc-input]

### bytebot

Bytebot gives the agent a separate Ubuntu/XFCE desktop. The repository includes a desktop daemon, agent service, task web UI and APIs. It explicitly documents takeover mode and persistence of the desktop environment. This separation avoids sharing the human's local pointer during normal operation. [README][bytebot]

The desktop service dispatches `move_mouse`, `trace_mouse`, `click_mouse`, `press_mouse`, `drag_mouse`, `scroll`, `type_keys`, `press_keys`, `type_text`, `paste_text`, `wait`, `screenshot`, `cursor_position`, `application`, `write_file`, and `read_file`. It delegates mouse/keyboard work to `NutService`; the daemon depends on `@nut-tree-fork/nut-js`. The ultimate native X11 injection call was not established in this survey. [Service][bytebot-input] [Dependencies][bytebot-package]

`click_mouse` awaits pointer movement before invoking the click operation. Drag and modifier-key sequences similarly consist of separate awaited calls. The inspected sequences do not use `finally` for release cleanup. Container separation is its strongest directly documented answer to user interference; it is not evidence of input atomicity. [Service][bytebot-input] [Takeover description][bytebot]

The root license is Apache-2.0, but `packages/bytebotd/package.json` says `UNLICENSED`. Treat that as a packaging/license consistency question to resolve before copying daemon code, not as a reason to silently discard the root license. [Root license](https://github.com/bytebot-ai/bytebot/blob/main/LICENSE) [Package manifest][bytebot-package]

### PyAutoGUI on Windows: the click race

**Answer: `click(x,y)` moves the pointer with `SetCursorPos`, then injects the click separately with `mouse_event`. It does not submit a single `SendInput` array containing move, down, and up.** This conclusion is pinned to commit `b4255d0be42c377154c7d92337d7f8515fc63234`. [Public click path][py-click] [Windows implementation][py-win]

The source path is:

1. Public `click()` normalizes the arguments, calls `_mouseMoveDrag("move", x, y, ...)`, then enters the click loop and calls the platform backend. See [`__init__.py`, lines 980-1040][py-click].
2. Windows `_moveTo()` calls `ctypes.windll.user32.SetCursorPos(x,y)`. See [`_pyautogui_win.py`, lines 350-375][py-move].
3. Windows `_click()` chooses `MOUSEEVENTF_LEFTCLICK`, `MOUSEEVENTF_MIDDLECLICK`, or `MOUSEEVENTF_RIGHTCLICK`, then calls `_sendMouseEvent`. See [`_pyautogui_win.py`, lines 430-458][py-button].
4. Those click constants contain button-down plus button-up flags, not `MOUSEEVENTF_MOVE`. `_sendMouseEvent` computes coordinate values but calls `mouse_event(ev, ...)` with the button-only flags. The `SendInput` attempt immediately above is commented out. See [constants, lines 33-55][py-flags] and [helper, lines 465-505][py-event].

Passing coordinate arguments to `mouse_event` does not rescue the click. Microsoft's documentation says the position fields describe movement when `MOUSEEVENTF_MOVE` is set. Here it is not set. The click therefore uses the cursor position at injection time. A physical mouse move between `SetCursorPos` and `mouse_event` can redirect it. This is a source/API inference, not a measured race frequency. [Microsoft `mouse_event` documentation][mouse-event] [PyAutoGUI flags][py-flags] [Helper][py-event]

PyAutoGUI documents a corner failsafe and a default pause after calls. These are useful escape mechanisms, not mutual exclusion against concurrent user movement. The library itself recommends leaving the failsafe enabled. [Documentation][py-docs]

For comparison, Microsoft says events in a single `SendInput` call are inserted serially without interspersed user input or other injected input. That guarantee is about one array in one call. It does not apply across three separate `SendInput` calls, and it does not prove the UI remained unchanged since the screenshot. `SendInput` is also subject to UIPI and cannot freely inject into higher-integrity applications. [Microsoft `SendInput` documentation][sendinput]

### xdotool click semantics

`xdotool click 1` does not mean “click at this coordinate.” It sends button-down then button-up at the current pointer position. The manual describes a short delay, currently 12 ms for the documented version. `mousemove x y click 1` chains a movement command and a click command, even when issued in one CLI invocation. [Manual, mouse commands][xdo-man]

The project uses XTEST and Xlib. The source contains `XTestFakeButtonEvent` for the untargeted button path. The manual also distinguishes targeted-window `XSendEvent` behavior and its application-compatibility caveats. These paths should not be conflated with native hardware input. [Source][xdo] [Manual][xdo-man]

`mousemove --sync` waits until movement occurs, not necessarily until the intended destination is reached. It does not lock the pointer. Thus the Anthropic command chain is still move followed by button events, not an exclusive transaction. I would expect concurrent physical motion to be able to interfere, but this survey did not run an X11 race test. [Manual][xdo-man] [Anthropic executor][anthropic-code]

### Existing AutoHotkey efforts

The search covered “AutoHotkey MCP server”, “ahk mcp”, “AutoHotkey computer use agent”, “autohotkey claude code computer use”, and “AutoHotkey v2 MCP”, including combined and broader variants. The useful primary-source findings fall into three groups: direct desktop tools, AHK development/debugging tools, and scriptlet lifecycle managers. The projects below establish prior art; they do not establish production reliability. [spyoungtech][spyoung] [TrueCrimeDev][truecrime] [sandraschi][sandra] [MCPControl][mcpcontrol]

#### spyoungtech/ahk-mcp

This is the closest small direct-control prior art. It advertises 33 tools for windows, keyboard/mouse, control text, screenshots/OCR and monitor context. It uses FastMCP, the Python `ahk` package, `ahk-binary`, `mss`, EasyOCR and NumPy. The server's main file is 380 lines, 312 nonblank/noncomment lines as reported by GitHub, and 13.8 KB. [README][spyoung] [File metadata][spyoung-code]

Important correction: source initializes `AsyncAHK(version='v1')`. It is not an AHK v2 implementation. Its tools call AHK operations such as `control_send`, `mouse_move`, and `click`; the exact OS API depends on those AHK operations and send mode, which this survey did not trace through the dependency. [Source][spyoung-code]

Shutdown attempts to kill the daemon and stop hotkeys. The inspected code also defines `mouse_click_at_screen_coordinates` twice, with the second implementation using client coordinates. That is a concrete naming/registration hazard worth avoiding. No global cancellation contract was verified. [Source][spyoung-code]

Maintenance looks dormant in the retrieved main-branch history: 5 commits, latest 2025-05-21. No project license file or clear license grant was visible in the inspected repository. Do not infer permission from the license of its Python AHK dependency. [Repository][spyoung] [Commit feed][spyoung-history]

#### Xeo786/AutohotkeyV2_MCPServer

This is an AHK v2 development and debugging server. Tools validate syntax with `/Validate`, capture errors through `/ErrorStdOut`, execute temporary scripts with a timeout, inspect the active window, search a library, configure paths and restore past scripts. Its debugger supports attach/detach, break/continue/step, stack/variable inspection, evaluation and breakpoints. It is not documented as a complete screenshot perception loop. [README][xeo]

The action-history directory is `%AppData%\AutoHotkeyMCPServer\history\`. Script execution and debugger feedback are useful recovery facilities. A timeout or debugger break is not the same as a human-triggered global stop that remains available during a bad script. That latter guarantee was not verified. [README][xeo]

Size is modest: `server.py` has 719 lines, 619 LOC and 22.8 KB, plus a debugger client, config module, libraries, tests and an AHK history GUI. The repository has 23 commits; latest main-branch commit in the feed is 2026-03-30, with feature work concentrated in March. GitHub identifies GPL-3.0. [File][xeo-code] [Repository][xeo] [History][xeo-history]

#### TrueCrimeDev/ahk-mcp and the wizd copy

The old `012090120901209/ahk-mcp` URL resolves to TrueCrimeDev. Its current server is substantial AHK tooling, not merely a prompt collection. It lists 12 default core tools, optional debugger/library/UIA toolsets, process-tracked execution, a persistent language-server integration and MCP smoke tests. The six UIA tools inspect windows, trees, matches, elements, the item under the cursor and highlights. The README explicitly says they do not invoke control patterns. [README][truecrime]

Its distinctive feature is returning an AHK selector snippet that has been checked against the live UIA tree. It uses property paths rather than runtime IDs. For ACU, this is a better prior-art reference for selector discovery than a large screenshot/OCR dependency. That is my design judgment, not a measured accuracy comparison. [UIA description][truecrime]

File operations have allowed-directory and symlink checks. The server offers script execution, so those file-tool checks should not be mistaken for a sandbox around arbitrary AHK code. The repository has 180 commits, and the feed shows work through 2026-10-06, including toolset changes, Windows CI and evaluation work. [README][truecrime] [History][truecrime-history]

License caveat: the README says MIT and links `LICENSE`, but the raw `master/LICENSE` URL returned 404 and GitHub did not show a root license in the retrieved listing. Record this as “MIT claimed, grant file unresolved” before copying. [README][truecrime] [Attempted license](https://raw.githubusercontent.com/TrueCrimeDev/ahk-mcp/master/LICENSE)

`wizd/ahk-mcp` carries the older authoring-focused code and README with TrueCrimeAudit links. Its history lists seven TrueCrimeDev-authored commits ending 2025-07-07. It includes committed `node_modules` and `dist`, making repository disk size a poor measure of authored code. I would not count it as a separate mature desktop-control system. A license grant was not verified in the retrieved README/package material. [Repository][wizd] [History][wizd-history]

#### sandraschi/autohotkey-mcp and autohotkey-tools

The MCP server manages a scriptlet depot. `scriptlet_ops` lists, runs, stops, reads and promotes scripts. `ahk_dev_ops` generates drafts and provides help. It also handles text-expansion macros. The current README says nine MCP tools after consolidation, with six of those being UI-card tools. Transport options include stdio and HTTP; the optional bridge provides list/run/stop over local HTTP. [README][sandra]

The useful safety ideas are concrete: generated scripts first go into `ai_generated`, promotion checks lint and hotkey conflicts, running scripts have identities/PIDs, and the UI has an activity HUD with an e-stop button. “Sandbox” in this README describes draft staging; it is not evidence of Windows security isolation for executed AHK. [README][sandra]

The server has 54 commits and a latest retrieved commit of 2026-10-02. September history includes fixes to a HUD crash and broken web UI, so there is recent maintenance but also evidence of operational defects. The server is MIT. [Repository][sandra] [History][sandra-history]

The sibling `autohotkey-tools` repository supplies the AHK v2 scriptlets and `ScriptletCOMBridge.ahk`. Its README reports 64 utilities, and GitHub shows 99 commits. The feed extends to 2026-09-30. Its MIT license includes an explicit notice to review scripts before execution. This is a related script-generation/execution ecosystem, not a separate general-purpose perception engine. [Repository][sandra-tools] [History][sandra-tools-history] [License][sandra-tools-license]

#### claude-did-this/MCPControl

This is direct Windows computer-use prior art with an optional AHK v2 provider. Its default is `keysender`; it also supports PowerShell. The documented `AUTOMATION_PROVIDER=autohotkey` setting selects AHK, and `AUTOHOTKEY_PATH` selects the executable. Its operations cover screenshots, mouse movement/click/drag/scroll, keyboard press/release and text, windows, and clipboard. The actual Win32 injection implementation of each provider was not traced. [README][mcpcontrol]

It recommends running in a VM, documents SSE and HTTPS, and warns that direct computer control is dangerous. A global emergency stop or robust user-input arbitration mechanism was not verified. It has a larger implementation footprint than a single AHK script: TypeScript source, tests, scripts and multiple providers, with 333 commits. [Repository][mcpcontrol]

The latest retrieved main-branch commit is 2025-07-19 and is a dependency update. The visible feed is dominated by dependency bumps; it does not establish current feature development. The repository identifies MIT. [History][mcpcontrol-history] [Repository][mcpcontrol]

#### Does serious AHK MCP prior art exist?

Yes, if “serious” means implemented tools, execution/debugging support, tests and ongoing engineering rather than a directory listing. TrueCrimeDev's server and sandraschi's manager meet that practical threshold in different categories. MCPControl also implements an AHK v2 provider. The smallest direct-control server found, spyoungtech's, uses AHK v1 and has a short, old history. None of these sources establishes a dominant, independently validated, minimal AHK v2 desktop driver with a proven takeover protocol. [TrueCrimeDev][truecrime] [sandraschi][sandra] [MCPControl][mcpcontrol] [spyoungtech source][spyoung-code] [History][spyoung-history]

### Retrieval limits and unresolved evidence

- GitHub repository API scrapes returned HTTP 415, including [spyoungtech metadata](https://api.github.com/repos/spyoungtech/ahk-mcp). Consequently, repository byte sizes were not reported.
- GitHub HTML commit pages returned HTTP 429, including [TrueCrimeDev history](https://github.com/TrueCrimeDev/ahk-mcp/commits/master/). Atom feeds supplied the maintenance dates instead. [Working feed][truecrime-history]
- The historical [OpenInterpreter OS docs](https://docs.openinterpreter.com/guides/os-mode) yielded a JS-rendering warning and no useful body. The wrong initial Python source path also returned 404; the corrected [mouse source][oi-mouse] was retrieved.
- The attempted [OmniTool executor](https://raw.githubusercontent.com/microsoft/OmniParser/master/omnitool/omnibox/api.py) and [TrueCrimeDev license](https://raw.githubusercontent.com/TrueCrimeDev/ahk-mcp/master/LICENSE) returned 404.
- Several large READMEs and source files were truncated at the required caps. CSS selectors and smaller raw files recovered the load-bearing sections. Unretrieved native backend details, full LOC counts, and untested cancellation claims remain explicitly unverified above.
- No project was installed or exercised. Source inspection can establish the sequence of API calls, but not race frequency, practical task success, or emergency-stop latency.

## Patterns worth copying or avoiding for a minimal AHK tool

The following are design recommendations, not claims that ACU already implements them.

### Copy a small execution contract, not an entire agent

Keep planning in the caller. Start with screenshot, execute a short AHK script, inspect the result, and cancel the current run. Add typed mouse/keyboard helpers only where they eliminate recurring mistakes. Both current vendor guides separate the agent from the client-owned executor, and OpenAI explicitly supports generated-code computer use. [Anthropic][anthropic] [OpenAI][openai]

If vendor compatibility matters, add adapters outside the AHK core. Anthropic uses modifier strings and wheel-click amounts; OpenAI uses key arrays and scroll distances. Keeping those schemas out of the core avoids version-specific behavior leaking into basic input operations. [Anthropic actions][anthropic] [OpenAI actions][openai-actions]

### Make human takeover a first-class contract

Prefer “physical human input pauses the agent” over silently fighting the user's mouse. Provide an independent emergency hotkey and visible running state. Cancel future actions before doing cleanup. Track which keys/buttons the run owns, and release those on timeout, exception or cancel. Windows-MCP's injected-event filtering and fail-open hooks are concrete references; sandraschi's visible e-stop is a useful presentation pattern. [Windows hooks][windows-hooks] [Win32 bindings][windows-control] [AHK manager][sandra]

Do not promise cancellation of arbitrary AHK by merely setting a flag inside the same busy script. Use a supervising process with a run ID, deadline and owned PID. Xeo's timeout and debugger facilities, and sandraschi's PID-scoped stop operations, show parts of this lifecycle without proving a complete safety boundary. [Xeo][xeo] [sandraschi][sandra]

### Specify input atomicity precisely

If ACU promises that one coordinate click cannot be redirected between its move and press, implement and test a single Win32 `SendInput` array containing absolute movement and button events. Check the returned inserted-event count. Do not infer this property just because a dependency calls `SendInput`. Terminator's three calls and PyAutoGUI's separate move/click are counterexamples. [Win32 guarantee][sendinput] [Terminator implementation][terminator-input] [PyAutoGUI implementation][py-win]

Keep this guarantee narrow. It does not prevent the target window moving before injection, solve stale screenshots, or bypass UIPI. It also does not replace a human takeover policy. Test AHK's chosen send mode and fallback behavior before claiming it has the same guarantee as a hand-built Win32 batch. [Win32 documentation][sendinput] [AHK send documentation](https://www.autohotkey.com/docs/v2/lib/Send.htm)

### Return evidence and explicit errors

Return a run ID, exit status, elapsed time, stdout/stderr, screenshot metadata and a follow-up image when useful. Distinguish “input accepted by Windows” from “task succeeded.” UFO's error traces are useful; unconditional success wording after a failed helper is not. OpenInterpreter's ambiguous-target errors are worth copying. [UFO controller][ufo-controller] [OpenInterpreter mouse][oi-mouse]

For ACU, I recommend persistent `%LOCALAPPDATA%\ACU\logs\acu.jsonl` and `%LOCALAPPDATA%\ACU\crashes\` paths, with stack traces or native dumps where available. Record script/run hashes rather than secret-bearing text by default. Keep screenshots and full scripts opt-in or retention-limited. This is a proposed diagnostic policy, not an existing project fact.

### Keep the screenshot coordinate system explicit

Return image dimensions, physical display bounds, scale and monitor origin with each screenshot. Do not allow a resized image to silently redefine coordinates. Keep zoom's coordinate semantics explicit too. Anthropic's reference handles screenshot scaling and documents that a zoom image does not become a new coordinate frame. [Reference executor][anthropic-code]

Test mixed DPI and negative virtual-desktop origins before advertising multi-monitor support. Do not copy Agent-S's single-monitor assumption into a general Windows tool without making the limitation visible. [Agent-S prerequisite][agent-s]

### Add accessibility inspection only when it pays for itself

A screenshot-and-script tool can remain small. Add an optional read-only UIA inspector for selectors, text and control identity when tasks need it. TrueCrimeDev's verified selector snippets are especially relevant. Keep inspection separate from action permissions, as that project does for its six UIA tools. [UIA tooling][truecrime]

Avoid requiring OCR, a detector model, a web dashboard, an LLM planner and MCP just to click or type. OmniParser, UFO and Bytebot solve broader problems. Their architectures are useful references, not an appropriate minimum dependency set for ACU. [OmniParser][omni] [UFO][ufo] [Bytebot][bytebot]

### Treat script execution as trusted code execution

AHK validation catches syntax/load errors, not malicious intent. A staged draft directory is not an OS sandbox. Do not expose an unauthenticated HTTP “run script” endpoint or imply that a file allowlist confines arbitrary AHK. Prefer local invocation first, explicit user authorization, and an isolated desktop for untrusted workflows. The prior art separates these concerns imperfectly, but its execution and deployment designs make the risk clear. [Xeo execution][xeo] [TrueCrimeDev file rules][truecrime] [sandraschi staging][sandra] [MCPControl warning][mcpcontrol]

My preferred ACU scope is a small AHK v2 executor with dependable screenshots, truthful results and an independently enforceable stop path. The opportunity is not inventing AHK-plus-LLM. It is making those few behaviors precise and testable. The existing direct-control, authoring and lifecycle projects already establish the broader idea. [spyoungtech][spyoung] [TrueCrimeDev][truecrime] [sandraschi][sandra] [MCPControl][mcpcontrol]

[anthropic]: https://platform.claude.com/docs/en/agents-and-tools/tool-use/computer-use-tool
[anthropic-code]: https://github.com/anthropics/anthropic-quickstarts/blob/main/computer-use-demo/computer_use_demo/tools/computer.py
[anthropic-param]: https://github.com/anthropics/anthropic-sdk-python/blob/main/src/anthropic/types/beta/beta_tool_computer_use_20251124_param.py
[anthropic-license]: https://github.com/anthropics/anthropic-quickstarts/blob/main/LICENSE
[openai]: https://developers.openai.com/api/docs/guides/tools-computer-use
[openai-actions]: https://github.com/openai/openai-python/blob/main/src/openai/types/responses/computer_action.py
[openai-call]: https://github.com/openai/openai-python/blob/main/src/openai/types/responses/response_computer_tool_call.py
[ufo]: https://github.com/microsoft/UFO
[ufo-controller]: https://github.com/microsoft/UFO/blob/main/ufo/automator/ui_control/controller.py
[omni]: https://github.com/microsoft/OmniParser
[terminator]: https://github.com/mediar-ai/terminator
[terminator-input]: https://github.com/mediar-ai/terminator/blob/73a381c0c1c33eda55f2c0ecb1d918bf5ec7561a/crates/terminator/src/platforms/windows/input.rs
[windows-use]: https://github.com/Jeomon/Windows-Use
[windows-mcp]: https://github.com/CursorTouch/Windows-MCP
[windows-core]: https://github.com/CursorTouch/Windows-MCP/blob/b04359e8445d46b381cc43793cb23559c1d71610/src/windows_mcp/uia/core.py
[windows-hooks]: https://github.com/CursorTouch/Windows-MCP/blob/b04359e8445d46b381cc43793cb23559c1d71610/src/windows_mcp/desktop/control_hooks.py
[windows-control]: https://github.com/CursorTouch/Windows-MCP/blob/main/src/windows_mcp/desktop/control_win32.py
[agent-s]: https://github.com/simular-ai/Agent-S
[agent-s-grounding]: https://github.com/simular-ai/Agent-S/blob/main/gui_agents/s3/agents/grounding.py
[oi-current]: https://github.com/openinterpreter/openinterpreter
[oi-profile]: https://github.com/endolith/open-interpreter/blob/main/interpreter/terminal_interface/profiles/defaults/os.py
[oi-mouse]: https://github.com/endolith/open-interpreter/blob/main/interpreter/core/computer/mouse/mouse.py
[oi-license]: https://github.com/endolith/open-interpreter/blob/main/LICENSE
[soc]: https://github.com/OthersideAI/self-operating-computer
[soc-input]: https://github.com/OthersideAI/self-operating-computer/blob/main/operate/utils/operating_system.py
[bytebot]: https://github.com/bytebot-ai/bytebot
[bytebot-input]: https://github.com/bytebot-ai/bytebot/blob/main/packages/bytebotd/src/computer-use/computer-use.service.ts
[bytebot-package]: https://github.com/bytebot-ai/bytebot/blob/main/packages/bytebotd/package.json
[py-docs]: https://pyautogui.readthedocs.io/en/latest/index.html
[py-win]: https://github.com/asweigart/pyautogui/blob/b4255d0be42c377154c7d92337d7f8515fc63234/pyautogui/_pyautogui_win.py
[py-click]: https://github.com/asweigart/pyautogui/blob/b4255d0be42c377154c7d92337d7f8515fc63234/pyautogui/__init__.py#L980-L1040
[py-move]: https://github.com/asweigart/pyautogui/blob/b4255d0be42c377154c7d92337d7f8515fc63234/pyautogui/_pyautogui_win.py#L350-L375
[py-button]: https://github.com/asweigart/pyautogui/blob/b4255d0be42c377154c7d92337d7f8515fc63234/pyautogui/_pyautogui_win.py#L430-L458
[py-flags]: https://github.com/asweigart/pyautogui/blob/b4255d0be42c377154c7d92337d7f8515fc63234/pyautogui/_pyautogui_win.py#L33-L55
[py-event]: https://github.com/asweigart/pyautogui/blob/b4255d0be42c377154c7d92337d7f8515fc63234/pyautogui/_pyautogui_win.py#L465-L505
[sendinput]: https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-sendinput
[mouse-event]: https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-mouse_event
[xdo-man]: https://manpages.debian.org/bookworm/xdotool/xdotool.1.en.html
[xdo]: https://github.com/jordansissel/xdotool/blob/14ca26a2c95035f9c635a6a11d075e8d7d0d6529/xdo.c
[xdo-license]: https://github.com/jordansissel/xdotool/blob/main/COPYRIGHT
[spyoung]: https://github.com/spyoungtech/ahk-mcp
[spyoung-code]: https://github.com/spyoungtech/ahk-mcp/blob/main/main.py
[spyoung-history]: https://github.com/spyoungtech/ahk-mcp/commits/main.atom
[xeo]: https://github.com/Xeo786/AutohotkeyV2_MCPServer
[xeo-code]: https://github.com/Xeo786/AutohotkeyV2_MCPServer/blob/main/server.py
[xeo-history]: https://github.com/Xeo786/AutohotkeyV2_MCPServer/commits/main.atom
[truecrime]: https://github.com/TrueCrimeDev/ahk-mcp
[truecrime-history]: https://github.com/TrueCrimeDev/ahk-mcp/commits/master.atom
[wizd]: https://github.com/wizd/ahk-mcp
[wizd-history]: https://github.com/wizd/ahk-mcp/commits/master.atom
[sandra]: https://github.com/sandraschi/autohotkey-mcp
[sandra-history]: https://github.com/sandraschi/autohotkey-mcp/commits/master.atom
[sandra-tools]: https://github.com/sandraschi/autohotkey-tools
[sandra-tools-history]: https://github.com/sandraschi/autohotkey-tools/commits/master.atom
[sandra-tools-license]: https://github.com/sandraschi/autohotkey-tools/blob/master/LICENSE
[mcpcontrol]: https://github.com/claude-did-this/MCPControl
[mcpcontrol-history]: https://github.com/claude-did-this/MCPControl/commits/main.atom
