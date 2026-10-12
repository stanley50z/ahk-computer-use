# Adobe Illustrator Pen and Export assets

New v0.6 actors receive two files separately:

- `Cloud9-Pen-Starter.ai`: unchanged blank document, one 800 × 800-point RGB artboard named `Drawing`, one empty visible/unlocked layer named `Drawing`. No artwork, embedded reference, reference layer or hidden solution. SHA-256: `d2197b639dd7c9d4528962f8252bdbb0e6d250551f16675324ea95e2e0d99445`.
- `Cloud9-Reference.png`: 800 × 800 RGB, opaque white background, solid blue #00AEEF. SHA-256: `03dd860809cbfa143c35b50bd78fbdb8e43346e47d76e9aba5afc94a4e00a32c`.

## Reference provenance and framing

The new reference is downsampled from the official lossless `PNG/Icon/C9_Icon_Blue_AllMode.png` in the package already supplied by the user, not converted from the JPEG. Official source: 2657 × 2657 RGBA, SHA-256 `49d3d3dd25a58c216fa92557e4d15423bf599952ccbc97a49dd0ca29986ecebb`. Its solid fill is #00AEEF. The old JPEG's dominant #00ADEF is one green level lower, consistent with its lossy conversion.

The official PNG has different framing. The fixed maintainer transform area-averages the source's alpha coverage to **550 × 551** with Pillow BOX, retains the official solid #00AEEF, composites it at **(143,120)** onto an 800 × 800 opaque white canvas, and saves RGB PNG with 72-ppi metadata. Coverage sampling avoids invented interior colors from RGBA resampling and ringing; edge pixels are the official blue blended with white. The small per-axis scale difference preserves the old reference's 550 × 379 blue footprint rather than introducing a one-pixel height change. Under the benchmark's foreground classification the resulting bounds are **(143,206,693,585)**, with exclusive right/bottom edges, matching the previous reference's placement and size. This transform applies to the prepared reference only; actor outputs are never aligned or rescaled during grading.

After verifying the official source hash above, this Pillow transformation reproduces the preparation (run from the repository root with `source_path` pointing to that official PNG):

```python
from PIL import Image

with Image.open(source_path) as source:
    coverage = source.getchannel('A').resize((550, 551), Image.Resampling.BOX)
logo = Image.new('RGBA', (550, 551), (0, 174, 239, 255))
logo.putalpha(coverage)
canvas = Image.new('RGBA', (800, 800), 'white')
canvas.alpha_composite(logo, (143, 120))
canvas.convert('RGB').save('bench/assets/illustrator-pen-export/Cloud9-Reference.png', dpi=(72, 72))
```

Construction script, source/output fingerprints and logs: `.pi/benchmark-v06/build-reference.py`, `reference-build.json`, `reference-build.log`; failures persist `reference-build-crash.txt`. The original official source and historical reference are unchanged. `Cloud9-Reference.jpg` is retained here for provenance/history only and is not copied to new actor workspaces. Earlier inspection evidence: [source inspection](../../../docs/reports/testbench-2-source-inspection-2026-10-11.md). Official vectors, source URLs, brand documents and these notes remain maintainer-only context.

## Task and preparation

The starter retains white fill and a black 1-point stroke. Selecting fill #00AEEF and recreating the reference's remaining appearance are actor work. The prompt does not prescribe stroke, opacity, a Color Picker route, visually authored coordinates or restrictions on off-app geometry analysis/code. All Illustrator interactions must use the assigned computer-use tool; the requested drawing method is the Pen tool. The final PNG is the only deliverable.

Normal preparation maximizes the initial window, centers the view and prepares English input, but does not perform a blank export or prime PNG preferences. The starter already has blank-export validation; an explicit desktop-marked maintainer fixture can recheck it. At 72 ppi, exporting its single artboard is 800 × 800 pixels. A white Illustrator canvas is not a white background object; White remains an explicit PNG export setting.

Workspace, Scratch folder and Final output paths are resolved in every actor prompt. The scratch folder is created but is only a location hint; writing scratch elsewhere is not a hidden completion failure. Grading accepts the requested filename or one unique ordinary artboard-suffixed filename without renaming it. Quality is observational, without a numeric shape threshold. Models, three-trial/all-successes aggregation, measurement policy, neutral skills and owned-resource cleanup are unchanged. Historical trials retain their original assets and policies.
