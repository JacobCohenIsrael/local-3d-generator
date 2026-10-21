# Local 3D Generator

Create a useful 3D asset locally on Windows from one reference image, using an
LLM served by Strata to plan the job, Hunyuan3D-2.1 to generate geometry, and
Blender to inspect/process and export it.

## First milestone

Complete one native Windows image-to-mesh generation and Blender export.
Start with shape generation only within a 16 GB VRAM planning budget. Tencent documents approximately 10 GB for shape generation and
21 GB for textures; local success and memory peaks have not been measured.

Success requires:

- One recorded reference image and its provenance. Use an owner-selected image;
  if none is supplied, use the official Hunyuan3D bundled demo image and record it.
- One real response from the Strata-served LLM yielding a bounded structured job.
  Validate it in ordinary code; do not require native/general tool calling.
- Confirm the owned Strata inference process has stopped and its GPU allocation
  has been released before loading Hunyuan3D. Keep the controller independent.
- One real Hunyuan3D shape-generation result saved as an untouched raw mesh.
- Blender imports the mesh, performs explicitly recorded processing, saves a
  .blend file and exports a separate GLB. Reopen the export and verify geometry.
- A preview and report record versions, settings, seed, timings, observed memory
  readings, output paths, validation, failures and confirmed owned shutdown.
- Visual acceptance remains a human decision. File validity and mesh statistics
  alone do not establish that an asset is ready for a game.

## Architecture

Owner request + reference image -> independent Windows controller
-> Strata-served LLM creates job -> validate and save job -> stop Strata engine
-> native Python/PyTorch Hunyuan3D generates mesh -> stop owned generator
-> Blender imports/processes/exports -> validate outputs -> owner reviews preview.

Strata is a language-model runtime; it does not execute Hunyuan3D weights.
Hunyuan3D retains its own dependencies and model files. Use loopback interfaces
if a service is needed. A simple script is sufficient for the first milestone.

## Initial scope

Native Windows processes and project-specific environments. Inspect existing
Strata, Python, Blender, CUDA driver and model caches before installing anything.
Reuse compatible installations without modifying their shared configurations.
Keep heavy inference stages sequential and verify memory is actually released.

Defer PBR texture generation, training, batches, UI, game-engine integration,
automatic retries and arbitrary model-generated shell/Python execution.
Do not assume native Windows solves all memory or performance limitations.
Measure results; do not claim speedups or paid-token savings without comparison.

This project is separate from Unrelated projects. Its Docker coding viability clock,
consumed attempts and workload policies are not inherited or reset here.
Preserve that repository and its installations, caches, logs and evidence.

## Files and directories

- AGENTS.md: standard agent entry point; points to the requested AGENT.md.
- AGENT.md: authoritative project instructions.
- NEXT_STEPS.md: single current checkpoint.
- inputs/: recorded reference image(s).
- jobs/: validated job descriptions and settings.
- outputs/<run-id>/: raw mesh, .blend, exported GLB, preview and result report.
- work/: scripts, scratch files, logs and intermediate assets.
- .venv/: isolated native Python environment when needed.

## Sources

- Hunyuan3D: https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1
- Hunyuan3D API: https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1/blob/main/API_DOCUMENTATION.md
- Model weights: https://huggingface.co/tencent/Hunyuan3D-2.1
- Strata: https://github.com/Niko1221/Strata

## License

This project's original code and documentation are licensed under the
[MIT License](LICENSE), copyright 2026 Jacob Cohen. Strata, Hunyuan3D,
Blender, model weights and other third-party components retain their own
licenses; this repository does not relicense or redistribute them.

See [NEXT_STEPS.md](NEXT_STEPS.md) for the current checkpoint. No image-to-mesh
generation has run yet.
