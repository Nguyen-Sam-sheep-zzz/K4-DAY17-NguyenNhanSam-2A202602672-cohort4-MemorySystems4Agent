# Phần 4 — Benchmark và phân tích

Thiết kế đã thống nhất theo README/Guide/Rubric: chạy hai agent với dữ liệu gốc, hỏi recall ngay sau từng hội thoại trong thread mới, lưu bảng sáu chỉ số và bằng chứng. Tiếp tục trực tiếp trong checkout hiện tại, không commit/push.

## Quy ước đo

- Offline mặc định, kể cả khi .env chọn live; chỉ CLI `--mode live` mới gọi model thật.
- Mỗi suite/lần chạy dùng state tạm riêng; profile tồn tại qua hội thoại trong cùng suite. Không xóa state demo.
- Output/prompt tokens cộng mọi lượt training và recall, có breakdown theo phase trong JSON. Token dùng estimator hiện có, không phải hóa đơn API.
- Recall: không match = 0, match một phần = 0.5, match toàn bộ = 1; so chuỗi Unicode chuẩn hóa, không phân biệt hoa thường.
- Quality: tỷ lệ expected_contains match trên các câu recall (0–1). Đây là độ phủ facts heuristic, không đo chất lượng trả lời kỹ thuật hay LLM judge.
- Memory growth: tổng byte hồ sơ cuối trừ đầu của các user được đánh giá; Baseline = 0. Compactions cộng chênh lệch bộ đếm từng lượt, không cộng số tích lũy lặp lại.
- JSON chứa metadata, SHA256 dataset, số lượt/câu recall, mọi câu trả lời và counters để kiểm tra được. Không ghi config keys/base URLs.

## Thực hiện

- [x] Test loader/scoring: lỗi schema báo ValueError; điểm 0/0.5/1 và Unicode; triển khai các hàm scaffold.
- [x] Test runner thực: hai correction được chấm ở đúng thời điểm, Baseline quên thread mới, Advanced nhớ, profile growth và tổng compactions đúng; triển khai runner.
- [x] Test CLI: hai suite đủ cột, chạy lặp không nhiễm profile, dữ liệu gốc không đổi, JSON đủ bằng chứng; triển khai CLI offline/live và tham số compact.
- [x] Chạy pytest toàn repo, benchmark mặc định và cấu hình 1200/4; lưu JSON thật, phân tích trade-off và cập nhật hướng dẫn demo. Thêm ablation threshold 1000000.
- [x] Rà soát độc lập: không có findings cần sửa; reviewer chạy 24 test và kiểm tra hash/tổng counters. Toàn repo 153 passed.

## Lệnh kiểm chứng

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_benchmark.py -q
.\.venv\Scripts\python.exe -m pytest -q --tb=short
.\.venv\Scripts\python.exe src\benchmark.py --output docs\PHAN_4_BENCHMARK.json
.\.venv\Scripts\python.exe src\benchmark.py --compact-threshold 1200 --keep-messages 4 --output docs\PHAN_4_BENCHMARK_1200_4.json
```
