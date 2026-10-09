# Cua survey for ACU

Survey target: `trycua/cua`, commit `48cc491463491c55287f86a552989e8c19e72583`, in `C:\Users\13982\github repo ref\cua`.

Method: static inspection only. I read source, manifests, and documentation. I did not pull, install, build, run repository code, launch a browser, or inject input. I did not modify the checkout. Line counts are local measurements, not claims copied from the project. Behavioral conclusions describe the code at this commit, not behavior I verified on Windows. Citations are repository-relative paths and inclusive line ranges.

## 1. Repo map

The part closest to ACU is `libs/cua-driver`, not the Python agent or the Spaces app. Its Rust workspace contains the driver runtime, shared core, Windows adapter, SDK, cursor renderer, and separate macOS and Linux adapters. The Python sandbox opener explicitly rejects `localhost` and directs host-machine automation to cua-driver. [`libs/cua-driver/rust/Cargo.toml:1-27`; `libs/python/agent/cua_agent/computers/sandbox.py:140-156`]

| Component | What it contains | Relevance to one Windows host |
| --- | --- | --- |
| `libs/cua-driver` | Rust desktop observation and action runtime. Shared core, platform adapters, CLI, SDK, UIAccess worker, cursor overlay, optional perception. | Primary source to study. The workspace separates these concerns. [`libs/cua-driver/rust/Cargo.toml:1-27`; `libs/cua-driver/rust/crates/platform-windows/src/tools/impl_.rs:10340-10418`] |
| `libs/cua` | Rust SDK and `cua` CLI. Sandbox lifecycle, local runtimes, Fleet, authentication, Spaces, remote daemon clients, streaming, files, and processes. `cua-sdk` is the UniFFI export crate. | Mostly outside ACU's scope. Do not confuse `cua daemon`, the shared SDK runtime, with the desktop driver. [`libs/cua/crates/cua-sdk/src/lib.rs:1-28`; `Development.md:11-14`] |
| `libs/cua-spacesd` | Rust server inside an environment. Native gRPC, gRPC-Web, HTTP side channels, desktop capture/input, processes, files, streaming, and presence. Default port is 3211. | Optional remote-machine layer, not necessary for a local agent talking to a local tool. Desktop input delegates to cua-driver. [`libs/cua-spacesd/crates/cua-spacesd/src/main.rs:4-6,81-88`; `libs/cua-spacesd/crates/cua-spacesd-desktop/src/grpc/tool_backend.rs:4-16`; `libs/cua/crates/cua-sdk/src/lib.rs:16-20`] |
| `libs/python/agent` | Model selection, provider-specific loops, action parsing, callbacks, tool dispatch, and UI integrations. | Useful if ACU needs a reference agent loop. Not required if an existing coding agent supplies the loop. [`libs/python/agent/cua_agent/agent.py:321-381,936-1045`] |
| `libs/python/core` | Shared HTTP version headers and telemetry support. | Not a Windows input backend. The package exports HTTP helpers; telemetry lives in separate modules. [`libs/python/core/cua_core/__init__.py:1-5`; `libs/python/core/cua_core/http.py:1-35`; `libs/python/agent/cua_agent/agent.py:386-396`] |
| The Python “computer” interface | `AsyncComputerHandler`, adapted to `cua_sandbox.Sandbox` by `SandboxComputerHandler`. Screenshot, mouse, keyboard, wait, and drag methods. | A useful small interface. It is an abstraction, not a second native Windows injector. [`libs/python/agent/cua_agent/computers/base.py:16-82`; `libs/python/agent/cua_agent/computers/sandbox.py:11-46`] |
| `libs/python/cua-sandbox` | High-level screen, mouse, keyboard, shell, and environment transport wrappers. The normal environment transport uses the Rust SDK's `SpacesdClient`; agentless alternatives are separate transports. | Skip lifecycle and remote transport for ACU. Study the distinction between model coordinates and native coordinates. [`libs/python/cua-sandbox/cua_sandbox/interfaces/mouse.py:1-48`; `libs/python/cua-sandbox/cua_sandbox/transport/env.py:1-13,635-743`] |
| `libs/cua-bench` | Task setup, solve/evaluate decorators, desktop sessions, action types, and benchmark runners. It also installs a compatibility alias for the retired `computer` package. | Useful testing ideas, not a minimal host driver dependency. Source says the old simulated desktop was removed, despite the root README still promoting a simulated quickstart. [`libs/cua-bench/cua_bench/__init__.py:1-55`; `README.md:191-195`] |
| `libs/cua-bench-rl`, `libs/cua-s1` | Separate training-related components. Bench workers/trainers moved to `cua-bench-rl`; CUA-S1 is specialized model research. | Skip for ACU. Neither is needed to expose desktop actions. [`libs/cua-bench/cua_bench/__init__.py:29-30`; `README.md:177-185`] |
| `libs/lume` | Swift macOS VM management using Apple's Virtualization framework and `VZVirtualMachine`. | Skip. It targets macOS 14+, not a Windows host. [`libs/lume/Package.swift:1-10`; `libs/lume/src/Virtualization/VMVirtualizationService.swift:1-34,37-60`] |
| `apps/cua-spaces` | Tauri desktop app and shared Spaces UI. It links Spaces, remote media, presence, agents, teleport, and Keyvault components. | Skip for a CLI/MCP-first local tool. Its cursor-presence UI is worth reading only if ACU later gets a viewer. [`apps/cua-spaces/src-tauri/Cargo.toml:1-8,28-85`; `apps/cua-spaces/src/viewer/presence/PresenceOverlay.tsx:4-15,35-75`] |
| `apps/cua-spaces-macos`, Swift support libraries | Native macOS Spaces app and streaming/teleport support. | Skip for Windows-only work. The project identifies the macOS app separately from its Linux/Windows Tauri app. [`README.md:219-220`; `Development.md:13,18`] |
| Fleet, images, container/VM tooling | Fleet is a mirrored dependency. Image, QEMU/container, XFCE, and related directories build or operate environments. | Skip for direct host input. [`Development.md:19,32-36`] |

My scope recommendation is to study `platform-windows`, then only the core modules that own targeting, snapshot lifetime, coordinate transforms, and result semantics. The workspace already separates those from the model loop and environment management. [`libs/cua-driver/rust/Cargo.toml:3-19`; `libs/cua-driver/rust/crates/cua-driver-core/src/snapshot_store.rs:9-23`; `libs/python/agent/cua_agent/agent.py:936-1045`]

## 2. Cua-driver

### Language and process boundary

The current implementation is Rust, edition 2021. Windows code uses the Rust `windows` bindings to Win32 and COM APIs. It is not an AutoHotkey or Python wrapper. [`libs/cua-driver/rust/Cargo.toml:22-27`; `libs/cua-driver/rust/crates/platform-windows/src/input/mouse.rs:6-27`; `libs/cua-driver/rust/crates/platform-windows/src/uia/mod.rs:18-30`]

The documented Windows process choices are an in-process SDK runtime, a private worker, an MCP process that owns its runtime, or a long-lived daemon. Bare Windows MCP does not inherently need the separate daemon. The docs require access to the interactive desktop and warn about Session 0. [`docs/content/docs/cua-driver/concepts/how-cua-driver-works.mdx:86-103`]

### Observation

- `list_windows` merges `EnumWindows` results with UI Automation-only windows and deduplicates by HWND. Win32 order comes first. Window records contain HWND, PID, title, rectangle, on-screen state, and minimized state. [`libs/cua-driver/rust/crates/platform-windows/src/win32/windows.rs:1-20,24-84`]
- `get_window_state(pid, window_id)` checks ownership before observation. It does not silently substitute another window. It returns metadata and, by default, both the accessibility tree and screenshot. Either can be disabled, but not both. [`libs/cua-driver/rust/crates/platform-windows/src/tools/impl_.rs:1243-1257,1263-1314`]
- The UIA walk uses `IUIAutomationCacheRequest`, `ElementFromHandle`, and `BuildUpdatedCache` rather than fetching every property in a separate call. There is an MSAA route for selected legacy surfaces, including SAL/VCL. [`libs/cua-driver/rust/crates/platform-windows/src/uia/mod.rs:252-348`]
- The default tree budget is 250 elements and depth 25. Output can be compact Markdown, structured elements, or both. Query projection and `since` diff reads reduce repeated output. A fresh diff still has a new snapshot ID. [`libs/cua-driver/rust/crates/platform-windows/src/tools/impl_.rs:1178-1214,1251-1256`]
- The snapshot retains COM element references and cached centers/rectangles. Action admission clones a retained reference, so replacement of the cache does not free the object during a pending call. [`libs/cua-driver/rust/crates/platform-windows/src/uia/snapshot.rs:8-15,49-89,98-132`; `libs/cua-driver/rust/crates/cua-driver-core/src/snapshot_store.rs:647-690`]

