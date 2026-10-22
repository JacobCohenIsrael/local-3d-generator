# Local asset workshop

Double-click **Start Local 3D.cmd** in the project folder, or run
`scripts/start_app.ps1`. Open http://127.0.0.1:8765. A hidden native Python
process serves the app. Codex, Docker and an open browser tab are not needed
for submitted jobs to finish. Restart the launcher after reboot; no scheduled
task or automatic Windows startup entry is installed.

## Use

1. Upload a front view and optionally left, back and right views of one subject.
   JPEG, PNG and WebP are accepted, up to 12 MB and 20 megapixels per image.
   Keep pose, framing, lighting and distance consistent. Transparent PNGs work
   best; otherwise choose automatic background removal for objects or people.
   **Add photos** accepts extra candidates up to 16 total / 48 MiB combined.
   Enter their azimuths; CPU selection chooses at most four supported inputs.
   The job shows all selected/unselected photos and reasons. See MORE_ANGLES.md.
2. Name the asset, choose quality, height in meters and a triangle budget.
3. Click Generate. The local queue runs one job at a time. Inspect the cutouts
   and final mesh in the viewer. Drag to orbit; use Wireframe to inspect density.
4. Download the FBX or Unity ZIP. Drag asset.fbx into a Unity project's Assets
   folder and assign a material. These are static meshes: no generated PBR
   textures, rig, animations, collision setup or LOD system.

One selected reference uses the existing Hunyuan3D-2.1 checkpoint. Two to four
selected views use Tencent's separate **Hunyuan3D-2mv** checkpoint. Extra uploads
are prepared and scored, but only the selected cardinal images reach its image
processor. Every photo has a selection reason and remains saved. This is
candidate selection, not fusion of every angle, and not calibrated
photogrammetry; extra views do not guarantee correct faces, hands or backs.

The default preset avoids loading the large Strata language model, which came
close to exhausting host RAM in earlier tests. Advanced options can use Strata
to choose settings from metadata; it does not have photo vision. Either option
runs autonomously. Nothing depends on Codex messages or approvals at job time.

## Automatic processing

The app keeps originals, generates alpha cutouts locally on CPU, plans bounded
settings, loads the appropriate CUDA shape model and checks finite geometry,
triangle count and bounding-box thickness. A rejected collapsed mesh may get
one new seed, capped at two attempts total. Crashes/OOM are reported without
restart. Flat-object checking can be disabled for intentionally thin subjects.
These heuristic checks cannot judge resemblance or accept a result for you.

Blender joins mesh objects, grounds the base, centers horizontally, scales the
height in meters, reduces triangles when above budget and triangulates. It saves
a .blend, browser-preview GLB, and FBX with -Z forward/Y up and unit metadata.
It independently reimports the FBX and compares triangle counts and world
bounds, then renders a preview from that FBX. Unity itself still needs visual
inspection of orientation/materials; an Editor import is not claimed by Blender
validation. A triangle budget is a reduction target, not a promise of useful
animation topology.

## Persistence and limits

- SQLite queue: work/web-jobs.sqlite3. Private originals, prepared images,
  raw attempts, settings, telemetry, logs and downloads: outputs/web-jobs/JOB_ID/.
  Both are Git-ignored. No automatic deletion or cloud upload is performed.
- Closing a browser tab leaves the app/worker running. App restart retains
  finished results and pending jobs; an in-flight job is marked interrupted,
  not secretly rerun. Cancellation closes the owned Windows process tree.
- At most 10 queued/running jobs. Preparation 240 seconds, optional Strata
  600 seconds, each shape attempt 1,200 seconds, Blender 300 seconds and overall
  job 3,600 seconds. Jobs stop if a deadline, cancellation or process error occurs.
- At least 8 GiB free system RAM and 10,000 MiB free GPU memory are required at
  job start. These checks are floors, not guarantees of memory fit. Work is
  sequential and existing hardware protections remain unchanged.
- Loopback binding only, checked Host/Origin, per-launch request token, fixed
  download paths and image size/format validation. The app is intended for
  this one machine; it is not a publicly hosted or multi-user service.

## Reproduce setup and checks

The current machine is prepared. A fresh Windows setup with Git and uv can run:

```powershell
.\scripts\setup_web_app.ps1
.\.venv\Scripts\python.exe -B -m unittest discover -s scripts -p 'test_*.py'
.\scripts\start_app.ps1
```

Setup downloads the pinned original 2.1 source/weights plus about 4.9 GB for
the multi-view checkpoint and local foreground models. It preserves shared
Strata configuration. Source and model revisions/hashes are in upstream.json.
The bundled Three.js 0.180.0 viewer works offline; its MIT license is retained
at web/vendor/THREE-LICENSE.txt. Tencent models/source and Blender retain their
own licenses. This project's MIT license does not relicense them.

## Verification

An end-to-end job ran through the real HTTP queue with Tencent's official
front/left/back example, composited to opaque images to exercise automatic
foreground removal. It passed on its first seed, used every view with
Hunyuan3D-2mv and generated 277,416 raw triangles.
Blender exported 50,000 triangles at 1.8 meters; independent FBX reimport retained
counts and world bounds. The browser
loaded the resulting GLB without console errors and rendered the interactive
mesh. The FBX and Unity ZIP download endpoints were checked separately.

Eleven automated checks cover process ownership, bounded second-seed behavior,
queue persistence, interrupted-job recovery, queued/running cancellation,
no crash restart, invalid uploads/settings, Host/Origin/token checks and file
path boundaries. Browser checks also exercised selecting a local image,
loading example views, submitting a job and cancelling it while queued.

An earlier test exposed one duplicate triangle after decimation; validation
now removes invalid/duplicate faces before recording the expected export.
Its failed result remains preserved. A repair check passed on the same raw
mesh before the final end-to-end run. Actual Unity Editor import and the
optional Strata path through this new app were not part of the final live test;
the original CLI Strata path was tested in FIRST_RUN.md.

Host-specific paths, hardware inventories, activity timestamps and detailed
resource observations remain in ignored local reports rather than public files.

## Sources

- https://huggingface.co/tencent/Hunyuan3D-2mv
- https://github.com/Tencent-Hunyuan/Hunyuan3D-2
- https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1
- https://github.com/danielgatis/rembg/tree/v2.0.65/rembg/sessions
