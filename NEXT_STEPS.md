# Current checkpoint: setting help, low-poly export and fresh drafts

## Completed

- All eleven fields in section 02 have labelled, keyboard-accessible ! help
  disclosures explaining model effects and processing tradeoffs. Only one opens
  at a time; clicking outside or Escape dismisses it. Help can open upward near
  the viewport bottom, and advanced fields have their own explanations.
- Triangle choices now include 500, 1,000, 2,500, 5,000 and 10,000. Shared limits
  keep web validation and both Blender paths consistent at 500–200,000.
  Reduction precedes UV/color baking; lower budgets do not change inference.
- Existing demo mesh checks exported 499 triangles for a 500 target with a
  512-pixel photo-color atlas, and 2,499 triangles for a 2,500 untextured target.
  Both passed FBX reimport geometry/bounds checks; the textured minimum also
  passed UV/image checks. Original mesh bytes stayed unchanged, owned stages
  shut down, and no new shape inference was run.
- Create an asset clears all uploads and the name, restores default options,
  closes advanced options and hides the previous result. It cancels pending
  history restoration; polling cannot refill the blank draft. History stays saved.
- History selections still restore original uploads, including unselected extras,
  and all saved options. Missing images preserve the previous draft, stale loads
  cannot replace newer selections, and normal polling preserves edits.
- All 45 Python tests and the JavaScript interaction test pass. Checks include
  lower-budget persistence/bounds, low-poly history resubmission and complete
  reset during a pending restore. Browser checks verified help opening/dismissal,
  advanced help placement, the low-poly selector and the empty Create form.
- Existing extra-photo selection, photo colors and textured FBX/ZIP export
  remain integrated. The earlier color-only comparison retained its geometry
  and improved observed UV-texel coverage from 30.0% to 46.4%; optional estimated
  fill is reported separately. No shape inference is needed for history reuse.

## Next action / limits

- Owner selects a previous asset, reads the ! explanations and chooses a lower
  triangle budget for a separate variation, or uses Create an asset for a blank
  draft. Review silhouette and thin parts; very coarse reduction loses detail.
  Use README.md and MANUAL_TEST.md for the Unity workflow.
- Low-poly export is automatic simplification, not authored retopology or LODs.
  Actual game performance depends on texture/material/scene and import settings.
- Input/settings reuse does not promise an identical mesh: random seeds and
  optional Strata selection/planning can vary between generations.
- Estimated colors do not recover unseen detail. Tiny sprites, perspective,
  shadows and approximate camera fits still limit quality; seams can remain.
- Coverage measures UV texels, not likeness or physical area. Neutral/coverage/
  inferred masks are diagnostic and must not drive material opacity.
- Models remain static/unrigged, without generated PBR maps. Actual Unity Editor
  import remains a manual acceptance step. Neural Paint remains research only.
- Keep model weights, source images, generated assets and host-specific evidence
  ignored. Preserve existing jobs and shared Strata configuration.
