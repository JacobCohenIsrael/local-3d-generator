# Native Windows setup

The native Strata/Hunyuan3D/Blender pipeline has completed real image-to-mesh
validation. See [FIRST_RUN.md](FIRST_RUN.md) for functional results and
[README.md](README.md) for fresh installation and everyday web-app use.

Machine-specific paths, hardware inventories and resource telemetry belong in
ignored local reports, not in this public document.

## Project environment

- Managed Python 3.10.22 in `work/python/`; isolated environment `.venv/`.
- PyTorch 2.5.1+cu124, torchvision 0.20.1+cu124, CUDA runtime 12.4. The selected
  wheel-based shape path does not require a separate CUDA Toolkit installation.
- Reproducible dependencies: `requirements-shape.lock.txt` and
  `requirements-segmentation.txt`. Source/model revisions: `upstream.json`.
- Hunyuan3D-2.1 source: `work/vendor/Hunyuan3D-2.1/`. Multi-view source:
  `work/vendor/Hunyuan3D-2/`. Model files live under ignored `models/`.
- The single-view checkpoint is 7,366,389,768 bytes with upstream-verified SHA-256
  `6b519fc7242f78e9b5f47ea4d55668fe3d944a2d27332f4ca68d29a6ff603f5e`.
  Upstream licenses/notices are stored beside downloaded weights.
- Blender runs as an external executable. It is discovered from
  `LOCAL3D_BLENDER`, PATH, or the standard Windows Blender 5.2 installation.
- Texture weights, training extensions and a standalone `bpy` Python package
  are not part of the original shape-only setup.

## Optional Strata configuration

Provide the path to an existing compatible Strata base configuration:

```powershell
.\.venv\Scripts\python.exe -B scripts/prepare_strata_config.py --base-config '.\work\strata-base.json'
```

The path above is an example ignored local location, not an installation
requirement. The helper validates referenced engine/model/tokenizer files,
creates `work/strata-native.json` and preserves the base configuration.
The tokenizer/frontend modules are loaded relative to the configured engine.

The current adapter targets Strata 0.1.41 and its tested IQ pack. It uses a
4K context, mapped experts, `--spec 2` without an MTP model, disabled parked
conversation/prompt caches and a 4 GiB VRAM reserve. Confirm compatibility
before adapting it to a different engine/model. Strata receives metadata,
not image pixels. The default web-app preset does not require Strata.

## Reproduce preparation

With Git and uv installed, run from the project folder:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup_web_app.ps1
.\.venv\Scripts\python.exe -B scripts/check_shape_environment.py
```

A read-only inventory helper accepts explicit installation locations:

```powershell
.\.venv\Scripts\python.exe -B scripts/inspect_native.py --strata-root '.\work\strata' --model-root '.\models\strata'
```

Replace those example locations with your local installations. Reports include
local paths and belong under ignored `work/`; do not publish them.

## CLI generation and export

For the original one-shot controller, prepare a compatible Strata config first:

```powershell
.\.venv\Scripts\python.exe -B scripts/controller.py --image '.\inputs\reference.png' --subject 'a reference object'
```

The reference must be RGBA and have a sibling `provenance.json` containing its
SHA-256. The helper verifies integrity before generation. Use `--quality detailed`
for the higher-detail profile. Output goes to a fresh ignored run directory.

The CLI owns process trees with Windows Job Objects, enforces stage deadlines,
confirms shutdown and retains raw meshes/logs. It has no inference-retry loop.
For an active CLI run, create `CANCEL` in its output directory to cancel it.
The web app has its own bounded second-seed policy after geometric rejection.

Blender saves a project and exports/reopens the mesh, checking geometry and
raw input integrity. The web-app FBX path also validates final scale and
triangle count by independent reimport. Visual quality remains a human decision.

## Resource handling

Recheck available RAM and VRAM before execution. Keep heavy models sequential
and confirm GPU allocation release before loading the next stage. CPU checkpoint
loading has a separate RAM budget from GPU inference. Do not close unrelated
apps or change hardware protections automatically. Exact host specifications,
paths and timestamped telemetry remain in ignored local evidence only.
