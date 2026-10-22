"""Blender background script: import a mesh, save .blend, export and reopen GLB.

Usage: blender --background --factory-startup --python-exit-code 1
       --python scripts/blender_export.py -- --input RAW.glb --output-dir DIR
"""

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import time

import bpy


def stats():
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    low, high = [math.inf] * 3, [-math.inf] * 3
    for obj in meshes:
        for vertex in obj.data.vertices:
            coordinate = obj.matrix_world @ vertex.co
            if not all(math.isfinite(value) for value in coordinate):
                raise ValueError("Mesh contains non-finite world coordinates.")
            for axis in range(3):
                low[axis] = min(low[axis], coordinate[axis])
                high[axis] = max(high[axis], coordinate[axis])
    return {"mesh_objects": len(meshes),
            "vertices": sum(len(obj.data.vertices) for obj in meshes),
            "polygons": sum(len(obj.data.polygons) for obj in meshes),
            "triangles": sum(sum(len(poly.vertices) - 2 for poly in obj.data.polygons) for obj in meshes),
            "world_bounds": [low, high] if any(obj.data.vertices for obj in meshes) else None}


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--preview", action="store_true")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    source = args.input.resolve(strict=True)
    output = args.output_dir.resolve()
    blend = output / "asset.blend"
    exported = output / "asset.glb"
    report_path = output / "blender-report.json"
    if source.suffix.lower() != ".glb":
        raise ValueError("The first milestone accepts GLB input only.")
    if source in (blend, exported) or any(path.exists() for path in (blend, exported, report_path)):
        raise FileExistsError("Choose a fresh output directory; raw inputs and old outputs are preserved.")
    output.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    input_digest = hashlib.sha256(source.read_bytes()).hexdigest()
    clear_scene()
    bpy.ops.import_scene.gltf(filepath=str(source))
    before = stats()
    if not before["vertices"] or not before["triangles"]:
        raise ValueError("Input has no usable mesh geometry.")
    # Make no intentional simplification or transform edits in this first check.
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    bpy.ops.export_scene.gltf(filepath=str(exported), export_format="GLB")
    clear_scene()
    bpy.ops.import_scene.gltf(filepath=str(exported))
    reopened = stats()
    if not reopened["vertices"] or reopened["triangles"] != before["triangles"]:
        raise ValueError("Exported GLB did not preserve triangle geometry when reopened.")
    for expected, actual in zip(sum(before["world_bounds"], []), sum(reopened["world_bounds"], [])):
        if not math.isclose(expected, actual, rel_tol=1e-5, abs_tol=1e-5):
            raise ValueError("Exported GLB changed the world-space bounds.")
    if hashlib.sha256(source.read_bytes()).hexdigest() != input_digest:
        raise RuntimeError("Raw input changed during Blender processing.")
    preview = None
    if args.preview:
        from mathutils import Vector
        low, high = (Vector(v) for v in reopened["world_bounds"])
        center = (low + high) * 0.5
        span = max(high - low)
        camera_data = bpy.data.cameras.new("Preview Camera")
        camera = bpy.data.objects.new("Preview Camera", camera_data)
        bpy.context.collection.objects.link(camera)
        camera.location = center + Vector((2.5, -3.5, 2.0)).normalized() * span * 3
        camera.rotation_euler = (center - camera.location).to_track_quat("-Z", "Y").to_euler()
        camera_data.type = "ORTHO"
        camera_data.ortho_scale = span * 1.6
        camera_data.clip_end = max(100, span * 20)
        scene = bpy.context.scene
        scene.camera = camera
        scene.render.engine = "CYCLES"
        scene.cycles.device = "CPU"
        scene.cycles.samples = 16
        scene.render.resolution_x = 640
        scene.render.resolution_y = 640
        scene.render.resolution_percentage = 100
        scene.world.color = (0.18, 0.18, 0.18)
        for index, direction in enumerate(((2, -3, 4), (-3, 1, 2))):
            light_data = bpy.data.lights.new(f"Preview Light {index}", "AREA")
            light_data.energy = 500 * span * span
            light_data.shape = "DISK"
            light_data.size = span * 2
            light = bpy.data.objects.new(light_data.name, light_data)
            bpy.context.collection.objects.link(light)
            light.location = center + Vector(direction) * span
            light.rotation_euler = (center - light.location).to_track_quat("-Z", "Y").to_euler()
        preview = output / "preview.png"
        scene.render.image_settings.file_format = "PNG"
        scene.render.filepath = str(preview)
        bpy.ops.render.render(write_still=True)
    report = {"blender_version": bpy.app.version_string, "input": str(source),
              "input_sha256": input_digest, "before": before, "reopened": reopened,
              "processing": "Import and re-export; no simplification or scale edits requested. Export may split vertices for normals.",
              "blend": str(blend), "glb": str(exported), "raw_input_unchanged": True,
              "export_reopened": True, "elapsed_seconds": time.monotonic() - started,
              "preview": str(preview) if preview else None,
              "visual_acceptance": "pending human review"}
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
