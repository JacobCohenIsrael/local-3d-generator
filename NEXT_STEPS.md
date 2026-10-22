# Current checkpoint: improved color baking for small references

## Completed

- Combined extra-photo selection and textured FBX remain integrated. Up to 16
  candidates are audited; at most four selected cardinal cutouts supply shape
  and color. Strata vision and shape inference run sequentially with bounds.
- Color camera search now spans 0 through 60 degrees in ten-degree steps, while
  retaining the level-camera prior that prevented doubled facial details.
- Visibility uses a 512-pixel geometry buffer independently of source size;
  color still samples original image pixels. Tiny sloped surfaces are retained
  while hidden geometry remains rejected.
- Optional nearest-surface color extension reduces neutral patches. It preserves
  observed colors and records an inferred mask/fraction separate from photo
  coverage. Neutral gray remains the default. No neural paint or new weights.
- A color-only comparison on the same 25,000-triangle mesh improved photo
  coverage from 30.0% to 46.4%. The remaining 53.6% can use explicitly estimated
  extension. Raw/prepared geometry hashes and exported bounds/counts are unchanged.
- Exported/reopened textured FBX and relocated ZIP passed UV/image hash checks.
  GLB embedded pixels matched; ZIP includes observed/inferred masks and selection
  audit. Owned heavy stages stopped; originals and prior results remain saved.
- Character demo regression retained 75.7% coverage and its level front camera.
  All 44 Python tests and the JavaScript drop/settings test passed, including
  visibility/occlusion, elevated fitting and honest inferred-mask packaging.
- The app exposes Unseen surface colors, separate observed/estimated percentages,
  mask downloads and a color-rebake label. A separate improved result is prepared
  for manual comparison in the primary app; no new shape inference was run.

## Next action / limits

- Owner reviews the improved color result and may select Extend nearby colors
  for future sparse inputs. Use MANUAL_TEST.md for the Unity import workflow.
- Estimated colors do not recover unseen detail. Tiny sprites, perspective,
  shadows and approximate camera fits still limit quality; seams can remain.
- Coverage measures UV texels, not likeness or physical area. Neutral/coverage/
  inferred masks are diagnostic and must not drive material opacity.
- Models remain static/unrigged, without generated PBR maps. Actual Unity Editor
  import remains a manual acceptance step. Neural Paint remains research only.
- Keep model weights, source images, generated assets and host-specific evidence
  ignored. Preserve existing jobs and shared Strata configuration.
