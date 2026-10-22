"""Blender-only synthetic CPU bake/FBX/GLB probe; no photos or neural models.

Run through Blender --background --factory-startup --python-exit-code 1
--python scripts/probe_texture_roundtrip.py -- --output-dir work/texture-probe
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys

import bpy


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def material_images(obj):
    result = []
    for material in obj.data.materials:
        if material and material.use_nodes:
            for node in material.node_tree.nodes:
                if node.type == 'TEX_IMAGE' and node.image:
                    image_path = Path(bpy.path.abspath(node.image.filepath))
                    result.append({'image':node.image.name, 'path':str(image_path),
                        'exists':image_path.is_file(), 'sha256':sha256(image_path) if image_path.is_file() else None})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    out = args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=False)
    (out/'textures').mkdir()
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    bpy.ops.mesh.primitive_cube_add()
    obj = bpy.context.object
    # Blender's primitive cube includes a UV map; this checks transport, not
    # a photogrammetric camera solve or automatic UV unwrap on a generated mesh.
    assert len(obj.data.uv_layers) == 1
    source = bpy.data.images.new('SyntheticSource', width=16, height=16, alpha=True)
    source.pixels = [channel for y in range(16) for x in range(16)
        for channel in ((.9,.08,.03,1) if (x//4+y//4)%2 else (.02,.25,.8,1))]
    material = bpy.data.materials.new('SyntheticTextureProbe')
    material.use_nodes = True
    obj.data.materials.append(material)
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    nodes.clear()
    source_node = nodes.new('ShaderNodeTexImage')
    source_node.image = source
    emission = nodes.new('ShaderNodeEmission')
    output = nodes.new('ShaderNodeOutputMaterial')
    links.new(source_node.outputs['Color'], emission.inputs['Color'])
    links.new(emission.outputs[0], output.inputs['Surface'])
    baked = bpy.data.images.new('BaseColor', width=64, height=64, alpha=True)
    baked_node = nodes.new('ShaderNodeTexImage')
    baked_node.image = baked
    nodes.active = baked_node
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = 1
    scene.render.threads_mode = 'FIXED'
    scene.render.threads = 2
    scene.render.bake.margin = 2
    bpy.ops.object.bake(type='EMIT')
    baked.filepath_raw = str(out/'textures/basecolor.png')
    baked.file_format = 'PNG'
    baked.save()
    colors = list(baked.pixels)
    assert max(colors[0::4])-min(colors[0::4]) > .5, 'CPU bake did not retain the color pattern'
    nodes.remove(source_node)
    nodes.remove(emission)
    bsdf = nodes.new('ShaderNodeBsdfPrincipled')
    links.new(baked_node.outputs['Color'], bsdf.inputs['Base Color'])
    links.new(bsdf.outputs[0], output.inputs['Surface'])
    source_hash = sha256(out/'textures/basecolor.png')
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'probe.blend'))
    bpy.ops.export_scene.fbx(filepath=str(out/'probe.fbx'), use_selection=True,
        object_types={'MESH'}, axis_forward='-Z', axis_up='Y', bake_anim=False,
        path_mode='RELATIVE', embed_textures=False)
    bpy.ops.export_scene.gltf(filepath=str(out/'probe.glb'), export_format='GLB', use_selection=True)
    glb_bytes = (out/'probe.glb').read_bytes()
    json_length, chunk_type = struct.unpack_from('<II', glb_bytes, 12)
    assert chunk_type == 0x4E4F534A
    gltf = json.loads(glb_bytes[20:20+json_length])
    assert gltf['images'] and all('bufferView' in image for image in gltf['images'])
    assert gltf['materials'][0]['pbrMetallicRoughness']['baseColorTexture']['index'] >= 0
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    # Clear unused material/image datablocks so reimport cannot pass by reusing
    # the original in-memory texture or material.
    for old in list(bpy.data.materials):
        bpy.data.materials.remove(old)
    for old in list(bpy.data.images):
        bpy.data.images.remove(old)
    bpy.ops.import_scene.fbx(filepath=str(out/'probe.fbx'), use_anim=False)
    fbx_obj = next(o for o in bpy.context.scene.objects if o.type=='MESH')
    images = material_images(fbx_obj)
    assert any(i['exists'] and i['sha256']==source_hash for i in images), images
    assert len(fbx_obj.data.uv_layers) == 1
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    for old in list(bpy.data.materials):
        bpy.data.materials.remove(old)
    for old in list(bpy.data.images):
        bpy.data.images.remove(old)
    bpy.ops.import_scene.gltf(filepath=str(out/'probe.glb'))
    glb_obj = next(o for o in bpy.context.scene.objects if o.type=='MESH')
    assert len(glb_obj.data.uv_layers)==1
    assert any(node.type=='TEX_IMAGE' and node.image for mat in glb_obj.data.materials
        if mat and mat.use_nodes for node in mat.node_tree.nodes)
    report = {'blender':bpy.app.version_string, 'synthetic_only':True,
        'cpu_bake_pass':True, 'fbx_external_basecolor_and_uv_roundtrip_pass':True,
        'glb_embedded_image_and_uv_roundtrip_pass':True, 'basecolor_sha256':source_hash,
        'fbx_reimport_images':images, 'neural_texture_generation_tested':False,
        'camera_alignment_or_photo_projection_tested':False, 'unity_editor_import_tested':False}
    (out/'probe-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2),flush=True)


if __name__ == '__main__':
    main()
