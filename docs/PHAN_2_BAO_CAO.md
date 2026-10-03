# Báo cáo phần 2 — Hồ sơ người dùng và compact memory

## Đã làm

- Hoàn thiện memory_store.py: estimate_tokens(), User.md read/write/edit, đọc/upsert facts, summary và CompactMemoryManager.
- Tách quy tắc trích facts sang profile_extraction.py để phần lưu trữ không bị trộn với xử lý ngôn ngữ. Import extract_profile_updates từ memory_store vẫn tương thích scaffold.
- Hồ sơ lưu UTF-8 bằng atomic replace. Cùng fact không tạo thêm dòng; correction thay field cũ và bảo toàn ghi chú khác.
- Tách hồ sơ theo user; xử lý ID Unicode/khác hoa thường/tên reserved trên Windows và từ chối đường dẫn vượt root.
- Trích facts tự khai, tránh câu hỏi, lời đùa, câu giả định và nội dung của người khác. Có regression cho correction trong cùng câu.
- Compact giữ summary trước, facts từ user và message gần đây; chỉ tăng counter nếu lượng context thật sự giảm. Summary trả về snapshot để caller không sửa nhầm state.
- Hoàn thiện hai test User.md/compact trong src/test_agents.py; thêm tests/test_memory_store.py và lệnh replay scripts/check_memory_layer.py.

## Kiểm chứng và số đo thật

84 tests pass gồm phần 1, phần 2 và hai test scaffold đã hoàn thiện. Các test memory ban đầu fail trước implementation. Regression mới bắt được lỗi correction trong cùng câu, nhầm lời người khác và collision giữa ID hash với ID ASCII; các lỗi đã được sửa. Rà soát độc lập phát hiện thêm chuyến đi tạm, correction sở thích, phủ định style và reported speech; tất cả đã có test tái hiện fail rồi pass sau sửa.

Replay chỉ nhận turns, không dùng expected_contains làm input. Dữ liệu và hồ sơ trong số đo là fixtures công khai của repo, không phải hồ sơ người dùng thật. Mỗi suite chạy trong thư mục tạm riêng.

| Suite / chính sách | Tổng context nguyên lịch sử | Tổng context sau compact | Giảm | Số compactions |
|---|---:|---:|---:|---:|
| Standard, threshold 2000 / giữ 6 | 8270 | 8270 | 0% | 0 |
| Stress, threshold 2000 / giữ 6 | 20527 | 17668 | 13.93% | 1 |
| Stress, threshold 1200 / giữ 4 | 20527 | 13274 | 35.33% | 3 |

Số liệu lấy từ PHAN_2_SO_DO.json và PHAN_2_SO_DO_1200_4.json. Token dùng heuristic ceil(stripped characters / 4); tổng context là cộng context sau mỗi lượt user, chưa có assistant replies, recall questions hay phần User.md được đưa vào prompt. Đây là kiểm tra memory layer, chưa phải bảng benchmark hai agent hoặc tiền API tiết kiệm được.

Hồ sơ Standard cuối: DũngCT, Huế, MLOps engineer, cà phê sữa đá, mì Quảng, corgi tên Bơ, Python/AI, style ngắn gọn. Hồ sơ Stress cuối: DũngCT Stress, Đà Nẵng, MLOps engineer, style 3 bullet. Correction và nhiễu không làm nơi ở đổi sai thành Hà Nội hoặc nghề thành product manager.

## Bạn cần hiểu và cách demo phần này

Persistent memory nằm trên đĩa nên tạo lại UserProfileStore vẫn đọc được. Upsert thay field cũ để nơi ở/nghề không tồn tại đồng thời hai giá trị mâu thuẫn. Compact làm nhỏ phần cũ nhưng giữ nguyên một số message gần nhất; facts và notes được tách trong summary để facts không mất sau nhiều lần nén.

Từ root repo trên PowerShell:

```powershell
$env:PYTHONIOENCODING = 'utf-8'
.\.venv\Scripts\python.exe -m pytest tests src/test_agents.py::test_user_markdown_read_write_edit src/test_agents.py::test_compact_trigger -q
.\.venv\Scripts\python.exe scripts/check_memory_layer.py
.\.venv\Scripts\python.exe scripts/check_memory_layer.py --threshold 1200 --keep 4
```

Trình bày: “Ở hội thoại ngắn chưa cần nén. Khi hạ ngưỡng và giữ ít message hơn, stress có nhiều lần compact hơn và tổng ngữ cảnh giảm thêm. Nhưng bản tóm tắt ngắn có thể mất chi tiết, nên bước tiếp theo phải kiểm chứng chất lượng trả lời.”

## Giới hạn và phần tiếp theo

Rule extraction chỉ hỗ trợ một số cách diễn đạt, chưa phải bộ hiểu tiếng Việt tổng quát hoặc confidence scorer. Summary heuristic giữ facts và trích đoạn ngắn, có thể mất nội dung dài. Ngưỡng là trigger, không phải giới hạn tuyệt đối vì recent messages có thể rất lớn. Atomic write không thay thế cơ chế lock cho nhiều process cùng cập nhật một hồ sơ.

Chưa hoàn thiện reply của hai agent, benchmark sáu chỉ số và hai test agent còn lại; toàn bộ bài chưa thể demo chat đầy đủ. Chưa gọi API, chưa commit/push. Phần 3 sẽ nối memory vào Baseline/Advanced và kiểm chứng nhớ trong cùng thread, nhớ qua thread mới, khởi tạo lại agent và cách cộng token.


Reviewer xác nhận các finding đã được sửa. Sau đó bổ sung regression danh sách sở thích có dấu phẩy; lần chạy cuối 84 passed và replay xác nhận lại số đo trong bảng.
