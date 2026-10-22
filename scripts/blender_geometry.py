"""Freeze reduced, normalized geometry and UVs before photo color baking."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import bpy
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
from blender_unity import prepare_geometry
from blender_export import stats
from mesh_budget import MIN_TRIANGLES, MAX_TRIANGLES


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--height',type=float,required=True)
    parser.add_argument('--triangles',type=int,required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    if not .1 <= args.height <= 20 or not MIN_TRIANGLES <= args.triangles <= MAX_TRIANGLES:
        raise ValueError('Invalid geometry budget')
    out = args.output_dir.resolve()
    out.mkdir(exist_ok=False)
    source = args.input.resolve(strict=True)
    report = prepare_geometry(source,args.height,args.triangles)
    obj = bpy.context.object
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=1.151917,island_margin=.012,area_weight=0,
                            correct_aspect=True,scale_to_bounds=True)
    bpy.ops.object.mode_set(mode='OBJECT')
    mesh = obj.data
    vertices = np.array([v.co[:] for v in mesh.vertices],np.float32)
    faces = np.array([p.vertices[:] for p in mesh.polygons],np.int32)
    vertex_normals = np.array([v.normal[:] for v in mesh.vertices],np.float32)
    uv = np.array([[mesh.uv_layers.active.data[i].uv[:] for i in p.loop_indices] for p in mesh.polygons],np.float32)
    np.savez_compressed(out/'geometry.npz',vertices=vertices,faces=faces,uv=uv,normals=vertex_normals[faces])
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'geometry.blend'))
    report.update(raw_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        prepared=stats(),uv_method='Blender smart project',topology_frozen=True)
    (out/'geometry-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report),flush=True)


if __name__=='__main__':
    main()
