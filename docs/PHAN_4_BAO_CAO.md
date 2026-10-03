# Phần 4 — Benchmark đã chạy được

Ngày chạy: 03/10/2026. Đã hoàn thiện `src/benchmark.py`, test benchmark, hai bảng sáu chỉ số, JSON bằng chứng và hướng dẫn demo. Chạy offline bằng dữ liệu gốc; không gọi API, chưa commit/push hay nộp bài.

## Kết quả mặc định: threshold 2000, giữ 6 messages

### Standard Benchmark — 10 hội thoại, 101 lượt user, 14 câu recall

| Agent | Agent tokens only | Prompt tokens processed | Cross-session recall | Response quality | Memory growth (bytes) | Compactions |
|---|---:|---:|---:|---:|---:|---:|
| Baseline | 1022 | 19075 | 0.00% | 0.00% | 0 | 0 |
| Advanced | 829 | 25722 | 100.00% | 100.00% | 264 | 0 |

### Long-Context Stress Benchmark — 1 hội thoại, 16 lượt user, 3 câu recall

| Agent | Agent tokens only | Prompt tokens processed | Cross-session recall | Response quality | Memory growth (bytes) | Compactions |
|---|---:|---:|---:|---:|---:|---:|
| Baseline | 316 | 23075 | 0.00% | 0.00% | 0 | 0 |
| Advanced | 328 | 18682 | 100.00% | 100.00% | 213 | 1 |

Nguồn: [JSON mặc định](PHAN_4_BENCHMARK.json). Mỗi lượt có input, answer, tokens, compact delta; mỗi câu recall có expected_contains và điểm. SHA256 của hai dataset được lưu trong JSON. Dữ liệu và đáp án gốc không bị sửa.

## Hiểu kết quả

Baseline nhớ trong cùng chat nhưng không còn history khi hỏi ở chat mới, nên recall qua phiên = 0%. Advanced đọc User.md và trả đủ facts kỳ vọng ở 14 + 3 câu recall. Correction về nơi ở/nghề được cập nhật trước khi chấm; không nạp facts của hội thoại tương lai vào câu hỏi quá khứ.

Ở Standard, Advanced xử lý nhiều prompt hơn **34,85%** (25722 so với 19075). Chat ngắn chưa kích hoạt compact, nhưng Advanced vẫn đưa hồ sơ vào mỗi prompt. Khả năng nhớ tốt hơn có overhead thực tế.

Ở Stress, Advanced giảm prompt **19,04%** so với Baseline. Nén phần history cũ giúp không đọc lại toàn bộ các đoạn tin tức dài ở mỗi lượt. Output tokens không giảm (328 so với 316): compact chủ yếu giảm context đầu vào, không đảm bảo câu trả lời ngắn hơn.

Một byte count nhỏ không có nghĩa memory luôn an toàn: hiện file chỉ chứa một số fields và correction thay giá trị cũ, nên hồ sơ không tăng theo mọi lượt tin tức. Rủi ro vẫn có nếu extractor hiểu sai, facts cũ hết hiệu lực, hoặc profile chứa dữ liệu nhạy cảm. Short-term history và summary nằm trong RAM, không được tính vào cột growth của file User.md.

## Kiểm chứng tác dụng compact và thử cấu hình

Chạy cùng Advanced với ngưỡng 1.000.000 để không kích hoạt compact; đây là ablation, không phải tắt persistent memory.

| Stress — cùng Advanced | Prompt tokens | Output tokens | Recall | Compactions |
|---|---:|---:|---:|---:|
| Không compact (threshold 1000000, keep 6) | 23942 | 328 | 100% | 0 |
| Mặc định (2000/6) | 18682 | 328 | 100% | 1 |
| Nén sớm hơn (1200/4) | 14182 | 328 | 100% | 2 |

So với chính Advanced không compact, prompt giảm **21,97%** ở mặc định và **40,77%** ở 1200/4. So với Baseline, cấu hình 1200/4 giảm **38,54%**. Standard giữ nguyên kết quả vì chưa chạm ngưỡng.

Nguồn: [JSON 1200/4](PHAN_4_BENCHMARK_1200_4.json), [JSON không compact](PHAN_4_BENCHMARK_NO_COMPACT.json). Không tự đổi config mặc định để làm số đẹp hơn. Nén sớm hơn có nguy cơ mất chi tiết; ba câu recall stress tập trung vào hồ sơ, chưa chứng minh giữ đủ mọi tin tức trong summary.

## Quy ước và giới hạn

