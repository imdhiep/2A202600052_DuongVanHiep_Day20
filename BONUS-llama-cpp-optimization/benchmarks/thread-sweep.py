#!/usr/bin/env python3
"""Sweep -t (thread count) and chart tokens/sec.

The intuition: physical cores beat logical cores for LLM decode (it's
memory-bandwidth-bound, not compute-bound). On a 12-core / 24-thread CPU
the curve typically peaks around 8-12 threads then *drops* as you push
into hyperthreads that fight over the same memory channels.

Usage:
    # Uses build/bin/llama-bench from BONUS-llama-cpp-optimization/llama.cpp
    python BONUS-llama-cpp-optimization/benchmarks/thread-sweep.py
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

# llama-bench prints a markdown-ish table; this regex grabs the tg128 (decode) row.
TG_RE = re.compile(r"\|\s*tg128\s*\|\s*([0-9.]+)\s*±")
TEXT_ENCODING = "utf-8"


def find_bench() -> Path:
    # Locations where llama-bench might be
    candidates = [
        Path("BONUS-llama-cpp-optimization/llama.cpp/build/bin/llama-bench"),
        Path("BONUS-llama-cpp-optimization/llama.cpp/build/bin/llama-bench.exe"),
        Path("BONUS-llama-cpp-optimization/llama.cpp/build/bin/Release/llama-bench.exe"),
    ]
    for p in candidates:
        if p.exists():
            return p

    print(f"ERROR: llama-bench not found at {candidates[0]}", file=sys.stderr)
    print("       Build llama.cpp first — see BONUS-llama-cpp-optimization/01-build-from-source.md.", file=sys.stderr)
    sys.exit(1)


def load_active() -> str:
    return json.loads(Path("models/active.json").read_text(encoding=TEXT_ENCODING))["primary_model"]


def load_hw() -> dict:
    return json.loads(Path("hardware.json").read_text(encoding=TEXT_ENCODING))


def thread_grid(hw: dict) -> list[int]:
    physical = hw["cpu"].get("cores_physical") or 4
    logical = hw["cpu"]["cores_logical"]
    raw = sorted({1, 2, max(physical // 2, 1), physical, logical})
    if logical >= 8:
        raw.append(logical * 2)  # oversubscribe — usually slower, included to demonstrate
    return [t for t in raw if t > 0]


def run_one(bench: Path, model: str, threads: int, n_gpu_layers: int) -> float:
    """Returns decode tokens/sec for a single -t value."""
    cmd = [
        str(bench), "-m", model,
        "-t", str(threads),
        "-ngl", str(n_gpu_layers),
        "-p", "0", "-n", "64",
        "-r", "2",
    ]
    print(f"   running: {' '.join(cmd[1:])}")
    out = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding=TEXT_ENCODING,
        errors="replace",
        check=False,
    ).stdout
    m = TG_RE.search(out)
    if not m:
        # Fall back: scan for any decimal followed by t/s
        m = re.search(r"([0-9.]+)\s*tokens/s", out)
    return float(m.group(1)) if m else 0.0


def main() -> int:
    bench = find_bench()
    model = load_active()
    hw = load_hw()
    backends = hw.get("gpu", {}).get("backends", {})
    n_gpu = 99 if any(v for k, v in backends.items() if k != "cpu_only") else 0

    grid = thread_grid(hw)
    print(f"==> thread sweep on {Path(model).name}")
    print(f"    grid    : {grid}")
    print(f"    n_gpu   : {n_gpu}")
    print(f"    physical: {hw['cpu'].get('cores_physical')}  logical: {hw['cpu']['cores_logical']}")
    print()

    rows: list[dict] = []
    for t in grid:
        tps = run_one(bench, model, t, n_gpu)
        rows.append({"threads": t, "tok_s": tps})
        print(f"   t={t:3d}  tg128={tps:6.1f} tok/s")

    out_dir = Path("benchmarks")
    out_dir.mkdir(exist_ok=True)

    best = max(rows, key=lambda r: r["tok_s"]) if rows else {"threads": 0, "tok_s": 0}
    md = "# Bonus — Thread sweep\n\n"
    md += f"Model: `{Path(model).name}`  ·  GPU layers: `{n_gpu}`\n\n"
    md += "| threads | tg128 (tok/s) |\n|---:|---:|\n"
    md += "\n".join(f"| {r['threads']} | {r['tok_s']:.1f} |" for r in rows)
    md += f"\n\n**Best**: `-t {best['threads']}` at {best['tok_s']:.1f} tok/s.\n\n"
    md += (
        "Look at the curve. If it peaks around your **physical** core count and "
        "drops as you go higher, that's the memory-bandwidth ceiling: extra threads "
        "fight over the same memory channels and slow each other down.\n"
    )
    (out_dir / "bonus-thread-sweep.md").write_text(md, encoding=TEXT_ENCODING)
    (out_dir / "bonus-thread-sweep.json").write_text(json.dumps(rows, indent=2), encoding=TEXT_ENCODING)

    print("\n" + md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
