# Báo cáo phần 1 — Môi trường, cấu hình, provider

## Đã làm

- Tạo .venv bằng Python 3.12.14; cài pytest, dotenv, tabulate, LangChain/LangGraph và SDK sáu provider.
- Hoàn thiện src/config.py: đọc .env đúng thư mục, ưu tiên biến process, tạo state/, cấu hình model chính và judge riêng, kiểm tra tham số compact/temperature.
- Hoàn thiện src/model_provider.py: chuẩn hóa tên provider; tạo adapter openai, custom, gemini, anthropic, ollama, openrouter. SDK chỉ được import khi cần live.
- Offline load cấu hình không cần API key. Key được ẩn khỏi repr; lỗi cấu hình không in giá trị key.
- Thêm .env.example, requirements.txt (offline), requirements-live.txt (SDK) và requirements-live.lock.txt (phiên bản thực tế đã cài). Ignore .venv/.
- Giữ nguyên dataset và các interface mà hai agent đang dùng; chưa commit/push.

## Bạn cần hiểu

LabConfig là nơi tập trung đường dẫn và các tham số dùng chung. ProviderConfig mô tả model và cách kết nối. build_chat_model() tạo đối tượng SDK; gọi invoke/generate ở phần sau mới sinh câu trả lời.

Ngưỡng compact mặc định là 2000 token và giữ lại 6 messages. Một lượt user + assistant gồm hai messages. Phần này chỉ cấu hình chính sách; cơ chế nén thật thuộc phần 2.

Judge mặc định giống model chính. JUDGE_PROVIDER/JUDGE_MODEL cho phép chọn riêng; judge khác provider dùng key của provider tương ứng, hoặc JUDGE_API_KEY nếu được ghi đè.

## Kiểm chứng

- Test trước triển khai: 39 fail, do scaffold NotImplementedError và key còn xuất hiện trong repr.
- Sau triển khai: 39 passed, gồm constructor SDK thực của cả sáu provider. Tests chặn socket connect và không gọi invoke/generate. Custom và Ollama được kiểm tra khi không có key.
- Kiểm tra thiếu SDK bằng subprocess -S: báo RuntimeError kèm lệnh cài đúng package.
- pip check: No broken requirements found.
- Smoke load_config tại repo: state được tạo; threshold=2000, keep_messages=6. Kiểm tra credential chỉ in set/missing.

## Lệnh kiểm tra trên PowerShell

Chạy ở root repo:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_config_provider.py -q
.\.venv\Scripts\python.exe -m pip check
```

Muốn tái tạo đúng dependency đã kiểm chứng trên Python 3.12:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-live.lock.txt
```

Nếu chỉ làm offline, dùng requirements.txt; sáu test SDK sẽ skip khi package tương ứng chưa được cài. Các test cấu hình vẫn chạy.

Muốn sửa cấu hình có thể copy .env.example sang .env nếu chưa có .env. Không ghi đè một .env đang có key. Các giá trị LLM_MODEL trong mẫu/mặc định là tên cấu hình, chưa chứng minh model đó được endpoint/tài khoản hiện tại hỗ trợ.

## Giới hạn và bước tiếp theo

Chưa gọi API sinh câu trả lời, chưa xác minh key/quota hoặc server Ollama/custom. Agent, memory, benchmark và bốn test scaffold trong src/test_agents.py vẫn chưa triển khai; không được coi 39 test phần 1 là toàn bài đã pass.

Phần 2 sẽ làm estimate_tokens(), User.md read/write/edit, trích facts ổn định, xử lý correction và CompactMemoryManager; có test hành vi memory riêng trước khi nối vào agent.

Rà soát độc lập phần 1: không phát hiện lỗi cần sửa; reviewer chạy lại bộ test và xác nhận 39 passed.
