# Day 20 Lab - Model Serving & Inference Optimization (Track 2)

Lab này tập trung vào một mục tiêu rõ ràng: dựng, đo và tối ưu một stack suy luận cục bộ với `llama.cpp`, sau đó giải thích kết quả bằng tư duy hệ thống thay vì chỉ ghi lại con số. Repo được thiết kế để chạy trên laptop cá nhân, không yêu cầu Docker, và giữ cùng một bề mặt kỹ thuật trên Windows, Linux, macOS.

## Mục tiêu học tập

- Đo đúng các chỉ số quan trọng của suy luận: `TTFT`, `TPOT`, `P50/P95/P99`, goodput dưới ràng buộc SLO.
- So sánh tác động của quantization, số luồng, context length, batching và GPU offload trên chính phần cứng đang có.
- Dựng được endpoint OpenAI-compatible bằng `llama-server`, gắn thêm quan sát qua `/metrics`, rồi tích hợp endpoint đó vào một pipeline RAG tối thiểu.
- Viết một báo cáo cá nhân có lập luận: thay đổi nào đem lại hiệu quả lớn nhất, vì sao nó hiệu quả, và giới hạn của kết quả là gì.

## Yêu cầu môi trường

- Python `>= 3.10`
- Không cần Docker
- Không cần OpenAI API key
- Repo phù hợp với:
  - Windows
  - macOS Intel / Apple Silicon
  - Linux

## Quick Start

```bash
git clone https://github.com/<your-username>/Day20-Track2-ModelServing-Lab.git
cd Day20-Track2-ModelServing-Lab

make probe
make setup
make bench
make serve
make smoke
make load-10
make load-50
make metrics
make pipeline
make verify
```

Windows nên dùng `pwsh -ExecutionPolicy Bypass -File 00-setup/windows-setup.ps1`, sau đó gọi từng script Python/PowerShell tương ứng.

## Cấu trúc bài lab

| Track | Thư mục | Mục tiêu |
|---|---|---|
| 00 | `00-setup/` | Phát hiện phần cứng, chọn backend, tải model phù hợp |
| 01 | `01-llama-cpp-quickstart/` | Benchmark baseline cho `TTFT/TPOT/P95` và so sánh quantization |
| 02 | `02-llama-cpp-server/` | Chạy `llama-server`, load test, Prometheus metrics |
| 03 | `03-milestone-integration/` | Gắn endpoint vào pipeline RAG tối thiểu |
| Bonus | `BONUS-llama-cpp-optimization/` | Build source + sweep các knob tối ưu |
| Bonus | `BONUS-mlx-macos/` | So sánh MLX với llama.cpp trên Apple Silicon |

## Luồng làm việc khuyến nghị

1. Chạy `00-setup/detect-hardware.py` để sinh `hardware.json`.
2. Tải model phù hợp bằng `00-setup/download-model.py`, sinh `models/active.json`.
3. Benchmark baseline tại `01-llama-cpp-quickstart/benchmark.py`.
4. Khởi động server ở Track 02.
   - Script launcher hiện ưu tiên native `llama-server` nếu binary đã được build.
   - Nếu chưa có binary native, launcher sẽ fallback sang `python -m llama_cpp.server`.
5. Chạy load test với `locust`, scrape `/metrics`, rồi tổng hợp kết quả.
6. Tích hợp server vào `03-milestone-integration/pipeline.py`.
7. Hoàn thiện báo cáo tại `submission/REFLECTION.md`.

## Tài liệu quan trọng nên đọc trước

- [`rubric.md`](rubric.md): tiêu chí chấm điểm
- [`HARDWARE-GUIDE.md`](HARDWARE-GUIDE.md): chọn model/backend theo phần cứng
- [`VIBE-CODING.md`](VIBE-CODING.md): gợi ý workflow ra quyết định và review

## Kết quả và artefact chính

- `hardware.json`: hồ sơ phần cứng
- `models/active.json`: model đang dùng
- `benchmarks/01-quickstart-results.md`: baseline quickstart
- `benchmarks/02-server-metrics.csv`: dữ liệu metrics Track 02
- `02-llama-cpp-server/02-server-results.md`: phân tích kết quả load test
- `submission/REFLECTION.md`: báo cáo cá nhân chính để chấm điểm

## Những điều grader thường nhìn

- Repo có tái lập được luồng `setup -> bench -> verify` hay không
- Số liệu có gắn với phần cứng thực tế và được giải thích hợp lý hay không
- Báo cáo có phân biệt rõ `TTFT`, `TPOT`, `tail latency`, `goodput`, `KV-cache pressure` hay không
- Phần "single change that mattered most" có nêu được cơ chế tác động, thay vì chỉ nói nhanh hơn/chậm hơn

## Gợi ý để đạt điểm cao

- Ghi rõ cấu hình chạy: model, quantization, số luồng, context size, GPU offload.
- Khi so sánh trước/sau, luôn giữ nguyên workload để kết luận có giá trị.
- Nếu có giới hạn hoặc phần còn stub, nêu thẳng và giải thích vì sao. Sự trung thực kỹ thuật thường thuyết phục hơn việc "làm đầy" bằng mô tả mơ hồ.
- Ưu tiên một hoặc hai insight mạnh, thay vì rất nhiều bảng số liệu không có kết luận.

## Submission

1. Hoàn thành bốn track chính.
2. Commit đầy đủ artefact và screenshot trong `submission/screenshots/`.
3. Hoàn thiện `submission/REFLECTION.md`.
4. Chạy `make verify`.
5. Đẩy repo public lên GitHub và nộp URL trên LMS.

Repo này được tối ưu cho việc học và giải thích nguyên lý tối ưu serving trên máy cá nhân. Điểm mạnh của nó không nằm ở "số nhanh tuyệt đối", mà ở chỗ cho phép thấy rõ mối quan hệ giữa phần cứng, runtime, và độ trễ đầu-cuối trong một môi trường dễ tái lập.
