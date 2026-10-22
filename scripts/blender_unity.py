"""Static Unity FBX + preview GLB, with independent FBX reimport validation."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
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


def prepare_geometry(source, height_meters, triangles):
    clear_scene()
    bpy.ops.import_scene.gltf(filepath=str(source))
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
    scale = height_meters / height
    center = Vector(((low.x + high.x) / 2, (low.y + high.y) / 2, low.z))
    for vertex in obj.data.vertices:
        vertex.co = (vertex.co - center) * scale
    obj.data.update()
    if original['triangles'] > triangles:
        modifier = obj.modifiers.new('Unity triangle budget', 'DECIMATE')
        modifier.ratio = triangles / original['triangles']
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
    final_scale = height_meters / (high.z - low.z)
    center = Vector(((low.x + high.x) / 2, (low.y + high.y) / 2, low.z))
    for vertex in obj.data.vertices:
        vertex.co = (vertex.co - center) * final_scale
    obj.data.update()
    obj.name = 'GeneratedAsset'
    bpy.context.scene.unit_settings.system = 'METRIC'
    bpy.context.scene.unit_settings.scale_length = 1.0
    return {'original':original, 'scale_factor_applied':scale, 'final_scale_correction':final_scale,
        'mesh_validation_changed':mesh_validation_changed,
        'triangles_removed_by_validation':before_cleanup['triangles']-stats()['triangles']}


def texture_signature():
    result = {'uv_layers':0, 'images':[]}
    for obj in bpy.context.scene.objects:
        if obj.type != 'MESH':
            continue
        result['uv_layers'] += len(obj.data.uv_layers)
        for material in obj.data.materials:
            if material and material.use_nodes:
                for node in material.node_tree.nodes:
                    if node.type == 'TEX_IMAGE' and node.image:
                        path = Path(bpy.path.abspath(node.image.filepath))
                        result['images'].append({'file':path.name, 'exists':path.is_file(),
                            'sha256':hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None})
    return result


def apply_texture(texture_dir, output):
    report = json.loads((texture_dir/'bake-report.json').read_text())
    (output/'textures').mkdir()
    for name in ('basecolor','coverage','uvmask',*(['inferred'] if 'inferred' in report['maps'] else [])):
        source = texture_dir/f'{name}.png'
        if hashlib.sha256(source.read_bytes()).hexdigest() != report['maps'][name]['sha256']:
            raise ValueError('Texture integrity check failed')
        shutil.copy2(source,output/'textures'/source.name)
    image = bpy.data.images.load(str(output/'textures/basecolor.png'),check_existing=False)
    image.colorspace_settings.name = 'sRGB'
    image.pack()  # make the separate .blend download portable too
    material = bpy.data.materials.new('PhotoBaseColor')
    material.use_nodes = True
    nodes, links = material.node_tree.nodes, material.node_tree.links
    principled = nodes.get('Principled BSDF')
    principled.inputs['Metallic'].default_value = 0
    principled.inputs['Roughness'].default_value = .8
    texture = nodes.new('ShaderNodeTexImage')
    texture.image = image
    links.new(texture.outputs['Color'],principled.inputs['Base Color'])
    for obj in bpy.context.scene.objects:
        if obj.type=='MESH':
            obj.data.materials.clear()
            obj.data.materials.append(material)
    manifest = dict(report, maps={name:dict(record,file='textures/'+record['file']) for name,record in report['maps'].items()})
    (output/'material-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--height',type=float,required=True)
    parser.add_argument('--triangles',type=int,required=True)
    parser.add_argument('--prepared-blend',type=Path)
    parser.add_argument('--texture-dir',type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    args.input = args.input.resolve(strict=True)
    out = args.output_dir.resolve()
    if not .1 <= args.height <= 20 or not 5000 <= args.triangles <= 200000:
        raise ValueError('Invalid Unity size or triangle budget')
    out.mkdir(exist_ok=False)
    digest = hashlib.sha256(args.input.read_bytes()).hexdigest()
    if args.prepared_blend:
        geometry_path = args.prepared_blend.resolve(strict=True)
        metadata = json.loads((geometry_path.parent/'geometry-report.json').read_text())
        if metadata['raw_sha256'] != digest:
            raise ValueError('Prepared geometry input hash differs')
        bpy.ops.wm.open_mainfile(filepath=str(geometry_path),load_ui=False,use_scripts=False)
        for obj in bpy.context.scene.objects:
            obj.select_set(obj.type=='MESH')
    else:
        metadata = prepare_geometry(args.input,args.height,args.triangles)
    manifest = apply_texture(args.texture_dir.resolve(),out) if args.texture_dir else None
    expected = stats()
    bpy.ops.wm.save_as_mainfile(filepath=str(out / 'asset.blend'))
    bpy.ops.export_scene.gltf(filepath=str(out / 'asset.glb'), export_format='GLB', use_selection=True)
    bpy.ops.export_scene.fbx(filepath=str(out / 'asset.fbx'), use_selection=True, object_types={'MESH'},
        axis_forward='-Z', axis_up='Y', apply_unit_scale=True, apply_scale_options='FBX_SCALE_UNITS',
        use_mesh_modifiers=True, bake_anim=False, add_leaf_bones=False,
        path_mode='RELATIVE',embed_textures=False)
    clear_scene()
    for material in list(bpy.data.materials):
        bpy.data.materials.remove(material)
    for image in list(bpy.data.images):
        bpy.data.images.remove(image)
    bpy.ops.import_scene.fbx(filepath=str(out / 'asset.fbx'), use_anim=False)
    reopened = stats()
    compare(expected, reopened)
    texture_check = texture_signature()
    if manifest and (not texture_check['uv_layers'] or not any(image['sha256']==manifest['maps']['basecolor']['sha256']
            for image in texture_check['images'])):
        raise ValueError('FBX lost its UV map or external base-color texture')
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
    report = {**metadata, 'exported': expected, 'fbx_reopened': reopened,
        'fbx_validation_pass': True, 'raw_unchanged': True, 'height_meters': args.height,
        'requested_triangle_budget': args.triangles, 'axis_forward': '-Z', 'axis_up': 'Y',
        'grounded': True, 'blender_version': bpy.app.version_string,
        'textures': bool(manifest), 'fbx_texture_validation':texture_check,
        'material_manifest':manifest, 'rigged': False, 'unity_editor_import_tested': False,
        'fbx_sha256': hashlib.sha256((out / 'asset.fbx').read_bytes()).hexdigest()}
    (out / 'export-report.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
