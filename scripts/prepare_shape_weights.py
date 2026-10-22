"""Download only official shape weights, configuration and license at one revision."""

import hashlib
import json
import os
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
os.environ["HF_HOME"] = str(ROOT / "work/huggingface")
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"

from huggingface_hub import HfApi, hf_hub_download


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    metadata_path = ROOT / "upstream.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    source = metadata["hunyuan3d"]
    repo = source["model_repository"]
    info = HfApi().model_info(repo, revision=source.get("model_revision", "main"), files_metadata=True)
    subfolder = source["model_subfolder"]
    required = [f"{subfolder}/config.yaml", f"{subfolder}/{source['weights_filename']}", "LICENSE", "Notice.txt"]
    available = {item.rfilename: item for item in info.siblings}
    report = {"started_at_utc": datetime.now(timezone.utc).isoformat(),
              "repository": repo, "revision": info.sha, "files": [], "model_loaded": False}
    output = ROOT / "work/shape-model-download.json"
    for filename in required:
        if filename not in available:
            raise FileNotFoundError(f"Required upstream file is absent: {filename}")
        print(f"Downloading {filename}", flush=True)
        path = Path(hf_hub_download(repo, filename, revision=info.sha,
                    local_dir=str(ROOT / "models/hunyuan3d-2.1")))
        digest = sha256_file(path)
        lfs = available[filename].lfs
        expected = lfs.sha256 if lfs else None
        if expected and digest != expected:
            raise ValueError(f"SHA-256 mismatch: {filename}")
        report["files"].append({"file": filename, "bytes": path.stat().st_size,
                                "sha256": digest, "upstream_lfs_sha256": expected})
        output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    source["model_revision"] = info.sha
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    report["completed_at_utc"] = datetime.now(timezone.utc).isoformat()
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"revision": info.sha, "files": len(report["files"]), "model_loaded": False}))


if __name__ == "__main__":
    main()
