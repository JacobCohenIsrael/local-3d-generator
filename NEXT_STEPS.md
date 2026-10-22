# Current checkpoint: reuse asset history

## Completed

- Selecting a history item restores sections 01 and 02: original labelled
  uploads, all extra photos in saved order, name and every saved generation
  setting. The latest asset is restored once on page load. Polling preserves
  subsequent edits; generating creates a separate job without changing history.
- A bounded upload route returns original JPEG/PNG/WebP bytes with their correct
  MIME type. It exposes only registered images, supports older labelled-view
  jobs, and does not use prepared cutouts or discard unselected extras.
- Reference loading is staged before replacing the form. Missing originals
  preserve the previous inputs. Submission is blocked while loading, switching
  history cancels stale loads, and replaced preview URLs are released.
- Advanced options expose the saved color-atlas size. History can restore custom
  triangle budgets and fractional heights accepted by the API. Old jobs use
  historical defaults for absent settings, including untextured output.
- All 44 Python tests and the expanded JavaScript interaction test pass.
  Checks cover original-byte replay, JPEG/WebP and legacy HTTP retrieval,
  boundaries, all settings, polling, missing images and stale selection races.
  Browser checks verified restoring older demos and editing advanced settings.
- Existing extra-photo selection, photo colors and textured FBX/ZIP export
  remain integrated. The earlier color-only comparison retained its geometry
  and improved observed UV-texel coverage from 30.0% to 46.4%; optional estimated
  fill is reported separately. No shape inference is needed for history reuse.

## Next action / limits

- Owner selects a previous asset, reviews restored inputs/settings and generates
  a separate variation when ready. See README.md and MANUAL_TEST.md.
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