- Token là `ceil(len(text.strip()) / 4)`, cộng nội dung các messages trong prompt; không đo tokenizer/role overhead/provider usage hay hóa đơn API.
- Hai cột tokens bao gồm mọi lượt training **và** recall hoàn thành. JSON có phase_totals để đọc riêng. Với Advanced mặc định: Standard training 23722 + recall 2000 = 25722; Stress 18241 + 441 = 18682 prompt tokens.
- Recall chuẩn hóa Unicode, hoa thường và khoảng trắng, rồi so substring: không có fact = 0, có một phần = 0.5, đủ = 1. Mỗi câu hỏi có trọng số bằng nhau.
- Response quality là tỷ lệ facts kỳ vọng xuất hiện, trung bình trên câu recall; không chấm câu trả lời kỹ thuật, độ tự nhiên, đúng/sai ngữ nghĩa hay bằng LLM judge. Điểm Baseline 0% chỉ phản ánh thiếu facts qua phiên. Câu phủ định/lặp lại query có thể được thưởng nhầm bởi scoring chuỗi.
- Memory growth = tổng bytes hồ sơ cuối trừ đầu cho các user của suite; Baseline không ghi hồ sơ. Compactions cộng delta từng lượt, không cộng lại số tích lũy.
- State benchmark tạm và riêng cho từng agent/suite/lần chạy; hồ sơ được giữ qua các hội thoại trong cùng suite. Không đụng profile demo. Mỗi câu recall dùng thread mới riêng.
- CLI mặc định offline kể cả `.env` chọn live. `--mode live` mới gọi model; kể cả live thì scoring và counters hiện vẫn heuristic, không gọi judge. Chi phí extraction/summary/judge LLM chưa được đo vì không có các lời gọi đó trong triển khai hiện tại.

## Kiểm chứng và rubric

24 test benchmark pass, gồm ordering correction, thread recall riêng, Unicode/partial score, schema lỗi, byte delta nhiều user, compact delta, CLI chạy lặp, dữ liệu gốc bất biến và profile demo được giữ nguyên. Các test dùng agent và file thật; không mock bảng điểm.

Kiểm tra toàn repo cuối: **153 passed trong 8,86 giây**. `pip check` không có dependency lỗi; `git diff --check` không có whitespace lỗi. Rà soát độc lập chạy lại 24 test, tái tạo bảng mặc định, kiểm tra hash và tổng counters của cả ba JSON; không có findings cần sửa. Không còn `NotImplementedError`/`Student TODO` trong src.

Phần triển khai offline đáp ứng các nhóm yêu cầu: hai agent, User.md, compact, hai suite/sáu chỉ số, test cốt lõi và phân tích overhead/hiệu quả. Bonus hiện có entity extraction theo fields, conflict handling, tránh ghi câu hỏi/nhiễu thành facts; đây là rule có phạm vi hỗ trợ hữu hạn, không phải confidence model hoặc memory decay. Không tự quy đổi thành điểm giảng viên.

## Chạy và demo

Từ root repo trong PowerShell:

```powershell
.\.venv\Scripts\python.exe scripts\demo_agents.py
.\.venv\Scripts\python.exe src\benchmark.py
.\.venv\Scripts\python.exe -m pytest -q --tb=short
```

Muốn tái tạo số liệu:

```powershell
.\.venv\Scripts\python.exe src\benchmark.py --output docs\PHAN_4_BENCHMARK.json
.\.venv\Scripts\python.exe src\benchmark.py --compact-threshold 1200 --keep-messages 4 --output docs\PHAN_4_BENCHMARK_1200_4.json
.\.venv\Scripts\python.exe src\benchmark.py --compact-threshold 1000000 --output docs\PHAN_4_BENCHMARK_NO_COMPACT.json
```

Kịch bản ba phút:

1. Nói mục tiêu: “Em so sánh agent chỉ nhớ trong chat với agent lưu hồ sơ và nén lịch sử dài.”
2. Chạy demo: cùng chat cả hai nhớ; chat mới và tạo lại object chỉ Advanced nhớ; correction đổi Đà Nẵng → Huế; user khác không đọc nhầm hồ sơ.
3. Chạy benchmark: chỉ vào Standard overhead +34,85%, Stress tiết kiệm 19,04%, và recall 17/17 theo chuỗi.
4. Giải thích User.md giữ facts xuyên phiên; summary nén history trong thread. Cho xem bảng ablation để thấy compact giảm prompt.
5. Chạy pytest và nói rõ offline/heuristic. Chưa có chứng cứ LLM live, chưa triển khai web UI, chưa commit/push/nộp LMS.
