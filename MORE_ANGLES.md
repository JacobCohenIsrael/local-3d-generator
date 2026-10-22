# Hybrid photo selection with a four-view model

Upload one required **front** photo, optional labelled **left/back/right** anchors,
and extra photos by dragging a group into the drop zone or browsing. No angle
numbers are required. Up to 16 photos total / 48 MiB combined are supported.

Strata vision compares each usable extra with the labelled anchors. The app
uses its strictly validated observations plus deterministic clarity metrics to
select at most four compatible inputs. Every original and cutout is retained,
and every photo receives a selected/skipped reason.

**Only selected photos condition Hunyuan.** This is candidate selection; it does
not fuse every upload. Reconstruction quality gains have not been benchmarked.

## Setup

The existing Strata 0.1.41 / Qwen Coder IQ1_M installation and matching
`strata-vision.exe` helper are required. Prepare the ordinary project config as
described in README, then run:

```powershell
.\.venv\Scripts\python.exe -B scripts/setup_strata_vision.py --base-config .\work\strata-native.json
```

This downloads the 907,543,008-byte BF16 encoder into `models/strata-vision/`,
verifies SHA-256, and creates the ignored project-owned `work/strata-vision.json`.
The original config and shared installation are preserved. No engine upgrade or
inference occurs during setup. The encoder remains under its upstream terms.

Encoder source: [ISTA-DASLab model repository](https://huggingface.co/ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF/tree/ed59f92082b1e93c0e96d60a8b11aab089b52f09).
Revision: `ed59f92082b1e93c0e96d60a8b11aab089b52f09`.
SHA-256: `b1a82259702816a5330d7bd7607cd9676b11780e79ff7348c21103ff3ce49bd0`.

The vision config uses GPU encoding, a small explicit resident expert RAM budget,
direct expert reads, bounded prompt batches and mapped-page release. These
settings reduce host memory pressure; they can increase disk reads and latency.
`--cpu` configures CPU encoding but is not part of the live validation.

## Automatic decisions

- The front photo is required and must contain usable foreground. It establishes
  the baseline orientation. Optional labelled sides are trusted anchors.
- A visual request contains the prepared anchors plus one extra, never user
  filenames or asset names as instructions. The image encoder supplies actual
  visual embeddings to Strata; this is not metadata-only planning.
- The observation schema is fixed: `direction`, `confidence`, `same_subject`,
  `pose_consistent`, `usable`, `reason`. No generated commands, paths or settings
  are executed. Invalid output skips that candidate without an inference retry.
- Missing directions can be filled when model-reported confidence is at least
  0.85 and subject, pose and visibility checks all pass. Ambiguous, diagonal,
  above/below, obstructed, mismatched or changed-pose photos are skipped.
- Labelled anchors stay unless an extra is compatible, confidence is at least
  0.95, and its CPU quality score exceeds the anchor by at least 0.15. That score
  combines foreground sharpness, source resolution and exposure. Ties are stable.
- Exact duplicate bytes cannot establish an independent view. Copies of anchors
  skip visual inference. Confidence is model-reported, not a calibrated
  probability; subject/pose checks are fallible and are not identity verification.
- At most one photo per supported direction reaches the shape model. One selected
  image uses Hunyuan3D-2.1; two to four use Hunyuan3D-2mv. Top/bottom views have no
  supported conditioning slot in this workflow.

The settings planner remains a separate advanced option. Extras automatically
trigger vision even with the preset planner. Labelled photos alone need no
Strata runtime. A missing vision configuration stops extra-photo jobs with a
setup message; an engine error stops the stage with diagnostics. It does not
silently pretend the extras were analysed.

## Runtime and evidence

Preparation is sequential on CPU. Recognition runs in its own hidden owned
Windows process tree with a 900-second deadline, cancellation, no automatic
restart and an available-RAM guard. It needs 12 GiB available RAM before loading
and stops below 2 GiB. The engine and encoder must exit and release allocations
before generation; RAM/VRAM are checked again before loading Hunyuan. Existing
mesh attempt limits remain unchanged.

Per-job files under ignored `outputs/web-jobs/JOB_ID/`:

- `uploads/`: unchanged originals.
- `prepared/candidates/` and `prepared-records.json`: cutouts, hashes, CPU metrics.
- `vision/`: actual model replies, engine diagnostics and image exchanges.
- `vision-analysis.json`: validated observations and token/request metadata.
- `view-selection.json`: every decision and the actual selected mapping.
- `prepared/provenance.json`: selected canonical cutout hashes and source IDs.

The UI shows the audit; the selection report is downloadable and included in the
Unity ZIP. `submitted_view_count` counts all uploads; `views_used` contains only
the selected model directions. Legacy stored jobs and their old angle-based
selection manifests remain readable.

## API

```json
{
  "name": "Example object",
  "views": {"front": "BASE64_IMAGE", "left": "BASE64_IMAGE"},
  "extra_views": [
    {"name": "another photo", "image": "BASE64_IMAGE"},
    {"name": "another reference", "image": "BASE64_IMAGE"}
  ],
  "view_strategy": "hybrid_vision_v1"
}
```

`views.front` is required. Extra entries omit `azimuth`; submitting one is rejected
with a migration message. Limits remain 12 MiB / 20 megapixels per image, 16
images / 48 MiB combined, and 68 MiB encoded HTTP body. User names are display
metadata; storage IDs and paths are generated by the server.

## Model boundary and verification

The pinned Tencent `MVImageProcessorV2` maps front/left/back/right to four
indices. `DinoImageEncoderMV` constructs four sinusoidal direction embeddings;
this is not an arbitrary camera-pose interface. A different supported backend
or trained extension is needed for true all-view reconstruction.

- [View mapping](https://github.com/Tencent-Hunyuan/Hunyuan3D-2/blob/f8db63096c8282cb27354314d896feba5ba6ff8a/hy3dgen/shapegen/preprocessors.py)
- [Four-view conditioner](https://github.com/Tencent-Hunyuan/Hunyuan3D-2/blob/f8db63096c8282cb27354314d896feba5ba6ff8a/hy3dgen/shapegen/models/conditioner.py)
- [Strata vision documentation](https://github.com/Niko1221/Strata/blob/v0.1.41/docs/DETAILS.md#images-vision)

Automated tests cover angle-free requests, caps, trusted anchors, conservative
replacement, missing/uncertain/invalid observations, incompatible subjects and
poses, duplicates, provenance, selected model inputs, audit packaging, HTTP
boundaries and stopping before generation after a vision failure. A JavaScript
interaction test exercises multi-file drops, removal and angle-free submission.
Run:

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s scripts -p 'test_*.py'
node scripts/test_upload_ui.mjs
node --check web/app.js
```

A real Strata vision check using the official front as its sole anchor selected
the unlabelled left/back example images and excluded a repeated front. Native
HTTP/browser validation then completed that selection, Hunyuan generation and a
50,000-triangle FBX, independently reopened by Blender. A separate real six-photo
check retained three labelled anchors, declined an equivalent alternate, rejected
a different character and skipped a duplicate. These examples do not establish
general recognition accuracy or reconstruction quality. Details are recorded in NEXT_STEPS.md. Private
observations, exact host resources, outputs and screenshots stay ignored.
