"""Import the exact shape pipeline and report CUDA visibility without loading weights."""

import importlib.metadata
import json
import os
from pathlib import Path
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_HOME"] = str(ROOT / "work/huggingface")
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
sys.path.insert(0, str(ROOT / "work/vendor/Hunyuan3D-2.1/hy3dshape"))

import torch
import torchvision
from PIL import Image
from hy3dshape.pipelines import Hunyuan3DDiTFlowMatchingPipeline
from hy3dshape.models.denoisers.hunyuandit import HunYuanDiTPlain
from hy3dshape.models.conditioner import SingleImageEncoder
from hy3dshape.schedulers import FlowMatchEulerDiscreteScheduler


def main():
    image_path = ROOT / "work/vendor/Hunyuan3D-2.1/assets/demo.png"
    with Image.open(image_path) as image:
        image_info = {"mode": image.mode, "size": list(image.size),
                      "alpha_extrema": list(image.getchannel("A").getextrema())
                      if "A" in image.getbands() else None}
    available = torch.cuda.is_available()
    report = {
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version, "python_executable": sys.executable,
        "packages": {name: importlib.metadata.version(name) for name in (
            "torch", "torchvision", "transformers", "diffusers", "accelerate",
            "numpy", "pymeshlab", "trimesh", "timm")},
        "pipeline_import": Hunyuan3DDiTFlowMatchingPipeline.__name__,
        "model_class_import": HunYuanDiTPlain.__name__,
        "conditioner_import": SingleImageEncoder.__name__,
        "scheduler_import": FlowMatchEulerDiscreteScheduler.__name__,
        "cuda_available": available, "pytorch_cuda_runtime": torch.version.cuda,
        "gpu_name": torch.cuda.get_device_name(0) if available else None,
        "demo_image": image_info, "model_loaded": False, "inference_started": False,
    }
    output = ROOT / "work/shape-environment-check.json"
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    if not available:
        raise SystemExit("CUDA is not visible; do not start the GPU pipeline.")


if __name__ == "__main__":
    main()
