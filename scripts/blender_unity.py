"""Static Unity FBX + preview GLB, with independent FBX reimport validation."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector
sys.path.insert(0, str(Path(__file__).resolve().parent))
from blender_export import stats, clear_scene


def compare(expected, actual, tolerance=1e-4):
    if expected['triangles'] != actual['triangles']:
        raise ValueError('FBX reimport changed triangle count')
    for a, b in zip(sum(expected['world_bounds'], []), sum(actual['world_bounds'], [])):
        if not math.isclose(a, b, rel_tol=tolerance, abs_tol=tolerance):
            raise ValueError('FBX reimport changed model bounds or scale')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--height', type=float, required=True)
    parser.add_argument('--triangles', type=int, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    args.input = args.input.resolve(strict=True)
    args.output_dir = args.output_dir.resolve()
    if not .1 <= args.height <= 20 or not 5000 <= args.triangles <= 200000:
        raise ValueError('Invalid Unity size or triangle budget')
    out = args.output_dir
    out.mkdir(exist_ok=False)
    digest = hashlib.sha256(args.input.read_bytes()).hexdigest()
    clear_scene()
    bpy.ops.import_scene.gltf(filepath=str(args.input))
    original = stats()
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
    bpy.ops.object.select_all(action='DESELECT')
    for obj in meshes:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    if len(meshes) > 1:
        bpy.ops.object.join()
    obj = bpy.context.object
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    # Blender's GLB importer already converts glTF Y-up to Blender Z-up.
    low, high = map(Vector, stats()['world_bounds'])
    height = high.z - low.z
    if height <= 1e-6:
        raise ValueError('Generated mesh has no height')
    scale = args.height / height
    center = Vector(((low.x + high.x) / 2, (low.y + high.y) / 2, low.z))
    for vertex in obj.data.vertices:
        vertex.co = (vertex.co - center) * scale
    obj.data.update()
    if original['triangles'] > args.triangles:
        modifier = obj.modifiers.new('Unity triangle budget', 'DECIMATE')
        modifier.ratio = args.triangles / original['triangles']
        bpy.ops.object.modifier_apply(modifier=modifier.name)
    triangulate = obj.modifiers.new('Explicit triangles', 'TRIANGULATE')
    bpy.ops.object.modifier_apply(modifier=triangulate.name)
    # Decimation can introduce duplicate faces. FBX silently removes them on
    # import, so validate explicitly before recording/exporting expected data.
    before_cleanup = stats()
    mesh_validation_changed = obj.data.validate(verbose=True, clean_customdata=True)
    obj.data.update()
    # Reduction may slightly move extremal vertices; enforce requested height
    # and base position on the final geometry, not on the pre-decimation mesh.
    low, high = map(Vector, stats()['world_bounds'])
    final_scale = args.height / (high.z - low.z)
    center = Vector(((low.x + high.x) / 2, (low.y + high.y) / 2, low.z))
    for vertex in obj.data.vertices:
        vertex.co = (vertex.co - center) * final_scale
    obj.data.update()
    obj.name = 'GeneratedAsset'
    bpy.context.scene.unit_settings.system = 'METRIC'
    bpy.context.scene.unit_settings.scale_length = 1.0
    expected = stats()
    bpy.ops.wm.save_as_mainfile(filepath=str(out / 'asset.blend'))
    bpy.ops.export_scene.gltf(filepath=str(out / 'asset.glb'), export_format='GLB', use_selection=True)
    bpy.ops.export_scene.fbx(filepath=str(out / 'asset.fbx'), use_selection=True, object_types={'MESH'},
        axis_forward='-Z', axis_up='Y', apply_unit_scale=True, apply_scale_options='FBX_SCALE_UNITS',
        use_mesh_modifiers=True, bake_anim=False, add_leaf_bones=False)
    clear_scene()
    bpy.ops.import_scene.fbx(filepath=str(out / 'asset.fbx'), use_anim=False)
    reopened = stats()
    compare(expected, reopened)
    if hashlib.sha256(args.input.read_bytes()).hexdigest() != digest:
        raise ValueError('Raw mesh changed')
    # Preview from the FBX reimport, not the in-memory pre-export model.
    low, high = map(Vector, reopened['world_bounds'])
    center = (low + high) / 2
    span = max(high - low)
    camera_data = bpy.data.cameras.new('Camera')
    camera = bpy.data.objects.new('Camera', camera_data)
    bpy.context.collection.objects.link(camera)
    camera.location = center + Vector((2, -3, 1.5)).normalized() * span * 3
    camera.rotation_euler = (center - camera.location).to_track_quat('-Z', 'Y').to_euler()
    camera_data.type = 'ORTHO'
    camera_data.ortho_scale = span * 1.45
    scene = bpy.context.scene
    scene.camera = camera
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = 12
    scene.render.resolution_x = scene.render.resolution_y = 640
    scene.world.color = (.16, .16, .16)
    for index, direction in enumerate(((2, -3, 4), (-3, 1, 2))):
        data = bpy.data.lights.new(f'Light {index}', 'AREA')
        data.energy = 500 * span**2
        data.size = span * 2
        light = bpy.data.objects.new(data.name, data)
        bpy.context.collection.objects.link(light)
        light.location = center + Vector(direction) * span
        light.rotation_euler = (center - light.location).to_track_quat('-Z', 'Y').to_euler()
    scene.render.image_settings.file_format = 'PNG'
    scene.render.filepath = str(out / 'preview.png')
    bpy.ops.render.render(write_still=True)
    report = {'original': original, 'exported': expected, 'fbx_reopened': reopened,
        'fbx_validation_pass': True, 'raw_unchanged': True, 'height_meters': args.height,
        'requested_triangle_budget': args.triangles, 'axis_forward': '-Z', 'axis_up': 'Y',
        'scale_factor_applied': scale, 'grounded': True, 'blender_version': bpy.app.version_string,
        'final_scale_correction': final_scale, 'mesh_validation_changed': mesh_validation_changed,
        'triangles_removed_by_validation': before_cleanup['triangles'] - expected['triangles'],
        'textures': False, 'rigged': False, 'unity_editor_import_tested': False,
        'fbx_sha256': hashlib.sha256((out / 'asset.fbx').read_bytes()).hexdigest()}
    (out / 'export-report.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
