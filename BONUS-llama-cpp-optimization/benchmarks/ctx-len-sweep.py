#!/usr/bin/env python3
"""Sweep context length and chart prefill cost.

Prefill is O(N²) in attention math, so doubling the context window roughly
quadruples prefill time. This sweep shows the curve directly using llama-bench's
`-p` (prompt processing tokens) parameter, which simulates a realistic prefill.

Useful for thinking about TTFT under long-context (RAG, agents, long documents)
which is the §2 / §3 deck conversation.

Usage:
    python BONUS-llama-cpp-optimization/benchmarks/ctx-len-sweep.py
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

    # Smaller laptops shouldn't run 4096 — they'll OOM the KV cache.
    ram_gb = hw.get("ram_gb", 8)
    if ram_gb < 8:
        ctx_grid = [128, 256, 512, 1024]
    elif ram_gb < 16:
        ctx_grid = [128, 256, 512, 1024, 2048]
    else:
        ctx_grid = [128, 256, 512, 1024, 2048, 4096]

    pp_args = ",".join(str(c) for c in ctx_grid)
    cmd = [
        str(bench), "-m", model,
        "-t", str(threads), "-ngl", str(n_gpu),
        "-p", pp_args, "-n", "0", "-r", "2",
    ]
    print(f"==> ctx-len sweep")
    print(f"    grid : {ctx_grid}")
    print(f"    cmd  : {' '.join(cmd[1:])}\n")

    out = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding=TEXT_ENCODING,
        errors="replace",
        check=False,
    ).stdout

    rows: list[dict] = []
    for m in PP_RE.finditer(out):
        ctx = int(m.group(1))
        tps = float(m.group(2))
        # Prefill latency for ctx tokens at this rate, in ms:
        ms = (ctx / tps) * 1000.0 if tps > 0 else 0
        rows.append({"ctx": ctx, "pp_tok_s": tps, "prefill_ms": round(ms, 1)})
        print(f"   ctx={ctx:5d}  pp={tps:7.1f} tok/s  prefill≈{ms:7.1f} ms")

    if not rows:
        print("ERROR: couldn't parse llama-bench output.", file=sys.stderr)
        return 1

    md = "# Bonus — Context-length sweep (prefill cost)\n\n"
    md += f"Model: `{Path(model).name}`  ·  threads: `{threads}`  ·  n_gpu: `{n_gpu}`\n\n"
    md += "| ctx tokens | pp (tok/s) | prefill latency (ms) |\n|--:|--:|--:|\n"
    md += "\n".join(f"| {r['ctx']} | {r['pp_tok_s']:.1f} | {r['prefill_ms']:.1f} |" for r in rows)
    md += (
        "\n\nPrefill scales **super-linearly** with context length — that's where "
        "TTFT comes from in long-context RAG. This is also why the deck's "
        "*disaggregated prefill/decode* pattern (Mooncake / llm-d / Dynamo) exists: "
        "give prefill its own GPU pool so long-context requests don't block decode.\n"
    )
    out_dir = Path("benchmarks")
    out_dir.mkdir(exist_ok=True)
    (out_dir / "bonus-ctx-len-sweep.md").write_text(md, encoding=TEXT_ENCODING)
    (out_dir / "bonus-ctx-len-sweep.json").write_text(json.dumps(rows, indent=2), encoding=TEXT_ENCODING)
    print("\n" + md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
