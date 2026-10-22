# Texture support: feasibility and implementation plan

## Recommendation

Texture support is feasible, but the current shape pipeline cannot simply enable
a flag and produce a reliably textured FBX on the **16 GB VRAM / 32 GB RAM target**.
Build a material-aware export contract first, then add an optional color-texture
stage. Keep the working shape-only path available when texturing cannot finish.

Recommended order:

1. **UVs, external PNGs, material-preserving preview and Unity packaging.** A
   synthetic Blender CPU-bake/FBX/GLB probe passed in this worktree. This part
   needs no new neural weights or CUDA compiler.
2. **Photo base color** for consistent, aligned views, with a coverage map and
   explicit handling of unseen surfaces. This is the best direction when
   preserving photographed colors matters, but camera alignment is real work.
3. **Paint 2.0 with CPU offload** as the first neural-color experiment. It has an
   official offload method, unlike the audited 2.1 wrapper. Validate fit and
   native builds before offering it as a supported app option.
4. **Paint 2.1 PBR** as an experimental later backend. Its documented texture
   configuration exceeds the target GPU's memory; an offloaded implementation
   needs measurement before making a support claim.

This fork is a feasibility investigation. It does **not** enable textures in the
app, install a texture toolchain, download texture weights, or claim a successful
neural paint run. No Unity Editor material import was performed.

## Options and evidence

| Route | What it can supply | Native Windows / target-memory assessment |
| --- | --- | --- |
| Blender photo projection and CPU bake | Observed photo colors in a base-color atlas; UVs and material references | Lowest additional model-memory burden. CPU baking and texture transport are verified synthetically; automatic photo/camera alignment is not. |
| Hunyuan3D Paint 2.0 / Turbo | Generated color texture, including inferred unseen surfaces | Best first neural candidate. Official wrapper exposes CPU offload; still needs CUDA rasterizer, native dependencies and new weights. No measured paint-memory peak on this target. |
| Hunyuan3D Paint 2.1 | Generated base color plus metallic/roughness | Standard documented setting recommends at least 21 GB VRAM, already above 16 GB before desktop use. Not ready as the default backend. |

Tencent documents Paint 2.1's minimum example as six generated views at 512
resolution with at least 21 GB VRAM. Its configuration also has separate render
and atlas dimensions. Lowering an atlas size alone therefore does not establish
that the neural stage will fit. See the pinned [Paint 2.1 guide](https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1/blob/82920d643c0dc2f7bfd7255f45f62d386edfe60c/hy3dpaint/README.md)
and [configuration](https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1/blob/82920d643c0dc2f7bfd7255f45f62d386edfe60c/hy3dpaint/textureGenPipeline.py).

### Offload is not already implemented for Paint 2.1

The pinned 2.1 Gradio app comments out its old texture-offload calls and
constructs a different PBR wrapper. That wrapper loads a multiview diffusion
pipeline onto CUDA, with a separate DINO encoder and Real-ESRGAN upsampler.
Calling `empty_cache()` does not unload those live models. The stock
`--low_vram_mode` must not be advertised as a complete 16 GB texture solution.
This follows from [Gradio initialization](https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1/blob/82920d643c0dc2f7bfd7255f45f62d386edfe60c/gradio_app.py),
[multiview loading](https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1/blob/82920d643c0dc2f7bfd7255f45f62d386edfe60c/hy3dpaint/utils/multiview_utils.py)
and [upsampler loading](https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1/blob/82920d643c0dc2f7bfd7255f45f62d386edfe60c/hy3dpaint/utils/image_super_utils.py).

