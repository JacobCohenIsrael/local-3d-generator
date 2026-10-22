"""Deterministic CPU selection for a model with four supported view indices.

Extra photos compete for a supported direction. They are never presented to
the checkpoint as novel camera indices or as an all-angle reconstruction.
"""
import json
import math

import numpy as np
from PIL import Image

DIRECTIONS = ('front', 'left', 'back', 'right')
ANGLES = dict(zip(DIRECTIONS, (0, 90, 180, 270)))
MAX_CANDIDATES = 16
MAX_TOTAL_BYTES = 48 * 1024 * 1024
MAX_ANGLE_ERROR = 30
STRATEGY = 'cardinal_selection_v1'


def candidates_for(job):
    """Read new jobs while supporting the original four-view job format."""
    return job.get('candidates') or [
        {'id': view, 'name': view, 'azimuth': ANGLES[view]}
        for view in job['views']]


def closest_direction(angle):
    distances = {name: abs((angle - value + 180) % 360 - 180) for name, value in ANGLES.items()}
    name = min(DIRECTIONS, key=distances.get)
    return name, distances[name]


def image_metrics(image):
    """A heuristic for sharpness, source size and exposure, not semantic quality."""
    rgba = image.convert('RGBA')
    gray = np.asarray(rgba.convert('L').resize((256, 256), Image.Resampling.LANCZOS), dtype=np.float32)
    alpha = np.asarray(rgba.getchannel('A').resize((256, 256), Image.Resampling.NEAREST))
    interior = (alpha[1:-1, 1:-1] > 128) & (alpha[:-2, 1:-1] > 128) & (alpha[2:, 1:-1] > 128)
    interior &= (alpha[1:-1, :-2] > 128) & (alpha[1:-1, 2:] > 128)
    laplacian = (gray[:-2, 1:-1] + gray[2:, 1:-1] + gray[1:-1, :-2]
                 + gray[1:-1, 2:] - 4 * gray[1:-1, 1:-1])
    pixels = gray[alpha > 128]
    sharpness = float(np.var(laplacian[interior])) if interior.any() else 0.0
    exposure = float(np.mean((pixels > 8) & (pixels < 247))) if len(pixels) else 0.0
    resolution = min(1.0, math.sqrt(rgba.width * rgba.height) / 768)
    quality = .65 * min(1.0, math.log1p(sharpness) / math.log1p(500)) + .2 * resolution + .15 * exposure
    return {'sharpness': sharpness, 'exposure': exposure, 'resolution_score': resolution,
            'quality_score': quality}


def select_candidates(items):
    """Every input gets a reason. At most one candidate per supported direction."""
    records = []
    for item in items:
        entry = dict(item)
        direction, error = closest_direction(entry['azimuth'])
        entry.update(closest_direction=direction, angular_error_degrees=error,
                     selected_as=None, status='not_selected')
        if entry.get('error'):
            entry['reason'] = entry['error']
        elif error > MAX_ANGLE_ERROR:
            entry['reason'] = f'Outside the {MAX_ANGLE_ERROR}° selection window for a supported direction'
        else:
            # Exact angle matters, but a sharper nearby candidate may win.
            entry['selection_score'] = entry['metrics']['quality_score'] - .35 * error / MAX_ANGLE_ERROR
            entry['reason'] = 'A higher-ranked candidate was selected for this direction'
        records.append(entry)
    selected, used_hashes = {}, set()
    for direction in DIRECTIONS:
        eligible = [entry for entry in records if entry['closest_direction'] == direction
                    and 'selection_score' in entry]
        eligible.sort(key=lambda entry: (-entry['selection_score'], entry['angular_error_degrees'],
                                         entry['id'] not in DIRECTIONS, entry['id']))
        for entry in eligible:
            if entry['original_sha256'] in used_hashes:
                entry['reason'] = 'Duplicate image bytes already selected for another direction'
                continue
            selected[direction] = entry['id']
            used_hashes.add(entry['original_sha256'])
            entry.update(selected_as=direction, status='selected', reason='Highest heuristic score for this direction')
            break
    return {'strategy': STRATEGY, 'max_conditioned_views': 4,
            'submitted_count': len(records), 'selected_count': len(selected),
            'selected': selected, 'candidates': records,
            'all_uploads_conditioned': len(selected) == len(records),
            'extra_view_fusion': False,
            'limitation': 'Hunyuan3D-2mv conditions on at most four selected cardinal views. '
                          'Other uploads are retained and scored, not fused into the mesh.',
            'selection_window_degrees': MAX_ANGLE_ERROR,
            'quality_scoring': 'Heuristic sharpness, resolution, exposure and angular distance; '
                               'does not assess correct pose, framing, identity or reconstruction accuracy.'}


def conditioned_views(folder, job):
    path = folder / 'view-selection.json'
    if not path.exists():
        if job.get('candidates') or job.get('extra_views') or len(candidates_for(job)) > 4:
            raise ValueError('Extra-view job has no selection manifest; generation cannot silently ignore uploads')
        names = list(job['views'])
    else:
        selection = json.loads(path.read_text(encoding='utf-8'))
        names = list(selection['selected'])
        if selection['strategy'] != STRATEGY:
            raise ValueError('Unknown view selection strategy')
    if not names or 'front' not in names or len(names) > 4 or set(names) - set(DIRECTIONS):
        raise ValueError('The selected input needs a front view and at most four supported directions')
    return [view for view in DIRECTIONS if view in names]
