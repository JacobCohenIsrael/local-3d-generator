# Try extra-photo selection and textured FBX together

## Open

From the primary project folder, double-click **Start Local 3D.cmd** and open
http://127.0.0.1:8765. The prepared local installation has Strata vision configured.
For a fresh machine, follow README.md and its extra-photo recognition setup first.
Closing the browser leaves submitted jobs running; launch again after a reboot.
The app does not require Codex.

The history contains **Combined demo · extra photos and colors** as a reference:
six uploads, three selected directions and a textured 50,000-triangle export.
Its 76.7% UV-texel color coverage includes an automatically selected extra photo.

## Your photos

1. Upload a clear **front** view. Optional **left/back/right** photos act as
   trusted anchors. Keep the whole subject visible with the same pose and lighting.
2. Drop more photos into **Drop extra photos here**, or use **Browse photos**.
   There are no angle fields. The limit is 16 total photos / 48 MiB.
3. Start with **Balanced**, **50,000** triangles and **Automatic preset** planning.
   Leave **Bake colors from your photos** selected. Choose background removal for
   objects/people, or keep background only for clean isolated images.
4. Click **Select views & generate**. Extra photos trigger Strata vision even
   with preset planning. It stops before Hunyuan loads, then Blender prepares
   UVs, bakes photo colors and exports the files automatically.

## Review

- Expand **selected / submitted photos**. Each upload should have a selected or
  skipped reason. Confirm that selected directions match your subject. At most
  four photos condition Hunyuan and supply color. Extras improve input selection;
  they are not all fused together. Top/bottom views are not selected.
- Drag to rotate and scroll to zoom. Use **Hide colors / Show colors** to
  distinguish mesh defects from projection errors, and **Wireframe** for density.
- Review coverage. Unobserved surface texels stay gray. This is UV-texel coverage,
  not likeness or physical surface area. Seams and misplaced details can remain.
- A warned untextured result means baking failed; inspect the report. Failed
  vision/generation processes stop without automatically restarting inference.

## Unity

Download **FBX + colors ZIP**, extract it and copy the whole folder into Assets.
Keep `textures/` beside `asset.fbx`. Create a material for your render pipeline,
assign `textures/basecolor.png` to Base Map/Albedo with sRGB enabled, metallic 0
and smoothness 0.2 (assumed roughness 0.8). Assign it to the model in a scene.
Coverage and UV masks are diagnostics, not opacity maps.

Check scale, orientation, seams and geometry before use. The model is static and
unrigged, without generated PBR maps or animation-ready topology. Automated checks
use Blender reimport; actual Unity Editor import remains a manual acceptance step.

**Try an example** loads official front/left/back images and clears existing
uploads. This skips vision when no extras are present, while still exercising
image-to-mesh and photo color export.
