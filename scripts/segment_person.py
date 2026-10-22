"""Local CPU human segmentation; preserves source RGB pixels and records provenance."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil

import numpy as np
import onnxruntime as ort
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--crop", nargs=4, type=int, required=True)
    args = parser.parse_args()
    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    original = output / "original.jpg"
    if original.exists():
        raise FileExistsError("Use a fresh input directory to preserve existing images.")
    shutil.copy2(args.input, original)
    with Image.open(original) as opened:
        image = ImageOps.exif_transpose(opened).convert("RGB")
    crop = image.crop(tuple(args.crop))
    crop.save(output / "crop.png")
    model = ROOT / "models/segmentation/u2net_human_seg.onnx"
    options = ort.SessionOptions()
    options.intra_op_num_threads = 4
    options.inter_op_num_threads = 1
    session = ort.InferenceSession(str(model), sess_options=options, providers=["CPUExecutionProvider"])
    # U2Net human-segmentation input/output contract documented by rembg 2.0.65.
    rgb = np.asarray(crop.resize((320, 320), Image.Resampling.LANCZOS), dtype=np.float32)
    rgb /= max(float(rgb.max()), 1)
    normalized = (rgb - np.array([0.485, 0.456, 0.406], dtype=np.float32)) / np.array([0.229, 0.224, 0.225], dtype=np.float32)
    prediction = session.run(None, {session.get_inputs()[0].name: normalized.transpose(2, 0, 1)[None]})[0][0, 0]
    mask = np.clip((prediction - prediction.min()) / max(float(prediction.max() - prediction.min()), 1e-8), 0, 1)
    alpha = Image.fromarray((mask * 255).astype(np.uint8)).resize(crop.size, Image.Resampling.LANCZOS)
    alpha.save(output / "mask.png")
    cutout = crop.convert("RGBA")
    cutout.putalpha(alpha)
    box = alpha.point(lambda value: 255 if value > 32 else 0).getbbox()
    if not box:
        raise ValueError("No person mask returned.")
    cutout = ImageOps.expand(cutout.crop(box), border=16, fill=(0, 0, 0, 0))
    path = output / "reference.png"
    cutout.save(path)
    record = {"source": "Owner-provided photograph; local processing only",
        "source_sha256": hashlib.sha256(original.read_bytes()).hexdigest(),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "crop_xyxy": args.crop,
        "segmentation_model": "u2net_human_seg", "segmentation_runtime": ort.__version__,
        "segmentation_model_sha256": hashlib.sha256(model.read_bytes()).hexdigest(),
        "rgb_regenerated": False, "reference_size": list(cutout.size),
        "limitations": "Occluded hand/body surfaces and low-resolution facial detail remain inferred by the 3D model."}
    (output / "provenance.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
