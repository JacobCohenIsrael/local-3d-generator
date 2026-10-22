"""Foreground preparation for uploaded views, entirely local."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

import numpy as np
import onnxruntime as ort
from PIL import Image, ImageOps
from app_views import candidates_for, image_metrics, select_candidates, select_hybrid, HYBRID_STRATEGY
from runtime_paths import asset_root

ROOT = Path(__file__).resolve().parents[1]


def prepare_job(folder):
    job = json.loads((folder / 'job.json').read_text(encoding='utf-8'))
    output = folder / 'prepared'
    (output / 'candidates').mkdir(parents=True, exist_ok=False)
    session = None
    records = []
    for candidate in candidates_for(job):
        if (folder / 'CANCEL').exists():
            raise InterruptedError('Job cancelled during image preparation')
        view = candidate['id']
        source = folder / 'uploads' / f'{view}.image'
        record = dict(candidate, original_sha256=hashlib.sha256(source.read_bytes()).hexdigest())
        with Image.open(source) as opened:
            image = ImageOps.exif_transpose(opened).convert('RGBA')
        image.thumbnail((2048, 2048), Image.Resampling.LANCZOS)
        alpha = image.getchannel('A')
        if alpha.getextrema()[0] == 255 and job['settings']['background'] != 'keep':
            if session is None:
                model_name = 'u2net_human_seg' if job['settings']['background'] == 'person' else 'u2net'
                options = ort.SessionOptions()
                options.intra_op_num_threads = 4
                options.inter_op_num_threads = 1
                session = ort.InferenceSession(str(asset_root(ROOT) / f'models/segmentation/{model_name}.onnx'),
                    sess_options=options, providers=['CPUExecutionProvider'])
            rgb = np.asarray(image.convert('RGB').resize((320, 320), Image.Resampling.LANCZOS), dtype=np.float32)
            rgb /= max(float(rgb.max()), 1)
            rgb = (rgb - np.array([.485, .456, .406], dtype=np.float32)) / np.array([.229, .224, .225], dtype=np.float32)
            mask = session.run(None, {session.get_inputs()[0].name: rgb.transpose(2, 0, 1)[None]})[0][0, 0]
            mask = (mask - mask.min()) / max(float(mask.max() - mask.min()), 1e-8)
            alpha = Image.fromarray((np.clip(mask, 0, 1) * 255).astype(np.uint8)).resize(image.size, Image.Resampling.LANCZOS)
        # Remove faint background remnants; preserve antialiasing on foreground edges.
        alpha = alpha.point(lambda value: 0 if value < 16 else value)
        box = alpha.point(lambda value: 255 if value > 64 else 0).getbbox()
        if not box or (box[2] - box[0]) * (box[3] - box[1]) < 256:
            records.append(dict(record, error='No usable foreground; use a clearer photo or transparent PNG'))
            continue
        image.putalpha(alpha)
        image = ImageOps.expand(image.crop(box), border=16, fill=(0, 0, 0, 0))
        path = output / 'candidates' / f'{view}.png'
        image.save(path)
        records.append(dict(record, sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                            size=list(image.size), metrics=image_metrics(image)))
        print(f'Prepared {view}: {image.size}', flush=True)
    (folder / 'prepared-records.json').write_text(json.dumps(records, indent=2), encoding='utf-8')
    if job.get('view_strategy') == HYBRID_STRATEGY and any(c['id'] not in ('front', 'left', 'back', 'right') for c in records):
        if next((r for r in records if r['id'] == 'front'), {}).get('error'):
            finalize_job(folder, records, select_hybrid(records))  # retain audit before failing
        return None  # independent, bounded vision stage finalizes the selected inputs
    selection = select_hybrid(records) if job.get('view_strategy') == HYBRID_STRATEGY else select_candidates(records)
    return finalize_job(folder, records, selection)


def finalize_job(folder, records, selection):
    output = folder / 'prepared'
    (folder / 'view-selection.json').write_text(json.dumps(selection, indent=2), encoding='utf-8')
    if 'front' not in selection['selected']:
        raise ValueError('No usable front view after selection; supply a clear front image or a nearby alternate')
    by_id = {record['id']: record for record in records}
    views = {}
    for direction, candidate_id in selection['selected'].items():
        record = by_id[candidate_id]
        shutil.copy2(output / 'candidates' / f'{candidate_id}.png', output / f'{direction}.png')
        views[direction] = {key: record[key] for key in ('sha256', 'size', 'original_sha256')}
        views[direction].update(candidate_id=candidate_id, direction=direction)
    (output / 'provenance.json').write_text(json.dumps({'views': views, 'local_processing': True,
        'rgb_regenerated': False, 'selection_strategy': selection['strategy']}, indent=2), encoding='utf-8')
    print(f'{selection["submitted_count"]} submitted; {selection["selected_count"]} selected for conditioning', flush=True)
    return selection


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--job-dir', type=Path, required=True)
    args = parser.parse_args()
    prepare_job(args.job_dir)


if __name__ == '__main__':
    main()
