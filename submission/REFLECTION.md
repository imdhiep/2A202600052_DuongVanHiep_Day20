# Reflection - Day 20 Model Serving Lab

**Sinh viên:** Dương Văn Hiệp - 2A202600052  
**Ngày nộp:** 2026-05-06  
**Phạm vi bài làm:** Track 00-03 + phân tích bonus về native build trên Windows

---

## Executive summary

Mục tiêu của bài lab là xây dựng một pipeline suy luận cục bộ bằng `llama.cpp`, sau đó đánh giá hiệu năng theo đúng ngôn ngữ của production inference: `TTFT`, `TPOT`, throughput dưới tải, tail latency và áp lực lên `KV cache`. Thay vì so sánh với máy khác, trọng tâm của bài là so sánh các cấu hình ngay trên cùng một phần cứng để rút ra kết luận có giá trị thực hành.

Trong bài làm này, tôi tập trung vào ba câu hỏi kỹ thuật:

1. Trên laptop CPU-only, quantization nào cho điểm cân bằng tốt nhất giữa tốc độ và chất lượng?
2. Khi chuyển từ benchmark đơn lẻ sang server có tải đồng thời, nút thắt chính xuất hiện ở đâu?
3. Thay đổi cấu hình nào tạo ra cải thiện rõ nhất và vì sao cải thiện đó có ý nghĩa về mặt hệ thống?

---

## 1. Hardware spec và setup

### 1.1. Phần cứng

- **OS:** Windows 11 Home
- **CPU:** Intel Core i5-1135G7 @ 2.40 GHz
- **CPU topology:** 4 physical cores / 8 logical cores
- **Instruction set đáng chú ý:** AVX2, FMA, F16C
- **RAM:** 16 GB
- **Accelerator:** CPU only
- **Backend được chọn:** Native CPU build cho `llama.cpp`
- **Model tier phù hợp:** `Qwen2.5-1.5B-Instruct`

### 1.2. Ghi chú setup

Điểm khó chính trong quá trình chuẩn bị môi trường là khả năng tương thích UTF-8 trên Windows. Một số thao tác đọc file markdown/json ban đầu có nguy cơ phát sinh `UnicodeDecodeError`, vì vậy phần mã nguồn đã được chuẩn hóa lại theo hướng luôn đọc/ghi bằng `utf-8`. Sau đó tôi build `llama-server` native bằng MSVC ở chế độ Release để tận dụng tốt hơn tập lệnh AVX2 và có được đường đi phù hợp cho Track 02.

Nhìn từ góc độ tái lập, đây là một bước quan trọng: với workload LLM cỡ nhỏ trên CPU, sai khác giữa bản build generic và bản native không chỉ đến từ "compiler optimization" chung chung, mà chủ yếu đến từ khả năng vectorization và cách binary khai thác băng thông bộ nhớ của phần cứng thực tế.

---

## 2. Track 01 - Quickstart benchmark

### 2.1. Kết quả đo

| Model | Load (ms) | TTFT P50/P95 (ms) | TPOT P50/P95 (ms) | E2E P50/P95/P99 (ms) | Decode rate (tok/s) |
|---|---:|---:|---:|---:|---:|
| Qwen2.5-1.5B (Q4_K_M) | 1389 | 148 / 195 | 48.2 / 50.0 | 3162 / 3309 / 3351 | 20.7 |
| Qwen2.5-1.5B (Q2_K) | 1157 | 191 / 230 | 40.1 / 43.7 | 2721 / 2945 / 2986 | 24.9 |

### 2.2. Phân tích

Kết quả cho thấy `Q2_K` nhanh hơn `Q4_K_M` ở pha decode, thể hiện qua `TPOT` thấp hơn và decode rate cao hơn. Đây là hành vi phù hợp với trực giác hệ thống: trên CPU-only inference, decode thường bị ràng buộc bởi băng thông bộ nhớ hơn là compute thuần túy; vì vậy quantization nhỏ hơn làm giảm lượng dữ liệu phải di chuyển và kéo latency xuống.

Tuy nhiên, `Q4_K_M` vẫn là lựa chọn hợp lý hơn cho cấu hình này. Chênh lệch decode rate chỉ khoảng 20%, trong khi chất lượng đầu ra thực tế ổn định hơn và đáng tin cậy hơn cho các prompt giải thích kỹ thuật. Nói cách khác, bài toán ở đây không phải là tối đa hóa tokens/s bằng mọi giá, mà là chọn mức nén vừa đủ để vẫn giữ được chất lượng semantic trong một ngữ cảnh học thuật và RAG.

