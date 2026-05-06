#!/usr/bin/env python3
"""Skeleton RAG pipeline gluing N19 retrieval + N20 llama-server.

Replace the STUB markers with your actual N18/N19 code. Runs as-is using
in-memory toy data so you can confirm the OpenAI-compat call before wiring
in your real lakehouse + vector store.
"""
from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from typing import Iterable

import httpx

LLAMA_SERVER_BASE = os.environ.get("LLAMA_SERVER_BASE", "http://localhost:8080/v1").rstrip("/")
SYSTEM_PROMPT = (
    "You are a serving-engineering tutor. Answer using only the retrieved documents. "
    "Cite the source ids you used in square brackets. If the documents do not contain "
    "the answer, say so clearly instead of guessing."
)
TOKEN_RE = re.compile(r"[a-z0-9_+-]+", re.IGNORECASE)


# ────────────────────────────────────────────────────────────────────────
# Replace this STUB with retrieval against your N19 vector index.
# ────────────────────────────────────────────────────────────────────────

TOY_DOCS = [
    {"id": "n20-paged", "text": "PagedAttention treats KV cache like virtual memory pages, eliminating 60-80% fragmentation."},
    {"id": "n20-radix", "text": "RadixAttention stores KV in a prefix trie; cache hit on shared prefix lets the engine skip prefill."},
    {"id": "n20-disagg", "text": "Disaggregated serving (Mooncake, llm-d, Dynamo) splits prefill and decode onto separate GPU pools."},
    {"id": "n20-goodput", "text": "Goodput@SLO = req/s satisfying TTFT and TPOT SLOs. Throughput at saturation ignores SLO."},
    {"id": "n20-quant", "text": "GGUF Q4_K_M is the production-quality default for laptop/edge serving via llama.cpp."},
]


@dataclass
class Doc:
    id: str
    text: str
    score: float


def normalize_terms(text: str) -> set[str]:
    return {token.lower() for token in TOKEN_RE.findall(text)}


def retrieve(query: str, k: int = 3) -> list[Doc]:
    """STUB: replace with your N19 vector index call."""
    # Toy keyword overlap so the demo does *something* sensible without an embedder.
    q_terms = normalize_terms(query)
    scored: list[Doc] = []
    for d in TOY_DOCS:
        d_terms = normalize_terms(d["text"])
        overlap = len(q_terms & d_terms)
        phrase_bonus = 0.25 if query.lower() in d["text"].lower() else 0.0
        score = overlap + phrase_bonus
        scored.append(Doc(d["id"], d["text"], score=score))

    ranked = sorted(scored, key=lambda doc: (-doc.score, doc.id))
    top = [doc for doc in ranked if doc.score > 0][:k]
    return top or ranked[:k]


# ────────────────────────────────────────────────────────────────────────
# Prompt assembly
# ────────────────────────────────────────────────────────────────────────


def build_prompt(query: str, contexts: Iterable[Doc]) -> list[dict]:
    ctx_block = "\n".join(f"[{c.id}] {c.text}" for c in contexts)
    user = (
        "Retrieved context:\n"
        f"{ctx_block}\n\n"
        "Instruction: answer the question using only the retrieved context and include "
        "the ids of the supporting documents.\n\n"
        f"Question: {query}"
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]


# ────────────────────────────────────────────────────────────────────────
# llama-server call
# ────────────────────────────────────────────────────────────────────────


def call_llm(messages: list[dict]) -> tuple[str, float]:
    t0 = time.perf_counter()
    with httpx.Client() as client:
        r = client.post(
            f"{LLAMA_SERVER_BASE}/chat/completions",
            json={"model": "local", "messages": messages, "max_tokens": 200, "temperature": 0.3},
            timeout=120.0,
        )
        r.raise_for_status()
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    body = r.json()
    return body["choices"][0]["message"]["content"], elapsed_ms


def answer(query: str) -> dict:
    t_total = time.perf_counter()

    t = time.perf_counter()
    docs = retrieve(query, k=3)
    t_retrieve_ms = (time.perf_counter() - t) * 1000.0

    messages = build_prompt(query, docs)

    text, t_llm_ms = call_llm(messages)

    return {
        "query": query,
        "answer": text,
        "contexts": [{"id": d.id, "score": round(d.score, 2), "text": d.text} for d in docs],
        "timings_ms": {
            "retrieve": round(t_retrieve_ms, 1),
            "llm": round(t_llm_ms, 1),
            "total": round((time.perf_counter() - t_total) * 1000.0, 1),
        },
    }


def main() -> None:
    queries = [
        "Why is goodput more useful than throughput?",
        "What problem does PagedAttention actually solve?",
        "When should I think about disaggregated serving?",
    ]
    for q in queries:
        print(f"\n=== {q} ===")
        result = answer(q)
        print("  contexts:")
        for context in result["contexts"]:
            print(f"    - {context['id']} (score={context['score']:.2f}): {context['text']}")
        print(f"  timings : {result['timings_ms']}")
        print(f"  answer  : {result['answer'].strip()[:300]}")


if __name__ == "__main__":
    main()
