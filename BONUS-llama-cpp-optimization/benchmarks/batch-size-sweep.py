#!/usr/bin/env python3
"""Sweep --batch-size and --ubatch-size for prefill throughput.

llama.cpp's `--batch-size` is the logical prefill batch (tokens processed in
one forward); `--ubatch-size` (since b3500) is the physical micro-batch
actually shipped to the kernel. They're the closest analogue of vLLM's
chunked-prefill knob from the deck §3 Production Tuning frame.

Usage:
    python BONUS-llama-cpp-optimization/benchmarks/batch-size-sweep.py
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

LLAMA_BENCH = Path("BONUS-llama-cpp-optimization/llama.cpp/build/bin/llama-bench")
LLAMA_BENCH_EXE = LLAMA_BENCH.with_suffix(".exe")
PP_RE = re.compile(r"\|\s*pp(\d+)\s*\|\s*([0-9.]+)\s*±")
TEXT_ENCODING = "utf-8"


def find_bench() -> Path:
    for p in (LLAMA_BENCH, LLAMA_BENCH_EXE):
        if p.exists():
            return p
    print("ERROR: build llama.cpp first.", file=sys.stderr)
    sys.exit(1)


def main() -> int:
    bench = find_bench()
    model = json.loads(Path("models/active.json").read_text(encoding=TEXT_ENCODING))["primary_model"]
    hw = json.loads(Path("hardware.json").read_text(encoding=TEXT_ENCODING))
    threads = hw["cpu"].get("cores_physical") or 4
    backends = hw.get("gpu", {}).get("backends", {})
    n_gpu = 99 if any(v for k, v in backends.items() if k != "cpu_only") else 0

    grid = [
        (128, 128),
        (256, 256),
        (512, 256),
        (512, 512),
        (1024, 512),
        (2048, 512),
    ]
    rows: list[dict] = []
    print(f"==> batch-size sweep on {Path(model).name}\n")
    for b, ub in grid:
        cmd = [str(bench), "-m", model, "-t", str(threads), "-ngl", str(n_gpu),
               "-b", str(b), "-ub", str(ub), "-p", "512", "-n", "0", "-r", "2"]
        out = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding=TEXT_ENCODING,
            errors="replace",
            check=False,
        ).stdout
        m = PP_RE.search(out)
        tps = float(m.group(2)) if m else 0.0
        rows.append({"batch": b, "ubatch": ub, "pp_tok_s": tps})
        print(f"   -b {b:4d}  -ub {ub:4d}  pp512={tps:7.1f} tok/s")

    md = "# Bonus — batch-size sweep (prefill)\n\n"
    md += f"Model: `{Path(model).name}`  ·  threads: `{threads}`  ·  n_gpu: `{n_gpu}`\n\n"
    md += "| -b (logical) | -ub (micro) | pp512 (tok/s) |\n|--:|--:|--:|\n"
    md += "\n".join(f"| {r['batch']} | {r['ubatch']} | {r['pp_tok_s']:.1f} |" for r in rows)
    md += (
        "\n\nLarger batch lets prefill amortize per-step overhead (better tok/s) but "
        "also blocks the engine for longer (worse TTFT for queued requests). On a "
        "real serving stack you'd pick `--ubatch` based on the longest TTFT you can "
        "tolerate per slot under contention — exactly the chunked-prefill conversation "
        "from the deck.\n"
    )
    out_dir = Path("benchmarks")
    out_dir.mkdir(exist_ok=True)
    (out_dir / "bonus-batch-size-sweep.md").write_text(md, encoding=TEXT_ENCODING)
    (out_dir / "bonus-batch-size-sweep.json").write_text(json.dumps(rows, indent=2), encoding=TEXT_ENCODING)
    print("\n" + md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
