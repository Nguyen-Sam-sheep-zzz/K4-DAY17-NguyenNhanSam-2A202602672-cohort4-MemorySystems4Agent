# Day 17 — Hướng dẫn hiểu bài, làm bài và demo

Tài liệu dựa trên README.md, Guide.md, Rubric.md và hai dataset gốc. Cập nhật ngày 03/10/2026: phần offline đã chạy được, có demo terminal và benchmark thật; live smoke cũng đã kiểm chứng bằng model thật qua gateway DevQuota.

## 1. Trạng thái repo

Cập nhật sau phần 4: đã hoàn thiện hai agent, benchmark sáu chỉ số và demo terminal. Xem [báo cáo phần 1](docs/PHAN_1_BAO_CAO.md), [phần 2](docs/PHAN_2_BAO_CAO.md), [phần 3](docs/PHAN_3_BAO_CAO.md), [phần 4 và kịch bản ba phút](docs/PHAN_4_BAO_CAO.md).

- Repo ở nhánh main; các thay đổi chưa commit/push/nộp bài. Commit clone ban đầu: dc0e2da.
- Python 3.12.14 trong `.venv`; chạy trực tiếp python.exe ở đó, không cần activate hay Python trên PATH.
- Advanced recall đủ 17/17 câu theo chuỗi; Baseline 0/17 ở thread mới.
- Standard prompt Advanced tăng 34,85%; Stress giảm 19,04% so với Baseline ở mặc định 2000/6, hoặc giảm 38,54% với 1200/4.
- Có JSON mọi lượt/counters/dataset hash và test chống nhiễm state. Sau phần 5 có web UI tiếng Việt và toàn repo **165 tests pass**; xem [báo cáo UI/live](docs/PHAN_5_BAO_CAO.md). Live smoke đã có 6 response thật qua gateway DevQuota; LLM judge chưa triển khai. Các số benchmark offline vẫn giữ nguyên.

## 2. Bài này giải quyết vấn đề gì?

Một người dùng nói: “Mình tên Sâm, thích câu trả lời ngắn gọn.” Trong chat hiện tại, agent có thể nhắc lại vì lịch sử được đưa vào prompt. Khi mở chat mới, nếu ứng dụng không lưu gì, agent không còn biết thông tin đó.

Bài yêu cầu xây hai agent trên cùng dữ liệu:

| Agent | Trong cùng thread | Sang thread mới | Khi chat rất dài |
|---|---|---|---|
| Baseline | Giữ lịch sử để trả lời follow-up | Không có hồ sơ để nhớ fact cũ | Mang theo lịch sử ngày càng dài |
| Advanced | Giữ các lượt gần đây và summary | Đọc hồ sơ User.md của đúng user | Nén phần cũ để giảm ngữ cảnh |

“Nhớ” ở đây là ứng dụng quản lý dữ liệu và đưa lại vào prompt. Việc ghi User.md không làm thay đổi trọng số của LLM. Khả năng đọc hồ sơ qua lần chạy mới cũng cần được kiểm chứng bằng việc tạo lại agent và đọc file đã lưu.

## 3. Ba loại memory cần phân biệt

| Loại | Cách hiểu | Ví dụ | Phạm vi |
|---|---|---|---|
| Short-term | Lịch sử chat hiện tại | “Giải thích kỹ hơn ý thứ hai” | Theo thread_id |
| Persistent | Hồ sơ người dùng lưu trên đĩa | Tên, nơi ở hiện tại, nghề, style trả lời | Theo user_id, dùng lại ở thread mới |
| Compact | Tóm tắt phần hội thoại cũ, giữ nguyên một số message mới | Tóm tắt phần trao đổi dài về MLOps | Theo thread, phải giữ ý quan trọng |

user_id định danh người dùng; thread_id định danh cuộc chat. Cùng user có thể mở nhiều thread. User khác không được đọc nhầm hồ sơ của nhau.

User.md dự kiến nằm ở state/profiles/<user_id>/User.md. Persistent memory ưu tiên facts ổn định; summary giữ nội dung và mục tiêu của cuộc trao đổi. Không nên đưa mọi đoạn tin tức hoặc mọi câu nói vào hồ sơ.

Luồng một lượt Advanced:

