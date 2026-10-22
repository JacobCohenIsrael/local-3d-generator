# Current checkpoint

## Done in the extra-photo worktree

- Rebased onto sanitized main b652be3; the former public base is not an ancestor.
  This branch preserves portable Blender discovery and the noreply identity.
- Added up to 16 candidate uploads, explicit extra-photo camera azimuths and a
  48 MiB combined upload limit. Original four-slot requests remain supported.
- Every original is retained and every usable cutout is prepared locally.
  Deterministic CPU selection chooses at most four supported cardinal inputs;
  records every selection/non-selection reason; excludes unsupported angles;
  detects repeated bytes; and can replace an unusable/blurry front candidate.
- Candidate selection is explicitly separate from true all-angle conditioning
  or fusion. The checkpoint's four direction indices remain unchanged.
- Selection is exposed in the job history/UI, a downloadable report and the
  Unity ZIP. Reports distinguish submitted photos from conditioned views.
  Missing selection manifests fail closed for new-format jobs.
- Pipeline planning and shape model selection use actual conditioned directions,
  keeping GPU workload, deadlines, cancellation and retry bounds unchanged.
- CPU/HTTP tests pass, including the existing process lifecycle and resource
  boundary checks. The six-photo pipeline test uses real image preparation with
  stubbed model/export boundaries; no new GPU inference is claimed.
- Browser QA covered base uploads, multi-file extra uploads, azimuth entry,
  six-photo submission and visible per-photo reasons using an isolated CPU-only
  preview. The primary server and texture worktree were not modified.
- See MORE_ANGLES.md for the model boundary, API, selection rules and verification.

## Left / limitations

- True conditioning/fusion of more than four independent angles needs a new
  supported backend or trained model extension. This change does not supply it.
- Candidate sharpness/angle heuristics are not semantic or likeness evaluation;
  no improvement over the original four-view reconstruction has been measured.
- GPU generation through the new selection path and actual Unity Editor import
  have not been run in this worktree. Existing FBX export code is unchanged.
- Keep this branch isolated for review; do not merge or push changes to main.
  Preserve the sanitized history and keep local evidence/images Git-ignored.
- Texture, rigging, LODs, colliders and arbitrary camera-pose reconstruction remain
  separate features.
