"""One native Strata -> Hunyuan3D -> Blender job, with no inference retries."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import uuid

import psutil
from native_process import OwnedProcess
from runtime_paths import blender_executable

ROOT = Path(__file__).resolve().parents[1]


def save(path, data):
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def resources():
    result = {"utc": datetime.now(timezone.utc).isoformat(),
              "ram_available_bytes": psutil.virtual_memory().available,
              "ram_used_bytes": psutil.virtual_memory().total - psutil.virtual_memory().available}
    reading = subprocess.run(["nvidia-smi", "--query-gpu=memory.used,memory.free,temperature.gpu,power.draw,utilization.gpu",
        "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=5,
        creationflags=subprocess.CREATE_NO_WINDOW)
    result["gpu_raw"] = reading.stdout.strip()
    result["gpu_query_exit"] = reading.returncode
    if reading.returncode == 0:
        fields = reading.stdout.splitlines()[0].split(",")
        result["gpu_used_mib"], result["gpu_free_mib"] = float(fields[0]), float(fields[1])
    return result


def stage(command, name, timeout, folder, report, env=None):
    started = time.monotonic()
    record = {"name": name, "timeout_seconds": timeout, "command": list(map(str, command))}
    report["stages"].append(record)
    save(folder / "result.json", report)
    print(f"Starting {name} (limit {timeout}s)", flush=True)
    owned = OwnedProcess(list(map(str, command)), folder / f"{name}.log", env=env, cwd=str(ROOT))
    record["pid"] = owned.proc.pid
    def observe(pid, elapsed):
        sample = resources()
        sample.update(stage=name, pid=pid, elapsed_seconds=elapsed)
        with (folder / "telemetry.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(sample) + "\n")
        print(f"{name}: {elapsed:.0f}s, RAM available {sample['ram_available_bytes']/2**30:.1f} GiB, GPU {sample['gpu_raw']}", flush=True)
    try:
        code = owned.wait(timeout, observe=observe, cancel=folder / "CANCEL")
        record["exit_code"] = code
        if code:
            raise RuntimeError(f"{name} failed with exit code {code}; see {name}.log")
    finally:
        owned.close()
        record["owned_shutdown_confirmed"] = owned.shutdown_confirmed
        record["elapsed_seconds"] = time.monotonic() - started
        save(folder / "result.json", report)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strata-config", type=Path, default=ROOT / "work/strata-native.json")
    parser.add_argument("--blender", default=str(blender_executable()))
    parser.add_argument("--image", type=Path, default=ROOT / "inputs/demo.png")
    parser.add_argument("--subject", default="official demo object")
    parser.add_argument("--quality", choices=("balanced", "detailed"), default="balanced")
    args = parser.parse_args()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    folder = ROOT / "outputs" / run_id
    folder.mkdir(parents=True, exist_ok=False)
    lock = ROOT / "work/controller.lock"
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    os.write(fd, str(os.getpid()).encode())
    os.close(fd)
    report = {"run_id": run_id, "status": "running", "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "stages": [], "retry_policy": "No inference retries or restarts", "visual_acceptance": "pending human review",
        "resource_policy": "Record observations; stop on deadline, cancellation, process failure or shutdown failure. Hardware protections unchanged."}
    save(ROOT / "work/latest-run.json", {"run_id": run_id, "directory": str(folder)})
    try:
        from PIL import Image
        image_path = args.image.resolve(strict=True)
        provenance_path = image_path.parent / "provenance.json"
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
        digest = hashlib.sha256(image_path.read_bytes()).hexdigest()
        if digest != provenance["sha256"]:
            raise ValueError("Selected input differs from its recorded provenance.")
        with Image.open(image_path) as image:
            if image.mode != "RGBA":
                raise ValueError("Prepare a transparent RGBA reference before running the controller.")
            dimensions = list(image.size)
        shutil.copy2(image_path, folder / "reference.png")
        save(folder / "input.json", {"sha256": digest, "dimensions": dimensions,
            "subject": args.subject, "quality": args.quality, "provenance": provenance})
        report["reference_sha256"] = digest
        report["quality"] = args.quality
        baseline = resources()
        report["baseline"] = baseline
        print(f"Run directory: {folder}", flush=True)
        print(f"Baseline RAM available: {baseline['ram_available_bytes']/2**30:.2f} GiB; GPU: {baseline['gpu_raw']}", flush=True)
        config = json.loads(args.strata_config.read_text(encoding="utf-8"))
        save(folder / "strata-config.json", config)
        py = ROOT / ".venv/Scripts/python.exe"
        stage([py, "-B", "scripts/strata_plan.py", "prepare", "--run-dir", folder,
               "--config", args.strata_config], "prepare-plan", 30, folder, report)
        env = dict(os.environ)
        env["PATH"] = os.pathsep.join(config.get("lib_dirs", []) + [env.get("PATH", "")])
        # CLI mode terminates after this single bounded request. No HTTP service.
        command = [config["exe"], *config["args"], "--gpu", "0", "--tokens-file",
                   str(folder / "prompt-tokens.txt"), "--max-new", "512", "--stop-eos"]
        stage(command, "strata", 600, folder, report, env)
        released = False
        for _ in range(15):
            after = resources()
            if after.get("gpu_used_mib", float("inf")) <= baseline.get("gpu_used_mib", 0) + 512:
                released = True
                break
            time.sleep(1)
        report["after_strata"] = after
        report["strata_gpu_release_confirmed"] = released
        if not released:
            raise RuntimeError("GPU allocation did not return near baseline after Strata shutdown.")
        stage([py, "-B", "scripts/strata_plan.py", "decode", "--run-dir", folder,
               "--config", args.strata_config], "decode-plan", 30, folder, report)
        jobs = ROOT / "jobs" / run_id
        jobs.mkdir(parents=True, exist_ok=False)
        shutil.copy2(folder / "plan.json", jobs / "plan.json")
        stage([py, "-B", "scripts/generate_shape.py", "--run-dir", folder], "shape", 1200, folder, report)
        report["raw_sha256"] = hashlib.sha256((folder / "raw.glb").read_bytes()).hexdigest()
        stage([args.blender, "--background", "--factory-startup", "--python-exit-code", "1",
            "--python", "scripts/blender_export.py", "--", "--input", folder / "raw.glb",
            "--output-dir", folder / "blender", "--preview"], "blender", 180, folder, report)
        report["status"] = "completed"
        report["shape"] = json.loads((folder / "shape-report.json").read_text())
        report["blender"] = json.loads((folder / "blender/blender-report.json").read_text())
    except BaseException as exc:
        report["status"] = "failed"
        report["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        report["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        report["all_owned_stages_stopped"] = all(stage.get("owned_shutdown_confirmed", False) for stage in report["stages"])
        save(folder / "result.json", report)
        lock.unlink()
        print(json.dumps({"run_id": run_id, "status": report["status"],
                          "all_owned_stages_stopped": report["all_owned_stages_stopped"]}), flush=True)


if __name__ == "__main__":
    main()