Window screenshots have several routes, not one universal capture API. Known XAML/WinUI/UWP hosts try Windows Graphics Capture first. On failure they try screen-region `BitBlt`, with an occlusion flag, then the GDI route. The ordinary GDI route uses `GetWindowDC`, compatible bitmap/DC allocation, `PrintWindow(PW_RENDERFULLCONTENT)`, and `BitBlt` if `PrintWindow` fails. It crops against `DWMWA_EXTENDED_FRAME_BOUNDS`. Minimized windows are refused before capture. [`libs/cua-driver/rust/crates/platform-windows/src/capture.rs:421-559`]

This distinction matters: a screen-region fallback can show an occluding window, while WGC reads the target's composited image. The implementation carries that difference as capture metadata instead of treating every bitmap as equally trustworthy. [`libs/cua-driver/rust/crates/platform-windows/src/capture.rs:454-486`]

### Exact Windows input routes

There is no single “Windows click API” in this driver. Target, element/pixel addressing, button/count, toolkit, and delivery mode select the route. The following are implemented routes, not a guarantee that every application accepts them. [`libs/cua-driver/rust/crates/platform-windows/src/tools/impl_.rs:3860-4050,4215-4351`]

| Route | APIs and behavior |
| --- | --- |
| Element action | Tries `IUIAutomationInvokePattern::Invoke`, then `Toggle`, `SelectionItem::Select`, and `ExpandCollapse::Expand` where applicable. The calls use a foreground-steal guard. [`libs/cua-driver/rust/crates/platform-windows/src/tools/impl_.rs:3939-4050`] |
| Pixel action with semantic hit-test | Looks for an invokable UIA element within the target window at the point, before falling back to posted messages on applicable single-click routes. A pixel request is therefore not necessarily a physical mouse event. [`libs/cua-driver/rust/crates/platform-windows/src/tools/impl_.rs:4183-4210,4320-4351`] |
| Posted background mouse | `ChildWindowFromPointEx` finds the deepest child HWND. `ScreenToClient` converts the point. `PostMessageW` sends `WM_MOUSEMOVE`, button-down, then button-up. Double-click-capable classes get `WM_*BUTTONDBLCLK` on the second press. The code sleeps 35 ms between down/up and 80 ms between clicks. [`libs/cua-driver/rust/crates/platform-windows/src/input/mouse.rs:29-171`] |
| Synthetic pointer fallback | `CreateSyntheticPointerDevice(PT_PEN)` plus separate `InjectSyntheticPointerInput` down/up calls. Left uses a normal pen tap; right uses the barrel flag. It rejects an occluded target point rather than raising the target. Middle has no supported mapping here. [`libs/cua-driver/rust/crates/platform-windows/src/input/inject.rs:239-397`] |
| Foreground mouse | `SetForegroundWindow` with `AttachThreadInput` assistance, exact foreground-target checks, `SetCursorPos`, and `SendInput`. The public click path schedules restoration of the previous foreground app. [`libs/cua-driver/rust/crates/platform-windows/src/input/inject.rs:119-159`; `libs/cua-driver/rust/crates/platform-windows/src/input/mouse.rs:569-640`; `libs/cua-driver/rust/crates/platform-windows/src/tools/impl_.rs:4215-4245`] |
| Background text/keys | `PostMessageW(WM_CHAR)` for UTF-16 text units; Enter uses `WM_KEYDOWN/WM_KEYUP`. Named keys and modifiers use posted key messages, including system-key handling. Delivery targets a focused descendant where available. [`libs/cua-driver/rust/crates/platform-windows/src/input/keyboard.rs:223-234,275-405`] |
| Semantic text/value | `ValuePattern::SetValue`; `set_value` also supports `RangeValuePattern::SetValue`. `type_text` with an element token appends text to the current ValuePattern value and reads the same element back. It is not caret-aware insertion. This is distinct from sending keystrokes. [`libs/cua-driver/rust/crates/platform-windows/src/tools/impl_.rs:4900-4965,6105-6168`] |
| Foreground text/keys | `SendInput` key sequences. Text uses `KEYEVENTF_UNICODE`; line breaks are key events. The code checks how many input records Windows accepted. [`libs/cua-driver/rust/crates/platform-windows/src/input/keyboard.rs:428-480,500-561,752-776`] |
| Combo selection and native queries | Not all messages are asynchronous. Native combo handling uses bounded `SendMessageTimeoutW` for `CB_*` messages and parent `WM_COMMAND` notifications. Non-client hit-testing also uses `SendMessageTimeoutW(WM_NCHITTEST, SMTO_ABORTIFHUNG)`. [`libs/cua-driver/rust/crates/platform-windows/src/win32/combo.rs:119-146,193-207,235-266`; `libs/cua-driver/rust/crates/platform-windows/src/input/mouse.rs:1013-1053`] |
| Scroll | Background paths include UIA `ScrollPattern` and posted `WM_VSCROLL/WM_HSCROLL` scrollbar messages. Desktop wheel delivery uses `SendInput` with `MOUSEEVENTF_WHEEL/HWHEEL` and a delta of 120 per tick. [`libs/cua-driver/rust/crates/platform-windows/src/uia/scroll.rs:123-157`; `libs/cua-driver/rust/crates/platform-windows/src/tools/impl_.rs:6313-6350`; `libs/cua-driver/rust/crates/platform-windows/src/input/mouse.rs:908-978`] |
| Drag | Posted press/move/release sequences, synthetic touch/pen strokes for selected background targets, or a `SendInput` sequence with interpolated motion. WPF background injection explicitly refuses rather than forcing foreground. [`libs/cua-driver/rust/crates/platform-windows/src/input/mouse.rs:174-307,735-913`; `libs/cua-driver/rust/crates/platform-windows/src/input/inject.rs:689-765`] |

An important commit-specific exception: background single left-clicks on a direct Chromium window bypass UIA and go straight to `post_click_screen`, for both element and pixel addressing. The result is unverified. Other Chromium click shapes can reach the synthetic-pointer route. Do not infer the current routing solely from old comments saying Chromium always ignores `PostMessage`. [`libs/cua-driver/rust/crates/platform-windows/src/tools/impl_.rs:3908-3937,4262-4318`; compare `libs/cua-driver/rust/crates/platform-windows/src/input/delivery.rs:101-112`]

### Is a click one SendInput batch?

Yes, on the synthesized mouse-click route, each click is one `SendInput` call containing `[move_input, down_input, up_input]`. Only the move record has absolute coordinates. It is not three separate `SendInput` calls. There is also an earlier `SetCursorPos`. Modifier-down and modifier-up batches are separate calls. Double/triple-click repeats the three-record batch, with an 80 ms gap. [`libs/cua-driver/rust/crates/platform-windows/src/input/mouse.rs:613-660`]

That answer does not apply to other routes. Posted clicks use separate `PostMessageW` calls. Synthetic pen taps use separate down/up injection calls with a 25 ms gap. UIA Invoke has no mouse down/up sequence. [`libs/cua-driver/rust/crates/platform-windows/src/input/mouse.rs:149-164`; `libs/cua-driver/rust/crates/platform-windows/src/input/inject.rs:281-299`; `libs/cua-driver/rust/crates/platform-windows/src/tools/impl_.rs:3998-4008`]

### Background versus foreground

