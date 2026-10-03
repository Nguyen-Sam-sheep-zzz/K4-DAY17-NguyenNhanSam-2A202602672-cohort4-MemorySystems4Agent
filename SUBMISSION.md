# Day 17 — Hồ sơ bài nộp

## Nội dung đã hoàn thiện

| Yêu cầu | File / bằng chứng |
|---|---|
| Baseline chỉ nhớ trong chat | src/agent_baseline.py; tests/test_agent_behavior.py |
| Advanced: profile + short-term + compact | src/agent_advanced.py; src/memory_store.py; src/profile_extraction.py |
| User.md, correction và tránh nhiễu/câu hỏi | tests/test_memory_store.py; tests/test_agent_behavior.py |
| Hai benchmark, sáu chỉ số | src/benchmark.py; docs/PHAN_4_BENCHMARK.json |
| Phân tích overhead và compact | docs/PHAN_4_BAO_CAO.md; cấu hình 1200/4 và ablation không compact |
| Demo web tiếng Việt | app.py; src/demo_service.py; docs/images/PHAN_5_WEB.jpg |
| Luồng live và kiểm chứng endpoint | scripts/check_live.py; docs/PHAN_5_LIVE.json; docs/PHAN_5_BAO_CAO.md |
| Hướng dẫn hiểu bài, chạy và thuyết trình | HUONG_DAN_HOC_VA_DEMO_VI.md; README.md |

Ngày 03/10/2026 kiểm tra lại: **165 tests pass**, pip check không lỗi; dataset gốc giữ nguyên. API key/state/.venv được ignore và không nằm trong tracked files. Chưa commit/push hoặc nộp LMS.

Benchmark offline mặc định: Advanced recall 14/14 Standard + 3/3 Stress theo expected_contains; prompt Standard tăng 34,85%, Stress giảm 19,04% so với Baseline. Token/quality là heuristic, không phải provider usage hay LLM judge. Không tự khẳng định điểm rubric.

Live đã pass qua gateway OpenAI-compatible DevQuota với model `gpt-6-luna`: `PHAN_5_LIVE.json` ghi `status: passed`, 6 response thật và ba checks đạt. Key chỉ nằm trong `.env` local; không đưa `.env` hoặc key vào bài nộp.

## Dựng lại và chạy

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-ui.txt -r requirements-live.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe src\benchmark.py
.\.venv\Scripts\python.exe scripts\demo_agents.py
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1
```

Live dùng .env riêng của người chạy. Environment ưu tiên hơn .env; xem báo cáo phần5 để bỏ overrides cũ trong cửa sổ terminal. Benchmark mặc định luôn offline; chỉ `--mode live` mới gọi model. Script check_live dùng facts giả lập, state tạm, không dùng profile thật.

## Demo ngắn

1. Giới thiệu → hỏi lại: hai agent nhớ trong cùng chat.
2. Chat mới → hỏi lại: chỉ Advanced nhớ.
3. Đổi nơi ở → tạo lại agent → hỏi lại: Advanced đọc fact mới trên đĩa.
4. User khác không đọc nhầm hồ sơ; ngữ cảnh dài tạo summary/compact.
5. Hai bảng benchmark cho thấy overhead chat ngắn và lợi ích compact chat dài.
6. Khi live đã pass: chạy check_live hoặc chọn Live trên web, chỉ rõ câu trả lời đến từ provider thật; counters vẫn heuristic.

## Git do user thực hiện

```powershell
git status --short
git add .
git diff --cached --stat
git commit -m "Complete Day 17 memory systems lab and demo"
git push origin main
```

Sau push, nộp link repo và các tài liệu theo yêu cầu lớp/LMS. Git push không tự tạo bài nộp trên LMS. Không tự xóa lịch sử lỗi live; bằng chứng cuối phải phản ánh đúng lần chạy hiện tại.
