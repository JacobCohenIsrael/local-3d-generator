"""Read-only native inventory. No inference, installation, or server startup."""

import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from datetime import datetime, timezone


class MemoryStatus(ctypes.Structure):
    _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
        (name, ctypes.c_ulonglong) for name in (
            "total_physical", "available_physical", "total_pagefile",
            "available_pagefile", "total_virtual", "available_virtual", "extended"
        )
    ]


def file_record(path):
    path = Path(path)
    if not path.is_file():
        return {"path": str(path), "exists": False}
    return {"path": str(path), "exists": True, "bytes": path.stat().st_size}


def command(args):
    try:
        completed = subprocess.run(args, capture_output=True, text=True, timeout=30)
        return {"exit_code": completed.returncode,
                "stdout": completed.stdout.strip(), "stderr": completed.stderr.strip()}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"error": str(exc)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strata-root", type=Path, default=Path("work/strata"))
    parser.add_argument("--model-root", type=Path, default=Path("models/strata"))
    parser.add_argument("--output", type=Path, default=Path("work/native-inventory.json"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    report = {"observed_at_utc": datetime.now(timezone.utc).isoformat(),
              "inference_started": False, "inventory_python": sys.version,
              "project_root": str(root)}
    memory = MemoryStatus()
    memory.length = ctypes.sizeof(memory)
    if os.name == "nt" and ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory)):
        report["ram_bytes"] = {"total": memory.total_physical,
                               "available": memory.available_physical}
    report["disk_bytes"] = {str(root.anchor): dict(zip(
        ("total", "used", "free"), shutil.disk_usage(root.anchor)))}
    report["gpu"] = command(["nvidia-smi", "--query-gpu=name,memory.total,memory.used,driver_version",
                             "--format=csv,noheader"])
    strata = {"files": [file_record(args.strata_root / p) for p in (
        "strata.exe", "engine/strata.exe", ".venv/Scripts/python.exe", "serve/server.py")],
        "build_manifests": {}}
    for relative in ("BUILD.json", "engine/BUILD.json"):
        path = args.strata_root / relative
        if path.is_file():
            strata["build_manifests"][relative] = json.loads(path.read_text(encoding="utf-8-sig"))
    original_config = args.strata_root / "strata-coder-iq1_m.json"
    if original_config.is_file():
        strata["original_config_sha256"] = hashlib.sha256(original_config.read_bytes()).hexdigest()
    strata["model_files"] = [file_record(path) for path in sorted(
        (args.model_root / "models/coder-IQ1_M").glob("*.gguf"))]
    strata["pack_files"] = [file_record(args.model_root / "packs/coder-iq1_m" / name)
                            for name in ("dense.bin", "experts.bin", "index.txt")]
    report["strata"] = strata
    blender = shutil.which("blender")
    report["blender"] = {"path": blender, "version": command([blender, "--version"]) if blender else None}
    report["hunyuan3d"] = {
        "existing_cache_locations": {str(path): path.exists() for path in (
            Path.home() / ".cache/huggingface/hub/models--tencent--Hunyuan3D-2.1",
            Path.home() / ".cache/hy3dgen/tencent/Hunyuan3D-2.1")},
        "project_source": str(root / "work/vendor/Hunyuan3D-2.1"),
        "project_python": command([str(root / ".venv/Scripts/python.exe"), "--version"]),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(args.output.resolve()), "ram": report.get("ram_bytes"),
                      "strata_version": strata["build_manifests"].get("engine/BUILD.json", {}).get("version"),
                      "blender": blender, "inference_started": False}, indent=2))


if __name__ == "__main__":
    main()