The intended background contract is no raise, no foreground swap, and no movement of the user's real cursor. Failure to satisfy a route returns `background_unavailable` or a more specific refusal, rather than silently retrying foreground. Foreground is a per-action choice, not a persistent session setting. [`libs/cua-driver/rust/crates/platform-windows/src/input/delivery.rs:1-31,324-403`; `docs/content/docs/cua-driver/concepts/how-cua-driver-works.mdx:28-55`]

The implementation is more involved than the phrase “non-interfering” suggests. `NoActivateGuard` temporarily adds `WS_EX_NOACTIVATE`. Posted and injected routes can restore the previous foreground afterward. The touch-drag implementation also contains a real-cursor save/restore path and acknowledges that promotion can cause a brief cursor excursion. I would treat non-interference as a per-route contract requiring tests, not as proof of independent Windows input seats. [`libs/cua-driver/rust/crates/platform-windows/src/input/inject.rs:161-235,372-387,576-596,673-684`; `libs/cua-driver/rust/crates/platform-windows/src/input/mouse.rs:145-171`]

UIPI is checked before relevant input paths. The ordinary executable has `uiAccess="false"`; the separate worker has `uiAccess="true"` and documents signing and secure-location requirements. That is deployment complexity ACU should not inherit casually. [`libs/cua-driver/rust/crates/platform-windows/src/input/mouse.rs:108-116,472-481`; `libs/cua-driver/rust/crates/cua-driver/cua-driver.manifest:8-13`; `libs/cua-driver/rust/crates/cua-driver-uia/cua-driver-uia.manifest:8-30`]

### MCP vocabulary

There are two useful views of the schema. The checked-in portable contract is an experimental subset. The live Windows registry also exposes native convenience and compatibility tools. For example, portable `click` requires `target` and `delivery_mode`, while the native definition also accepts flat `pid/window_id/scope`, `modifier`, `action`, and `from_zoom`. Do not copy the manifest as though it describes every native MCP option. [`libs/cua-driver/contract/manifest.json:1-8,11-172`; `libs/cua-driver/rust/crates/platform-windows/src/tools/impl_.rs:3341-3358,10340-10501`]

For core input tools, prefer `target: {kind:"window", pid, window_id}` or `target: {kind:"desktop", display_id:"primary"}`. The generated MCP reference says this cannot be mixed with the legacy flat target fields. `session` is an optional public label, not a credential. [`docs/content/docs/cua-driver/reference/mcp-tools/index.mdx:17-36`; `libs/cua-driver/contract/manifest.json:104-153`]

The tables below list parameter names, not a replacement JSON schema. Brackets mean optional. Tool definitions cited in each row own the precise types and validation.

| Desktop tool | Parameters |
| --- | --- |
| `list_apps` | No portable parameters. The native schema also starts empty; common session metadata is added to the advertised MCP surface. [`libs/cua-driver/contract/manifest.json:2500-2587`; `libs/cua-driver/rust/crates/platform-windows/src/tools/impl_.rs:696-749`; `docs/content/docs/cua-driver/reference/mcp-tools/apps-and-windows.mdx:84-88`] |
| `list_windows` | `[pid, on_screen_only]`. [`libs/cua-driver/contract/manifest.json:2721-2877`] |
| `get_window_state` | `pid, window_id`; `[session, include_accessibility_tree, include_screenshot, query, max_elements, max_depth, timeout_ms, max_image_dimension, max_dimension, screenshot_out_file, tree_format, full_output, verbose, since]`. [`libs/cua-driver/contract/manifest.json:1626-2048`] |
| `get_desktop_state` | `[session, max_image_dimension, screenshot_out_file]`. [`libs/cua-driver/contract/manifest.json:1240-1370`] |
| `get_screen_size`, `get_cursor_position` | `[session]`. [`libs/cua-driver/contract/manifest.json:1189-1239,1371-1423`] |
| `click` | `target, delivery_mode`; either `element_token` or `x,y`; `[session, button, count, capture_id]`. Native additions include `modifier`, `action`, `from_zoom`, and flat target fields. [`libs/cua-driver/contract/manifest.json:11-172`; `libs/cua-driver/rust/crates/platform-windows/src/tools/impl_.rs:3341-3358`] |
| `double_click`, `right_click` | Native convenience tools with window/pixel or element targeting, delivery mode, session, and zoom-coordinate support. [`libs/cua-driver/rust/crates/platform-windows/src/tools/impl_.rs:6872-6927,7238-7295`] |
| `type_text` | `text`; `[target, scope, session]` in the subset. Native schema also has `pid, window_id, element_token, x,y, delay_ms, delivery_mode`. [`libs/cua-driver/contract/manifest.json:5172-5414`; `libs/cua-driver/rust/crates/platform-windows/src/tools/impl_.rs:4595-4607`] |
| `press_key` | `key`; `[target, modifiers, scope, session]`. Native targeting also supports `element_token` or `x,y` to focus first, plus `delivery_mode`. [`libs/cua-driver/contract/manifest.json:3621-3868`; `libs/cua-driver/rust/crates/platform-windows/src/tools/impl_.rs:5306-5318`] |
| `hotkey` | `keys`; `[target, scope, session]`. Native form adds flat target, element/pixel focus, and delivery mode. [`libs/cua-driver/contract/manifest.json:2049-2293`; `libs/cua-driver/rust/crates/platform-windows/src/tools/impl_.rs:5658-5675`] |
| `scroll` | Portable `x,y,direction`; `[target, amount, by, scope, session]`. Native form also accepts an element token and delivery mode; its required set is only `direction`. [`libs/cua-driver/contract/manifest.json:3869-4136`; `libs/cua-driver/rust/crates/platform-windows/src/tools/impl_.rs:6323-6337`] |
| `drag` | `from_x,from_y,to_x,to_y`; `[target, button, duration_ms, steps, modifier, scope, session]`; native `delivery_mode` and `from_zoom`. [`libs/cua-driver/contract/manifest.json:476-752`; `libs/cua-driver/rust/crates/platform-windows/src/tools/impl_.rs:7600-7622`] |
| `move_cursor` | `x,y`; `[target, scope, session]`. [`libs/cua-driver/contract/manifest.json:2878-3125`] |
| `set_value` | Native `pid,value`; element token targeting, `[window_id, session, delivery_mode]`. [`libs/cua-driver/rust/crates/platform-windows/src/tools/impl_.rs:6024-6033`] |
| `invoke_menu` | `pid,window_id,path`; `[session]`. Path is a sequence of menu labels. [`libs/cua-driver/contract/manifest.json:2294-2499`] |
| `set_window_frame` | `pid,window_id,x,y,width,height`; `[session]`. [`libs/cua-driver/contract/manifest.json:4557-4770`] |
| `verify_state` | `pid,window_id,expect`; `[session, timeout_ms, stable_samples, include_screenshot]`. [`libs/cua-driver/contract/manifest.json:5415-5678`] |
| `clipboard_read` | `[session, include_text]`. [`libs/cua-driver/contract/manifest.json:319-395`] |
| `clipboard_write` | One of `text`, `image_path`, `file_path`; `[session]`. [`libs/cua-driver/contract/manifest.json:396-475`] |
| `parse_visual_regions` | `capture_id`; `[options]`. Optional perception rather than the base accessibility route. [`libs/cua-driver/contract/manifest.json:3126-3620`; `docs/content/docs/cua-driver/concepts/how-cua-driver-works.mdx:23-25`] |

