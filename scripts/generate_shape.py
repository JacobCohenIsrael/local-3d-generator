"""One offline Hunyuan3D generation using a validated Strata plan."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
os.environ["HF_HOME"] = str(ROOT / "work/huggingface")
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
sys.path.insert(0, str(ROOT / "work/vendor/Hunyuan3D-2.1/hy3dshape"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args()
    from strata_plan import validate_plan
    plan = validate_plan(json.loads((args.run_dir / "plan.json").read_text()))
    image = args.run_dir / "reference.png"
    provenance = json.loads((args.run_dir / "input.json").read_text())
    if hashlib.sha256(image.read_bytes()).hexdigest() != provenance["sha256"]:
        raise ValueError("Reference image differs from its recorded provenance.")
    import torch
    import trimesh
    from PIL import Image
    from hy3dshape.pipelines import Hunyuan3DDiTFlowMatchingPipeline
    output = args.run_dir / "raw.glb"
    if output.exists():
        raise FileExistsError(output)
    started = time.monotonic()
    torch.cuda.reset_peak_memory_stats()
    # The verified checkpoint is FP16. Constructing its modules in FP16 avoids
    # temporary full-FP32 parameter copies on the CPU; this worker is isolated.
    previous_dtype = torch.get_default_dtype()
    torch.set_default_dtype(torch.float16)
    print("Loading the local verified FP16 shape checkpoint", flush=True)
    pipeline = Hunyuan3DDiTFlowMatchingPipeline.from_pretrained(
        str(ROOT / "models/hunyuan3d-2.1"), device="cuda", dtype=torch.float16,
        use_safetensors=False)
    torch.set_default_dtype(previous_dtype)
    loaded = time.monotonic()
    print("Shape model loaded; starting the single image-to-mesh request", flush=True)
    with Image.open(image) as reference:
        mesh = pipeline(image=reference.convert("RGBA"), num_inference_steps=plan["steps"],
            guidance_scale=plan["guidance_scale"], octree_resolution=plan["octree_resolution"],
            num_chunks=plan["num_chunks"], generator=torch.Generator(device="cuda").manual_seed(plan["seed"]))[0]
    if not isinstance(mesh, trimesh.Trimesh) or not len(mesh.faces):
        raise ValueError("No usable mesh returned.")
    mesh.export(str(output))
    report = {"plan": plan, "raw_mesh": str(output), "vertices": len(mesh.vertices),
        "triangles": len(mesh.faces), "model_load_seconds": loaded - started,
        "total_seconds": time.monotonic() - started, "torch_version": torch.__version__,
        "cuda_peak_allocated_bytes": torch.cuda.max_memory_allocated(),
        "cuda_peak_reserved_bytes": torch.cuda.max_memory_reserved(),
        "raw_sha256": hashlib.sha256(output.read_bytes()).hexdigest()}
    (args.run_dir / "shape-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
