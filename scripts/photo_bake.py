"""Bake source-photo base color on a frozen UV mesh. CPU only, no neural paint."""
import argparse
import hashlib
import json
from pathlib import Path
import time

import numpy as np
from PIL import Image
from scipy import ndimage
from app_views import conditioned_views
from photo_projection import atlas_surface, fit_camera, sample_view, linear_to_srgb, extend_surface_colors


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bake(job_dir, geometry, output, size=1024, fill='neutral'):
    if fill not in ('neutral','nearest_surface'):
        raise ValueError('Unknown unseen-surface color mode')
    started = time.monotonic()
    output.mkdir(parents=True, exist_ok=False)
    job = json.loads((job_dir/'job.json').read_text())
    selected_views = conditioned_views(job_dir,job)
    provenance = json.loads((job_dir/'prepared/provenance.json').read_text())
    with np.load(geometry, allow_pickle=False) as data:
        vertices, faces, uv, normals = (data[name] for name in ('vertices','faces','uv','normals'))
    if not all(np.isfinite(a).all() for a in (vertices, uv, normals)):
        raise ValueError('Non-finite bake geometry')
    points, surface_normals, mask = atlas_surface(vertices, faces, uv, normals, size)
    selected_color = np.zeros((len(points), 3), np.float32)
    weights = np.zeros(len(points), np.float32)
    selected_view = np.full(len(points),-1,np.int16)
    view_reports = {}
    warnings = []
    for view_index,view in enumerate(selected_views):
        path = job_dir/'prepared'/f'{view}.png'
        if digest(path) != provenance['views'][view]['sha256']:
            raise ValueError(f'{view} reference integrity check failed')
        with Image.open(path) as image:
            rgba = np.asarray(image.convert('RGBA'), dtype=np.float32)/255
        camera = fit_camera(vertices, faces, rgba[:, :, 3], view)
        accepted = camera['silhouette_iou'] >= .40
        source = provenance['views'][view]
        view_reports[view] = dict(camera, accepted=accepted, source_sha256=digest(path),
            candidate_id=source.get('candidate_id',view),original_sha256=source.get('original_sha256'))
        if not accepted:
            warnings.append(f'{view}: silhouette fit rejected; use a more consistent angle/pose')
            continue
        rgb, weight = sample_view(points, surface_normals, vertices, faces, rgba, camera)
        # Approximate cameras do not align fine details across photos. Averaging
        # them produces doubled eyes/edges. Take the best visible view per texel.
        replace = weight > weights
        selected_color[replace] = rgb[replace]
        weights[replace] = weight[replace]
        selected_view[replace] = view_index
        view_reports[view]['contributing_texels'] = int(np.count_nonzero(weight > 1e-5))
        print(f'{view}: fit {camera["silhouette_iou"]:.3f}, contributes {(weight>1e-5).sum()} texels', flush=True)
    covered = weights > 1e-5
    for view_index,view in enumerate(selected_views):
        view_reports[view]['selected_texels'] = int(np.count_nonzero(covered & (selected_view==view_index)))
    coverage = float(covered.mean()) if len(covered) else 0
    if coverage < .20:
        raise ValueError('Too little photo coverage after visibility/alignment checks; shape remains preserved')
    colors = np.full((len(points), 3), .5, np.float32)  # explicit neutral sRGB fill
    colors[covered] = linear_to_srgb(selected_color[covered])
    inferred = np.zeros_like(covered)
    if fill == 'nearest_surface':
        colors = extend_surface_colors(points,colors,covered)
        inferred = ~covered
    atlas = np.full((size, size, 3), .5, np.float32)
    atlas[mask] = colors
    coverage_mask = np.zeros((size, size), bool)
    coverage_mask[mask] = covered
    # Pad outside UV islands only; gutters are never counted as photo coverage.
    distance, nearest = ndimage.distance_transform_edt(~mask, return_indices=True)
    gutter = (~mask) & (distance <= 4)
    atlas[gutter] = atlas[nearest[0][gutter], nearest[1][gutter]]
    Image.fromarray(np.rint(np.clip(atlas,0,1)*255).astype(np.uint8)).save(output/'basecolor.png')
    Image.fromarray(coverage_mask.astype(np.uint8)*255).save(output/'coverage.png')
    Image.fromarray(mask.astype(np.uint8)*255).save(output/'uvmask.png')
    map_names = ['basecolor','coverage','uvmask']
    if inferred.any():
        inferred_mask = np.zeros((size,size),bool)
        inferred_mask[mask] = inferred
        Image.fromarray(inferred_mask.astype(np.uint8)*255).save(output/'inferred.png')
        map_names.append('inferred')
    if coverage < .95:
        method = 'nearby surface colors extended as estimates' if inferred.any() else 'neutral fill applied'
        warnings.append(f'{100*(1-coverage):.1f}% of UV surface texels have no trusted photo color; {method}')
    report = {'mode':'photo_basecolor', 'status':'applied', 'atlas_size':size,
        'coverage_fraction':coverage, 'coverage_metric':'covered texels / UV surface texels; not physical area',
        'views':view_reports, 'views_used':[v for v,r in view_reports.items() if r['accepted']],
        'unknown_fill_srgb':None if inferred.any() else [.5,.5,.5],
        'fill_mode':fill,'inferred_fraction':float(inferred.mean()),
        'inference_method':'nearest observed 3D surface color; estimated, not recovered detail' if inferred.any() else None,
        'warnings':warnings, 'seconds':time.monotonic()-started,
        'geometry_sha256':digest(geometry), 'generated_or_inpainted_pixels':bool(inferred.any()),
        'neural_paint_used':False,'visibility_buffer_max_dimension':512,
        'camera_calibration':'approximate silhouette fit, not measured camera calibration',
        'color_fusion':'highest-confidence visible view per texel; no cross-view color averaging',
        'maps':{name:{'file':name+'.png', 'sha256':digest(output/(name+'.png')),
            'colorspace':'sRGB' if name=='basecolor' else 'linear data'}
            for name in map_names},
        'material':{'metallic':0., 'roughness':.8, 'parameters_are_assumed':True},
        'pbr_maps_generated':False}
    (output/'bake-report.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--job-dir',type=Path,required=True)
    parser.add_argument('--geometry',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--size',type=int,choices=(512,1024),default=1024)
    parser.add_argument('--fill',choices=('neutral','nearest_surface'),default='neutral')
    args = parser.parse_args()
    print(json.dumps(bake(args.job_dir,args.geometry,args.output_dir,args.size,args.fill),indent=2))
