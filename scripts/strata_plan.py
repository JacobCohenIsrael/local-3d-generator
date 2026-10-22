"""Prepare/decode one native Strata CLI request; no server, no retries."""

import argparse
import json
import math
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]


def tokenizer(config):
    strata_root = Path(config["exe"]).parent.parent
    sys.path.insert(0, str(strata_root / "tools"))
    sys.path.insert(0, str(strata_root))
    import strata_tokenizer
    folder = Path(config["tokenizer"])
    vocab = json.loads((folder / "vocab.json").read_text(encoding="utf-8"))
    tokens = [None] * len(vocab)
    for text, index in vocab.items():
        tokens[index] = text
    return strata_tokenizer.Tokenizer(tokens,
        (folder / "merges.txt").read_text(encoding="utf-8").split("\n"),
        json.loads((folder / "token_type.json").read_text(encoding="utf-8")))


def validate_plan(plan):
    keys = {"seed", "steps", "octree_resolution", "guidance_scale", "num_chunks"}
    if not isinstance(plan, dict) or set(plan) != keys:
        raise ValueError("Plan must contain exactly the five generation settings.")
    for key, low, high in (("seed", 0, 2**31 - 1), ("steps", 20, 50), ("num_chunks", 1024, 8000)):
        if type(plan[key]) is not int or not low <= plan[key] <= high:
            raise ValueError(f"Invalid {key}")
    if type(plan["octree_resolution"]) is not int or plan["octree_resolution"] not in (128, 192, 256, 384):
        raise ValueError("Invalid octree resolution")
    guidance = plan["guidance_scale"]
    if type(guidance) not in (int, float) or not math.isfinite(guidance) or not 3 <= guidance <= 7:
        raise ValueError("Invalid guidance scale")
    return plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "decode"))
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    tok = tokenizer(config)
    folder = args.run_dir
    if args.action == "prepare":
        from serve.frontend import ChatTemplate
        reference = json.loads((folder / "input.json").read_text(encoding="utf-8"))
        width, height = reference["dimensions"]
        detail = ("The owner requests the best detail practical for this GPU: prefer 50 steps and extraction resolution 384, with decoding chunks around 2048 to limit memory. "
                  if reference["quality"] == "detailed" else "Plan a balanced first test with modest decoding memory. ")
        messages = [
            {"role": "system", "content": "You plan one local image-to-mesh test. Return only one JSON object with the requested five settings. No markdown, explanations, tools, commands or code."},
            {"role": "user", "content": detail + f"Plan one geometry-only {reference.get('model', 'Hunyuan3D-2.1')} run within a 16 GB VRAM budget. The front input is a {width}x{height} transparent RGBA cutout: {reference['subject']}. Supplied views: {reference.get('views', ['front'])}. You have image metadata only; do not claim to see it. " + "Choose these five JSON fields: seed (integer 0..2147483647), steps (integer 20..50), octree_resolution (128, 192, 256, or 384), guidance_scale (number 3..7), num_chunks (integer 1024..8000). The controller fixes image/output paths and runs Blender afterward; do not include those fields."},
        ]
        rendered = ChatTemplate(Path(config["tokenizer"]) / "chat_template.jinja").render(
            messages, enable_thinking=False)
        tokens = tok.encode(rendered, parse_special=True)
        if len(tokens) + 512 > 4096:
            raise ValueError("Prompt/output exceed the prepared context.")
        (folder / "prompt.txt").write_text(rendered, encoding="utf-8")
        (folder / "prompt-tokens.txt").write_text(",".join(map(str, tokens)), encoding="ascii")
        (folder / "request.json").write_text(json.dumps({"messages": messages,
            "input_tokens": len(tokens), "max_output_tokens": 512, "vision_used": False}, indent=2), encoding="utf-8")
        print(f"Prepared one real planning request: {len(tokens)} input tokens, up to 512 output.")
    else:
        log = (folder / "strata.log").read_text(encoding="utf-8", errors="replace")
        match = re.search(r"^output\s*:\s*([\d \t]+)$", log, re.MULTILINE)
        if not match:
            raise ValueError("Strata did not return its generated token IDs.")
        ids = list(map(int, match.group(1).split()))
        text = tok.decode(ids)
        (folder / "response.txt").write_text(text, encoding="utf-8")
        content = text
        for marker in ("<|im_end|>", "<|endoftext|>"):
            content = content.split(marker, 1)[0]
        content = content.strip()
        if content.startswith("```json\n") and content.endswith("```"):
            content = content[8:-3].strip()
        plan = validate_plan(json.loads(content))
        (folder / "plan.json").write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
        (folder / "response-metrics.json").write_text(json.dumps({"output_tokens": len(ids),
            "response_repaired": False, "valid_plan": True}), encoding="utf-8")
        print(json.dumps(plan))


if __name__ == "__main__":
    main()
