"""Foreground preparation for uploaded views, entirely local."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import onnxruntime as ort
from PIL import Image, ImageOps
from runtime_paths import asset_root

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--job-dir', type=Path, required=True)
    args = parser.parse_args()
    job = json.loads((args.job_dir / 'job.json').read_text())
    output = args.job_dir / 'prepared'
    output.mkdir(exist_ok=False)
    session = None
    views = {}
    for view in job['views']:
        source = args.job_dir / 'uploads' / f'{view}.image'
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
            raise ValueError(f'No usable foreground in {view}; use a clear photo or transparent PNG.')
        image.putalpha(alpha)
        image = ImageOps.expand(image.crop(box), border=16, fill=(0, 0, 0, 0))
        path = output / f'{view}.png'
        image.save(path)
        views[view] = {'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'size': list(image.size),
                       'original_sha256': hashlib.sha256(source.read_bytes()).hexdigest()}
        print(f'Prepared {view}: {image.size}', flush=True)
    (output / 'provenance.json').write_text(json.dumps({'views': views, 'local_processing': True,
        'rgb_regenerated': False}, indent=2))


if __name__ == '__main__':
    main()
