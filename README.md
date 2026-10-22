# Local 3D Generator

Turn reference images into a static 3D mesh on a Windows PC, then download an
FBX to import into Unity. The local web app handles background removal,
generation, geometry checks, photo color baking, Blender export and a rotatable preview. Submitted
jobs run without Codex or an open browser tab.

- **One image:** Hunyuan3D-2.1.
- **Two to four selected views:** Hunyuan3D-2mv uses front/left/back/right inputs.
- **Extra photos:** upload up to 16 total without angle numbers. Local Strata
  vision selects compatible views and explains every choice; at most four
  selected photos condition the model. See [MORE_ANGLES.md](MORE_ANGLES.md).
- **Photo colors:** project selected photos onto UVs; optional estimated color
  extension reduces gray gaps while preserving a separate photo-coverage mask.
- **Downloads:** FBX with external color PNGs in a Unity ZIP, Blender project and report.
- **Local processing:** uploads, models, job history and generated assets stay on
  your machine. Installation downloads dependencies and model files once.

Exports are unrigged static meshes with optional photo base color. This is generative reconstruction,
not a measured 3D scan. Inspect resemblance and geometry before using an asset.

## Requirements

The supported setup is native **64-bit Windows with an NVIDIA CUDA GPU**.
The workflow targets a 16 GB VRAM budget and uses Blender 5.2. Runtime details
are recorded in ignored local reports rather than published host inventories.

Before installing:

