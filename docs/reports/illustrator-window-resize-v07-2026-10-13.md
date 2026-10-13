# First v0.7 trial: Illustrator resize at 02:19

The actor explicitly restored Illustrator and moved/resized it to `(0, 0, 1600, 1000)`. Initial maintainer maximization had succeeded. This transition was not an unexplained ACU, DPI or cursor effect.

The actual script, `attempts/01-pi-acu/workspace/scratch/look.ahk`, contains at lines 3–4:

```autohotkey
WinRestore(t)
WinMove(0,0,1600,1000,t)
```

No `WinMaximize` follows. Its successful ACU result reports `source=0,0 1600x1000`, `image=1600x1000` and `scale=1`; the script SHA-256 matches the contemporaneous ACU run log.

## Clock correlation

Recording: `E:/Videos/2026-10-13 04-51-00.mp4`, 3840 × 2160 at 30 fps.

- OBS logs Recording Start at **04:51:00.304 local, UTC−04:00**, naming that exact video. The historical ACU log independently records the same timezone offset.
- Maintainer normalization finished at **04:52:28.962 local**, with `maximized:true` and frame bounds `[-13,-13,3866,2186]` covering the primary screen.
- The resize tool ran between **04:53:19.082 and 04:53:20.326 local** (08:53:19.082–08:53:20.326 UTC). These bracket the action; individual native API calls were not timestamped.
- The recorded window first shows the reduced upper-left footprint at **02:19.667**, zero-based frame 4190. By 02:19.767 it is visibly in the small-window layout; the 02:20 frame matches approximately 1600 × 1000.

OBS start plus video PTS gives a nominal wall-clock mapping, not a calibrated millisecond timestamp. Capture/encoder/display latency is unmeasured. The independent 1.244-second tool bracket contains the nominal transition. Worker-start, session-start and event-capture timer origins differ; simply adding event elapsed time to the recording filename or worker start would misalign the history.

## Why

The recorded reasoning is only **"Resizing the canvas window"**. It does not explain why 1600 × 1000 was chosen.

Coordinate convenience is plausible: the actor first received a downsampled maximized screenshot, then requested this smaller full-resolution capture, fitted the artboard with Ctrl+0 and authored a screen-coordinate mapping. That specific motivation is an inference, not an explicit statement. The intentional resize itself is proven.

No runtime fix, benchmark-specific ACU instruction or new actor window-size constraint was added for this finding.

## Evidence and reproducible check

Original round: `.pi/rounds/illustrator-pen-export-v07-20261013T085142Z/`.

- First trial `session.jsonl:13–14`; `events.jsonl:212,215,217`.
- Tool ID: `call_QkyWU72fgnLq8TTlBjnOGOgy|fc_0023b8554c9755ec016acdf17c6dc087d1b2e06e714a763192`.
- Initial state: `illustrator-window.json`, `observer-window.log`, `session.jsonl:9`.
- OBS log: `C:/Users/13982/AppData/Roaming/obs-studio/logs/2026-10-13 04-47-07.txt:300–301`.
- ACU run log: `C:/Users/13982/AppData/Local/ACU/logs/runs.jsonl:2836,2841`.

`python .pi/window-resize-v07/diagnose.py` passes against the immutable recorded trace; `--expect-maximized` correctly fails. It reads the recorded pixels and historical source, never replays AHK or touches the desktop. The exact symptom and source/hash/timestamp checks were repeated. Historical evidence and verdicts remain unchanged.

[Full findings](file:///C:/Users/13982/ahk-computer-use/.pi/window-resize-v07/findings.md) · [Timeline JSON](file:///C:/Users/13982/ahk-computer-use/.pi/window-resize-v07/timeline.json) · [Before, 02:18](file:///C:/Users/13982/ahk-computer-use/.pi/window-resize-v07/frame-138.png) · [After, 02:20](file:///C:/Users/13982/ahk-computer-use/.pi/window-resize-v07/frame-140.png)

Persistent diagnosis output: `.pi/window-resize-v07/diagnostic.log`, `validation.log` and `diagnostic-crash.txt` when an expected assertion fails; extraction/video/timeline scripts retain their own crash stacks in the same directory. Implementation replay log: `.pi/benchmark-v08/resize-replay.log`.
