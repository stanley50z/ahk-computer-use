# Adobe Illustrator Pen and Export starter assets

Give the agent these two files separately:

- `Cloud9-Pen-Starter.ai`: a blank Illustrator document with one 800 × 800-point RGB artboard named `Drawing` and one empty, visible, unlocked layer named `Drawing`. It contains no paths, raster images, placed files, reference layers, or hidden artwork.
- `Cloud9-Reference.jpg`: the 800 × 800 reference image. It is not embedded or linked in the starter.

The starter retains white fill and a black 1-point stroke. The agent must select the task's specified fill color and stroke setting. Appearance selection, drawing, saving and exporting remain actor work and contribute to generated tokens and computer-use call durations. End-to-end model-response time is not a benchmark score; see `bench/README.md` for the measurement policy.

At 72 ppi, an artboard-clipped export is 800 × 800 pixels. A white canvas in Illustrator is not a white background object; specify White in the PNG export dialog when the task requires an opaque white background.

The starter was reopened and checked in Illustrator: RGB, one artboard, one unlocked layer, zero artwork items. A calibration export of the blank starter was 800 × 800 RGB and entirely white. The runnable pilot is `bench/scenarios/illustrator-pen-export.md` and the runner's `--scenario illustrator-pen-export` profile; see `bench/README.md`. The actor may place the separate JPEG as a Pen-tool tracing aid, but must remove it before exporting. The sole deliverable is Cloud9-Recreated.png; no report JSON or saved editable AI is required. Anchor/handle positions must be literal, visually authored coordinates; code may map/replay them but not generate them. The v0.4 task permits one drawing attempt, not full redraws or repeated refinement. Shape quality is measured afterward without a numeric pass threshold.