1. Nhận message cùng user_id và thread_id.
2. Trích facts rõ ràng, phân biệt câu hỏi, lời đùa, thông tin tạm và correction.
3. Cập nhật User.md: fact mới hợp lệ thay thế fact cũ mâu thuẫn.
4. Thêm message vào memory của thread; compact khi vượt ngưỡng.
5. Tạo ngữ cảnh từ User.md + summary + các message gần đây.
6. Sinh câu trả lời, lưu message assistant và cập nhật số token.

Baseline giữ lịch sử theo thread, không đọc User.md. Nó phải nhớ trong cùng thread nhưng không được nhớ fact từ thread cũ khi chuyển sang thread mới.

## 4. Cần hoàn thiện những gì?

| Thứ tự | File | Việc cần làm | Dấu hiệu kiểm chứng |
|---|---|---|---|
| 1 | src/model_provider.py | Chuẩn hóa provider, tạo chat model; để offline không bắt buộc SDK/API key | Chọn provider đúng, báo lỗi cấu hình rõ ràng |
| 2 | src/config.py | Đường dẫn data/state, ngưỡng compact, số message giữ lại, model chính/judge, env | load_config() trả về LabConfig hợp lệ |
| 3 | src/memory_store.py | Ước lượng token; read/write/edit User.md; trích facts; summary; compact và bộ đếm | File thật được cập nhật; compact thật sự giảm context |
| 4 | src/agent_baseline.py | Trả lời offline, lưu lịch sử riêng từng thread, đếm token | Nhớ cùng thread, quên ở thread mới |
| 5 | src/agent_advanced.py | Kết hợp ba lớp memory, cập nhật correction, trả lời từ memory, đếm token | Nhớ qua thread mới, không giữ nơi ở/nghề sai |
| 6 | src/benchmark.py | Đọc JSON, chạy cùng input, hỏi recall ở thread mới, tính và in hai bảng | Có Standard + Long-Context Stress với đủ sáu chỉ số |
| 7 | src/test_agents.py | Viết test thực tế cho file memory, compact, recall, giảm prompt load | Các assertions kiểm tra hành vi và chạy pass |
| 8 | Báo cáo kết quả | Lưu số liệu chạy thật và giải thích trade-off, hạn chế, bonus | Người đọc hiểu vì sao kết quả khác nhau |

Thiết kế hỗ trợ openai, custom (OpenAI-compatible), gemini, anthropic, ollama, openrouter. Không cần key của cả sáu provider để làm demo offline. README coi chế độ live LangChain/LangGraph là phần mở rộng; nên hoàn thiện memory và benchmark offline trước.

## 5. Dữ liệu đang kiểm tra điều gì?

data/conversations.json có 10 hội thoại của dungct, tổng 101 lượt người dùng và 14 câu recall. Các hội thoại phải được xử lý theo thứ tự vì hồ sơ thay đổi theo thời gian.

- Ban đầu: DũngCT, Đà Nẵng, backend engineer, thích Python/AI và cà phê sữa đá.
- Sau correction: nơi ở là Huế; nghề sau đó thành MLOps engineer.
- Có thêm món mì Quảng, nuôi corgi, thích trả lời ngắn gọn.
- Recall cần được hỏi sau hội thoại tương ứng, trong thread mới. Nếu nạp tất cả hội thoại trước rồi mới chấm mọi câu recall, correction về sau có thể làm sai câu hỏi ở thời điểm trước.

data/advanced_long_context.json có một hội thoại của dungct_stress, 16 lượt dài và ba câu recall. Hồ sơ cuối cần nhớ: DũngCT Stress, MLOps engineer, Đà Nẵng, style “3 bullet”.

Trường hợp gây nhiễu quan trọng:

- Huế là nơi ở ban đầu trong stress, sau đó đổi sang Đà Nẵng.
- Hà Nội chỉ là nơi đi họp, không phải nơi ở hiện tại.
- product manager là lời đùa, không phải nghề mới.
- Bốn chủ đề tin tức dài tạo áp lực context; không phải mọi chi tiết đều thuộc User.md.

Không sửa expected_contains để làm điểm tăng, không lấy expected_contains làm nguồn memory cho agent.

## 6. Đọc sáu chỉ số benchmark

