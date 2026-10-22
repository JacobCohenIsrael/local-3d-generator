# Current checkpoint: photo color baking and textured FBX

## Completed

- Implemented photo base-color baking on codex/texture-feasibility. No Paint
  weights or new dependencies installed; primary runtime remains unchanged.
- CPU projection uses frozen/reduced UV geometry, approximate cardinal camera
  fitting, depth/normal/alpha visibility, source hashes and neutral unknown fill.
- Visual review found color ghosting. Replaced cross-view averaging with source
  selection and constrained camera tilt; compared against an untextured render
  of the same preserved mesh before running a fresh end-to-end job.
- Textured FBX uses relative external PNGs. GLB embeds the color image and the
  Blender project packs it. Unity ZIP includes maps, material manifest, reports
  and import notes. Fresh FBX reimport validates geometry, UVs and color hash.
- Added Surface color selection, coverage/warning UI, material-preserving
  preview, Hide colors inspection and ZIP-first downloads. Fixed embedded-image
  blob loading. Independent worktree app uses port 8766.
- Corrected official three-view demo completed through browser/HTTP queue:
  one fresh Hunyuan3D-2mv attempt, 177 seconds, 50,000 triangles, 1.8 meters and
  75.7% UV-texel color coverage. Raw unchanged; owned stage processes stopped.
- Downloaded ZIP passed CRC/map checks and fresh Blender import after relocation;
  images resolved inside the extracted folder. Embedded GLB pixels matched.
  Browser color/clay/wireframe modes and actual ZIP download verified.
- All 24 regression checks, Python parsing, JavaScript syntax and diff whitespace
  checks passed. Machine-specific evidence and assets remain ignored in work/
  and outputs/. README, WEB_APP and docs/PHOTO_BAKING.md describe use and limits.

## Remaining limits / follow-up

- Camera fitting is approximate. Seams, inaccurate feature placement, shadows
  and gray unseen surfaces remain possible. Coverage measures UV texels, not
  physical area, likeness or confidence in reconstruction.
- Human visual review and actual Unity Editor import remain necessary. Metallic
  0 and roughness 0.8 are assumed constants. No generated PBR maps, rig or animation.
- Neural Paint remains research only; see docs/TEXTURE_FEASIBILITY.md.
- Rebased onto sanitized main b652be390f353ef7a1eb286143d3621e5b828ee1.
  No old ancestry is retained; no merge/push to main was performed. No further
  generation is required for this implementation task.