| Lifecycle/cursor tool | Parameters |
| --- | --- |
| `start_session` | `[session, capture_scope, cursor_motion, cursor_theme]`. Capture-scope fields are legacy compatibility, not a target lock. [`libs/cua-driver/contract/manifest.json:4771-5171`; `docs/content/docs/cua-driver/concepts/how-cua-driver-works.mdx:36-37`] |
| `get_session`, `get_session_state`, `end_session` | `[session]`. The state alias is legacy. [`libs/cua-driver/contract/manifest.json:753-801,1424-1625`; `docs/content/docs/cua-driver/reference/mcp-tools/index.mdx:178-189`] |
| `list_sessions` | `[cursor, limit]`. [`libs/cua-driver/contract/manifest.json:2588-2720`] |
| `escalate_session` | `session,reason`; `[detail]`. Deprecated compatibility tool, not an approval grant. [`libs/cua-driver/contract/manifest.json:802-919`; `docs/content/docs/cua-driver/reference/mcp-tools/index.mdx:178-189`] |
| `get_agent_cursor_state` | `session`. [`libs/cua-driver/contract/manifest.json:920-1188`] |
| `set_agent_cursor_enabled` | `session,enabled`. [`libs/cua-driver/contract/manifest.json:4137-4189`] |
| `set_agent_cursor_theme` | `session,theme_id`; `[reduced_motion]`. [`libs/cua-driver/contract/manifest.json:4456-4556`] |
| `set_agent_cursor_motion` | `session`; `[style, timing, effects, glide_duration_ms, idle_hide_ms, dwell_after_click_ms, start_handle, end_handle, arc_size, arc_flow, turn_radius, spring]`. [`libs/cua-driver/contract/manifest.json:4190-4455`] |

The broader Windows registry also adds `launch_app`, `kill_app`, `bring_to_front`, `debug_window_info`, `get_accessibility_tree`, `zoom`, configuration, permissions, and health tools. There is no separately registered `screenshot` tool. `get_window_state` owns window capture. `type_text_chars` is not advertised as its own registered tool. [`libs/cua-driver/rust/crates/platform-windows/src/tools/impl_.rs:10340-10485`]

Important additional vocabularies:

- `run_actions(steps, [pid,window_id,app,window,delay_ms,observe])` runs up to 32 ordered actions, stops on failure, and can perform one final observation. Steps can include named selectors, `wait_for`, and `expect`. [`libs/cua-driver/rust/crates/cua-driver-core/src/batch_tools.rs:165-284`]
- Experimental `run_script(script, [timeout_ms,max_calls])` exposes a bounded JavaScript `cua` API. It has loops, queries, waits, and normal driver calls, not filesystem/network/process access. Registration requires the `script` build feature and an operator opt-in, so it is not always advertised. [`libs/cua-driver/rust/crates/cua-driver-core/src/script_tool.rs:123-193`; `libs/cua-driver/rust/crates/cua-driver-core/src/tool.rs:1308-1335`]
- Browser tools are `get_browser_state`, `browser_prepare`, `browser_navigate`, `browser_click`, `browser_type`, `browser_pointer`, `browser_dialog`, `browser_set_input_files`, and `browser_download`, plus legacy `page`. Their own schemas define browser/window binding, tab/ref targeting, navigation, text, pointer actions, dialogs, and file paths. Windows registers this separate browser family. [`libs/cua-driver/rust/crates/platform-windows/src/tools/impl_.rs:10486-10498`; `docs/content/docs/cua-driver/reference/mcp-tools/index.mdx:154-176`]
- Recording and maintenance add `start_recording`, `stop_recording`, `get_recording_state`, `replay_trajectory`, `install_ffmpeg`, `get_config`, `set_config`, `check_permissions`, `health_report`, `check_for_update`, and `install_extension`. These are outside ACU's minimal input vocabulary; the generated references carry their full parameter tables. [`libs/cua-driver/rust/crates/platform-windows/src/tools/impl_.rs:10459-10477,10499`; `docs/content/docs/cua-driver/reference/mcp-tools/index.mdx:202-225`]

### Remaining tool parameters

For completeness, these are the remaining parameter names from the checked-in generated MCP reference, selecting Windows-specific rows plus shared rows. This is secondary schema evidence, not a runtime `tools/list` result. Dotted names below are nested fields, not literal dotted JSON keys. Platform registration is in the Windows registry; batch/script registration is shared. [`libs/cua-driver/rust/crates/platform-windows/src/tools/impl_.rs:10340-10501`; `libs/cua-driver/rust/crates/cua-driver-core/src/tool.rs:1307-1329`]

| Tool | Parameter names |
| --- | --- |
| `launch_app` | `additional_arguments`, `aumid`, `bundle_id`, `creates_new_application_instance`, `launch_path`, `name`, `path`, `start_minimized`, `urls`, `webkit_inspector_port`, `session`. [`docs/content/docs/cua-driver/reference/mcp-tools/apps-and-windows.mdx:213-231`] |
| `kill_app` | `pid`, `session`. [`docs/content/docs/cua-driver/reference/mcp-tools/apps-and-windows.mdx:259-260`] |
| `bring_to_front` | `pid`, `window_id`, `session`. [`docs/content/docs/cua-driver/reference/mcp-tools/apps-and-windows.mdx:309-319`] |
| `debug_window_info` | `pid`, `session`. [`docs/content/docs/cua-driver/reference/mcp-tools/apps-and-windows.mdx:376-377`] |
| `browser_click` | `delivery_mode`, `input_route`, `ref`, `session`, `tab_id`, `target_id`, `x`, `y`. [`docs/content/docs/cua-driver/reference/mcp-tools/browser-input.mdx:32-39`] |
| `browser_type` | `mode`, `ref`, `replace`, `session`, `tab_id`, `target_id`, `text`. [`docs/content/docs/cua-driver/reference/mcp-tools/browser-input.mdx:55-61`] |
| `browser_pointer` | `action`, `delivery_mode`, `delta_x`, `delta_y`, `destination_ref`, `input_route`, `ref`, `session`, `tab_id`, `target_id`, `to_x`, `to_y`, `x`, `y`. [`docs/content/docs/cua-driver/reference/mcp-tools/browser-input.mdx:77-90`] |
| `browser_dialog` | `action`, `delivery_mode`, `dialog_id`, `prompt_text`, `session`, `tab_id`, `target_id`. [`docs/content/docs/cua-driver/reference/mcp-tools/browser-input.mdx:106-112`] |
| `browser_set_input_files` | `files`, `ref`, `session`, `tab_id`, `target_id`. [`docs/content/docs/cua-driver/reference/mcp-tools/browser-input.mdx:128-132`] |
| `browser_download` | `destination_root`, `ref`, `session`, `tab_id`, `target_id`. [`docs/content/docs/cua-driver/reference/mcp-tools/browser-input.mdx:148-152`] |
| `get_config` | `session`. [`docs/content/docs/cua-driver/reference/mcp-tools/maintenance.mdx:67-67`] |
| `set_config` | `capture_mode`, `experimental_pip`, `experimental_pip_geometry`, `key`, `max_image_dimension`, `cursor.motion`, `cursor.motion.effects.glow`, `cursor.motion.effects.magnet`, `cursor.motion.effects.ripple`, `cursor.motion.effects.squish`, `cursor.motion.effects.trail`, `cursor.motion.style`, `cursor.motion.timing`, `session`, `value`. [`docs/content/docs/cua-driver/reference/mcp-tools/maintenance.mdx:137-159`] |
| `check_permissions` | `session`. [`docs/content/docs/cua-driver/reference/mcp-tools/maintenance.mdx:196-196`] |
| `health_report` | `include`, `session`, `skip`. [`docs/content/docs/cua-driver/reference/mcp-tools/maintenance.mdx:247-249`] |
| `check_for_update` | `session`. [`docs/content/docs/cua-driver/reference/mcp-tools/maintenance.mdx:259-259`] |
| `install_extension` | `confirm`, `name`, `session`. [`docs/content/docs/cua-driver/reference/mcp-tools/maintenance.mdx:269-271`] |
| `page` | `action`, `attributes`, `bundle_id`, `cdp_port`, `css_selector`, `javascript`, `pid`, `selector`, `session`, `target_url_contains`, `text`, `user_has_confirmed_enabling`, `window_id`. [`docs/content/docs/cua-driver/reference/mcp-tools/page.mdx:39-51`] |
| `get_browser_state` | `continuation`, `include_screenshot`, `pid`, `query`, `scope_ref`, `session`, `snapshot_format`, `tab_id`, `target_id`, `window_id`. [`docs/content/docs/cua-driver/reference/mcp-tools/page.mdx:67-76`] |
| `browser_prepare` | `allow_launch`, `pid`, `profile`, `profile.mode`, `profile.name`, `session`, `strategy`, `strategy.kind`, `window_id`. [`docs/content/docs/cua-driver/reference/mcp-tools/page.mdx:86-94`] |
| `browser_navigate` | `session`, `tab_id`, `target_id`, `url`. [`docs/content/docs/cua-driver/reference/mcp-tools/page.mdx:104-107`] |
| `start_recording` | `include_accessibility_tree`, `output_dir`, `record_video`, `session`, `state_timeout_ms`. [`docs/content/docs/cua-driver/reference/mcp-tools/recording.mdx:53-57`] |
| `stop_recording` | `session`. [`docs/content/docs/cua-driver/reference/mcp-tools/recording.mdx:75-75`] |
| `get_recording_state` | `session`. [`docs/content/docs/cua-driver/reference/mcp-tools/recording.mdx:87-87`] |
| `replay_trajectory` | `delay_ms`, `dir`, `session`, `stop_on_error`. [`docs/content/docs/cua-driver/reference/mcp-tools/recording.mdx:102-105`] |
| `install_ffmpeg` | `confirm`, `session`. [`docs/content/docs/cua-driver/reference/mcp-tools/recording.mdx:121-122`] |
| `zoom` | `pid`, `window_id`, `x1`, `x2`, `y1`, `y2`, `session`. [`docs/content/docs/cua-driver/reference/mcp-tools/screen.mdx:149-163`] |
| `get_accessibility_tree` | `session`. [`docs/content/docs/cua-driver/reference/mcp-tools/window-state.mdx:192-192`] |

