"""One offline single/multi-view inference, in a disposable owned process."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
os.environ.update(HF_HOME=str(ROOT / 'work/huggingface'), HF_HUB_OFFLINE='1',
                  TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--job-dir', type=Path, required=True)
    parser.add_argument('--attempt-dir', type=Path, required=True)
    args = parser.parse_args()
    job = json.loads((args.job_dir / 'job.json').read_text())
    plan = json.loads((args.attempt_dir / 'plan.json').read_text())
    multi = len(job['views']) > 1
    import torch
    import numpy as np
    from PIL import Image
    if multi:
        sys.path.insert(0, str(ROOT / 'work/vendor/Hunyuan3D-2'))
        from hy3dgen.shapegen import Hunyuan3DDiTFlowMatchingPipeline
        model_path, subfolder = ROOT / 'models/hunyuan3d-2mv', 'hunyuan3d-dit-v2-mv'
    else:
        sys.path.insert(0, str(ROOT / 'work/vendor/Hunyuan3D-2.1/hy3dshape'))
        from hy3dshape.pipelines import Hunyuan3DDiTFlowMatchingPipeline
        model_path, subfolder = ROOT / 'models/hunyuan3d-2.1', 'hunyuan3d-dit-v2-1'
    started = time.monotonic()
    torch.cuda.reset_peak_memory_stats()
    # Use upstream FP32 module construction for this smaller multiview checkpoint.
    # The larger 2.1 checkpoint retains the previously verified FP16 load path.
    previous_dtype = torch.get_default_dtype()
    if not multi:
        torch.set_default_dtype(torch.float16)
    try:
        pipeline = Hunyuan3DDiTFlowMatchingPipeline.from_pretrained(str(model_path), subfolder=subfolder,
            use_safetensors=multi, device='cuda', dtype=torch.float16)
    finally:
        torch.set_default_dtype(previous_dtype)
    prepared = args.job_dir / 'prepared'
    provenance = json.loads((prepared / 'provenance.json').read_text())
    views = {}
    for name in job['views']:
        path = prepared / f'{name}.png'
        if hashlib.sha256(path.read_bytes()).hexdigest() != provenance['views'][name]['sha256']:
            raise ValueError('Prepared image integrity check failed')
        views[name] = Image.open(path).convert('RGBA')
    print(f'Generating from {len(views)} view(s), seed {plan["seed"]}', flush=True)
    mesh = pipeline(image=views if multi else views['front'], num_inference_steps=plan['steps'],
        octree_resolution=plan['octree_resolution'], guidance_scale=plan['guidance_scale'],
        num_chunks=plan['num_chunks'], generator=torch.Generator('cuda').manual_seed(plan['seed']))[0]
    output = args.attempt_dir / 'raw.glb'
    mesh.export(str(output))
    finite = bool(np.isfinite(mesh.vertices).all())
    extents = mesh.extents.tolist()
    ratio = min(extents) / max(max(extents), 1e-9)
    reason = None
    if not finite or len(mesh.faces) < 64:
        reason = 'Empty, tiny or non-finite geometry'
    elif ratio < .015 and not job['settings']['allow_flat']:
        reason = 'Geometry collapsed into an almost flat slab'
    report = {'model': 'Hunyuan3D-2mv' if multi else 'Hunyuan3D-2.1', 'views_used': list(views),
        'plan': plan, 'vertices': len(mesh.vertices), 'triangles': len(mesh.faces), 'extents': extents,
        'extent_ratio': ratio, 'quality_pass': reason is None, 'rejection_reason': reason,
        'visual_acceptance': 'Human review required; automatic checks do not assess likeness',
        'seconds': time.monotonic() - started, 'cuda_peak_allocated_bytes': torch.cuda.max_memory_allocated(),
        'raw_sha256': hashlib.sha256(output.read_bytes()).hexdigest()}
    (args.attempt_dir / 'shape-report.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