### 2.3. Kết luận cho Track 01

Với laptop i5 Gen 11 và 16 GB RAM, `Qwen2.5-1.5B-Instruct (Q4_K_M)` là điểm cân bằng tốt hơn cho use case serving cục bộ. `Q2_K` có thể hữu ích khi RAM cực kỳ chật hoặc khi mục tiêu duy nhất là phản hồi nhanh, nhưng nếu xét tổng thể giữa độ mượt, độ chính xác và tính trình diễn, `Q4_K_M` đáng ưu tiên hơn.

---

## 3. Track 02 - llama-server, observability và load test

### 3.1. Kết quả tải đồng thời

| Concurrency | Total RPS | TTFB P50 (ms) | E2E P95 (ms) | E2E P99 (ms) | Failures |
|---:|---:|---:|---:|---:|---:|
| 10 | 8.5 | 120 | 4500 | 4800 | 0 |
| 50 | 6.2 | 450 | 12000 | 15000 | 0 |

### 3.2. Giải thích hiện tượng

Khi tăng tải từ 10 lên 50 users, throughput tổng không tăng tương ứng mà ngược lại giảm, trong khi `TTFB P50`, `P95` và `P99` đều tăng rất mạnh. Đây là dấu hiệu kinh điển cho thấy hệ thống đã đi vào vùng contention:

- Pha prefill và decode phải chia sẻ cùng tài nguyên CPU và RAM.
- Nhiều request cùng tồn tại làm `KV cache` phình ra theo số slot hoạt động.
- Tail latency tăng nhanh hơn median vì queueing bắt đầu chi phối trải nghiệm người dùng.

Từ góc nhìn vận hành, con số quan trọng nhất ở đây không phải chỉ là `RPS`, mà là việc ở tải 50 users hệ thống vẫn **không lỗi** nhưng chất lượng dịch vụ ở đuôi phân phối thời gian phản hồi đã suy giảm rõ rệt. Điều đó cho thấy server đủ ổn định để phục vụ đồng thời, nhưng chưa đạt trạng thái "goodput under SLO" nếu đặt mục tiêu phản hồi chặt chẽ hơn.

### 3.3. Quan sát về KV-cache

Quan sát từ endpoint `/metrics` cho thấy `llamacpp:kv_cache_usage_ratio` tăng mạnh dưới mức tải 50 concurrent users. Dù bài làm hiện không lưu lại peak ratio dưới dạng số cụ thể trong báo cáo này, xu hướng metric hoàn toàn nhất quán với việc `P95/P99` tăng vọt: khi nhiều request chia sẻ cùng không gian cache, chi phí quản lý bộ nhớ và cạnh tranh slot bắt đầu ảnh hưởng trực tiếp tới tail latency.

Điểm quan trọng là hệ thống **không bị crash**. Điều này cho thấy lựa chọn runtime và cấu hình server đủ an toàn cho laptop CPU-only, dù chưa tối ưu cho throughput cao.

### 3.4. Đánh giá kỹ thuật

Track 02 cho thấy một insight có giá trị: benchmark đơn lẻ thường nhìn khá "ổn", nhưng khi chuyển sang serving thật với concurrency, vấn đề không còn nằm ở một metric đơn lẻ. Nút thắt chuyển dịch từ tốc độ decode thuần sang khả năng chia sẻ tài nguyên giữa nhiều request, đặc biệt là cache và hàng đợi xử lý.

Nói ngắn gọn: **bottleneck của serving không chỉ là model chậm, mà là model chậm dưới contention**.

---

## 4. Track 03 - Milestone integration

### 4.1. Thành phần đã kết nối

- **N16 (Cloud / IaC):** stub ở mức localhost
- **N17 (Data pipeline):** dùng batch-style scripts
- **N18 (Lakehouse):** stub bằng SQLite/toy setup
- **N19 (Vector + feature store):** toy retrieval documents trong pipeline

### 4.2. Kết quả quan sát

- `retrieve`: ~0.1 ms
- `llama-server`: 10930 ms ở lần đầu
- `llama-server`: 2983 ms ở lần gọi thứ hai khi cache đã nóng

### 4.3. Phân tích pipeline

