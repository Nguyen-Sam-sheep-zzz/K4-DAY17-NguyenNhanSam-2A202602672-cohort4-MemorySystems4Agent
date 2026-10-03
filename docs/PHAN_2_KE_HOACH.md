# Phần 2 — Memory layer

Tiếp tục checkpoint memory đã được người dùng đồng ý. Giữ API scaffold; không sửa dataset, chưa triển khai reply/benchmark, chưa commit/push.

## Hợp đồng

- estimate_tokens: heuristic ceil(len(text.strip())/4), chuỗi trắng bằng 0; đây không phải tokenizer hay hóa đơn API.
- UserProfileStore: UTF-8, đọc chưa có file trả chuỗi rỗng; write atomic; edit thay đúng lần xuất hiện đầu. facts()/upsert_fact() quản lý các dòng `- key: value`, không tăng dung lượng khi lặp cùng fact, bảo toàn ghi chú khác.
- ID ASCII viết thường an toàn giữ nguyên thư mục; ID Unicode/khác hoa thường dùng hash tránh đụng thư mục trên Windows. Từ chối ID rỗng, dấu phân cách đường dẫn và đường dẫn thoát root.
- extract_profile_updates: rule offline chỉ nhận lời tự khai hoặc chỉ dẫn style rõ ràng. Field name/location/profession/interests/favorite_drink/favorite_food/pet/response_style. Bỏ câu hỏi, giả định, lời đùa, nội dung trích dẫn và thông tin đi họp tạm thời. Correction mới được ưu tiên.
- summarize_messages: giữ facts từ user và bản summary trước, thêm tối đa max_items ý ngắn. Heuristic có mất chi tiết; không gọi LLM.
- CompactMemoryManager: state tách theo thread gồm messages/summary/compactions. Token tính cả summary. Nén phần cũ khi vượt ngưỡng và còn nhiều hơn keep_messages; chỉ tăng bộ đếm nếu context thật sự nhỏ hơn. Giữ các message mới nguyên văn; không hứa tổng context luôn dưới ngưỡng nếu recent messages/facts quá lớn. context() trả snapshot tránh caller làm hỏng state.

## Kiểm chứng

- [x] Viết tests/test_memory_store.py và hoàn thiện hai test scaffold User.md/compact trước implementation.
- [x] Chạy test để xác nhận fail vì memory_store còn NotImplementedError.
- [x] Implement storage, extraction, summary và compact theo hợp đồng.
- [x] Chạy tests/ cùng hai test scaffold đã hoàn thiện; regression phần 1 phải pass.
- [x] Replay hai dataset theo thứ tự để kiểm tra hồ sơ cuối và compact/prompt load trên stress; không dùng expected_contains làm input extraction.
- [x] Rà soát độc lập, lưu số đo thật và báo cáo checkpoint. Dừng trước phần agent.