### Element tokens, invalidation, and sessions

A token is `s` plus eight hexadecimal digits, a colon, and the element index, for example `s00001234:42`. It names a row in a particular snapshot, not a durable element selector. The store keeps up to eight window snapshots per PID. [`libs/cua-driver/rust/crates/cua-driver-core/src/element_token.rs:4-32`]

Publishing a new semantic snapshot removes the prior snapshot for the same PID/window and returns the retired IDs. Other windows remain until eviction. Resolving a stale token returns `stale_element_token`; a token that conflicts with the supplied window returns `conflicting_element_target`. A screenshot-only refresh can preserve semantic rows/tokens. [`libs/cua-driver/rust/crates/cua-driver-core/src/snapshot_store.rs:340-364,384-438,647-690`; `libs/cua-driver/rust/crates/platform-windows/src/tools/impl_.rs:1199-1204`]

This is not automatic continuous detection of every UI mutation. Tokens are cache references with explicit replacement/lifecycle rules. An action can make later coordinates or element assumptions wrong before another snapshot replaces the cache. The batch implementation explicitly warns about actions that rearrange the UI. [`libs/cua-driver/rust/crates/cua-driver-core/src/snapshot_store.rs:647-690`; `libs/cua-driver/rust/crates/cua-driver-core/src/batch_tools.rs:173-180`]

Pixel grounding has its own ownership. Screenshot context stores scale and session owner. A window pixel action without an appropriate screenshot context refuses with `screenshot_context_missing`. Optional `capture_id` binds a click to one exact registered capture and is consumed before native dispatch. This is stronger than merely remembering the last image dimensions. [`libs/cua-driver/rust/crates/cua-driver-core/src/snapshot_store.rs:25-47,76-139`; `libs/cua-driver/rust/crates/platform-windows/src/tools/impl_.rs:3348,3571-3604`]

A connection has an implicit lifecycle session. Named labels provide readable identity and a separate cursor. The default idle TTL is five minutes. Session end retires owned screenshot state and removes its cursor. After an implicit idle expiry, a later call can create a new episode, but old state remains retired. [`libs/cua-driver/rust/crates/cua-driver-core/src/session.rs:30,450-483`; `libs/cua-driver/rust/crates/platform-windows/src/tools/impl_.rs:10302-10320`; `docs/content/docs/cua-driver/concepts/how-cua-driver-works.mdx:104-113`]

Sessions do not create independent Windows keyboards or focus. Desktop actions requiring coordination take a process-wide mutex. That serializes participating runtimes in the process, not every unrelated automation program on the machine. [`libs/cua-driver/rust/crates/cua-driver-core/src/tool.rs:2136-2153`]

### verify_state

`verify_state` is deterministic polling, not a second model looking at the screenshot. It obtains fresh window/element observations and evaluates bounded predicates. Window predicates check existence and bounds. Element selectors use role and/or label substring; element predicates can test state/value fields. [`libs/cua-driver/rust/crates/cua-driver-core/src/expectation.rs:4-8,58-73,278-311,412-505`; `libs/cua-driver/rust/crates/cua-driver-contract/src/verification.rs:100-150`]

The default timeout is 5 seconds. Limits are 1 to 8 predicates, at most 10 seconds, and 1 to 5 stable samples. Default stability is two consecutive satisfied samples, with 100 ms between polls. Results are `satisfied`, `unsatisfied`, or `unknown`. A final screenshot can be attached as evidence, but it is not the predicate evaluator. [`libs/cua-driver/rust/crates/cua-driver-contract/src/verification.rs:15-23`; `libs/cua-driver/rust/crates/cua-driver-core/src/expectation.rs:25-29,245-350`]

Unknown is meaningful. Missing/untrusted observations and unproven stability are not success. Negative element existence is rejected because snapshots may be incomplete. A successful native event is likewise not proof that an application changed; foreground clicks return `effect:"unverifiable"` and `verified:false`. [`libs/cua-driver/rust/crates/cua-driver-core/src/expectation.rs:313-322,354-377,538-606`; `libs/cua-driver/rust/crates/platform-windows/src/tools/impl_.rs:4232-4245`]

### DPI and multiple monitors

Both Windows executable manifests request Per-Monitor V2 DPI awareness. The capture code therefore treats `GetWindowRect` dimensions as physical pixels and explicitly avoids multiplying them by DPI/96 again. [`libs/cua-driver/rust/crates/cua-driver/cua-driver.manifest:15-20`; `libs/cua-driver/rust/crates/cua-driver-uia/cua-driver-uia.manifest:31-36`; `libs/cua-driver/rust/crates/platform-windows/src/capture.rs:512-525`]

Window action coordinates refer to the returned screenshot, not the client area. The driver restores the screenshot's scale, then adds the DWM visible-frame origin and a one-pixel inset. Using `ClientToScreen` directly for the screenshot point would wrongly add the title-bar offset. [`libs/cua-driver/rust/crates/platform-windows/src/tools/impl_.rs:230-275,4142-4175`]

`SendInput` mouse coordinates use `MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK`. The driver reads `SM_XVIRTUALSCREEN`, `SM_YVIRTUALSCREEN`, `SM_CXVIRTUALSCREEN`, and `SM_CYVIRTUALSCREEN`; its math subtracts the possibly negative virtual origin before normalization to 0..65535. Posted messages instead receive child-client coordinates. [`libs/cua-driver/rust/crates/platform-windows/src/input/mouse.rs:489-540,42-105`; `libs/cua-driver/rust/crates/platform-windows/src/virtualdesk.rs:49-68`]

Do not confuse this with arbitrary-display desktop capture support. The portable desktop target is `display_id:"primary"`, and the conceptual docs describe `get_desktop_state` as primary-display capture. Windows input normalization and the overlay know about the virtual desktop, but that alone does not promise a whole-multi-monitor screenshot API. [`libs/cua-driver/contract/manifest.json:111-153`; `docs/content/docs/cua-driver/concepts/how-cua-driver-works.mdx:16-21`; `libs/cua-driver/rust/crates/platform-windows/src/overlay.rs:1-9`]

## 3. Python computer interface and cua-spacesd

### Actions and transport

The agent protocol exposes environment/dimensions, screenshot, click with button, double-click, scroll at a point, type, wait, move, keypress, path drag, URL lookup, and left-button down/up. `SandboxComputerHandler` forwards these to `sandbox.mouse`, `sandbox.keyboard`, and screenshot helpers. Its drag adapter keeps only the first and last path points. [`libs/python/agent/cua_agent/computers/base.py:16-82`; `libs/python/agent/cua_agent/computers/sandbox.py:19-46,96-137`]

The normal path at this commit is:

