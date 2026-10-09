# A screenshot captures one display, one window, or one rectangle and reports its source and scale

The agent converts image points to screen points itself, so every capture prints the source rectangle and the scale instead of resizing to a fixed canvas the way vendor computer-use tools do. Fullscreen captures one display rather than the whole virtual desktop because the second display starts at x = 3840 and a single origin keeps the conversion to one multiplication and one addition. The app action asks the window to render itself instead of copying the screen, so a covered window still shows its own content and a capture never changes the foreground, which the restore rules depend on.

## Consequences

- A rectangle capture at full size is the close look; there is no separate zoom.
- Downscaling to 1280 pixels on the longest side is the default because a 3840-pixel capture is more than a vision model needs and slower to read; the scale line makes the choice reversible per capture.
