# Current checkpoint: combined extra-photo selection and photo color

## Implemented and checked

- Integrated the texture and more-than-four-angles branches on the sanitized
  main base. The owner authorized resolving conflicts and publishing to main.
- Up to 16 candidate photos: required front, optional trusted side/back anchors,
  and unlabelled extras analysed by local Strata vision. At most four selected
  cardinal cutouts condition Hunyuan and supply the photo bake.
- Frozen UV geometry, visibility-aware source selection, neutral unknown fill,
  textured FBX/GLB/Blender export and portable ZIP with maps and selection audit.
- Fixed cross-view color ghosting and excessive camera tilt. Added coverage,
  selection reasons, color/clay/wireframe inspection and ZIP-first downloads.
- Both feature branches passed real native generation/export checks separately.
  Combined code passed 40 Python tests and the JavaScript drop/payload test,
  including selected extras and replacement front images reaching the bake.
- Other branch completed a read-only integration review with no blocking code
  finding. Its documentation findings are reconciled in README and WEB_APP.
- MANUAL_TEST.md explains the combined upload-to-Unity acceptance workflow.

## Primary app and manual test

- Both branches are merged with resolved conflicts. The primary main checkout
  now serves the combined app on port 8765. Its own verified vision encoder and
  project config are prepared; shared Strata/base config is unchanged.
- Combined six-photo browser test passed: front/back anchors plus unlabelled
  left selected, three duplicates skipped, one fresh shape attempt, photo bake,
  Blender export and portable ZIP with audit. Measured 187 seconds, 50,000
  triangles, 1.8 meters and 76.7% UV-texel color coverage.
- Relocated FBX import, UV/image hashes, selected-extra provenance, GLB embedded
  pixels and ZIP CRC/map/audit checks passed. Raw mesh unchanged; owned heavy
  stages stopped. Existing jobs and prior demos remain preserved.
- Next action is the owner's manual test using MANUAL_TEST.md: consistent front
  plus optional anchors/extras, photo color enabled, inspect selection and model,
  download ZIP and assign base color in Unity. No further generation is required.
- Keep private photos, generated assets, model weights, host paths and telemetry
  under ignored runtime directories. Retain prior demos and raw meshes.
- No neural Paint, generated PBR maps, rig or animation. Approximate photo fitting
  can leave seams/misplaced details and gray unseen regions. Classification can
  be wrong. Coverage is a UV-texel metric, not likeness or physical area.
- Actual Unity Editor import remains the owner's manual acceptance step.
