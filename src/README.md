# Triển khai Day 17

`src/` đã hoàn thiện phần offline: cấu hình/provider, persistent User.md, compact memory, hai agent và benchmark hai bộ dữ liệu gốc.

- Baseline giữ history theo thread; Advanced kết hợp profile + summary + recent messages.
- Provider adapter hỗ trợ `openai`, `custom`, `gemini`, `anthropic`, `ollama`, `openrouter`. Live smoke đã có response thành công qua gateway DevQuota; xem báo cáo phần 5 và `docs/PHAN_5_LIVE.json`.
- Benchmark in Standard và Long-Context Stress, đủ sáu chỉ số. State tạm riêng, recall chấm ngay sau từng conversation ở thread mới.
- Token và quality là heuristic; xem định nghĩa/giới hạn tại [báo cáo](../docs/PHAN_4_BAO_CAO.md).

Thứ tự đọc để hiểu luồng:

1. `config.py`, `model_provider.py`: cấu hình và model adapter.
2. `memory_store.py`, `profile_extraction.py`: file User.md, trích facts, compact.
3. `agent_response.py`: responder offline chung và accounting.
4. `agent_baseline.py`, `agent_advanced.py`: hai chiến lược memory.
5. `benchmark.py`: đo hai suite, lưu trace/answers/counters/hash JSON.
6. `test_agents.py`, `../tests/`: kiểm chứng memory, agents và benchmark.
7. `demo_service.py`, `../app.py`: giao diện Streamlit với session state riêng, offline/live và nạp lại config.

Từ root repo: `.\.venv\Scripts\python.exe src\benchmark.py` và `.\.venv\Scripts\python.exe -m pytest -q`. Datasets ở `data/` được giữ nguyên. Demo: `.\.venv\Scripts\python.exe scripts\demo_agents.py`.