| Chỉ số | Ý nghĩa | Cách diễn giải |
|---|---|---|
| Agent tokens only | Token câu trả lời do agent sinh trong hội thoại, theo định nghĩa README | Tách khỏi token của lịch sử phải đọc lại |
| Prompt tokens processed | Tổng lượng ngữ cảnh đưa vào model qua các lượt | Chỉ số chính để thấy lợi ích của compact |
| Cross-session recall | Mức nhớ đúng facts khi hỏi ở thread mới | Advanced kỳ vọng tốt hơn Baseline |
| Response quality | Chất lượng phản hồi theo heuristic hoặc judge đã chọn | Cần công bố cách chấm; heuristic không tương đương judge LLM |
| Memory growth (bytes) | Dung lượng hồ sơ tăng thêm trong một lần benchmark | Theo dõi memory phình to, nên lấy sau trừ trước |
| Compactions | Số lần nén lịch sử thực sự diễn ra | Stress cần kích hoạt; nhiều lần chưa đủ chứng minh nén tốt |

Ví dụ minh họa cách cộng prompt, không phải số đo của repo: nếu context ở ba lượt là 100, 200, 300 token thì tổng processed là 600. Khi compact làm chúng thành 100, 150, 160 thì tổng là 410. Không chỉ lấy kích thước prompt cuối để kết luận.

Trong chat ngắn, profile và summary có thể tạo overhead nên Advanced chưa chắc rẻ hơn. Trong chat dài, tóm tắt giúp giảm việc đọc lại nguyên văn lịch sử. Đổi lại, summary có thể mất chi tiết hoặc giữ fact cũ sai.

Token offline là ước lượng ổn định, không phải hóa đơn API. Nếu dùng LLM để trích facts/tóm tắt/judge, cần báo riêng chi phí các lời gọi đó để đánh giá tổng chi phí thực tế.

Giới hạn của benchmark: kiểm tra chuỗi xuất hiện trong answer có thể thưởng nhầm câu phủ định hoặc câu lặp lại thông tin có sẵn trong question. Một số câu recall đã nhắc tên/nghề; cần thêm câu hỏi độc lập, kiểm tra câu trả lời sai và correction. Ba câu recall của stress tập trung vào hồ sơ, chưa đủ chứng minh summary giữ đúng mọi nội dung tin tức dài.

Benchmark phải bắt đầu từ state sạch hoặc thư mục state riêng, giữ hồ sơ xuyên các hội thoại trong cùng suite, và tách state giữa các lần chạy để tránh nhiễm kết quả. Không xóa hồ sơ demo đang dùng chỉ để reset benchmark.

## 7. Rubric và mục tiêu điểm

| Dải điểm trong rubric | Cần thể hiện |
|---|---|
| 0–60 | Baseline + Advanced, User.md, compact, dữ liệu và cấu trúc rõ ràng |
| 60–75 | Benchmark công bằng và các test memory cốt lõi |
| 75–90 | Cả hai suite; phân tích lợi ích compact ở chat dài và overhead ở chat ngắn |
| 90–100 | Bonus có ích, có kiểm chứng và giải thích cả tác dụng lẫn rủi ro |

Bonus phù hợp dữ liệu nhất là conflict handling và entity extraction có cấu trúc: cập nhật nơi ở/nghề đúng, phân biệt nơi đi họp và lời đùa. Có thể thêm confidence threshold hoặc memory decay. Đây là mục tiêu theo rubric, chưa phải điểm được chấm.

## 8. Chuẩn bị môi trường Windows

Môi trường `.venv` hiện đã có thư viện cần thiết. Có thể chạy ngay các lệnh demo, benchmark và pytest bên dưới. Các dòng tạo/cài môi trường chỉ cần khi dựng lại trên máy mới.

Trong PowerShell:

```powershell
cd 'C:\Users\SAM\IdeaProjects\VinUniAIThucChien\lap17\K4-DAY17-NguyenNhanSam-2A202602672-cohort4-MemorySystems4Agent'

# Nếu máy có Python >= 3.11:
python -m venv .venv

# Hoặc thay đúng dòng tạo venv ở trên bằng Python đã được xác minh trên máy này:
# & 'C:\Users\SAM\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m venv .venv

.\.venv\Scripts\python.exe -m pip install pytest tabulate python-dotenv
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8 = '1'

.\.venv\Scripts\python.exe src\benchmark.py
.\.venv\Scripts\python.exe scripts\demo_agents.py
.\.venv\Scripts\python.exe -m pytest src\test_agents.py -v
.\.venv\Scripts\python.exe -m pytest -q
```

Không cần activate venv khi dùng trực tiếp đường dẫn python.exe. Với triển khai offline chỉ dùng thư viện chuẩn, các SDK LLM chưa cần cài. Khi triển khai live, cài LangChain/LangGraph và SDK provider tương ứng; README có danh sách đầy đủ.