1. Install [Git for Windows](https://git-scm.com/download/win) and
   [uv](https://docs.astral.sh/uv/getting-started/installation/), and make sure
   both are available in PowerShell. For uv, Windows Package Manager supports:

   ```powershell
   winget install --id astral-sh.uv -e
   ```

2. Install [Blender](https://www.blender.org/download/). The app discovers Blender
   on PATH or in its standard Windows installation location. To select another
   executable, set a local override before starting the app:

   ```powershell
   $env:LOCAL3D_BLENDER = (Get-Command blender).Source
   ```

   If Blender is not on PATH, assign its full executable path to
   `LOCAL3D_BLENDER` instead. Start the app from that PowerShell window and
   restart an existing server to apply changes. Keep personal overrides out of
   tracked files. Other Blender versions have not been verified by this project.

3. Use an NVIDIA driver compatible with the bundled PyTorch CUDA 12.4 runtime.
   The tested wheel-based setup did not need a separate CUDA Toolkit or compiler.
4. Allow roughly **40 GB of free disk space** for installation, downloads and
   caches; this is an estimate, and generated jobs need additional storage.
   Installation needs internet access and downloads about **12.3 GB of shape
   weights**, plus foreground models and Python dependencies.

At generation time, the app requires at least **8 GiB available system RAM**
and **10,000 MiB free GPU memory**. These are starting checks, not a guarantee
that every quality setting will fit. Other hardware configurations and CPU-only
generation are not verified.

Python 3.10.22 is installed by the setup script into this project. A separate
Python installation, Node.js, Docker, Codex and Strata are not required for the
labelled-photo preset workflow. Extra-photo recognition needs the matching Strata
vision setup below and 12 GiB available RAM. After installing Git/uv, reopen PowerShell so PATH
changes take effect.

## Install

Open PowerShell and run:

```powershell
git clone https://github.com/JacobCohenIsrael/local-3d-generator.git
cd local-3d-generator
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup_web_app.ps1
```

The script creates `.venv/`, installs pinned Python dependencies, fetches pinned
Tencent source revisions, and downloads/validates the shape and foreground
models. Model downloads can take a while. The setup does not start generation.
The command-scoped execution policy applies to that PowerShell process only.

Check that installation succeeded:

```powershell
.\.venv\Scripts\python.exe -B scripts/check_shape_environment.py
.\.venv\Scripts\python.exe -B -m unittest discover -s scripts -p 'test_*.py'
```

The environment check should report CUDA available. The automated tests do not
load model weights or generate meshes. Exact source and model revisions are
recorded in [upstream.json](upstream.json); dependencies are pinned in
[requirements-shape.lock.txt](requirements-shape.lock.txt) and
[requirements-segmentation.txt](requirements-segmentation.txt).

## Start the app

Double-click **[Start Local 3D.cmd](Start%20Local%203D.cmd)** in the project folder.
It starts a hidden local server and opens your browser at:

**[http://127.0.0.1:8765](http://127.0.0.1:8765)**

Or start it from PowerShell:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\start_app.ps1
```

Opening the launcher again reuses a running server. Closing the browser tab
leaves submitted jobs running. After a Windows restart, run the launcher again;
no Windows startup entry is installed. Finished jobs remain in the history.
Queued jobs resume when the app starts, while a job interrupted during execution
is marked interrupted rather than automatically restarted.

For an isolated worktree, use `scripts/start_app.ps1 -Port 8766 -NoBrowser` and
open http://127.0.0.1:8766. To reuse an already prepared environment read-only,
set `LOCAL3D_PYTHON` to its Python executable and `LOCAL3D_ASSET_ROOT` to its
project directory before launching. The latter supplies weights and demo images;
it also supplies the pinned source checkouts under `work/vendor/` read-only.
Jobs, locks, exports and the queue remain in the current worktree. Run only one
GPU generation across these independent apps at a time.

To run with visible logs and an easy shutdown, start the server in a terminal
instead of using the launcher:

```powershell
.\.venv\Scripts\python.exe -B scripts/web_app.py
```

Open the same URL and press **Ctrl+C** in that terminal to stop the server.
If you already launched the hidden server, stop this project's `web_app.py`
Python process first using Task Manager's Details tab and Command line column.
Stopping the server also ends its owned active generation processes. Use the
app's **Cancel generation** button when you only want to stop a job.

## Generate an asset

1. Open the app. For an initial check, choose **Try an example** to load three
   official reference views, then click **Generate asset**.
2. For your own asset, replace/remove the example images. Upload a **front**
   image, then optionally add **left**, **back** and **right** views of the same
   subject. Supported files are JPEG, PNG and WebP, up to 12 MB and 20 megapixels
   each, with a minimum width/height of 64 pixels.
   Drag unlabelled images into **Drop extra photos here** or choose **Browse
   photos**. No angle entry is needed. The combined limit is 16 photos / 48 MiB.
   Labelled views are trusted anchors; Strata vision can fill missing directions
   or replace a clearly weaker anchor. Uncertain photos are skipped with reasons.
3. Keep the subject's pose, framing, lighting and camera distance consistent
   across views. Include the whole subject and avoid other people/objects in
   frame. More angles can help constrain shape but do not guarantee likeness.
4. Enter an asset name. Choose **Balanced** for the first run or **Detailed**
   for more sampling steps and higher extraction resolution.
5. Choose background preparation: **objects**, **people**, or **already
   isolated / keep background**. Transparent PNGs retain their alpha mask.
   Use background removal for ordinary photos with scenery behind the subject.
6. Set the desired **height in meters** and **triangle budget**. Leave **Surface
   color > Bake colors from your photos** selected for color, or choose
   **Untextured mesh**. The app defaults to a 1024-pixel color atlas on CPU without
   additional neural weights. Camera fitting is approximate; poor alignment
   can cause seams or misplaced details.
   Under **Unseen surface colors**, keep neutral gray for a diagnostic view or
   select **Extend nearby colors · estimated** to reduce gray gaps. Estimated
   color is labelled separately and does not increase photo coverage.
   Click the **!** beside any setting, including advanced options, for its
   meaning and effect on shape, color or processing. Click outside or press
   **Escape** to close the info box.
7. Click **Generate asset**. Watch progress and prepared cutouts. Jobs are queued
   and run one at a time. Use **Cancel generation** to stop a queued/running job.
8. Inspect the final mesh: drag to rotate, scroll to zoom and use **Wireframe**
   to inspect density. Use **Hide colors** to compare the geometry against its
   projected colors. Review the photo coverage percentage. Download
   **FBX + colors ZIP** for Unity, or the self-contained **Blender** file.
   **Color PNG**, **Coverage mask**, **FBX only** and **Report** are also available.

To reuse a previous creation, select it in **Recent assets**. Section **01**
restores the original labelled images and every extra photo in its saved order,
including photos that were not selected for generation. Section **02** restores
the asset name, quality, background, color options, scale, triangle budget and
advanced options. Adjust them if needed, then click **Generate asset** to create
a separate history item. The original asset stays unchanged. Automatic progress
refreshes preserve your edits. If an original upload is missing, the app reports
the problem and leaves your previous inputs unchanged.
**Create an asset** clears the name and all images, restores default settings
and hides the previous result. Saved history is kept.

Advanced options include a 512- or 1024-pixel color atlas. Older history entries
use the defaults for settings they predate. Reusing inputs/settings does not
guarantee an identical mesh: generation and view selection can vary between runs.

For lower-poly assets, the triangle budget offers **500**, **1,000**, **2,500**,
**5,000** and **10,000**, alongside the existing higher budgets. Simplification
happens before UV/color baking, so exported geometry and its colors agree.
Very small budgets can remove thin parts, soften silhouettes or lose small
details. Inspect the actual exported triangle count and the mesh from all sides.
This is automatic mesh reduction, not authored low-poly retopology or automatic LODs.
Lower budgets reduce geometry to store and draw; they do not lower Hunyuan's
generation steps or texture size. **Balanced** controls shape-generation work;
**512 × 512** in advanced options reduces the color atlas to one quarter as many
pixels as 1024 × 1024. Actual game performance depends on the full scene and
Unity's import/material settings; it is not established by triangle count alone.

The default **Automatic preset** planner works without a language model.
Advanced options allow one additional seed after geometric rejection, capped at
two attempts total. Crashed/OOM inference is not restarted. For genuinely flat
subjects, enable **My subject is intentionally flat** to disable the slab check.
The automated checks cannot judge facial resemblance or overall visual quality.
Review the **selected / submitted photos** panel. Only the chosen cardinal
cutouts condition the shape model and supply its color bake. Unselected photos
remain saved with an explanation; they are not fused into the mesh or texture.
The coverage figure counts UV surface texels, rather than physical surface area
or confidence in likeness. Unseen/rejected texels are neutral gray by default.
Optional nearest-surface color extension estimates missing colors and provides
an `inferred.png` mask; there is no neural painting. A failed photo bake preserves an untextured export
with a visible warning. Cancellation/deadlines stop the job rather than continuing
to export. See [photo baking](docs/PHOTO_BAKING.md) for the limits and file contract.

## Import into Unity

1. Download **FBX + colors ZIP** and extract it. Keep `textures/` beside
   `asset.fbx`; downloading the FBX alone does not include its PNGs.
2. Copy the extracted folder into your Unity project's **Assets** folder.
3. Create a material for your render pipeline. Assign `textures/basecolor.png`
   to **Base Map / Albedo** with **sRGB** enabled, metallic **0** and smoothness
   **0.2** (roughness **0.8**). Assign the material to the model and inspect it
   in a scene. These constants are assumptions, not measured surface properties.
4. Keep `coverage.png`, `uvmask.png` and optional `inferred.png` as diagnostics. Do **not** assign the
   coverage mask to opacity/alpha. Add colliders, LODs or other components as needed.

The exporter centers the model horizontally, grounds its base, sets the requested
height in meters, reduces triangles if above budget and exports with **-Z forward,
Y up** and unit metadata. The ZIP includes an import note and generation/export
reports, color PNGs and a relative-path material manifest; it is an ordinary ZIP,
not a `.unitypackage` file. The GLB preview embeds its color image, and the separate
Blender download packs it into the `.blend` file.

Blender automatically reimports the FBX and checks triangle counts, bounds,
UV presence and the resolved color-image hash.
**An actual Unity Editor import has not yet been verified.** These exports do
not include a skeleton, animations, generated PBR textures or animation-ready
retopology. A reduced triangle count alone does not establish game readiness.

## Optional Strata planning

The settings planner optionally uses Strata to choose settings from metadata.
Photo recognition is separate: unlabelled extras automatically use Strata vision,
including when the settings planner is **Automatic preset**. Labelled references
alone need no Strata installation. Strata does not run Hunyuan3D.

To enable it, first provide a compatible native Strata installation, model pack,
tokenizer, and existing base configuration. Then prepare the project-owned config:

```powershell
.\.venv\Scripts\python.exe -B scripts/prepare_strata_config.py --base-config '.\work\strata-base.json'
```

Replace the example path with your existing base config, or place a copy at
that ignored location. Select **Advanced options > Settings planner > Strata**
in the app. This writes
`work/strata-native.json` and preserves the base configuration. The current
adapter was tested against the owner's Strata 0.1.41/Qwen Coder installation;
its tokenizer/frontend modules are loaded relative to the configured engine
installation root. It is not a general Strata installer or a portable adapter
for arbitrary models. See
[NATIVE_SETUP.md](NATIVE_SETUP.md) before adapting it to another installation.
Earlier Strata runs nearly exhausted the tested host's RAM, so the preset is
the recommended starting option.

### Enable extra-photo recognition

With the compatible Strata 0.1.41 engine, `strata-vision.exe` helper and existing
Qwen Coder IQ1_M pack installed, prepare `work/strata-native.json` as above, then run:

```powershell
.\.venv\Scripts\python.exe -B scripts/setup_strata_vision.py --base-config .\work\strata-native.json
```

This downloads and verifies a pinned **907 MB** BF16 vision encoder and creates
`work/strata-vision.json`. It preserves the base config and shared installation;
it does not install or upgrade Strata. The encoder retains its upstream terms.
`--cpu` encoding is available but has not been measured here.

Recognition needs 12 GiB available RAM before loading, stops below 2 GiB and has
a 900-second total deadline. It closes the engine and encoder before generation,
then rechecks RAM/VRAM. Invalid or uncertain observations skip that photo; an
engine failure stops without restarting inference. Missing vision config stops
extra-photo jobs with a setup message. See [MORE_ANGLES.md](MORE_ANGLES.md).

Follow [MANUAL_TEST.md](MANUAL_TEST.md) to test extra-photo selection and textured
Unity export together in the prepared combined app.

## Troubleshooting

| Problem | What to check |
| --- | --- |
| `git` or `uv` is not recognized | Install the prerequisite and reopen PowerShell. |
| PowerShell blocks a script | Use the `powershell.exe -NoProfile -ExecutionPolicy Bypass -File ...` commands above. |
| CUDA is unavailable | Check the NVIDIA driver and run `scripts/check_shape_environment.py` with the project's `.venv` Python. |
| Blender cannot start | Add Blender to PATH or set `LOCAL3D_BLENDER` to its executable, then restart the app from that environment. |
| Not enough RAM/VRAM, or out of memory | Close other heavy apps/GPU workloads, select Balanced and the Automatic preset planner, then submit a new job. |
| Empty, flat or incorrect result | Inspect cutouts; try cleaner, consistent views. Use the flat-object option only for intentionally thin subjects. |
| App does not open | Check `work/web-app.log` and `work/web-app-errors.log`, or run `scripts/web_app.py` in a terminal. Port 8765 must be available. |
| A job fails | Its originals, raw attempts, settings and diagnostic logs remain under `outputs/web-jobs/JOB_ID/`. |

The app binds to loopback only and is intended for one local user. It does not
provide a publicly hosted service. See [WEB_APP.md](WEB_APP.md) for queue limits,
process deadlines, cancellation, recovery behavior and measured verification.

## Storage and privacy

| Location | Contents |
| --- | --- |
| `models/` | Downloaded model weights and upstream license files. |
| `.venv/` | Isolated Python environment. |
| `work/` | Download/source caches, local configuration, server logs and SQLite queue. |
| `outputs/web-jobs/JOB_ID/` | Original uploads, cutouts, raw attempts, exports, telemetry and reports. |
| `inputs/`, `jobs/`, other `outputs/` | References and evidence from the original CLI workflow. |

These runtime directories are Git-ignored. The app performs no automatic cleanup;
keep enough space for future jobs. Personal images and generated assets are not
included in this public repository.

## Verification and project notes

The combined primary-app smoke test submitted **six photos** through the browser.
Strata selected front/back anchors plus an unlabelled left photo and skipped three
duplicates. The same selected cutouts supplied photo color. The first shape attempt
finished the full workflow in **187 seconds**, producing a **50,000-triangle**
textured FBX at **1.8 meters** with **76.7% UV-texel color coverage**. The downloaded
ZIP retained maps and the selection audit; a relocated fresh Blender import and
embedded GLB pixel checks passed. This is one example, not an accuracy benchmark.

Photo base-color baking is implemented. The fresh official front/left/back demo
completed the HTTP queue in **177 seconds**, producing a **50,000-triangle** FBX
at **1.8 meters** with **75.7% UV-texel color coverage**. A fresh Blender import
from a relocated ZIP retained geometry, UVs and the correct local PNG. The GLB
embedded matching color pixels, and the browser rendered the textured model.
All **44 regression checks** passed, including selected extras and replacement
anchors reaching the bake, and protection against cross-view
color ghosting and excessive camera tilt. This is one measured example, not a
timing or quality guarantee. Seams and feature-placement errors can remain.
Small-sprite color rebaking improved photo coverage from 30.0% to 46.4% on the
same mesh. An optional 53.6% estimated color extension reduced gray patches;
these figures remain separate in the report. A previous character demo retained
its coverage and camera fit. See [photo baking](docs/PHOTO_BAKING.md).
Host-specific paths, specifications and telemetry are kept in ignored local reports.

- [WEB_APP.md](WEB_APP.md): app architecture, limits and validation details.
- [MANUAL_TEST.md](MANUAL_TEST.md): combined extra-photo/color workflow to try.
- [MORE_ANGLES.md](MORE_ANGLES.md): local Strata vision and selection audit.
- [docs/PHOTO_BAKING.md](docs/PHOTO_BAKING.md): color fitting, packaging and checks.
- [docs/TEXTURE_FEASIBILITY.md](docs/TEXTURE_FEASIBILITY.md): neural Paint research;
  those backends remain unimplemented.
- [NATIVE_SETUP.md](NATIVE_SETUP.md): native environment and optional Strata setup.
- [FIRST_RUN.md](FIRST_RUN.md): original Strata/Hunyuan3D/Blender CLI experiment.
- [NEXT_STEPS.md](NEXT_STEPS.md): current project checkpoint.
- [AGENT.md](AGENT.md): project agent guidance.

## License and upstream projects

Original project code/documentation use the **[MIT License](LICENSE)**,
copyright 2026 Jacob Cohen. Tencent model weights/source, Blender and other
third-party components retain their own licenses; this repository does not
relicense or redistribute model weights. The bundled Three.js viewer retains
its [MIT license](web/vendor/THREE-LICENSE.txt).

- [Hunyuan3D-2.1](https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1)
- [Hunyuan3D-2mv model card](https://huggingface.co/tencent/Hunyuan3D-2mv)
- [Hunyuan3D-2 source](https://github.com/Tencent-Hunyuan/Hunyuan3D-2)
- [Strata](https://github.com/Niko1221/Strata)
