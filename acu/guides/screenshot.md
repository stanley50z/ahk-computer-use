# Interpret a screenshot

Use `fullscreen` for one monitor, `app` with an observed `target` for a window, or `custom` with `rect` = [x1,y1,x2,y2] for a screen rectangle. Rectangle coordinates are exclusive at the far edge. `max` bounds the longest saved side; zero preserves full resolution.

The result includes the saved PNG path, image dimensions, source rectangle, and scale. An image point (px,py) maps to screen coordinates (sourceX + px * scale, sourceY + py * scale). App capture does not change the foreground and can render a covered window; minimized windows are errors.

Without `out`, only the newest thirty managed screenshots are retained. An explicit `out` is not pruned and may overwrite an existing file; select only an authorized path. MCP returns the image as well as metadata; CLI callers read the saved PNG.
