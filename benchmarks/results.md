# Day 20 Lab - Results Scratchpad

> File này là nơi ghi chép số liệu thô trong lúc làm bài. Báo cáo được chấm điểm vẫn là [`submission/REFLECTION.md`](../submission/REFLECTION.md).

## 1. Hardware profile

- Platform:
- CPU:
- RAM:
- GPU / accelerator:
- llama.cpp backend:
- Model tier đã chọn:

## 2. Track 01 - Quickstart baseline

| Model | Load (ms) | TTFT P50/P95 (ms) | TPOT P50/P95 (ms) | E2E P50/P95/P99 (ms) | Decode rate (tok/s) |
|---|---:|---:|---:|---:|---:|
| Primary (`Q4_K_M`) | | | | | |
| Compare (`Q2_K`) | | | | | |

Ghi chú nhanh:
- Chất lượng câu trả lời thay đổi thế nào giữa hai quantization?
- `TTFT` hay `TPOT` đang là bottleneck chính?
- Số luồng hiện tại có vẻ đã ở gần optimum chưa?

## 3. Track 02 - Server and load test

| Concurrency | Total RPS | TTFB P50 (ms) | E2E P95 (ms) | E2E P99 (ms) | Failures |
|---:|---:|---:|---:|---:|---:|
| 10 | | | | | |
| 50 | | | | | |

Metrics cần lưu ý:
- Peak `llamacpp:kv_cache_usage_ratio`:
- Peak `llamacpp:requests_processing`:
- Peak `llamacpp:requests_deferred`:
- Observation về queueing / tail latency:

## 4. Track 03 - Integration

- N16 piece connected:
- N17 piece connected:
- N18 piece connected:
- N19 piece connected:
- Thành phần nào đang là stub:

Đo latency tối thiểu:
- Retrieve:
- Prompt build:
- llama-server:
- Total:

## 5. Bonus optimization

### Thread sweep

| threads | tg128 (tok/s) |
|---:|---:|
| | |

### Quant sweep

| quant | size (MB) | tg128 (tok/s) |
|---|---:|---:|
| | | |

### Context-length sweep

| ctx tokens | pp (tok/s) | prefill latency (ms) |
|---:|---:|---:|
| | | |

### The single change that mattered most

- Change:
- Before:
- After:
- Estimated speedup:
- Why it worked:

## 6. Pitfalls, limitations, and next steps

- Điều gì làm kết quả dễ nhiễu?
- Phần nào hiện vẫn mang tính stub hoặc toy setup?
- Nếu có thêm thời gian, thay đổi tiếp theo nên là gì?
