# Launch llama-server reading models/active.json.
# Prefer native llama-server if available; otherwise fall back to llama-cpp-python.
# Windows PowerShell 7+.
$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')

$model   = python -c 'import json, pathlib; print(json.loads(pathlib.Path("models/active.json").read_text(encoding="utf-8"))["primary_model"])'
$threads = python -c 'import json, pathlib; hw=json.loads(pathlib.Path("hardware.json").read_text(encoding="utf-8")); print(hw["cpu"].get("cores_physical") or 4)'
$gpu     = if ($env:LAB_N_GPU_LAYERS) { $env:LAB_N_GPU_LAYERS } else { '99' }
$ctx     = if ($env:LAB_N_CTX) { $env:LAB_N_CTX } else { '2048' }
$parallel = if ($env:LAB_PARALLEL) { $env:LAB_PARALLEL } else { '4' }
$enableMetrics = if ($env:LAB_ENABLE_METRICS) { $env:LAB_ENABLE_METRICS } else { '1' }
$nativeCandidates = @(
    'BONUS-llama-cpp-optimization/llama.cpp/build/bin/llama-server.exe',
    'BONUS-llama-cpp-optimization/llama.cpp/build/bin/Release/llama-server.exe'
)
$nativeServer = $nativeCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1

Write-Host "==> Starting llama-server" -ForegroundColor Cyan
Write-Host "    model     : $model"
Write-Host "    threads   : $threads"
Write-Host "    gpu_layers: $gpu"
Write-Host "    parallel  : $parallel"
Write-Host "    ctx       : $ctx"
Write-Host "    listening : http://0.0.0.0:8080"
Write-Host ""

if ($nativeServer) {
    Write-Host "    launcher  : native llama-server ($nativeServer)"
    Write-Host ""
    $args = @(
        '-m', $model,
        '--host', '0.0.0.0',
        '--port', '8080',
        '-t', $threads,
        '-ngl', $gpu,
        '--ctx-size', $ctx,
        '--parallel', $parallel,
        '--cont-batching'
    )
    if ($enableMetrics -eq '1') {
        $args += '--metrics'
    }
    & $nativeServer @args
    exit $LASTEXITCODE
}

Write-Host "    launcher  : python -m llama_cpp.server (fallback)"
Write-Host "    note      : this fallback may not expose /metrics like native llama-server."
Write-Host ""

python -m llama_cpp.server `
    --model "$model" `
    --host 0.0.0.0 --port 8080 `
    --n_threads $threads `
    --n_gpu_layers $gpu `
    --n_ctx $ctx
