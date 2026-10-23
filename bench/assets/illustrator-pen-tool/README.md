# Adobe Illustrator Pen Tool assets

Current v0.11 actors receive the same two separate inputs introduced in v0.7:

- `Cloud9-Pen-Starter.ai`: unchanged blank document, one 800 × 800-point RGB artboard named `Drawing`, one empty visible/unlocked layer named `Drawing`. No artwork, embedded reference, reference layer or hidden solution. SHA-256: `d2197b639dd7c9d4528962f8252bdbb0e6d250551f16675324ea95e2e0d99445`.
- `Cloud9-Reference.png`: 800 × 800 RGB, opaque white background, solid blue #00AEEF. SHA-256: `03dd860809cbfa143c35b50bd78fbdb8e43346e47d76e9aba5afc94a4e00a32c`. Not in the repository; build it once per checkout with `uv run python bench/build_reference.py "<package>/PNG/Icon/C9_Icon_Blue_AllMode.png"` after downloading Cloud9's [brand assets](https://cloud9.gg/brand-assets/). The file is gitignored.

## Third-party rights

The reference is derived from third-party logo artwork, not covered by ACU's MIT license. Original source: [Cloud9's official brand-assets page](https://cloud9.gg/brand-assets/) and its [logo download](http://c9.gg/logos). The source package's brand guidelines and [Cloud9's terms](https://cloud9.gg/terms-of-service/) apply; no open-source license or explicit redistribution grant was found, so the repository ships only the build script, not the artwork. Earlier commits contained the reference PNG and an older JPEG.

No affiliation with or endorsement by Cloud9 is claimed. The blank, bench-created `Cloud9-Pen-Starter.ai` contains no logo artwork and is separate from the third-party reference.

## Reference provenance and framing

The reference PNG is downsampled from the official lossless `PNG/Icon/C9_Icon_Blue_AllMode.png` in the package already supplied by the user, not converted from the JPEG. Official source: 2657 × 2657 RGBA, SHA-256 `49d3d3dd25a58c216fa92557e4d15423bf599952ccbc97a49dd0ca29986ecebb`. Its solid fill is #00AEEF. The old JPEG's dominant #00ADEF is one green level lower, consistent with its lossy conversion.

The official PNG has different framing. The fixed maintainer transform area-averages the source's alpha coverage to **550 × 551** with Pillow BOX, retains the official solid #00AEEF, composites it at **(143,120)** onto an 800 × 800 opaque white canvas, and saves RGB PNG with 72-ppi metadata. Coverage sampling avoids invented interior colors from RGBA resampling and ringing; edge pixels are the official blue blended with white. The small per-axis scale difference preserves the old reference's 550 × 379 blue footprint rather than introducing a one-pixel height change. Under the benchmark's foreground classification the resulting bounds are **(143,206,693,585)**, with exclusive right/bottom edges, matching the previous reference's placement and size. This transform applies to the prepared reference only; actor outputs are never aligned or rescaled during grading.

`bench/build_reference.py` verifies the official source hash above, then applies this Pillow transformation and checks the output hash:

```python
from PIL import Image

with Image.open(source_path) as source:
    coverage = source.getchannel('A').resize((550, 551), Image.Resampling.BOX)
logo = Image.new('RGBA', (550, 551), (0, 174, 239, 255))
logo.putalpha(coverage)
canvas = Image.new('RGBA', (800, 800), 'white')
canvas.alpha_composite(logo, (143, 120))
canvas.convert('RGB').save('bench/assets/illustrator-pen-tool/Cloud9-Reference.png', dpi=(72, 72))
```

The original construction evidence is local: `.pi/benchmark-v06/build-reference.py`, `reference-build.json`, `reference-build.log`. The old `Cloud9-Reference.jpg` was never copied to v0.7+ actor workspaces. Earlier inspection evidence: [source inspection](../../../docs/reports/testbench-2-source-inspection-2026-10-11.md). Official vectors, source URLs, brand documents and these notes remain maintainer-only context.

## Task and preparation

The starter retains white fill and a black 1-point stroke. The [v0.11 prompt](../../scenarios/illustrator-pen-tool.md) asks the actor to use fill #00AEEF and no stroke, draw genuine Pen-tool Bézier curves rather than faceted approximations, and leave the finished drawing open. Every Illustrator interaction must use the assigned computer-use tool. No actor export, AI save or result manifest is requested. Off-app geometry analysis/code and ordinary GUI editing, recovery and navigation are not prohibited.

Normal preparation maximizes the initial window, resets Illustrator's Getting Started workspace, centers the view at 100%, prepares English input, and enables and reads back Smart Guides and Snap to Point. Actors may change snapping during the trial. Preparation does not perform a blank export or prime PNG preferences.

After the actor stops and the conduct audit finishes, maintainer-only code inspects the live owned drawing and exports it unchanged to `<run>/grading/Cloud9-Recreated.png`. The maintainer export policy requires 800 × 800 pixels, 72-ppi metadata, an opaque white background and non-interlaced PNG encoding. These are evidence-collection requirements, not actor deliverables. The controller allows at most two export attempts, verifies unchanged pixels during metadata encoding, and preserves an unexported drawing on export failure. It does not repair artwork, align or rescale outputs, or grade unsolicited actor exports in place of its own evidence.

Workspace and Scratch folder paths are rendered in every actor prompt; there is no Final output path. Scratch outside the workspace is not itself a failure, but guarded-file changes and verified screenshot overwrites of pre-existing files fail conduct. Shape quality is observational, without a numeric pass threshold. Full-session review is still needed for Pen construction, faceted curves in mixed paths and no-stroke compliance; native evidence records each path's `stroked` flag, but the automatic verdict has no separate no-stroke gate. The [benchmark guide](../../README.md) defines models, metrics, recovery, three-trial/all-successes aggregation and owned-resource cleanup. Historical actor-export tasks and their assets, verdicts and measurements remain unchanged.
