#!/usr/bin/env bash
# Launch llama-server reading models/active.json.
# Prefer native llama-server if available; otherwise fall back to llama-cpp-python.
# Linux + macOS. Windows users: see start-server.ps1.
set -euo pipefail

cd "$(dirname "$0")/.."

MODEL=$(python -c 'import json, pathlib; print(json.loads(pathlib.Path("models/active.json").read_text(encoding="utf-8"))["primary_model"])')
THREADS=$(python -c 'import json, pathlib; hw=json.loads(pathlib.Path("hardware.json").read_text(encoding="utf-8")); print(hw["cpu"].get("cores_physical") or 4)')
GPU_LAYERS="${LAB_N_GPU_LAYERS:-99}"
PARALLEL="${LAB_PARALLEL:-4}"
CTX="${LAB_N_CTX:-2048}"
ENABLE_METRICS="${LAB_ENABLE_METRICS:-1}"

BIN_CANDIDATES=(
  "BONUS-llama-cpp-optimization/llama.cpp/build/bin/llama-server"
  "BONUS-llama-cpp-optimization/llama.cpp/build/bin/llama-server.exe"
  "BONUS-llama-cpp-optimization/llama.cpp/build/bin/Release/llama-server.exe"
)

SERVER_BIN=""
for candidate in "${BIN_CANDIDATES[@]}"; do
  if [[ -x "$candidate" || -f "$candidate" ]]; then
    SERVER_BIN="$candidate"
    break
  fi
done

echo "==> Starting llama-server"
echo "    model     : $MODEL"
echo "    threads   : $THREADS"
echo "    gpu_layers: $GPU_LAYERS"
echo "    parallel  : $PARALLEL"
echo "    ctx       : $CTX"
echo "    listening : http://0.0.0.0:8080"
echo

if [[ -n "$SERVER_BIN" ]]; then
  echo "    launcher  : native llama-server ($SERVER_BIN)"
  echo
  cmd=(
    "$SERVER_BIN"
    -m "$MODEL"
    --host 0.0.0.0
    --port 8080
    -t "$THREADS"
    -ngl "$GPU_LAYERS"
    --ctx-size "$CTX"
    --parallel "$PARALLEL"
    --cont-batching
  )
  if [[ "$ENABLE_METRICS" == "1" ]]; then
    cmd+=(--metrics)
  fi
  exec "${cmd[@]}"
fi

echo "    launcher  : python -m llama_cpp.server (fallback)"
echo "    note      : this fallback may not expose /metrics like native llama-server."
echo

exec python -m llama_cpp.server \
  --model "$MODEL" \
  --host 0.0.0.0 --port 8080 \
  --n_threads "$THREADS" \
  --n_gpu_layers "$GPU_LAYERS" \
  --n_ctx "$CTX"
