#!/usr/bin/env python3
"""Sweep -ngl (GPU layer offload) on CUDA / Metal / Vulkan / ROCm builds.

For students with a GPU. Shows the "split inference" knob explicitly:
0 = CPU only, 8/16/24 = partial offload, 99 = full offload. Useful for
understanding when partial offload beats nothing (small VRAM, large model).

Usage:
    python BONUS-llama-cpp-optimization/benchmarks/gpu-offload-sweep.py
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

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


def main() -> int:
    hw = json.loads(Path("hardware.json").read_text(encoding=TEXT_ENCODING))
    backends = hw.get("gpu", {}).get("backends", {})
    if not any(v for k, v in backends.items() if k != "cpu_only"):
        print("No GPU detected — this sweep needs CUDA / Metal / Vulkan / ROCm.")
        print("Run BONUS-llama-cpp-optimization/benchmarks/thread-sweep.py instead.")
        return 1

    bench = find_bench()
    model = json.loads(Path("models/active.json").read_text(encoding=TEXT_ENCODING))["primary_model"]
    threads = hw["cpu"].get("cores_physical") or 4

    grid = [0, 8, 16, 24, 32, 99]
    print(f"==> gpu-offload sweep on {Path(model).name}")
    print(f"    threads: {threads}  grid: {grid}  active: {[k for k,v in backends.items() if v and k != 'cpu_only']}\n")

    rows: list[dict] = []
    for ngl in grid:
        cmd = [str(bench), "-m", model, "-t", str(threads), "-ngl", str(ngl),
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
        tps = float(m.group(1)) if m else 0.0
        rows.append({"ngl": ngl, "tok_s": tps})
        print(f"   -ngl {ngl:3d}  tg128={tps:6.1f} tok/s")

    md = "# Bonus — GPU-offload sweep\n\n"
    md += f"Model: `{Path(model).name}`  ·  threads: `{threads}`\n\n"
    md += "| -ngl | tg128 (tok/s) |\n|--:|--:|\n"
    md += "\n".join(f"| {r['ngl']} | {r['tok_s']:.1f} |" for r in rows)
    md += (
        "\n\nWhen the model fits in VRAM, `-ngl 99` (full offload) is fastest. "
        "When it doesn't, partial offload (`-ngl 16` or `-ngl 24`) keeps the most "
        "compute on the GPU while spilling weights to RAM — usually still beats "
        "CPU-only (`-ngl 0`). Watch for the curve flattening: after the layer count "
        "covers the model's actual depth, more `-ngl` does nothing.\n"
    )
    out_dir = Path("benchmarks")
    out_dir.mkdir(exist_ok=True)
    (out_dir / "bonus-gpu-offload-sweep.md").write_text(md, encoding=TEXT_ENCODING)
    (out_dir / "bonus-gpu-offload-sweep.json").write_text(json.dumps(rows, indent=2), encoding=TEXT_ENCODING)
    print("\n" + md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