`ComputerAgent -> SandboxComputerHandler -> cua_sandbox interfaces -> EnvTransport -> Rust SpacesdClient -> cua-spacesd ComputerService -> cua-driver`.

Each forwarding boundary is present in source. There is no PyAutoGUI or pynput injector in this particular chain. The key-map comment that still mentions pynput/computer-server is not evidence of the current backend. [`libs/python/agent/cua_agent/computers/sandbox.py:19-52,96-103`; `libs/python/cua-sandbox/cua_sandbox/interfaces/mouse.py:14-48`; `libs/python/cua-sandbox/cua_sandbox/transport/env.py:1-13,637-731`; `libs/cua/crates/cua-spacesd-client/src/computer.rs:198-255`; `libs/cua-spacesd/crates/cua-spacesd-desktop/src/grpc/tool_backend.rs:54-86`]

The spacesd backend invokes an in-process driver registry. It deliberately uses the native-window-pixel entry point because its coordinates come from stream/window geometry, not a prior driver screenshot. Window-targeted Auto delivery maps to background; untargeted desktop Auto delivery maps to foreground. [`libs/cua-spacesd/crates/cua-spacesd-desktop/src/grpc/tool_backend.rs:54-86,366-438`]

There is a scroll convention worth checking before borrowing adapters. The OpenAI function schema describes positive `scroll_y` as down. The sandbox mouse interface describes positive `scroll_y` as up. `SandboxComputerHandler` passes it through unchanged, then `EnvTransport` negates it for spacesd. This is a source-level convention mismatch across those adapters, not a runtime-tested failure. [`libs/python/agent/cua_agent/loops/openai.py:98-105`; `libs/python/agent/cua_agent/computers/sandbox.py:40-41`; `libs/python/cua-sandbox/cua_sandbox/interfaces/mouse.py:25-32`; `libs/python/cua-sandbox/cua_sandbox/transport/env.py:660-684`]

### Screenshots

Python requests screenshot bytes through the transport and can base64-encode them. `EnvTransport` requests PNG or JPEG from `SpacesdClient`; it does not perform native Windows capture itself. [`libs/python/cua-sandbox/cua_sandbox/interfaces/screen.py:16-34`; `libs/python/cua-sandbox/cua_sandbox/transport/env.py:363-381`]

spacesd takes a BGRA frame from its capture provider, optionally crops/downscales it, and encodes the result. The response includes image size, native size, logical bounds, scale, screenshot ID, and capture time. Its Windows window provider uses WGC with D3D11, a free-threaded frame pool, and cursor capture disabled. [`libs/cua-spacesd/crates/cua-spacesd-desktop/src/grpc/tool_backend.rs:391-410`; `libs/cua-spacesd/crates/cua-spacesd-desktop/src/grpc/computer.rs:355-453`; `libs/cua-spacesd/crates/cua-spacesd-desktop/src/windows_capture.rs:115-188`]

### Screenshot-to-click scaling

There are several distinct transforms:

1. spacesd accepts screen, window, normalized, and screenshot coordinate spaces. Screenshot space uses `screenshot_id`, source logical bounds, and actual returned image dimensions. Unknown/expired IDs and changed source sizes refuse. The transform is `logical_origin + image_point * logical_size / image_size`. [`libs/cua-spacesd/crates/cua-spacesd-desktop/src/grpc/computer.rs:125-191`]
2. Its driver adapter converts global logical points to native window pixels or desktop pixels using the display scale. This is separate from model-side image resizing. [`libs/cua-spacesd/crates/cua-spacesd-desktop/src/grpc/tool_backend.rs:355-388`]
3. The simple Python `EnvTransport` screenshot method returns only image bytes. Its click helper forwards raw coordinates to the SDK's default screen-point click and does not attach the screenshot ID or divide by screenshot scale. Therefore the simple agent wrapper does not itself provide the richer screenshot-bound coordinate contract. Do not assume this wrapper automatically fixes every DPI or resized-image case. [`libs/python/cua-sandbox/cua_sandbox/transport/env.py:370-381,637-655`; `libs/cua/crates/cua-spacesd-client/src/computer.rs:31-48,223-255`]
4. The Anthropic loop separately downsizes images to fit 1024 by 768 and multiplies returned action coordinates by the original/resized ratios. This is implemented model-adapter scaling, not Windows DPI handling. [`libs/python/agent/cua_agent/loops/anthropic.py:38-50,667-729,798-817`]

For ACU, I would choose one externally visible coordinate space and return the exact transform whenever capture is resized or cropped. Cua's separation of screenshot scale, logical geometry, and native pixels is useful; its multiple overlapping interfaces are not a good minimal API template. [`libs/cua-spacesd/crates/cua-spacesd-desktop/src/grpc/computer.rs:125-191,431-453`; `libs/cua-driver/rust/crates/platform-windows/src/tools/impl_.rs:4142-4175`]

## 4. Agent loop, safety, and multiplayer

### Model input and action execution

`ComputerAgent` selects a provider loop from the model configuration. Each iteration preprocesses history through callbacks, calls `predict_step`, normalizes the returned output, yields it, then executes the returned items in order. It repeats until an assistant response ends the loop or a continuation callback says stop. [`libs/python/agent/cua_agent/agent.py:369-381,936-1045`]

The internal action shape is a `computer_call` with an `action` dictionary. Dispatch removes the `type` field, looks up that method on the computer handler, validates the callable signature, and awaits it. Unknown methods return a tool error. The normalizer repairs common aliases and parameter shapes; it is not an authorization layer. [`libs/python/agent/cua_agent/agent.py:740-764`; `libs/python/agent/cua_agent/callbacks/operator_validator.py:20-108`]

After an ordinary computer action, the agent waits the configured screenshot delay, takes a screenshot, and returns `computer_call_output` containing an `input_image` data URL. The default delay is 0.5 seconds. Terminate actions skip the screenshot. The next loop iteration includes the new output in model history. [`libs/python/agent/cua_agent/agent.py:267,782-823,946-952,1013-1032`]

The OpenAI loop forwards Responses-style messages and either a native computer tool or a function schema through `litellm.aresponses`. The Anthropic adapter converts tool-use outputs into the internal action shape and rescales coordinates as described above. These are model-specific adapters, not one universal parser. [`libs/python/agent/cua_agent/loops/openai.py:18-65,145-178,220-250`; `libs/python/agent/cua_agent/loops/anthropic.py:763-817`]

The loop also executes registered function tools, including normal Python callables. Async functions run directly; sync functions run in a worker thread. That is the concrete mechanism for combining application/API/code tools with GUI actions in one history. [`libs/python/agent/cua_agent/agent.py:837-874`]

### Safety and cancellation

The most important finding is negative: the Python agent automatically acknowledges every `pending_safety_checks` item. It does so after executing the action. The intended confirmation callback is a TODO in commented code. This is not a working user-confirmation barrier. [`libs/python/agent/cua_agent/agent.py:757-762,794-804,810-823`]

There are usable extension points. Callbacks run before computer calls, before/after model calls, and at continuation checks. The optional budget manager stops future iterations when accumulated cost reaches its budget. Neither is an automatic safety policy by itself. [`libs/python/agent/cua_agent/agent.py:619-659,937-940`; `libs/python/agent/cua_agent/callbacks/budget_manager.py:12-55`]

The Gradio UI has a Cancel button, but the inspected handler only prints a message and appends “Task cancelled by user” to chat. Its event wiring does not cancel the running task. I would not borrow it as an emergency-stop implementation. [`libs/python/agent/cua_agent/ui/gradio/ui_components.py:539-572,798-803`]

The PII callback is also incomplete: initialization is a TODO, and its anonymize/deanonymize helpers return their arguments unchanged. A class named for safety is not evidence that the safety behavior exists. [`libs/python/agent/cua_agent/callbacks/pii_anonymization.py:12-18,33-54,93-99`]

The Rust driver has a separate authorization system. Its dispatch path performs authorization and routes private observations, clipboard, file transfer, and desktop input through approval helpers before committing authorized dispatch. That is distinct from the Python loop's automatic acknowledgement of model safety checks. [`libs/cua-driver/rust/crates/cua-driver-core/src/tool.rs:1700-1710,1860-1940,2040-2064`]

