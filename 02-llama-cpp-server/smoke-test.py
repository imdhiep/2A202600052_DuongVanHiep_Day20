#!/usr/bin/env python3
"""Smoke-test the local llama-server's OpenAI-compatible endpoint."""
from __future__ import annotations

import os
import sys
import time

import httpx

BASE_URL = os.environ.get("LLAMA_SERVER_BASE", "http://localhost:8080/v1").rstrip("/")


def main() -> int:
    print(f"==> POST {BASE_URL}/chat/completions")
    payload = {
        "model": "local",
        "messages": [
            {"role": "system", "content": "You are a serving-engineering tutor."},
            {"role": "user", "content": "Define goodput@SLO in one sentence."},
        ],
        "max_tokens": 80,
        "temperature": 0.3,
        "stream": False,
    }
    t0 = time.perf_counter()
    with httpx.Client() as client:
        try:
            r = client.post(f"{BASE_URL}/chat/completions", json=payload, timeout=120.0)
            r.raise_for_status()
            body = r.json()
            msg = body["choices"][0]["message"]["content"].strip()
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            print(
                "Is llama-server running on :8080? Start it first (see this directory's README).",
                file=sys.stderr,
            )
            return 1

        elapsed = (time.perf_counter() - t0) * 1000.0
        print(f"\n[{elapsed:.0f} ms]\n{msg}\n")

        print("==> GET /metrics (head)")
        metrics_url = BASE_URL.removesuffix("/v1") + "/metrics"
        try:
            m = client.get(metrics_url, timeout=5.0)
            m.raise_for_status()
            for line in m.text.splitlines()[:25]:
                print(f"   {line}")
        except httpx.HTTPError:
            print("   /metrics unavailable. Start native llama-server with --metrics enabled.")

    print("\nOK. Smoke test passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
