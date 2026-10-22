# Current checkpoint

## Implemented in the hybrid-photo worktree

- Front is required; back/left/right remain optional trusted labelled anchors.
  Extra photos support multi-file browsing and drag/drop without angle entry.
  Limits remain 16 total photos / 48 MiB combined. Legacy stored jobs remain readable.
- Installed and SHA-256 verified the pinned matching Strata BF16 vision encoder
  in this worktree's ignored models cache. Created a project-owned vision config,
  preserving the shared Strata installation and source config; no engine upgrade.
- Actual image embeddings reach the installed Strata 0.1.41 / Qwen Coder IQ1_M
  runtime. Each usable extra is compared with the anchors using a strict fixed
  observation schema. Filenames and asset names are not prompt instructions.
- Deterministic conservative selection fills missing cardinal directions, keeps
  anchors unless an extra clearly improves clarity at high confidence, and skips
  uncertain, incompatible, obstructed or unsupported views. Duplicate-anchor bytes
  bypass inference. Every original/cutout and selection reason remains retained.
- Recognition has a deadline, cancellation, no automatic restart, RAM checks and
  confirmed owned-process shutdown before Hunyuan. A small explicit resident RAM
  tier and direct expert reads resolved host-memory pressure during visual prompts.
  The settings planner is a separate optional feature.
- Model/source caches may be reused read-only with LOCAL3D_ASSET_ROOT. Interpreter
  and port overrides support isolated launches without altering the primary app.

## Verified

- Real native recognition with only the front anchor correctly selected official
  unlabelled left/back photos and excluded a repeated front.
- A browser-submitted job ran through the actual durable HTTP queue, CPU cutouts,
  Strata recognition, Hunyuan3D-2mv and Blender. Three of four photos conditioned
  the model. The first seed passed geometry checks; Blender exported 50,000
  triangles at 1.8 meters and independently reopened the FBX with matching bounds
  and counts. Raw input was unchanged.
- Live FBX, Unity ZIP and selection-report downloads were checked. Packaged FBX
  and audit matched their download endpoints. The interactive browser mesh and
  selection reasons rendered with no console warnings/errors; a screenshot is
  retained in ignored work/.
- A separate real six-photo recognition check with three labelled anchors kept
  those anchors, declined an equivalent alternate, rejected a different character
  and skipped a duplicate. It exercised longer multi-image prompts without running
  another mesh generation.
- Python tests cover request limits, angle-free data, trusted anchors, uncertain/
  malformed observations, subject/pose mismatch, duplicates, replacement rules,
  selected-input provenance, audit packaging and stopping before mesh loading on
  a vision failure, alongside existing process/queue/HTTP checks. A JavaScript
  interaction test exercises multi-file dropping, removal and angle-free submit.
  Final verification passed 30 Python tests, the JavaScript interaction test,
  JavaScript syntax checks and Git whitespace checks. The isolated launcher
  recognized the running hybrid app on its alternate port.

## Boundaries and next action

- At most four selected front/left/back/right photos condition Hunyuan. Extra
  photos improve input selection; they are not all fused into the geometry.
  Top/bottom conditioning, textures, rigging and arbitrary camera poses remain
  separate work. Reconstruction improvements are not benchmarked.
- Model-reported confidence is not a calibrated probability. Recognition and
  subject/pose checks can be wrong; the example checks do not establish general
  accuracy. Inspect selected cutouts and generated geometry for your own subjects.
- Actual Unity Editor import and CPU-only encoder performance remain unverified.
- Keep the branch isolated for review; do not merge or push to main. Preserve
  the sanitized base/history and keep weights, photos and host evidence ignored.
- Next action: owner tests the hybrid uploader with their own consistent photos.
  Setup and API details are in README.md and MORE_ANGLES.md.
