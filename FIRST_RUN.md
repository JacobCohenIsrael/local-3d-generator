# First native image-to-mesh validation

The original native Strata -> Hunyuan3D -> Blender pipeline completed a real
shape-generation test using Tencent's official transparent penguin/sign image.
Technical validation passed; visual acceptance remains with the owner.

## Functional results

- Strata returned a bounded plan: seed 42, 30 diffusion steps, extraction
  resolution 128, guidance 5.0 and 2,048 decoding chunks. The request contained
  216 input tokens and returned 45 output tokens, including its end marker.
- Strata received metadata rather than image pixels. The response was validated
  without content repair, then the owned engine process was stopped.
- Hunyuan3D generated 39,766 raw vertices and 79,532 triangles.
- Blender saved a project and exported/reopened the GLB. Triangle counts and
  bounds matched, and the raw mesh hash stayed unchanged.
- A rendered preview showed the penguin and sign with visible ridging at this
  extraction resolution. No PBR textures, rig, collider or game readiness was
  established by this test.

## Process validation

Hidden stage processes were started suspended, placed in Windows kill-on-close
Job Objects and resumed under fixed deadlines. Tests checked normal exit,
timeout with descendant cleanup, cancellation and invalid-plan rejection.
All owned stage trees stopped and a separate check confirmed the recorded
processes were absent. The original external Strata configuration was unchanged.

An earlier startup rejected an incompatible speculative setting before model
inference. The separate project config was corrected to the pack's required
`--spec 2`, with no MTP model, before the successful request. No failed model
answer was retried or repaired.

## Private evidence

Original references, raw/generated assets, stage settings, exact executed-source
snapshots, hashes, logs and resource observations remain under ignored local
`inputs/`, `jobs/`, `outputs/` and `work/`. Public documentation deliberately
omits host paths, hardware inventories, local timezones and activity timestamps.
No model weights or generated assets are distributed in this repository.

File validity alone does not establish visual quality, game readiness, general
inference speed or cost savings. See WEB_APP.md for later app validation.