I did not find a universal host-user-takeover or emergency-stop mechanism in the inspected Python execution loop. The concrete mechanisms there are continuation callbacks, tool execution, and UI wiring described above. The multiplayer implementation belongs mainly to the driver/Spaces stack, not that loop. [`libs/python/agent/cua_agent/agent.py:936-1045`; `libs/python/agent/cua_agent/ui/gradio/ui_components.py:552-572,800-803`; `libs/cua-spacesd/crates/cua-spacesd-desktop/src/grpc/presence.rs:4-24`]

### What “each with your own cursor” means here

The README's multiplayer claim is under Cua Spaces. It is not merely aspirational: this checkout contains per-session driver cursors, a presence protocol/server, client rendering, and per-window input leases. [`README.md:67-73`; `libs/cua-driver/rust/crates/platform-windows/src/overlay.rs:12-22`; `libs/cua-spacesd/crates/cua-spacesd-desktop/src/grpc/presence.rs:4-24`; `apps/cua-spaces/src/viewer/presence/PresenceOverlay.tsx:35-75`; `libs/cua-spacesd/crates/cua-spacesd-session/src/media/leases.rs:4-17`]

On Windows, the agent cursors are painted in a transparent, click-through, non-activating layered window. A keyed render map gives each session its own visual cursor. `tiny-skia` renders BGRA pixels and `UpdateLayeredWindow` composites them. These are overlays, not separate Windows hardware mouse pointers. [`libs/cua-driver/rust/crates/platform-windows/src/overlay.rs:1-29`]

Spaces presence sends cursor state separately from video. The server assigns colors, coalesces positions, broadcasts at 20 Hz, supports cursor shapes/batches and an optional QUIC datagram channel, and removes idle agent participants. The Tauri viewer creates a `PresenceLayer` over its media canvas and publishes the local pointer. [`libs/cua-spacesd/crates/cua-spacesd-desktop/src/grpc/presence.rs:9-24,46-64`; `apps/cua-spaces/src/viewer/presence/PresenceOverlay.tsx:43-70`]

Input leases allow one principal per window. Another principal gets a conflict until the five-second idle lease expires; separate windows can have separate holders. The inspected lease implementation does not give humans an unconditional priority override. The computer RPC layer exposes lease conflicts with holder and retry metadata. [`libs/cua-spacesd/crates/cua-spacesd-session/src/media/leases.rs:4-17,61-106`; `libs/cua-spacesd/crates/cua-spacesd-desktop/src/grpc/computer.rs:195-227`]

So the implementation supports multiple visible cursors and target-addressed work. It does not make foreground Windows input magically concurrent or isolated. Foreground delivery still uses the shared system queue, while driver actions requiring coordination are serialized. [`libs/cua-driver/rust/crates/platform-windows/src/input/mouse.rs:619-639`; `libs/cua-driver/rust/crates/cua-driver-core/src/tool.rs:2136-2153`]

## 5. The “Computer-Use 2.0” concept

The root README defines the phrase as an agent moving between code, APIs, and graphical interfaces within one task. It points to the driver concept page. That page currently describes the driver as the UI layer beneath an external model/agent loop, rather than an all-in-one autonomous agent. [`README.md:63`; `docs/content/docs/cua-driver/concepts/how-cua-driver-works.mdx:6-12`]

The current concept page recommends a ladder: observe tree and pixels together, try element/background action, then pixel/background, use browser DOM tools when suitable, and escalate the individual action to foreground when needed. Verification is a separate step, and successful delivery is not equated with an applied change. [`docs/content/docs/cua-driver/concepts/how-cua-driver-works.mdx:14-70`]

The source supplies concrete pieces of that idea:

- The Python agent accepts both computer calls and registered function calls in the same loop. Code/API work need not be expressed as mouse gestures. [`libs/python/agent/cua_agent/agent.py:740-874,1019-1032`]
- Browser tools are a separate family registered alongside native window tools. The docs describe typed CDP operations rather than requiring browser tasks to use the desktop mouse. [`libs/cua-driver/rust/crates/platform-windows/src/tools/impl_.rs:10486-10498`; `docs/content/docs/cua-driver/reference/mcp-tools/index.mdx:154-176`]
- `run_actions` batches known GUI steps and checks; experimental `run_script` adds JavaScript control flow over allowed driver operations. The latter does not grant arbitrary network or filesystem access. [`libs/cua-driver/rust/crates/cua-driver-core/src/batch_tools.rs:165-217`; `libs/cua-driver/rust/crates/cua-driver-core/src/script_tool.rs:123-162`]

My interpretation for ACU: expose a dependable GUI tool and let the existing agent choose shell, APIs, browser tools, or GUI. “Computer-Use 2.0” does not require ACU to implement the planner, VM manager, browser debugger, and GUI injector in one process. The documented boundary explicitly leaves the model and loop to the agent harness. [`docs/content/docs/cua-driver/concepts/how-cua-driver-works.mdx:6-12,49-55`]

## 6. Size

These are rough local physical-line measurements at the pinned commit. They include comments and blank lines, not just executable statements. I used read-only `git ls-files` enumeration and a separately written counting script because `tokei` and `scc` were not available. No repository script was executed.

The selection included common source extensions such as Rust, Python, TypeScript/JavaScript, Swift, Kotlin, Go, C/C++, C#, proto, HTML/CSS, shell, and PowerShell. It excluded test directories and test-named files, fixture/example/sample directories, dedicated E2E/testkit/test-app crates, scripts, docs, task datasets, benchmarks, and directories named `generated`. It also subtracted Rust `#[cfg(test)]` items with a lexical heuristic. Generated bindings stored under ordinary source directories remain included. Thus these are approximate non-test source footprints, not hand-written production SLOC. Subrows overlap parent rows and must not be added twice.

The numeric columns are measurements of the named file sets. The citations identify representative source boundaries, not source statements asserting these totals.

| Component | Approximate non-test lines | Scope evidence |
| --- | ---: | --- |
| `libs/cua-driver`, all selected languages/platforms | 307,000 | Workspace includes all adapters, SDK, cursor, perception, and CLI. [`libs/cua-driver/rust/Cargo.toml:1-19`] |
| Driver Windows adapter only | 32,800 | Native observation/input and registry. [`libs/cua-driver/rust/crates/platform-windows/src/tools/impl_.rs:10253-10501`] |
| Driver shared core | 57,600 | Shared dispatch, sessions, targeting, browser, verification, and related source. [`libs/cua-driver/rust/crates/cua-driver-core/src/tool.rs:1060-1145`; `libs/cua-driver/rust/crates/cua-driver-core/src/expectation.rs:4-29`] |
| Driver executable crate | 27,500 | Separate workspace member. [`libs/cua-driver/rust/Cargo.toml:3-11`] |
| Driver SDK crate | 10,700 | Separate workspace member. [`libs/cua-driver/rust/Cargo.toml:4-7`] |
| Driver macOS adapter | 37,800 | Separate platform member. [`libs/cua-driver/rust/Cargo.toml:12-14`] |
| Driver Linux adapter | 58,900 | Separate platform member. [`libs/cua-driver/rust/Cargo.toml:12-14`] |
| Shared cursor overlay / motion crates | 5,900 / 2,300 | Separate rendering and motion members. [`libs/cua-driver/rust/Cargo.toml:15-16`; `libs/cua-driver/rust/crates/platform-windows/src/overlay.rs:24-29`] |
| `libs/cua` | 486,000 | SDK, CLI, environment/Spaces/media components and bindings. [`Development.md:11`; `libs/cua/crates/cua-sdk/src/lib.rs:1-28`] |
| `libs/cua-spacesd` | 70,500 | Server, desktop, session, relay, and related selected code. [`libs/cua-spacesd/crates/cua-spacesd/src/main.rs:4-20`; `libs/cua-spacesd/crates/cua-spacesd-desktop/src/grpc/tool_backend.rs:4-16`] |
| `libs/python/agent` | 25,900 | Agent loops and integrations. [`libs/python/agent/cua_agent/agent.py:936-1045`] |
| `libs/python/core` | 1,000 | HTTP and telemetry utility package. [`libs/python/core/cua_core/__init__.py:1-5`; `libs/python/core/cua_core/http.py:1-35`] |
| `libs/python/cua-sandbox` | 21,600 | Interfaces, transports, runtimes, and higher-level wrapper. [`libs/python/cua-sandbox/cua_sandbox/transport/env.py:1-13`] |
| `libs/cua-bench` | 25,800 | Library code; task datasets/examples excluded. [`libs/cua-bench/cua_bench/__init__.py:1-55`] |
| `libs/cua-bench-rl` / `libs/cua-s1` | 3,200 / 8,400 | Training/research components. [`libs/cua-bench/cua_bench/__init__.py:29-30`; `README.md:177-185`] |
| `libs/lume` | 32,300 | Swift VM application source. [`libs/lume/Package.swift:27-45`] |
| `apps/cua-spaces` | 41,300 | Tauri/web app; not the shared SDK counted above. [`apps/cua-spaces/src-tauri/Cargo.toml:1-18,45-70`] |
| `apps/cua-spaces-macos` | 26,200 | Native macOS app. [`README.md:219`] |
| `libs/spaces-app-swift` | 76,100 | Support/binding footprint, including generated FFI source outside `generated` directories. This is not a hand-written UI size estimate. [`Development.md:11`; `README.md:219`] |
| `libs/typescript/agent` | 600 | Separate TypeScript component, not the Python implementation. [`Development.md:16`] |
| `libs/fleet` | 129,500 | Mirrored dependency and bindings. [`Development.md:35-36`] |

