#!/usr/bin/env python3
"""Side-by-side: MLX-LM vs llama-cpp-python on Apple Silicon.

Same 10 prompts, same 64 max tokens, prints decode tokens/sec + TTFT for each.
Writes benchmarks/bonus-mlx-vs-llama-cpp.md.
"""
from __future__ import annotations

import json
import platform
import statistics
import sys
import time
from pathlib import Path

if platform.machine() not in ("arm64", "aarch64") or sys.platform != "darwin":
    print("This bonus requires Apple Silicon macOS.", file=sys.stderr)
    sys.exit(1)


PROMPTS = [
    "Define TTFT in one sentence.",
    "Why is FlashAttention IO-aware?",
    "Compare Q4_K_M vs Q2_K in three bullets.",
    "What is goodput@SLO and why does it matter?",
    "When would you use disaggregated prefill/decode serving?",
    "Sketch how PagedAttention avoids KV-cache fragmentation.",
    "What does --parallel do in llama-server?",
    "Explain MLA in two sentences.",
    "Why does context length make TTFT worse super-linearly?",
    "List two reasons MLX might beat Metal-via-llama.cpp on M-series chips.",
]


# Map our GGUF tier to the corresponding MLX-format repo. Students with other
# models can edit this dict.
MLX_TIER = {
    "TinyLlama-1.1B": "mlx-community/TinyLlama-1.1B-Chat-v1.0-mlx",
    "Qwen2.5-1.5B-Instruct": "mlx-community/Qwen2.5-1.5B-Instruct-4bit",
    "Llama-3.2-3B-Instruct": "mlx-community/Llama-3.2-3B-Instruct-4bit",
    "Qwen2.5-7B-Instruct": "mlx-community/Qwen2.5-7B-Instruct-4bit",
}
TEXT_ENCODING = "utf-8"


def quantile(xs: list[float], q: float) -> float:
    if not xs:
        return 0.0
    return statistics.quantiles(sorted(xs), n=100, method="inclusive")[int(q) - 1]


def bench_llama_cpp(model_path: str) -> dict:
    from llama_cpp import Llama
    llm = Llama(model_path=model_path, n_ctx=2048, n_gpu_layers=99, verbose=False)
    # warm up
    list(llm.create_completion("Hello.", max_tokens=4, stream=True))

    ttfts, decode_rates = [], []
    for p in PROMPTS:
        t0 = time.perf_counter()
        first = None
        ntok = 0
        for chunk in llm.create_completion(prompt=p, max_tokens=64, temperature=0.5, stream=True):
            if chunk["choices"][0].get("text"):
                if first is None:
                    first = time.perf_counter()
                ntok += 1
        end = time.perf_counter()
        if first and ntok > 1:
            ttfts.append((first - t0) * 1000)
            decode_rates.append((ntok - 1) / max(end - first, 1e-3))
    return {
        "runtime": "llama.cpp (Metal)",
        "ttft_p50_ms": round(quantile(ttfts, 50), 1),
        "ttft_p95_ms": round(quantile(ttfts, 95), 1),
        "decode_tok_s": round(statistics.median(decode_rates) if decode_rates else 0, 1),
    }


def bench_mlx(repo_id: str) -> dict:
    try:
        from mlx_lm import generate, load
    except ImportError:
        print("ERROR: pip install mlx mlx-lm first.", file=sys.stderr)
        sys.exit(1)
    print(f"   loading MLX model: {repo_id}")
    model, tokenizer = load(repo_id)

    ttfts, decode_rates = [], []
    # warm up
    generate(model, tokenizer, prompt="Hello.", max_tokens=4, verbose=False)

    for p in PROMPTS:
        t0 = time.perf_counter()
        # MLX-LM streams via generate_step; keep this simple — generate() returns full text,
        # we measure end-to-end and approximate TPOT from the token count.
        text = generate(model, tokenizer, prompt=p, max_tokens=64, verbose=False)
        elapsed = time.perf_counter() - t0
        # mlx-lm doesn't expose first-token timing easily; approximate from total/n_tokens.
        ntok = len(tokenizer.encode(text)) if text else 0
        if ntok > 1:
            tpot = elapsed / ntok
            ttfts.append(tpot * 1000)  # rough proxy: prefill ~ 1 step
            decode_rates.append(ntok / elapsed)
    return {
        "runtime": "MLX-LM",
        "ttft_p50_ms": round(quantile(ttfts, 50), 1),
        "ttft_p95_ms": round(quantile(ttfts, 95), 1),
        "decode_tok_s": round(statistics.median(decode_rates) if decode_rates else 0, 1),
    }


def main() -> int:
    active = json.loads(Path("models/active.json").read_text(encoding=TEXT_ENCODING))
    tier = active["tier"]
    if tier not in MLX_TIER:
        print(f"No MLX repo mapped for tier {tier}. Edit MLX_TIER in this script.", file=sys.stderr)
        return 1

    print(f"==> Benchmarking llama.cpp Metal on {Path(active['primary_model']).name}")
    llama_res = bench_llama_cpp(active["primary_model"])
    print(f"    {llama_res}\n")

    print(f"==> Benchmarking MLX-LM on {MLX_TIER[tier]}")
    mlx_res = bench_mlx(MLX_TIER[tier])
    print(f"    {mlx_res}\n")

    md = (
        f"# Bonus — MLX vs llama.cpp Metal\n\n"
        f"Tier: `{tier}`\n\n"
        f"| runtime | TTFT P50 (ms) | TTFT P95 (ms) | decode (tok/s) |\n"
        f"|---|--:|--:|--:|\n"
        f"| {llama_res['runtime']} | {llama_res['ttft_p50_ms']} | {llama_res['ttft_p95_ms']} | {llama_res['decode_tok_s']} |\n"
        f"| {mlx_res['runtime']} | {mlx_res['ttft_p50_ms']} | {mlx_res['ttft_p95_ms']} | {mlx_res['decode_tok_s']} |\n\n"
        f"MLX TTFT numbers are approximations (mlx-lm doesn't expose first-token timing as "
        f"readily as llama-cpp-python's stream API). Trust the decode tok/s for the "
        f"head-to-head; trust both implementations' P95 only as rough indicators.\n"
    )
    out = Path("benchmarks/bonus-mlx-vs-llama-cpp.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md, encoding=TEXT_ENCODING)
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
