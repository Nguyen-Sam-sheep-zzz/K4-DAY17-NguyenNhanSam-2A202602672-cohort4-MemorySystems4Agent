# Phần 1 — Cấu hình và provider

Thiết kế và thứ tự triển khai dựa trên Guide.md, các interface có sẵn trong src/ và lộ trình đã được người dùng đồng ý trong chat. Làm trực tiếp trong checkout bài lab, giữ nguyên dataset và chưa commit/push. Kết thúc phần 1 để người dùng xem checkpoint trước phần memory.

## Phạm vi và hợp đồng

- Giữ ProviderConfig, LabConfig và chữ ký load_config(base_dir=None), normalize_provider(value), build_chat_model(config).
- Offline đọc cấu hình được khi không có key hoặc SDK provider. Chỉ build_chat_model mới import SDK và kiểm tra cấu hình live.
- Dùng python-dotenv đọc .env của đúng repo, biến môi trường của process ưu tiên hơn .env. Không cập nhật os.environ khi load.
- Mặc định compact threshold 2000 token, giữ 6 messages (không phải 6 lượt user). Các giá trị phải là số nguyên dương.
- Provider mặc định openai, model gpt-4o-mini, temperature 0. Các provider khác có model mặc định và cho phép LLM_MODEL thay thế.
- Judge mặc định dùng cấu hình model chính; JUDGE_PROVIDER, JUDGE_MODEL, JUDGE_TEMPERATURE, JUDGE_API_KEY, JUDGE_BASE_URL cho phép ghi đè. Judge khác provider lấy key/model của provider tương ứng.
- Hỗ trợ openai/custom/gemini/anthropic/ollama/openrouter và alias anthorpic, google, google-genai, openai-compatible.
- Custom phải có base URL khi build; endpoint local không có key dùng giá trị placeholder của SDK. Ollama không cần key. Các provider cloud cần key.
- Lỗi đầu vào nêu tên biến/provider và không đưa giá trị key vào thông báo. ProviderConfig không hiển thị key trong repr.

## Kiểm tra độc lập cần chạy

Các test dùng tmp_path và môi trường đã cô lập, không gọi API. Bỏ ghi state sẽ làm test đường dẫn fail; ưu tiên .env hơn process sẽ làm test precedence fail; dùng key của model chính cho judge khác provider sẽ làm test judge fail; sai class hoặc tham số sẽ làm smoke constructor fail khi SDK tương ứng đã cài.

- [x] Tạo .venv bằng Python 3.12.14 đã xác minh, ignore .venv, thêm dependencies offline và live riêng.
- [x] Viết tests/test_config_provider.py: đường dẫn/state, không key, precedence, alias/provider không hợp lệ, judge riêng, cấu hình compact/temperature không hợp lệ, bảo vệ key trong repr, validation live.
- [x] Chạy `.venv\Scripts\python.exe -m pytest tests/test_config_provider.py -v` và xác nhận fail vì scaffold chưa triển khai.
- [x] Triển khai config.py và model_provider.py theo hợp đồng trên.
- [x] Chạy lại đúng bộ test để xác nhận pass.
- [x] Nếu cài được requirements-live.txt, khởi tạo cả sáu adapter bằng dummy key, không invoke/generate. Nếu chưa cài, báo rõ constructor chưa được kiểm chứng.
- [x] Bổ sung .env.example, báo cáo ngắn, lệnh chạy và kiểm tra Git chỉ có thay đổi đúng phạm vi.

Phần 1 chưa triển khai reply của hai agent, memory, benchmark hay test_agents.py. Toàn bộ bài lab chưa thể pass cho tới các phần sau.