.env, state/ và .venv/ đã được ignore sau phần 1. Không commit API key hoặc hồ sơ người dùng thật.

## 9. Kịch bản demo sau khi triển khai

Có thể demo bằng terminal trước. Web UI là tiện ích để thuyết trình, không được liệt kê là yêu cầu bắt buộc trong rubric.

Giao diện đã có sau phần 5: chạy `.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1`, mở http://127.0.0.1:8501. Các nút Giới thiệu, Hỏi lại, Mở chat mới, Tạo lại agent, Đổi nơi ở mô phỏng các bước A–E bên dưới; tab Hồ sơ & compact và Benchmark hiển thị bằng chứng. Cài `requirements-ui.txt` nếu dựng lại trên máy mới.

### Bước A — Nhớ trong cùng thread

Dùng user demo_sam, thread demo_1 cho cả hai agent. Gửi: “Mình tên Sâm. Mình ở Đà Nẵng. Mình thích trả lời ngắn gọn.” Hỏi ngay: “Mình tên gì?”

Kỳ vọng cả hai trả lời đúng. Giải thích: Baseline vẫn có short-term memory.

### Bước B — Nhớ qua thread mới

Giữ user demo_sam, chuyển sang thread demo_2. Hỏi: “Mình tên gì và đang ở đâu?”

Kỳ vọng Baseline thiếu thông tin, Advanced đọc hồ sơ và trả lời đúng. Mở state/profiles/demo_sam/User.md để cho thấy dữ liệu thật được lưu. Tạo lại AdvancedAgent hoặc khởi động lại ứng dụng và hỏi tiếp để chứng minh tính bền vững của file.

### Bước C — Correction và nhiễu

Gửi: “Mình đã chuyển vào Huế, hiện mình ở Huế.” Sau đó: “Tuần trước mình ra Hà Nội họp hai ngày.” Hỏi lại nơi ở ở thread mới.

Kỳ vọng Advanced trả lời Huế. Cho thấy User.md được cập nhật thay vì tích lũy ba nơi ở như ba facts ngang nhau. Các câu demo mới cũng giúp kiểm tra hệ thống có tổng quát hơn dữ liệu benchmark hay không.

### Bước D — Compact trong hội thoại dài

Chạy stress dataset, cho xem số compactions, summary và lượng recent messages. Đối chiếu Prompt tokens processed giữa hai agent. Chỉ nói “đã giảm X%” sau khi có số đo thật: (Baseline − Advanced) / Baseline × 100%, với Baseline > 0.

### Bước E — Bằng chứng và kết luận

Chạy hai bảng benchmark và pytest. Chỉ ra recall, prompt load, memory growth; nói rõ offline/live và estimator/judge. Nếu summary mất thông tin hoặc overhead chat ngắn lớn, trình bày đó là trade-off của thiết kế.

Câu mở đầu thuyết trình có thể dùng: “Em xây hai agent để so sánh: một agent chỉ nhớ trong cuộc chat hiện tại; agent còn lại lưu hồ sơ người dùng và nén lịch sử dài. Em kiểm tra cả việc nhớ đúng sau khi mở chat mới và lượng ngữ cảnh phải xử lý.”

Câu kết: “Persistent memory giúp nhớ qua phiên; compact giảm ngữ cảnh phải mang theo. Thiết kế tốt cần nhớ đúng, cập nhật đúng và giữ chi phí hợp lý, thay vì lưu mọi thứ mãi mãi.”

## 10. Các câu cần tự trả lời được

1. Vì sao Baseline nhớ trong cùng thread nhưng quên khi đổi thread?
2. user_id và thread_id khác nhau thế nào?
3. User.md và summary giữ những loại thông tin nào?
4. Khi nơi ở thay đổi, vì sao không chỉ append thêm dòng mới?
5. Vì sao đi Hà Nội họp không được cập nhật location thành Hà Nội?
6. Vì sao Prompt tokens processed khác Agent tokens only?
7. Vì sao Advanced có thể tốn hơn ở chat ngắn?
8. Compactions > 0 đã đủ chứng minh agent còn nhớ đúng chưa?
9. Vì sao phải tách state benchmark và state demo?
10. Điểm offline cho phép kết luận gì, và điều gì phải kiểm chứng thêm bằng LLM thật?


