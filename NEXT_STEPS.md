# Current checkpoint: texture feasibility fork

## Completed

- Isolated branch: codex/texture-feasibility. The running app and its primary
  environment remain unchanged.
- Audited pinned official Paint 2.1 and 2.0 source, native build requirements,
  CPU-offload paths, reference-image conditioning and material export behavior.
- Read-only runtime/toolchain inventory and official model file manifests saved
  under ignored work/. No paint weights downloaded and no dependencies installed.
- Synthetic Blender CPU bake passed. Fresh FBX reimport retained UVs and resolved
  the external base-color PNG with the same hash. GLB contained an embedded image
  and fresh import retained UVs/material texture. Owned process shutdown confirmed.
- docs/TEXTURE_FEASIBILITY.md records the recommendation, source links,
  limitations, material/Unity contract, integration changes and acceptance gates.
- Added reusable read-only readiness and synthetic bake/roundtrip probe scripts.
  README links the report without claiming texture support is implemented.
- All 15 existing regression checks passed on the sanitized base. Probe scripts
  parsed successfully; no primary environment or running service was modified.

## Recommendation / next work

- Build the material-aware export/preview/ZIP contract first.
- Add photo base-color projection for aligned consistent views, with a coverage
  mask and explicit unknown-surface behavior; alignment is not yet verified.
- Evaluate Paint 2.0 with CPU offload as the first neural-color experiment in a
  separate texture environment after native build/import checks pass.
- Keep Paint 2.1 PBR experimental: its documented configuration exceeds the
  16 GB VRAM target, and its wrapper lacks complete texture CPU offload.
- Actual neural texture generation, real-photo camera alignment and Unity Editor
  import remain untested. Existing app settings and shape pipeline are unchanged.
- Rebased onto sanitized main b652be390f353ef7a1eb286143d3621e5b828ee1.
  No old ancestry is retained; no merge/push to main was performed.
