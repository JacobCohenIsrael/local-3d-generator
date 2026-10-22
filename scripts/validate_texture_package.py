"""Blender check of an extracted Unity ZIP, including relocated texture paths.

Run Blender --background --factory-startup --python-exit-code 1 --python
scripts/validate_texture_package.py -- --asset-dir work/extracted --report work/check.json
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import bpy
sys.path.insert(0,str(Path(__file__).resolve().parent))
from blender_export import clear_scene, stats
from blender_unity import compare


def validate(folder):
    folder = folder.resolve(strict=True)
    manifest = json.loads((folder/'material-manifest.json').read_text())
    export = json.loads((folder/'export-report.json').read_text())
    for record in manifest['maps'].values():
        path = (folder/record['file']).resolve(strict=True)
        if not path.is_relative_to(folder):
            raise ValueError('Texture escaped the package folder')
        if hashlib.sha256(path.read_bytes()).hexdigest() != record['sha256']:
            raise ValueError('Packaged texture hash differs')
    fbx = folder/'asset.fbx'
    if hashlib.sha256(fbx.read_bytes()).hexdigest() != export['fbx_sha256']:
        raise ValueError('Packaged FBX hash differs')
    clear_scene()
    for material in list(bpy.data.materials):
        bpy.data.materials.remove(material)
    for image in list(bpy.data.images):
        bpy.data.images.remove(image)
    bpy.ops.import_scene.fbx(filepath=str(fbx),use_anim=False)
    actual = stats()
    compare(export['exported'],actual)
    linked_images = []
    meshes = [obj for obj in bpy.context.scene.objects if obj.type=='MESH']
    for obj in meshes:
        if not obj.data.uv_layers:
            raise ValueError('Imported mesh has no UVs')
        found = False
        for material in obj.data.materials:
            if not material or not material.use_nodes:
                continue
            for node in material.node_tree.nodes:
                if node.type!='BSDF_PRINCIPLED':
                    continue
                for link in node.inputs['Base Color'].links:
                    image = getattr(link.from_node,'image',None)
                    if image is None:
                        continue
                    path = Path(bpy.path.abspath(image.filepath)).resolve(strict=True)
                    if not path.is_relative_to(folder):
                        raise ValueError('FBX resolves its color image outside the extracted package')
                    if hashlib.sha256(path.read_bytes()).hexdigest()!=manifest['maps']['basecolor']['sha256']:
                        raise ValueError('FBX resolved a different base color')
                    found = True
                    linked_images.append(path.relative_to(folder).as_posix())
        if not found:
            raise ValueError('Imported mesh has no connected base-color image')
    return {'passed':True,'fbx_reopened':actual,'resolved_images':linked_images,
        'all_images_inside_package':True,'unity_editor_import_tested':False}


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--asset-dir',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    report = validate(args.asset_dir)
    args.report.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report),flush=True)
