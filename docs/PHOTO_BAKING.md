# Photo base color and textured FBX

## Use

Run the local app, choose **Try an example** or upload consistent labelled
views, and leave **Surface color > Bake colors from your photos** selected.
Submit a job; no Codex process or browser tab is needed for it to finish.
The default web workflow uses the bounded preset planner. Optional Strata
planning is unchanged and does not inspect photo contents.

Download **FBX + colors ZIP**. Extract it and copy the folder into Unity's
Assets. Keep this layout:

```text
asset.fbx
textures/basecolor.png
textures/coverage.png
textures/uvmask.png
material-manifest.json
generation-report.json
export-report.json
UNITY_README.txt
```

Create a material for the Unity render pipeline and assign `basecolor.png` to
Base Map/Albedo with sRGB enabled. Metallic 0 and roughness 0.8 (smoothness 0.2)
are assumed constants. The base color is opaque RGB. Coverage is a diagnostic
mask, **not** transparency. No normal, metallic, roughness, AO or displacement
maps are generated. The downloaded `.blend` packs its color image; the GLB
preview embeds it. FBX alone needs its external PNG.

## Processing and limits

1. Generate the mesh with the existing shape model and preserve `raw.glb`.
2. Blender cleans/reduces, sets meter scale and grounding, then uses Smart UV
   Project. Geometry and UVs are frozen in a prepared `.blend` and numeric NPZ.
3. A separate CPU process checks prepared-photo hashes and fits each cardinal
   orthographic camera to the foreground silhouette. Elevation is searched at
   0, 10 and 20 degrees, with bounded scale/translation adjustments. Level views
   are preferred: a 10-degree tilt must improve IoU by more than 0.02 to win.
   This avoids tilting fine details for a negligible silhouette improvement. Fits below
   0.40 silhouette IoU are rejected; this score does not establish feature alignment.
4. Rasterize the UV surface, project its texels, and use a depth buffer, front
   facing normals and alpha/edge confidence to reject hidden samples. Choose
   the highest-confidence visible source per texel. Do not average displaced
   eyes/edges from different photos into ghost details. Texture sampling uses
   linear RGB, then stores the chosen color as sRGB.
5. Unknown surface texels receive neutral gray. Only gutters outside UV islands
   receive up to four pixels of padding. Diagnostic masks distinguish UV
   coverage and trusted photo samples. At least 20% UV-texel coverage is required.
6. Apply the material, export, then independently reopen the FBX and verify its
   bounds/counts, UV presence and color-image hash. Render the reopened FBX.
   Package relative texture paths, reports and import notes in the ZIP.

This is approximate photo projection. It is not calibrated photogrammetry,
intrinsic-image decomposition or neural painting. Perspective, inconsistent
poses, shadows, reflections and inaccurate geometry can leave seams or misplaced
features. A good silhouette fit can still put a facial feature in the wrong
place. Use clean cutouts, similar camera distance and the same pose in every view.
Unseen surfaces stay gray; no invented back view or inpainting is hidden in coverage.

Coverage is **covered UV surface texels / all UV surface texels**, not physical
area, similarity or game readiness. Inspect both the textured and wireframe
views. **Hide colors / Show colors** switches the preview between textured and
clay rendering so projection artifacts can be distinguished from mesh defects.
The export is static and unrigged; Unity Editor material import has not
been verified.

The UI uses 1024-pixel maps. The API accepts `texture: "photo_basecolor"` with
`texture_size: 512` or `1024`; missing `texture` preserves the older untextured
API behavior. `texture: "none"` skips this path. No new neural weights, CUDA
extensions or Python dependencies are needed beyond the existing installation.

UV preparation, photo baking and export have separate owned process trees and
deadlines (300, 600 and 300 seconds), within the existing 3600-second job limit.
A nonzero bake exit preserves the mesh and produces a warned untextured export,
with logs retained. Cancellation, timeout and ownership failures propagate and
stop processing. There is no automatic texture retry or inference crash restart.

## Checks

The official front/left/back demo completed through the browser and HTTP queue
with a fresh Hunyuan3D-2mv inference, 30 steps, 256 extraction resolution and one
attempt. The corrected run took **177 seconds**, exported **50,000 triangles**
at **1.8 meters**, and covered **75.7% of UV surface texels**. A relocated ZIP
passed a fresh Blender import with relative image resolution, UVs, matching
geometry/bounds and hashes. The GLB embedded the same PNG pixels. All owned
stage processes stopped and the raw mesh hash remained unchanged.

An earlier visual check exposed doubled facial colors from cross-view averaging
and an overfitted camera tilt. Selecting one source per texel and preferring
level cardinal cameras improved the same mesh, then passed the fresh run above.
The browser's textured, clay and wireframe modes and actual ZIP download were
verified. Remaining seams, uncovered gray areas and shape inaccuracies are
visible limitations; passing file checks does not establish likeness. All
**24 regression tests** passed. No Unity Editor import is claimed.

Run the regression suite without loading GPU models:

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s scripts -p 'test_*.py'
```

To verify a downloaded ZIP independently, extract it to a new folder, then run
Blender (replace `blender` with the executable if it is not on PATH):

```powershell
blender --background --factory-startup --python-exit-code 1 --python scripts/validate_texture_package.py -- --asset-dir work/extracted --report work/texture-check.json
```

The checker validates the package hashes, imported geometry, UVs and connected
base-color image, and requires that the image resolves **inside the extracted
folder**. It does not depend on cached Blender images or the original job path.
Local detailed logs, source snapshots, telemetry and generated artifacts remain
under ignored `work/` and `outputs/` directories.
