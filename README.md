# Local 3D Generator

Turn reference images into a static 3D mesh on a Windows PC, then download an
FBX to import into Unity. The local web app handles background removal,
generation, geometry checks, Blender export and a rotatable preview. Submitted
jobs run without Codex or an open browser tab.

- **One image:** Hunyuan3D-2.1.
- **Two to four views:** the separate Hunyuan3D-2mv model uses all supplied angles.
- **Downloads:** FBX, Unity ZIP, Blender project and generation report.
- **Local processing:** uploads, models, job history and generated assets stay on
  your machine. Installation downloads dependencies and model files once.

Exports are untextured, unrigged static meshes. This is generative reconstruction,
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
default web-app workflow. After installing Git/uv, reopen PowerShell so PATH
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
3. Keep the subject's pose, framing, lighting and camera distance consistent
   across views. Include the whole subject and avoid other people/objects in
   frame. More angles can help constrain shape but do not guarantee likeness.
4. Enter an asset name. Choose **Balanced** for the first run or **Detailed**
   for more sampling steps and higher extraction resolution.
5. Choose background preparation: **objects**, **people**, or **already
   isolated / keep background**. Transparent PNGs retain their alpha mask.
   Use background removal for ordinary photos with scenery behind the subject.
6. Set the desired **height in meters** and **triangle budget**.
7. Click **Generate asset**. Watch progress and prepared cutouts. Jobs are queued
   and run one at a time. Use **Cancel generation** to stop a queued/running job.
8. Inspect the final mesh: drag to rotate, scroll to zoom and use **Wireframe**
   to inspect density. Download **FBX**, **Unity ZIP**, **Blender**, or **Report**.

The default **Automatic preset** planner works without a language model.
Advanced options allow one additional seed after geometric rejection, capped at
two attempts total. Crashed/OOM inference is not restarted. For genuinely flat
subjects, enable **My subject is intentionally flat** to disable the slab check.
The automated checks cannot judge facial resemblance or overall visual quality.

## Import into Unity

1. Download the FBX, or extract `asset.fbx` from the Unity ZIP.
2. Drag `asset.fbx` into your Unity project's **Assets** folder.
3. Drag the imported model into a scene, assign a material appropriate for your
   render pipeline, and inspect its scale and orientation.
4. Add any required colliders, LODs or other game components in Unity.

The exporter centers the model horizontally, grounds its base, sets the requested
height in meters, reduces triangles if above budget and exports with **-Z forward,
Y up** and unit metadata. The ZIP includes an import note and generation/export
reports; it is an ordinary ZIP, not a `.unitypackage` file.

Blender automatically reimports the FBX and checks triangle counts and bounds.
**An actual Unity Editor import has not yet been verified.** These exports do
not include a skeleton, animations, generated PBR textures or animation-ready
retopology. A reduced triangle count alone does not establish game readiness.

## Optional Strata planning

Strata is an optional language-model runtime for choosing bounded generation
settings from image metadata; it does not run Hunyuan3D or inspect the photos.
The default preset is simpler and uses less host memory.

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

A real three-view example completed automatic foreground removal and produced
a **50,000-triangle FBX** at 1.8 meters.
The FBX reopened with matching geometry/scale and the browser rendered the mesh.
This is one validated example, not a timing or quality guarantee for other inputs.
Host-specific paths, specifications and telemetry are kept in ignored local reports.

- [WEB_APP.md](WEB_APP.md): app architecture, limits and validation details.
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
