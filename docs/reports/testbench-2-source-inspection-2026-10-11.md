# Testbench 2: Cloud9 source inspection

Maintainer-only preparation notes. Do not copy this document, the source package, the official vectors, or the guidelines into an actor workspace. The actor needs a prepared drawing document and the drawing/export task, not asset provenance or brand research.

## Request and scope

Specification and continuing design: [issue #10](https://github.com/stanley50z/ahk-computer-use/issues/10).

The user proposed recreating the Cloud9 icon with Adobe Illustrator's Pen tool using the official JPEG as the visual reference, then comparing the output with the official artwork. Testbench 2 should test only drawing the shape with the Pen tool and exporting with the requested parameters. The user wants to remove unrelated decisions, not selectively remove actions from timing. Supply explicit values and instructions for supporting settings. Measure the actor's task continuously, including every setup, appearance, drawing, saving, and export action it performs. Do not time individual steps or subtract selected steps. A fixed starter may establish the common initial state before the actor begins; independent grading follows the task. The actor selects the specified fill color rather than receiving a preconfigured fill. No benchmark trials were authorized or run during this inspection.

The source of the official files is **http://c9.gg/logos**, recorded at the user's request. This URL must not appear in the actor prompt or starter document. It is provenance supplied by the user, not a web-source verification performed in this session.

## Local sources

Original files:

- `C:\Users\13982\Downloads\Cloud9 Icon.jpg`
- `C:\Users\13982\Downloads\Cloud9 Icon.ai`

Expanded official package:

`C:\Users\13982\Downloads\Cloud9 Logos\Cloud9 Logos`

The package includes `2026 Logo Guidelines.pdf`, JPEG, PNG, PSD, SVG, and Vector folders. `JPEG/Icon/Blue.jpg` and `Vector/Cloud9 Icon.ai` are byte-identical to the original files.

| Asset | Bytes | SHA-256 |
| --- | ---: | --- |
| Original JPEG / `JPEG/Icon/Blue.jpg` | 74,860 | `715a4a7e15cb0e5ecc3452ef53585971eb7cb9ca5e61334c10bf1de443333231` |
| Original AI / `Vector/Cloud9 Icon.ai` | 229,458 | `fb1813dbf8ceb30f046f10b2dd63ec4f0607bdbd69841e8b694662a18f0658aa` |
| `PNG/Icon/C9_Icon_Blue_AllMode.png` | 89,700 | `49d3d3dd25a58c216fa92557e4d15423bf599952ccbc97a49dd0ca29986ecebb` |

## Official AI

Opened in the installed Adobe Illustrator 2026. Native UI observations:

- RGB/CPU Preview.
- One artboard, `Artboard 1`, Custom preset, 5 × 5 inches (360 × 360 points).
- Artboard fill is Transparent (Default); the white canvas does not imply a white background object.
- Document units are inches.
- Artwork selects as a Group, centered at X = 2.5 in and Y = 2.5 in with the center reference point active. Displayed size: W = 4.1305 in, H = 2.8436 in.
- Fill `#00AEEF` / RGB `(0, 174, 239)`, no stroke, opacity 100%.

The embedded PDF is PDF 1.6, one 360 × 360-point page, no raster images, one filled drawing operation. Metadata identifies Adobe Illustrator 27.0 (Windows), Adobe PDF library 16.07, and a January 2023 save. The XMP startup profile is Web. PDF drawing extraction includes Bezier control points in its reported rectangle; that rectangle is not the visible logo bounds and must not be used as a native geometric-bounds measurement.

### Calibration export

Used Illustrator's File > Export > Export As > PNG:

- Use Artboards enabled for the calibration export.
- Resolution Other: 160 ppi.
- Anti-aliasing: Art Optimized (Supersampling).
- Background Color: White.
- Interlaced left off.

Observed output: 800 × 800 pixels, RGB, approximately 159.9946 ppi in PNG metadata. This proves an export recipe on this installation; it does **not** establish the settings used to create the official JPEG. These are distinct claims.

The PNG Options dialog initially showed Screen (72 ppi), Type Optimized (Hinted), Transparent. Those were session defaults, not recovered official-file export parameters. A custom resolution field advertised UIA value support, but setting Value failed; clicking it and entering text succeeded. The Export file-name control accepted the basename but saved in Downloads rather than the supplied full destination. The temporary export was copied into inspection evidence and removed from Downloads.

## Raster sources and framing mismatch

The JPEG is 800 × 800, RGB, white background, 72-dpi metadata, no embedded ICC profile. Its XMP says Photoshop converted PNG to JPEG in August 2022. Its most common interior blue is `(0, 173, 239)`, one green level below the native vector fill, consistent with lossy conversion.

The official PNG is 2657 × 2657, RGBA, approximately 72-dpi metadata, no embedded ICC profile. Its solid blue is `(0, 174, 239)` and its background is transparent. The logo extends almost to both horizontal edges; it is not framed like the JPEG or AI.

For comparison, classify blue foreground as R < 128, G > 100, B > 150, and alpha > 127 when present. Bounds below use an exclusive right/bottom edge and are raster measurements, not exact vector bounds:

| Raster | Canvas | Blue foreground bounds | Foreground pixels |
| --- | --- | --- | ---: |
| Official JPEG | 800 × 800 | `(143, 206, 693, 585)` | 96,019 |
| AI calibration PNG | 800 × 800 | `(70, 173, 730, 627)` | 138,483 |
| Official PNG | 2657 × 2657 | `(0, 414, 2656, 2243)` | Not counted in this inspection |

The AI's exported logo is about 20% wider than the JPEG's. The JPEG is slightly offset. The direct, unaligned JPEG-vs-AI mask intersection-over-union is only 0.45434. A pixel comparison would reject the official artwork itself unless the reference preparation fixes the framing first.

The package's SVG files also differ. `SVG/Blue.svg` uses a 1920-square viewBox and fill `#28ABE2`. `SVG/Cloud9 Logo_Blue_800x800px.svg` uses an 800-square viewBox, a white rectangle, and `#00AEEF`, but different framing again. Do not select a file solely because its name says blue or 800 × 800.

## Guidelines

`2026 Logo Guidelines.pdf` has seven pages and is dated November 2025 on its cover.

- Pages 2–4 distinguish icon, stacked, and horizontal versions and describe clear space.
- Page 6 specifies C9 blue `#00AEEF`, white `#FFFFFF`, black `#000000`, and Pantone 2995 C for print only.
- Page 5 explicitly says not to recreate, redraw, distort, or recolor the logo. A benchmark reconstruction should remain an evaluation exercise, not be represented as an official or brand-approved replacement. The guidelines themselves are not part of the actor's task.

## Proposed preparation and checks (not yet approved)

The user's scope is Pen-tool drawing and export. Selecting the stated fill color is part of that workflow; the proposed preconfigured blue fill is withdrawn. The user then clarified the measurement principle: the actor should not have to decide unrelated settings, but any instructed actions it performs are still part of one continuous task measurement. Do not introduce per-step timing exclusions. Earlier wording that put all supporting setup outside timing was too broad. Artboard and reference preparation are possible starter choices, not an approved requirement; if the actor performs them, count them.

Created starter (authorized by the user, then revised to remove the proposed reference layer):

- `bench/assets/testbench-2/Cloud9-Pen-Starter.ai`: a fresh 800 × 800-point RGB document, one artboard named `Drawing`, one empty visible/unlocked/printable layer named `Drawing`.
- `bench/assets/testbench-2/Cloud9-Reference.jpg`: a separate, byte-identical copy of the official 800 × 800 JPEG. It is not embedded or linked in the starter. The actor receives the two files plainly; no locked tracing reference is prepared.
- Default appearance is white fill and black 1-point stroke. Do not preconfigure blue fill. State `#00AEEF` in the task and let the actor select it as part of the timed workflow. Specifying no stroke remains the proposed instruction matching the official artwork.
- No artwork items, official vector paths, raster images, hidden solution layer, anchor guides, source URL, or brand-guideline text in the starter.
- Stable viewport, document state, and input language remain preparation concerns for repeatable trials. The Chinese-IME shortcut issue is deferred at the user's request; settle it before benchmark trials rather than treating it as Pen-tool difficulty.

The starter was created through a maintainer-only JSX script invoked through Illustrator's Other Script dialog. This preparation method is not permission for the benchmark actor to generate geometry with Illustrator scripting. Reopened the saved AI and verified native RGB mode, 800 × 800 dimensions, one unlocked layer, zero page/path/raster/placed items, ordinary appearance defaults, and saved state. Independent PDF inspection found a blank 800 × 800 page with no drawings, images, or text. A blank PNG calibration export was exactly 800 × 800 RGB and entirely white. Both original source-file hashes remained unchanged.

Proposed output: saved editable AI and 800 × 800 PNG, Use Artboards, 72 ppi, Art Optimized (Supersampling), white background, not interlaced. These are benchmark choices, not historical official export settings. The export-dialog defaults must be prepared consistently for every arm; do not let later trials inherit an earlier trial's settings accidentally.

Proposed grading:

- Check PNG file type, exact dimensions, opacity/background, blue fill, and placement without resizing or auto-aligning the submitted output.
- Compare foreground masks and boundary error with tolerance for hand-placed Bezier curves and antialiasing. Do not use exact RGB equality with the JPEG or full-canvas mean error alone: JPEG artifacts and the large white background would distort the result.
- Keep shape, export, and method verdicts separate. Transcript/script review is required to verify Pen-tool use and exclude Image Trace, imported/generated vector geometry, embedded-raster substitution, and direct Illustrator scripting during the actor trial. A matching PNG cannot establish how it was made.
- Inspect the saved AI independently: new visible artwork must be editable paths, the separately supplied reference must not substitute for the drawing, and no raster should masquerade as the recreated artwork. Do not compare AI bytes, exact anchor counts, or a required path topology.
- For a secondary comparison against the official vector/PNG shape, prepare and freeze any registration transform outside the trial. Do not align an actor's output after the fact in a way that conceals placement/export mistakes.
- Calibrate scoring tolerances against known-good exports and deliberate contour, fill, translation, crop, transparency, and resolution errors before setting a pass threshold. No numeric pass threshold is established yet.

Confirmed decisions:

- Give the actor the fill color `#00AEEF`; the actor selects it during the task. The earlier proposal to preconfigure blue fill is withdrawn.
- Supply concrete instructions for supporting settings rather than requiring the actor to research or choose them.
- Measure the task continuously. Every action the actor performs counts; no per-step measurements or selective subtraction.

- The user authorized creating the starter and then rejected a locked reference layer. The actor should receive the reference image and starter AI as separate files. This replaces the embedded-reference proposal, including its non-printing-layer/export checks.

Related decisions have been revisited: the starter remains a blank 800 × 800 RGB document; selecting appearance and executing export settings remain actor work; continuous task timing is unchanged. No reference placement or arrangement is forced in the starter. Whether an actor chooses to place the supplied raster as a drawing aid is not settled by this request; a submitted raster cannot substitute for the vector reconstruction.

The starter and separate JPEG are now created. A runnable Testbench 2, final actor prompt, scoring thresholds, and benchmark trials are not part of this starter-file change.

## Evidence and debugging

Raw local preparation evidence is under:

`C:\Users\13982\ahk-computer-use\.pi\testbench-2-design\`

Important files: `file-inspection.json`, `package-inspection.json`, `source-comparison.json`, `guidelines.txt`, `official-ai-xmp.xml`, `official-ai-export.png`, `artboard-properties.png`, `artwork.png`, `color.png`, and `png-options.png`. Logs: `file-inspection.log`, `package-inspection.log`, `source-comparison.log`, `starter-build.log`, `starter-reopen.log`, and `starter-file-check.log`. Starter evidence also includes `starter-created.png` and `starter-empty-export.png`. This directory is gitignored preparation evidence, not actor input. A COM automation attempt during starter preparation timed out; the Other Script UI route succeeded instead.

ACU run log: `C:\Users\13982\AppData\Local\ACU\logs\runs.jsonl`.

ACU crash reports: `C:\Users\13982\AppData\Local\ACU\crashes\`. This inspection encountered an ambiguous two-window launch, cursor-takeover notices (desktop actions paused until the user approved continuing), one unsupported UIA Value set, and a temporary Windows paging-file exhaustion error. Keep those separate from future benchmark results.

Original source hashes were captured before inspection and verified unchanged after starter creation. Maintainer-only preparation scripts and their logs are retained in the evidence directory to explain and reproduce this asset creation; they are not actor input. No benchmark agent or temporary test server was started. Closed the reopened starter after verification so Illustrator removed its temporary file from the asset directory. The original inspection document remained open with an unsaved-state indicator; it was preserved rather than saving or discarding uncertain in-memory changes. Its on-disk hash is unchanged.
