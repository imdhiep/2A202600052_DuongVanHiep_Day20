#!/usr/bin/env python3
"""Sweep GGUF quantizations (Q2_K → Q8_0) on the same model.

Downloads the missing quantizations on demand. Reports decode tok/s and
file size, so the trade-off is concrete: how many bits per weight buys
how many tokens per second on YOUR hardware.

Usage:
    python BONUS-llama-cpp-optimization/benchmarks/quant-sweep.py
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

try:
    from huggingface_hub import hf_hub_download
except ImportError:
    print("ERROR: huggingface_hub missing.", file=sys.stderr)
    sys.exit(1)


# Same tier mapping as 00-setup/download-model.py, plus extra quantization filenames.
TIERS: dict[str, dict] = {
    "TinyLlama-1.1B": {
        "repo": "TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF",
        "files": {
            "Q2_K":   "tinyllama-1.1b-chat-v1.0.Q2_K.gguf",
            "Q4_K_M": "tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf",
            "Q5_K_M": "tinyllama-1.1b-chat-v1.0.Q5_K_M.gguf",
            "Q6_K":   "tinyllama-1.1b-chat-v1.0.Q6_K.gguf",
            "Q8_0":   "tinyllama-1.1b-chat-v1.0.Q8_0.gguf",
        },
    },
    "Qwen2.5-1.5B-Instruct": {
        "repo": "Qwen/Qwen2.5-1.5B-Instruct-GGUF",
        "files": {
            "Q2_K":   "qwen2.5-1.5b-instruct-q2_k.gguf",
            "Q4_K_M": "qwen2.5-1.5b-instruct-q4_k_m.gguf",
            "Q5_K_M": "qwen2.5-1.5b-instruct-q5_k_m.gguf",
            "Q6_K":   "qwen2.5-1.5b-instruct-q6_k.gguf",
            "Q8_0":   "qwen2.5-1.5b-instruct-q8_0.gguf",
        },
    },
    "Llama-3.2-3B-Instruct": {
        "repo": "bartowski/Llama-3.2-3B-Instruct-GGUF",
        "files": {
            "Q2_K":   "Llama-3.2-3B-Instruct-Q2_K.gguf",
            "Q4_K_M": "Llama-3.2-3B-Instruct-Q4_K_M.gguf",
            "Q5_K_M": "Llama-3.2-3B-Instruct-Q5_K_M.gguf",
            "Q6_K":   "Llama-3.2-3B-Instruct-Q6_K.gguf",
            "Q8_0":   "Llama-3.2-3B-Instruct-Q8_0.gguf",
        },
    },
    "Qwen2.5-7B-Instruct": {
        "repo": "Qwen/Qwen2.5-7B-Instruct-GGUF",
        "files": {
            "Q2_K":   "qwen2.5-7b-instruct-q2_k.gguf",
            "Q4_K_M": "qwen2.5-7b-instruct-q4_k_m.gguf",
            "Q5_K_M": "qwen2.5-7b-instruct-q5_k_m.gguf",
            "Q6_K":   "qwen2.5-7b-instruct-q6_k.gguf",
            "Q8_0":   "qwen2.5-7b-instruct-q8_0.gguf",
        },
    },
}

LLAMA_BENCH = Path("BONUS-llama-cpp-optimization/llama.cpp/build/bin/llama-bench")
LLAMA_BENCH_EXE = LLAMA_BENCH.with_suffix(".exe")
TG_RE = re.compile(r"\|\s*tg128\s*\|\s*([0-9.]+)\s*±")
TEXT_ENCODING = "utf-8"


def find_bench() -> Path:
    for p in (LLAMA_BENCH, LLAMA_BENCH_EXE):
        if p.exists():
            return p
    print("ERROR: build llama.cpp first.", file=sys.stderr)
    sys.exit(1)


def pick_tier_for_active() -> tuple[str, dict]:
    active = json.loads(Path("models/active.json").read_text(encoding=TEXT_ENCODING))
    for key, t in TIERS.items():
        if key in active["repo_id"]:
            return key, t
    raise SystemExit(f"Tier not recognized for {active['repo_id']}")


def ensure_quant(tier: dict, label: str) -> Path:
    repo = tier["repo"]
    fname = tier["files"][label]
    out_dir = Path("models")
    existing = list(out_dir.rglob(fname))
    if existing:
        return existing[0]
    print(f"   downloading {label} ({fname})")
    return Path(hf_hub_download(repo_id=repo, filename=fname, local_dir=str(out_dir)))


def run_bench(bench: Path, model: Path, threads: int, n_gpu: int) -> float:
    cmd = [str(bench), "-m", str(model), "-t", str(threads), "-ngl", str(n_gpu),
           "-p", "0", "-n", "64", "-r", "2"]
    out = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding=TEXT_ENCODING,
        errors="replace",
        check=False,
    ).stdout
    m = TG_RE.search(out)
    return float(m.group(1)) if m else 0.0


def main() -> int:
    bench = find_bench()
    hw = json.loads(Path("hardware.json").read_text(encoding=TEXT_ENCODING))
    threads = hw["cpu"].get("cores_physical") or 4
    backends = hw.get("gpu", {}).get("backends", {})
    n_gpu = 99 if any(v for k, v in backends.items() if k != "cpu_only") else 0
    tier_key, tier = pick_tier_for_active()

    print(f"==> quant sweep on tier {tier_key}")
    print(f"    threads: {threads}  n_gpu: {n_gpu}\n")

    rows: list[dict] = []
    for label in ("Q2_K", "Q4_K_M", "Q5_K_M", "Q6_K", "Q8_0"):
        try:
            path = ensure_quant(tier, label)
        except Exception as e:
            print(f"   ! skip {label}: {e}")
            continue
        size_mb = path.stat().st_size / 1024 / 1024
        tps = run_bench(bench, path, threads, n_gpu)
        rows.append({"quant": label, "size_mb": round(size_mb, 1), "tok_s": tps})
        print(f"   {label:6s}  size={size_mb:6.1f} MB   tg128={tps:6.1f} tok/s")

    if not rows:
        return 1

    md = "# Bonus — Quantization sweep\n\n"
    md += f"Tier: `{tier_key}`  ·  threads: `{threads}`  ·  n_gpu_layers: `{n_gpu}`\n\n"
    md += "| quant | size (MB) | tg128 (tok/s) |\n|:--|--:|--:|\n"
    md += "\n".join(f"| {r['quant']} | {r['size_mb']:.1f} | {r['tok_s']:.1f} |" for r in rows)
    md += "\n\n"
    md += (
        "Smaller quantization = smaller file + faster decode (memory-bandwidth-bound) "
        "but lower output quality. Q4_K_M is the production sweet spot. Q8_0 is "
        "almost-lossless but ~4× the bytes per weight; useful only when you have RAM "
        "to spare. Q2_K is for *truly* tight RAM — quality drops noticeably.\n"
    )
    out_dir = Path("benchmarks")
    out_dir.mkdir(exist_ok=True)
    (out_dir / "bonus-quant-sweep.md").write_text(md, encoding=TEXT_ENCODING)
    (out_dir / "bonus-quant-sweep.json").write_text(json.dumps(rows, indent=2), encoding=TEXT_ENCODING)
    print("\n" + md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
