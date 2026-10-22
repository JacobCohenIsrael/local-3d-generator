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
HYBRID_STRATEGY = 'hybrid_vision_v1'


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


def validate_assessment(data):
    """A model supplies observations only; it cannot change paths or execute steps."""
    keys = {'direction', 'confidence', 'same_subject', 'pose_consistent', 'usable', 'reason'}
    if not isinstance(data, dict) or set(data) != keys:
        raise ValueError('Vision response must contain exactly the six observation fields')
    if not isinstance(data['direction'], str) or data['direction'] not in (*DIRECTIONS, 'unknown', 'unsupported'):
        raise ValueError('Invalid visual direction')
    confidence = data['confidence']
    if type(confidence) not in (int, float) or not math.isfinite(confidence) or not 0 <= confidence <= 1:
        raise ValueError('Invalid confidence')
    for key in ('same_subject', 'pose_consistent', 'usable'):
        if type(data[key]) is not bool:
            raise ValueError(f'Invalid {key}')
    if not isinstance(data['reason'], str) or not 1 <= len(data['reason'].strip()) <= 300:
        raise ValueError('Invalid observation reason')
    return data


def select_hybrid(items, assessments=None, analysis=None):
    """Trust explicit anchors; accept only confident, compatible extras. No angle input."""
    assessments = assessments or {}
    records, selected, hashes = [], {}, set()
    anchor_hashes = {r['original_sha256'] for r in items if r['id'] in DIRECTIONS and not r.get('error')}
    for item in items:
        entry = dict(item, selected_as=None, status='not_selected')
        anchor = item['id'] in DIRECTIONS
        entry['source'] = 'labelled_anchor' if anchor else 'strata_vision'
        entry['direction'] = item['id'] if anchor else 'unknown'
        if item.get('error'):
            entry['reason'] = item['error']
        elif anchor:
            entry['reason'] = 'Trusted labelled anchor'
        elif item['original_sha256'] in anchor_hashes:
            entry['source'] = 'duplicate_check'
            entry['reason'] = 'Duplicate image bytes match a labelled anchor; adds no independent view'
        else:
            observation = assessments.get(item['id'])
            try:
                entry['assessment'] = validate_assessment(observation)
                entry['direction'] = observation['direction']
                if not observation['same_subject']:
                    entry['reason'] = 'Subject match uncertain: ' + observation['reason']
                elif not observation['pose_consistent']:
                    entry['reason'] = 'Pose does not match the anchors: ' + observation['reason']
                elif not observation['usable']:
                    entry['reason'] = 'Obstructed, incomplete or unclear photo: ' + observation['reason']
                elif observation['direction'] not in DIRECTIONS:
                    entry['reason'] = 'Unsupported or uncertain viewpoint: ' + observation['reason']
                elif observation['confidence'] < .85:
                    entry['reason'] = 'Viewpoint confidence below the selection threshold: ' + observation['reason']
                else:
                    entry['eligible'] = True
                    entry['reason'] = 'A stronger photo is already available for this direction'
            except ValueError:
                entry['reason'] = 'Vision did not return a valid observation; retained without conditioning'
        records.append(entry)
    # Front first, then optional anchors. Repeated bytes cannot establish a new direction.
    for direction in DIRECTIONS:
        anchor = next((r for r in records if r['id'] == direction and not r.get('error')), None)
        if anchor:
            if anchor['original_sha256'] in hashes:
                anchor['reason'] = 'Duplicate image bytes already selected for another direction'
            else:
                selected[direction] = anchor
                hashes.add(anchor['original_sha256'])
    for direction in DIRECTIONS:
        eligible = [r for r in records if r.get('eligible') and r['direction'] == direction]
        eligible.sort(key=lambda r: (-r['metrics']['quality_score'], -r['assessment']['confidence'], r['id']))
        anchor = selected.get(direction)
        for entry in eligible:
            if entry['original_sha256'] in hashes:
                entry['reason'] = 'Duplicate image bytes already selected'
                continue
            if anchor and (entry['assessment']['confidence'] < .95 or
                           entry['metrics']['quality_score'] < anchor['metrics']['quality_score'] + .15):
                entry['reason'] = 'Kept the trusted anchor; this extra is not a clearly stronger replacement'
                continue
            if anchor:
                hashes.remove(anchor['original_sha256'])
                anchor['reason'] = 'Replaced by a clearly sharper, high-confidence compatible photo'
            selected[direction] = entry
            hashes.add(entry['original_sha256'])
            entry['reason'] = ('Clearly stronger compatible replacement for the labelled anchor' if anchor
                               else 'Confident compatible photo fills a missing direction')
            break
    for direction, entry in selected.items():
        entry.update(selected_as=direction, status='selected')
    return {'strategy': HYBRID_STRATEGY, 'selected': {d: r['id'] for d, r in selected.items()},
            'submitted_count': len(records), 'selected_count': len(selected), 'candidates': records,
            'max_conditioned_views': 4, 'extra_view_fusion': False,
            'all_uploads_conditioned': len(selected) == len(records),
            'vision': analysis or {'used': False, 'reason': 'No extra photos submitted'},
            'thresholds': {'fill_confidence': .85, 'replace_confidence': .95, 'replace_quality_gain': .15},
            'limitation': 'At most four selected cardinal photos condition Hunyuan. Confidence is model-reported, '
                          'not a calibrated probability. Unselected photos are retained, not fused.'}


def conditioned_views(folder, job):
    path = folder / 'view-selection.json'
    if not path.exists():
        if job.get('candidates') or job.get('extra_views') or len(candidates_for(job)) > 4:
            raise ValueError('Extra-view job has no selection manifest; generation cannot silently ignore uploads')
        names = list(job['views'])
    else:
        selection = json.loads(path.read_text(encoding='utf-8'))
        names = list(selection['selected'])
        if selection['strategy'] not in (STRATEGY, HYBRID_STRATEGY):
            raise ValueError('Unknown view selection strategy')
    if not names or 'front' not in names or len(names) > 4 or set(names) - set(DIRECTIONS):
        raise ValueError('The selected input needs a front view and at most four supported directions')
    return [view for view in DIRECTIONS if view in names]