Độ trễ của pipeline bị chi phối áp đảo bởi bước gọi LLM, không phải retrieval. Điều này phù hợp với thiết kế của pipeline hiện tại: lớp truy hồi mới là toy keyword retrieval, còn phần sinh văn bản mới là tác vụ tính toán nặng thực sự.

Điểm thú vị nhất là lần gọi thứ hai nhanh hơn rất nhiều. Đây là dấu hiệu của **prefix caching**: khi system prompt và cấu trúc prompt được giữ ổn định, một phần chi phí prefill có thể được tái sử dụng. Trên laptop CPU-only, việc giảm từ khoảng 10.9 giây xuống 3.0 giây là một cải thiện có ý nghĩa lớn, vì nó chứng minh rằng tối ưu hóa prompt shape và cache strategy có thể quan trọng ngang với việc đổi model.

### 4.4. Ý nghĩa thực tiễn

Trong pipeline RAG cục bộ, retrieval thường rất rẻ so với generation. Vì vậy, nếu muốn cải thiện trải nghiệm end-to-end, hướng tối ưu nên ưu tiên:

1. Giữ prefix ổn định để tận dụng cache.
2. Giảm độ dài context ghép vào prompt.
3. Tối ưu runtime/build trước khi nghĩ tới các thành phần phức tạp hơn.

---

## 5. The single change that mattered most

### 5.1. Thay đổi

**Build `llama.cpp` native từ source ở Release mode trên Windows thay vì chỉ dựa vào đường chạy Python mặc định.**

### 5.2. Before / after

```text
before: TPOT = 55.4 ms
after:  TPOT = 48.2 ms
speedup: ~1.15x
```

### 5.3. Vì sao thay đổi này hiệu quả

Thay đổi này hiệu quả vì nó tác động đúng vào bản chất của workload. Với mô hình nhỏ chạy trên CPU, decode không còn là bài toán "thiếu FLOPs" đơn thuần mà là bài toán phối hợp giữa vector instructions, cache locality và memory bandwidth. Khi build native, compiler có thể sinh mã tối ưu hơn cho tập lệnh thực tế của CPU như AVX2, đồng thời loại bỏ các tầng overhead không cần thiết của đường chạy generic.

Điểm đáng giá ở đây không chỉ là mức tăng 1.15x. Quan trọng hơn, đây là một cải thiện đạt được **mà không đổi model, không giảm chất lượng và không cần phần cứng mới**. Với bối cảnh edge/laptop inference, đây là loại tối ưu có giá trị vận hành cao nhất.

---

## 6. Hạn chế và hướng cải thiện tiếp

### 6.1. Hạn chế hiện tại

- Báo cáo hiện chưa lưu peak `kv_cache_usage_ratio` thành một số tuyệt đối trong bảng kết quả server.
- Track 03 vẫn đang dùng retrieval dạng toy/stub thay vì vector store hoàn chỉnh từ N19.
- Bài thử nghiệm mới tập trung vào CPU-only serving, nên chưa so sánh được ảnh hưởng của GPU offload hay batch scheduling phức tạp hơn.

### 6.2. Hướng cải thiện

Nếu có thêm thời gian, hai bước tiếp theo tôi sẽ ưu tiên là:

1. Commit lại `02-server-metrics.csv` kèm một bảng tóm tắt peak/median để phần observability định lượng hơn.
2. Thay retrieval toy bằng vector index thực từ milestone trước để đo chính xác hơn độ trễ toàn pipeline và chi phí context assembly.

---

## 7. Kết luận

Bài lab cho thấy một kết luận quan trọng: trên laptop cá nhân, serving LLM hiệu quả không đến từ một "mẹo thần kỳ", mà đến từ việc hiểu đúng nơi độ trễ phát sinh. `TTFT` chịu ảnh hưởng mạnh bởi prefill và context length; `TPOT` nhạy với quantization và build path; còn khi chuyển sang nhiều người dùng đồng thời, tail latency bị chi phối bởi contention và `KV cache pressure`.

Trong bối cảnh đó, lựa chọn `Q4_K_M` cho chất lượng ổn định, kết hợp native build để giảm chi phí decode, là phương án cân bằng tốt nhất cho hệ thống này. Kết quả không chỉ trả lời câu hỏi "máy có chạy được không", mà còn trả lời câu hỏi quan trọng hơn: **muốn phục vụ tốt hơn thì nên tối ưu đúng nút thắt nào trước**.
