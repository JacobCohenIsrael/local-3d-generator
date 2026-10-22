"""Prepare a project-owned native Strata config. Never start an engine."""

import argparse
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-config", type=Path, required=True,
                        help="Path to your existing Strata base configuration; never published.")
    parser.add_argument("--output", type=Path, default=Path("work/strata-native.json"))
    args = parser.parse_args()
    if args.output.resolve() == args.base_config.resolve():
        raise ValueError("The project config must not overwrite the original Strata config.")
    original = args.base_config.read_bytes()
    base = json.loads(original.decode("utf-8-sig"))
    base_args = base["args"]
    required = ("--pack", "--native", "--ple-gguf", "--expert-profile")
    values = {}
    for flag in required:
        index = base_args.index(flag)
        value = base_args[index + 1]
        if not Path(value).exists():
            raise FileNotFoundError(value)
        values[flag] = value
    for path in (base["exe"], Path(base["tokenizer"]) / "vocab.json"):
        if not Path(path).is_file():
            raise FileNotFoundError(path)
    for directory in base.get("lib_dirs", []):
        if not Path(directory).is_dir():
            raise FileNotFoundError(directory)
    engine_args = [part for flag, value in values.items() for part in (flag, value)]
    engine_args += ["--expert-cache", "auto", "--prefill", "auto", "--spec", "2",
                    "--max-context", "4096", "--kv", "int8", "--mmap-experts",
                    "--vram-reserve-mib", "4096", "--prompt-cache", "0",
                    "--conversation-cache-mib", "0"]
    root = Path(__file__).resolve().parents[1]
    config = {"exe": base["exe"], "args": engine_args, "cwd": str(root / "work"),
              "tokenizer": base["tokenizer"], "model_name": base["model_name"],
              "log": str(root / "work/strata-native.log"),
              "lib_dirs": base.get("lib_dirs", []), "host": "127.0.0.1", "port": 8092,
              "gpu": 0, "open_browser": False, "api_monitor": False,
              "engine_silence_s": 120, "fit_max_tokens": False}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    if hashlib.sha256(args.base_config.read_bytes()).digest() != hashlib.sha256(original).digest():
        raise RuntimeError("Original Strata config changed while preparing the project config.")
    print(json.dumps({"prepared_config": str(args.output.resolve()), "engine_started": False,
                      "original_config_unchanged": True, "context": 4096,
                      "expert_mode": "mmap", "mtp_enabled": False, "port": 8092}, indent=2))


if __name__ == "__main__":
    main()
