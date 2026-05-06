# Track 02 - llama-server Results and Analysis

## 1. Objective

Track 02 kiểm tra hệ thống ở chế độ gần với serving thực tế hơn benchmark đơn lẻ: cùng một model cục bộ, nhưng phải phục vụ nhiều request đồng thời qua HTTP API OpenAI-compatible, đồng thời để lộ telemetry qua Prometheus metrics.

Mục tiêu không chỉ là "server chạy được", mà là trả lời ba câu hỏi:

1. Độ trễ đầu-cuối thay đổi thế nào khi concurrency tăng?
2. Throughput có tiếp tục tăng khi thêm user hay không?
3. `KV cache` và queueing bắt đầu trở thành bottleneck từ mức tải nào?

## 2. Experimental setup

- Runtime: `llama-server`
- Host: `localhost:8080`
- Workload generator: `locust`
- Model tier: `Qwen2.5-1.5B-Instruct`
- Platform: Windows 11, Intel Core i5-1135G7, 16 GB RAM, CPU-only
- Observability: `/metrics` endpoint với Prometheus-style counters/gauges

## 3. Measured results

| Concurrency | Total RPS | TTFB P50 (ms) | E2E P95 (ms) | E2E P99 (ms) | Failures |
|---:|---:|---:|---:|---:|---:|
| 10 | 8.5 | 120 | 4500 | 4800 | 0 |
| 50 | 6.2 | 450 | 12000 | 15000 | 0 |

## 4. Interpretation

### 4.1. Throughput does not scale linearly

Khi tăng từ 10 lên 50 concurrent users, hệ thống không tăng throughput tương ứng. Total RPS còn giảm từ `8.5` xuống `6.2`. Điều này cho thấy server đã đi qua vùng làm việc hiệu quả và bước vào vùng contention, nơi tài nguyên chia sẻ trở thành giới hạn chính.

### 4.2. Tail latency grows much faster than median

`TTFB P50` tăng từ `120 ms` lên `450 ms`, trong khi `E2E P95` và `P99` tăng rất mạnh, lần lượt lên `12000 ms` và `15000 ms`. Diễn biến này đặc trưng cho hệ thống bị queueing dưới tải: ngay cả khi median vẫn còn chấp nhận được ở một số request, phần đuôi phân phối độ trễ đã kéo trải nghiệm người dùng xuống rõ rệt.

### 4.3. Stability was preserved

Điểm tích cực là cả hai workload đều không xuất hiện failure. Nghĩa là runtime đủ ổn định về mặt chức năng trên laptop CPU-only. Tuy nhiên, "ổn định" ở đây không đồng nghĩa với "đáp ứng SLO". Nếu đặt yêu cầu latency nghiêm ngặt hơn, tải 50 users đã vượt quá vùng goodput hữu ích.

## 5. KV-cache and scheduling discussion

Quan sát từ `/metrics` cho thấy `llamacpp:kv_cache_usage_ratio` tăng mạnh ở mức tải 50 users. Điều đó hợp logic với phần số liệu latency:

- Nhiều request hơn đồng nghĩa nhiều slot sống đồng thời hơn.
- Context của các request dài hơn làm tăng footprint của `KV cache`.
- Khi cache tiến gần trạng thái căng, chi phí chờ và tranh chấp tài nguyên đẩy `P95/P99` tăng lên rất nhanh.

Nói cách khác, bottleneck của bài toán không chỉ là "model chậm", mà là "model chậm khi phải chia sẻ bộ nhớ và thời gian xử lý cho nhiều request cùng lúc".

## 6. Key lesson from Track 02

Track 02 minh họa khá rõ sự khác biệt giữa benchmark đơn người dùng và serving đa người dùng:

- Benchmark đơn lẻ chủ yếu phản ánh chi phí compute/prefill/decode của một request.
- Serving thực tế còn phản ánh chi phí scheduling, queueing và pressure lên `KV cache`.

Vì vậy, khi tối ưu production inference, chỉ nhìn tokens/s là chưa đủ. Cần nhìn thêm tail latency và trạng thái tài nguyên dưới tải.

## 7. Recommended next optimization steps

1. Commit và phân tích trực tiếp `benchmarks/02-server-metrics.csv` để lượng hóa peak `kv_cache_usage_ratio`.
2. Thử native `llama-server` với `--parallel` và `--cont-batching` để kiểm tra xem tail latency có được cải thiện dưới tải vừa phải hay không.
3. So sánh thêm một workload context ngắn hơn để tách ảnh hưởng của prompt length khỏi ảnh hưởng của concurrency.

## 8. Conclusion

Trên phần cứng hiện tại, server hoạt động ổn định ở mức tải thấp đến trung bình, nhưng hiệu năng suy giảm mạnh khi concurrency tăng lên 50 users. Điều này xác nhận rằng trong môi trường CPU-only, yếu tố quyết định không còn là tốc độ một request riêng lẻ, mà là cách runtime quản lý contention, cache và hàng đợi khi phải phục vụ nhiều request cùng lúc.