An experimental adapter could load diffusion modules on CPU, install offload
hooks before CUDA residency, compute/release external reference embeddings,
load the upsampler only when needed, and test VAE slicing/tiling. Start with the
documented six-view/512 configuration, not the larger Gradio defaults. Reduce
render/atlas sizes separately and tile super-resolution. These are proposed
changes, **not proof of memory fit**. CPU offload also consumes host RAM and can
increase transfers/latency; its behavior must be measured with the custom model.
[Diffusers 0.30 memory guidance](https://huggingface.co/docs/diffusers/v0.30.0/en/optimization/memory)
describes the underlying techniques, not a Hunyuan-specific guarantee.

The older [Paint 2.0 wrapper](https://github.com/Tencent-Hunyuan/Hunyuan3D-2/blob/f8db63096c8282cb27354314d896feba5ba6ff8a/hy3dgen/texgen/pipelines.py)
does implement `enable_model_cpu_offload()` for its delight and multiview
pipelines. It accepts an existing mesh, so shape generation can remain on 2.1 or
2mv. Its color-atlas output is not equivalent to independently generated 2.1
PBR maps. Turbo changes sampling; do not assume its name guarantees a smaller
loading peak. Constructors move models to CUDA before the public offload call,
so initialization must be included in the memory test.

### Generated views are not additional uploaded reference angles

Paint's `max_num_view` describes generated render/bake views, not a new arbitrary
camera-conditioned photo-input API. In the audited 2.1 multiview wrapper,
conditioning uses the first reference image. Increasing this setting to twelve
does not mean twelve owner photographs are consumed. An uploaded-photo baking
route must retain each view's camera transform and coverage independently.
See [multiview conditioning](https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1/blob/82920d643c0dc2f7bfd7255f45f62d386edfe60c/hy3dpaint/utils/multiview_utils.py).

## Local prerequisites audit

The read-only readiness probe confirms that a working shape/CUDA environment
is not yet a prepared neural-paint environment. Tool availability, package
versions, resource snapshots and machine paths remain in ignored
`work/texture-readiness.json`, rather than a public host inventory.

For neural paint, prepare an **isolated texture environment**, preserving the
current shape environment. Required checks include a matching CUDA Toolkit,
MSVC C++ tools, build tools such as `setuptools`/`pybind11`/Ninja, UV support,
the rasterizer/inpaint modules and the selected backend's runtime dependencies.
An IDE installation alone does not establish that C++ tools are installed.
Build/import-test those modules before downloading large weights.
The CUDA runtime bundled with PyTorch is not `nvcc`. Paint 2.1's
[rasterizer setup](https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1/blob/82920d643c0dc2f7bfd7255f45f62d386edfe60c/hy3dpaint/custom_rasterizer/setup.py)
uses `CUDAExtension`. Its
[inpaint build command](https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1/blob/82920d643c0dc2f7bfd7255f45f62d386edfe60c/hy3dpaint/DifferentiableRenderer/compile_mesh_painter.sh)
is a Unix-style compiler invocation and needs a Windows build adaptation, not
just a Git Bash launch. The older branch has a
[Windows-aware C++ setup](https://github.com/Tencent-Hunyuan/Hunyuan3D-2/blob/f8db63096c8282cb27354314d896feba5ba6ff8a/hy3dgen/texgen/differentiable_renderer/setup.py).

Do not install the upstream full requirements into the working shape venv
blindly. They include training/demo packages and a separate Python `bpy`, while
the app already runs Blender as a separate executable. Stock 2.1's
[`mesh_utils.py`](https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1/blob/82920d643c0dc2f7bfd7255f45f62d386edfe60c/hy3dpaint/DifferentiableRenderer/mesh_utils.py)
imports Python `bpy` directly: having a Blender executable installed does not
satisfy that import in another Python environment. Either pin a compatible
`bpy` wheel in the texture environment or adapt that I/O boundary to the
existing Blender subprocess. Pin only runtime paint dependencies, check import
compatibility, retain original licenses, and keep
download/cache paths local. Verify package/native imports rather than assuming
every package in the full upstream list is needed during inference.

### Weight inventory, without downloading weights

Official file manifests were inspected and saved in ignored
`work/texture-model-manifests.json`. Audited source revisions are the same pinned
2.1/2 revisions already in `upstream.json`. Additional model revisions observed:

| Repository | Revision | Relevant finding |
| --- | --- | --- |
| `tencent/Hunyuan3D-2.1` | `0b94677654c57bb9a6b6845cd7b704ccf551d327` | PBR subtree totals about 6.89 GB of files, excluding external DINO/upsampler. |
| `facebook/dinov2-giant` | `611a9d42f2335e0f921f1e313ad3c1b7178d206d` | One safetensors copy is about 4.55 GB. Do not also download its duplicate bin format. |
| `tencent/Hunyuan3D-2` | `9cd649ba6913f7a852e3286bad86bfa9a2d83dcf` | Paint, Turbo and delight have distinct subtrees; some contain duplicate bin/safetensors weights. Select one paint variant plus required delight assets. |

These are **download sizes, not VRAM or RAM peaks**. The 2.1 route adds roughly
11.4 GB before Real-ESRGAN and package/cache overhead. Do not fetch an entire
model repository indiscriminately. Pin a future texture manifest separately
from the working shape model's pins. Reference manifests:
[2.1 files](https://huggingface.co/tencent/Hunyuan3D-2.1/tree/0b94677654c57bb9a6b6845cd7b704ccf551d327),
[2.0 files](https://huggingface.co/tencent/Hunyuan3D-2/tree/9cd649ba6913f7a852e3286bad86bfa9a2d83dcf),
[DINO files](https://huggingface.co/facebook/dinov2-giant/tree/611a9d42f2335e0f921f1e313ad3c1b7178d206d).

## Photo-based alternative

A Blender CPU-bake path avoids the neural paint weights and custom CUDA
rasterizer. It can preserve visible photographed colors, but a UV unwrap alone
does not align an arbitrary photo with a generated mesh. Proposed steps:

1. Finish cleanup/decimation/scale first; freeze target topology and create UVs.
2. Retain the original crop/alpha transforms and per-view camera metadata.
   Estimate projection, scale, elevation and pose by matching rendered silhouettes;
   cardinal labels alone are an initial guess, not camera calibration.
3. Project photo samples only onto front-facing, visible mesh surfaces, with
   depth/occlusion tests. Blend overlapping views by confidence and angle.
4. Bake a base-color atlas with island padding. Export a coverage mask showing
   where source photographs did not observe the mesh. Use a documented neutral
   fill there, or label any generated completion explicitly.
5. Reject poor alignment rather than stretch a face onto an unrelated surface.
   Start with a controlled turntable example before a person photograph.

This does not recover physically measured roughness/metallic maps from RGB.
For a base-color-only mode, use documented constant material parameters;
do not label assumed values as estimated PBR. Shadows/highlights in source
photos can remain baked into color unless a separate de-lighting process is used.

## Required app/export changes

| Area | Concrete change |
| --- | --- |
| `scripts/app_pipeline.py` | Separate final geometry preparation from optional texturing and export. Run owned stages sequentially; retain raw mesh, UV mesh, texture settings/maps and telemetry. |
| Texture worker | A fixed mode (`none`, photo base color, or validated neural backend), output manifest, explicit deadlines, one paint attempt and cancellation. No arbitrary code from Strata. |
| `scripts/blender_unity.py` | Keep final UVs/material slots and texture links; perform topology-changing work before painting, or explicitly rebake. Validate materials/images as well as counts/bounds. |
| `web/viewer.js` | Stop replacing imported GLB materials with the current green material in textured mode; preserve PBR textures and support wireframe without discarding them. |
| `scripts/web_app.py` | Add validated texture settings and safe manifest-based image downloads; keep existing upload/path/Origin/token limits. |
| Download ZIP | Include external PNGs and a material manifest with relative paths, dimensions, roles, colorspaces and hashes. FBX alone is insufficient. |
| UI/report | Show requested/applied texture mode, coverage or inference warnings, and a clear texture-failure fallback status. |

Keep shape and paint isolated in different processes; confirm shape CUDA
allocation is released before painting. If texture generation fails, preserve
the usable mesh and report an untextured fallback rather than repeat OOM or
claim texturing succeeded. The texture policy must be independent of the
existing bounded geometry-seed retry policy.

## FBX, GLB and Unity material contract

Recommended downloadable structure:

```text
asset.fbx
asset.glb
textures/basecolor.png
textures/metallic.png             # only when available
textures/roughness.png            # only when available
textures/metallic_smoothness.png  # Unity Standard/URP packing
material-manifest.json
UNITY_README.txt
```

Use Principled BSDF image nodes for Blender transport and relative image paths
in FBX. Prefer explicit external images in the ZIP over relying on embedded FBX
media. GLB embeds its textures for the local browser preview. The synthetic
probe confirms base-color transport; arbitrary PBR shader graphs are not
automatically portable through FBX.

For Unity Standard/URP metallic workflow, pack metallic into **R** and smoothness
into **A**, with `smoothness = 1 - roughness`. The source-map provenance and
colorspaces must be explicit: base color is sRGB; material masks are linear.
GLB's metallic/roughness packing is different (B/G), so reusing that PNG as a
Unity metallic map is wrong. If using HDRP, provide a separate HDRP mapping
profile rather than relabel the URP file. See
[Unity channel packing](https://docs.unity3d.com/6000.0/Documentation/Manual/urp/shaders-in-universalrp-channel-packed-texture.html),
[Unity Lit properties](https://docs.unity3d.com/6000.0/Documentation/Manual/urp/lit-shader.html)
and the [glTF material specification](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html#metallic-roughness-material).

A small optional Unity Editor importer could create the selected render-pipeline
material, apply texture import settings and assign it to the FBX. Until tested,
provide explicit manual instructions and the texture files; do not promise
automatic Unity PBR setup from the FBX alone.

## Verification and acceptance gates

Completed here:

- Read-only prerequisites inventory, pinned source audit and model manifest lookup.
- Synthetic CPU emission bake on a UV cube with a small color test pattern.
- FBX reimport after clearing original in-memory materials/images: UVs retained,
  external base-color PNG resolved and its file hash matched.
- GLB JSON contained an embedded image and base-color material link; fresh
  import retained UVs and an image texture. Probe process-tree shutdown confirmed.
- The 15 existing regression checks passed after rebasing onto the sanitized
  application base; the working app pipeline was not modified by this research.

Not performed: neural paint inference, real photo-to-mesh camera alignment,
real-person texturing, arbitrary generated-mesh UV quality, Unity Editor import,
or PBR image-channel validation in Unity. The probe is not a texturing-quality
benchmark and is not wired into the app.

Before shipping a texture mode, require a controlled real mesh/reference test,
both loading and sampling memory telemetry, visible seam/coverage inspection,
relocated ZIP import, cancellation/timeout/failure fallback checks, and one
actual Unity project test in the chosen render pipeline. Keep default model
weights/settings unchanged until those gates pass.

## Reproduce the lightweight probes

Use an existing compatible environment read-only or a separate environment;
do not install into another worktree's venv. From this worktree, set executable
paths for your own installation:

```powershell
$pythonExe = 'C:\path\to\python.exe'
$blenderExe = 'C:\path\to\blender.exe'
& $pythonExe -B scripts/inspect_texture_readiness.py --output work/texture-readiness.json
& $blenderExe --background --factory-startup --python-exit-code 1 --python scripts/probe_texture_roundtrip.py -- --output-dir work/texture-probe-new
```

Choose a new output directory for each bake probe; old evidence is preserved.
The probe creates synthetic test assets only, uses CPU baking, and does not
load neural weights. For automation, launch it through the project's
`OwnedProcess` with an explicit deadline as done in this investigation.
Machine-specific evidence belongs in ignored `work/`, not in tracked reports.
