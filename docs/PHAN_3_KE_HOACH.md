# Phần 3 — Baseline và Advanced

Tiếp tục phần 3 được người dùng chấp thuận. Giữ chữ ký scaffold và dữ liệu gốc; chưa commit/push, chưa làm benchmark.

## Hợp đồng

- Baseline chỉ giữ user/assistant messages và facts trích từ user messages của đúng thread, không tạo User.md. Thread mới và object mới không nhớ facts cũ.
- Advanced upsert facts vào User.md, dùng compact theo thread và nạp profile + summary + recent messages vào prompt. Object mới đọc được profile, không khôi phục lịch sử ngắn hạn.
- Cả hai dùng cùng responder offline: chọn field theo câu hỏi, lấy giá trị từ memory thực, thiếu thì nói chưa biết. Không lấy câu hỏi/expected_contains làm đáp án. Có câu hỏi nhắc lại message trước và formatting 3 bullet từ style đã nhớ.
- Thread có một user owner trong vòng đời object; reuse thread với user khác báo ValueError trước khi đổi memory. Kiểm tra ID/request trước khi mutate.
- LabConfig thêm mode mặc định offline, LLM_MODE=offline/live; force_offline=True thắng config. Chỉ live mới khởi tạo SDK. Live dùng chat-model adapter invoke với prompt được quản lý bởi hai class; không giả nhận đây là tool agent/LangGraph checkpointer.
- Reply trả response, mode, agent_tokens, prompt_tokens, compactions; token_source=heuristic. Accessors trả tổng output/prompt tokens đã xử lý ở các lượt hoàn thành, 0 cho thread chưa có. Prompt gồm system và user hiện tại, lịch sử assistant cũ, profile/summary nếu có; chưa cộng assistant mới vào prompt của chính lượt đó.
- API live thất bại phải báo lỗi, không âm thầm chuyển sang offline. Không gọi API thật trong tests; dùng Runnable ở boundary SDK để kiểm tra prompt/routing. Lịch sử user/facts nhận vào có thể đã được lưu trước lỗi sinh response; không báo đó là lượt hoàn thành.

## Thực hiện

- [x] Viết tests/test_agent_behavior.py, test mode config và hoàn thiện make_config/cross-session/prompt-load trong src/test_agents.py; xác nhận fail trước implementation.
- [x] Triển khai agent_response.py dùng chung, BaselineAgent và AdvancedAgent.
- [x] Nối mode config, mẫu .env và live adapter path; test không có network thật.
- [x] Test toàn repo; replay training + recall bằng hai agent để smoke thực tế (chưa là benchmark sáu chỉ số).
- [x] Thêm demo terminal offline bằng thư mục state tạm, report số đo thật và rà soát độc lập. Dừng trước phần 4 benchmark.