For calibration, the selected Windows adapter files contain 37,484 physical lines before subtracting inline Rust tests. Shared core contains 83,106 before that subtraction. The estimate is intended to distinguish tens of thousands of lines from a small AHK utility, not to claim compiler-grade precision.

The complete local checkout occupies approximately 489.9 MiB in file bytes, including `.git` and non-source assets. This is a disk measurement, not a build or installed binary size. No dependencies or build artifacts were produced during this survey.

## What a minimal AHK tool should borrow or skip

These are design recommendations, not claims about AHK features already implemented in ACU.

### Borrow first

1. **One exact target and one explicit coordinate space.** Require a window identity for window actions. Return screenshot origin, dimensions, and scale. Reject ambiguous or stale targets. This is the most useful part of Cua's design for a small tool. The source shows why screenshot pixels cannot be treated as client-area pixels. [`libs/cua-driver/rust/crates/platform-windows/src/tools/impl_.rs:1281-1302,230-275,4142-4175`]
2. **Atomic click delivery where appropriate.** For foreground input, submit move/down/up in one `SendInput` batch and check the inserted count. Keep modifiers and double-click timing explicit. Cua does exactly this in its synthesized click implementation. [`libs/cua-driver/rust/crates/platform-windows/src/input/mouse.rs:613-660`]
3. **A truthful result contract.** Separate refusal, delivery, and verified effect. Return `unknown` when evidence is missing. Do not call an accepted input event a successful task. Cua's click and verification results make this distinction. [`libs/cua-driver/rust/crates/platform-windows/src/tools/impl_.rs:4232-4245`; `libs/cua-driver/rust/crates/cua-driver-core/src/expectation.rs:313-350,538-606`]
4. **Fresh observation after meaningful changes.** Start with screenshots and window facts. Add bounded UIA reads only if they improve real tasks. If element handles are exposed, bind them to snapshot generations and refuse stale ones. [`libs/cua-driver/rust/crates/cua-driver-core/src/element_token.rs:4-32`; `libs/cua-driver/rust/crates/cua-driver-core/src/snapshot_store.rs:384-438,647-690`]
5. **DPI-aware geometry from the start.** Use physical-pixel semantics consistently. Test a monitor left of the primary, a monitor above it, mixed scaling, resized screenshots, and windows with non-client borders. Cua has separate code for these transforms because one generic offset was not sufficient. [`libs/cua-driver/rust/crates/cua-driver/cua-driver.manifest:15-20`; `libs/cua-driver/rust/crates/platform-windows/src/virtualdesk.rs:21-68`; `libs/cua-driver/rust/crates/platform-windows/src/tools/impl_.rs:230-275`]
6. **A small action set with a real stop path.** My proposed first set is observe, click, type, key/chord, scroll, drag, window selection, and cancel. Add a user-controlled emergency stop and release held inputs on exit. Do not copy the Python agent's auto-acknowledgement or chat-only Cancel handler. [`libs/python/agent/cua_agent/agent.py:794-804`; `libs/python/agent/cua_agent/ui/gradio/ui_components.py:552-572,800-803`]

### Add only after a demonstrated need

- UIA Invoke/Value support for forms and controls that expose dependable semantics. Keep it a distinct operation from a physical click/type request, or report which route ran. Cua shows that a pixel click can otherwise become UIA Invoke without being a mouse event. [`libs/cua-driver/rust/crates/platform-windows/src/tools/impl_.rs:4183-4210,4320-4337,6105-6168`]
- A bounded `verify` or wait operation with a timeout. Start with simple window/value predicates rather than a general workflow engine. Cua's implementation gives a concrete upper bound and an unknown result. [`libs/cua-driver/rust/crates/cua-driver-core/src/expectation.rs:25-29,245-350`]
- A simple visual agent cursor if users need to see intended targets. Treat it as an indicator, not another OS pointer. Cua's Windows implementation is a layered overlay. [`libs/cua-driver/rust/crates/platform-windows/src/overlay.rs:1-29`]
- Short ordered batches, only with stop-on-error and a clear final observation. Avoid silently retrying non-idempotent actions. Cua's batch design validates first and stops at the first failure, but also illustrates how selectors, retries, waits, and diffs quickly enlarge the implementation. [`libs/cua-driver/rust/crates/cua-driver-core/src/batch_tools.rs:165-217`]

### Skip initially

- Universal background automation. I would make foreground use explicit and reliable first. Add tested background operations by capability, not by a promise that every app can be driven without disturbance. Cua's route matrix, synthetic-pointer fallback, activation guards, and toolkit refusals show the cost of that promise. [`libs/cua-driver/rust/crates/platform-windows/src/input/delivery.rs:101-180`; `libs/cua-driver/rust/crates/platform-windows/src/input/inject.rs:161-235,689-765`]
- VM lifecycle, Fleet, remote streaming, presence, teleport, Keyvault, training, and benchmark orchestration. Those solve deployment, collaboration, or research problems outside a one-host GUI tool. Their source boundaries are separate from the Windows driver. [`libs/cua/crates/cua-sdk/src/lib.rs:14-23`; `apps/cua-spaces/src-tauri/Cargo.toml:45-85`; `libs/cua-bench/cua_bench/__init__.py:1-55`]
- An embedded model loop or JavaScript runtime. Let the calling agent use code and APIs alongside ACU. Cua's own concept separates the loop from the driver, and its experimental script tool carries its own limits and execution model. [`docs/content/docs/cua-driver/concepts/how-cua-driver-works.mdx:6-12`; `libs/cua-driver/rust/crates/cua-driver-core/src/script_tool.rs:123-162`]
- UIAccess deployment until elevated-target support is a real requirement. Signing and launch-location requirements are a substantial addition to a minimal host tool. [`libs/cua-driver/rust/crates/cua-driver-uia/cua-driver-uia.manifest:11-27`]

If code is copied rather than ideas adapted, inspect the license of the exact files. The driver workspace declares MIT. Spacesd and Spaces app files inspected here carry FSL-1.1-MIT headers or package metadata. Do not assume every part of the monorepo has the driver's license. [`libs/cua-driver/rust/Cargo.toml:22-27`; `libs/cua-spacesd/crates/cua-spacesd-desktop/src/grpc/tool_backend.rs:1-2`; `apps/cua-spaces/src-tauri/Cargo.toml:1-8`]

My preferred ACU boundary is a small Windows tool that observes one identified surface, performs one explicitly authorized action, and returns enough evidence to decide what to do next. Borrow Cua's targeting and failure semantics before borrowing its breadth.
