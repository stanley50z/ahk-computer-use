# Interpret a screenshot

Run `screenshot.ahk` through ACU's `run` tool. Arguments are `fullscreen [monitor]` for one monitor, `app <observed WinTitle or ahk_id>` for a window, or `custom <x1> <y1> <x2> <y2>` for a screen rectangle. Rectangle coordinates are exclusive at the far edge. Optional flags are `--max <pixels>` (longest saved side, zero preserves full resolution) and `--out <path.png>`. Put these strings after `--` in `acu run`.

The script prints `saved=`, `image=`, `source=`, and `scale=` lines in the run's `output`. Read the saved PNG separately; the tool does not automatically return image content. An image point (px,py) maps to screen coordinates (sourceX + px * scale, sourceY + py * scale). App capture does not change the foreground and can render a covered window; minimized windows are errors.

Without `--out`, only the newest thirty managed screenshots are retained. An explicit output is not pruned and may overwrite an existing file; select only an authorized path.
