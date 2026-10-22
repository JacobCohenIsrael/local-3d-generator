# Current checkpoint

## Done

- Native Windows web app: image uploads, local CPU cutouts, persistent SQLite
  queue, sequential CUDA inference, progress/history, cancellation, optional
  Strata planning, interactive offline viewer and Unity FBX/ZIP downloads.
- One reference uses Hunyuan3D-2.1; multiple labelled views use the separate
  official Hunyuan3D-2mv model. Upstream revisions are pinned in upstream.json.
- Jobs run independently of Codex with bounded geometry-rejection retries,
  process-tree ownership, deadlines and explicit cancellation.
- End-to-end multi-view validation produced a 50,000-triangle FBX at the
  requested height. Blender reimport retained geometry and world bounds.
  Download integrity, process shutdown and interactive rendering were checked.
- Tests cover process lifecycle, invalid plans/settings/images, request-origin
  boundaries, queue persistence/recovery, cancellation and bounded retries.
- Public documentation covers installation, usage, Unity import, optional Strata
  and troubleshooting. Original shape-only validation is in FIRST_RUN.md.
- Privacy cleanup replaces host-specific paths with configurable discovery or
  local CLI arguments. Host inventories, activity timestamps and raw telemetry
  stay in ignored local evidence. Commits use the GitHub noreply identity.

## Left

- Owner reviews likeness and suitability of new generated assets.
- Validate the FBX in an actual Unity Editor project; Blender checks alone do
  not establish game readiness or animation topology.
- Separate worktrees are investigating texture support and implementing a
  clearly labelled workflow for more than four candidate views. Their changes
  remain isolated from main until reviewed.
- Rebase local development work onto the sanitized main history before publishing.
  Do not merge old ancestry or reintroduce personal metadata/host paths.
- Texture generation, rigging, LOD and collider setup remain separate features.

Runtime inputs, model weights, generated assets, local paths and detailed
resource evidence remain Git-ignored. No general speed/cost saving is claimed.
