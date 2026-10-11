# Testbench 2 starter assets

Give the agent these two files separately:

- `Cloud9-Pen-Starter.ai`: a blank Illustrator document with one 800 × 800-point RGB artboard named `Drawing` and one empty, visible, unlocked layer named `Drawing`. It contains no paths, raster images, placed files, reference layers, or hidden artwork.
- `Cloud9-Reference.jpg`: the 800 × 800 reference image. It is not embedded or linked in the starter.

The starter retains white fill and a black 1-point stroke. The agent must select the task's specified fill color and stroke setting; these actions count toward the task time. Saving and exporting also count. There is no per-step timing subtraction.

At 72 ppi, an artboard-clipped export is 800 × 800 pixels. A white canvas in Illustrator is not a white background object; specify White in the PNG export dialog when the task requires an opaque white background.

The starter was reopened and checked in Illustrator: RGB, one artboard, one unlocked layer, zero artwork items. A calibration export of the blank starter was 800 × 800 RGB and entirely white. The runnable pilot is `bench/scenarios/testbench-2.md` and the runner's `--scenario testbench-2` profile; see `bench/README.md`. The actor may place the separate JPEG as a Pen-tool tracing aid, but must remove it before saving the editable AI. Anchor/handle positions must be literal, visually authored coordinates; code may map/replay them but not generate them. Numeric shape pass thresholds remain uncalibrated.
