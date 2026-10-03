# Phần 3 — Hai agent đã chạy được

## Đã làm

- Baseline giữ toàn bộ lịch sử của một thread, không ghi User.md và quên khi đổi thread/tạo lại object.
- Advanced nối profile, summary và recent messages vào luồng reply; profile còn trên đĩa sau khi tạo lại agent.
- Cả hai dùng chung responder offline, nhận facts từ memory thực. Câu hỏi không có dấu hỏi không được ghi nhầm thành tên/thú cưng mới.
- Đếm output và prompt tokens theo từng lượt/thread. Prompt tính cả system, user hiện tại, assistant cũ và profile/summary của Advanced; không tính response mới vào prompt của chính lượt đó.
- Thread chỉ có một user owner trong vòng đời object; input sai báo lỗi trước khi thêm message/fact.
- Thêm LLM_MODE=offline/live, mặc định offline; force_offline=True luôn thắng. Live dùng SDK chat-model invoke với memory do các class quản lý, không phải tool agent hoặc LangGraph checkpointer.
- Thêm scripts/demo_agents.py và hoàn thiện toàn bộ bốn test scaffold trong src/test_agents.py.

## Kiểm chứng

129 tests pass trong môi trường .venv đã cài SDK. Rerun gồm regression phần 1/2, các test agent, demo subprocess và toàn bộ test scaffold. Lỗi recall không dấu '?' được phát hiện qua dữ liệu gốc, viết test fail trước sửa và xác nhận pass sau sửa.

Advanced trả đủ các chuỗi expected_contains của 14 câu recall standard và 3 câu stress ở thread mới, không thay đổi file hồ sơ khi hỏi recall. Đây là kiểm tra fixture theo chuỗi, chưa phải đánh giá chất lượng bằng LLM judge hoặc bảng benchmark sáu chỉ số. Baseline thiếu facts khi sang thread mới như thiết kế.

Live routing/prompt được kiểm tra qua Runnable thay endpoint và socket bị chặn; chưa gọi API sinh câu trả lời thật hay kiểm chứng key/quota. Toàn bộ counters hiện là heuristic, kể cả live; không phải usage metadata/hóa đơn provider. Chỉ các lượt hoàn thành cộng vào counters. Nếu endpoint lỗi, lỗi được truyền ra; facts/user message nhận trước đó có thể đã được lưu.

Test live dùng SDK sẽ skip nếu chỉ cài requirements offline. Không có SDK vẫn dùng được responder/memory offline.

## Chạy demo

Trong PowerShell:

```powershell
cd 'C:\Users\SAM\IdeaProjects\VinUniAIThucChien\lap17\K4-DAY17-NguyenNhanSam-2A202602672-cohort4-MemorySystems4Agent'
.\.venv\Scripts\python.exe scripts\demo_agents.py
.\.venv\Scripts\python.exe -m pytest -q
```

Demo dùng facts giả lập và thư mục state tạm, không ghi vào hồ sơ đang dùng hoặc gọi API. Output thật đã lưu trong PHAN_3_DEMO.json.

| Bước | Baseline | Advanced |
|---|---|---|
| Cùng chat | Nhớ Sâm / Đà Nẵng | Nhớ Sâm / Đà Nẵng |
| Chat mới | Chưa biết | Vẫn nhớ |
| Correction trong chat | Huế / MLOps engineer | Huế / MLOps engineer |
| Tạo lại agent | Chưa biết | Đọc lại Sâm / Huế / MLOps engineer |
| Người dùng khác | Chưa biết | Không đọc nhầm hồ sơ Sâm |

Bạn có thể nói: “Baseline nhớ nhờ lịch sử chat. Advanced nhớ qua chat mới và sau restart nhờ file User.md. Compact giúp giữ lịch sử gọn hơn; các facts hiện tại trong hồ sơ được ưu tiên hơn summary cũ.”

## Trạng thái tiếp theo

Chưa commit/push. Benchmark trong src/benchmark.py còn scaffold; phần 4 sẽ hoàn thiện hai bảng sáu chỉ số, state tách biệt cho từng suite, ghi kết quả chạy thật và phân tích trade-off. Responder offline chỉ hỗ trợ một số dạng câu hỏi memory, không thay thế LLM cho câu hỏi kỹ thuật tổng quát.


Rà soát độc lập đã xác nhận lỗi recall có tiền tố 'Giúp mình' và câu 'Bạn còn nhớ ... không.' được sửa; reviewer chạy lại 86 test agent/memory pass. Lần kiểm tra toàn repo cuối: 129 passed.
