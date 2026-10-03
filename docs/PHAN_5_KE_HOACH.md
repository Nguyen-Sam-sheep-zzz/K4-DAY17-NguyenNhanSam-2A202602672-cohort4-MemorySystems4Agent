# Phần 5 — Web demo và LLM live

Mục tiêu: giao diện tiếng Việt so sánh hai agent thực, chế độ offline/live rõ ràng, chạy demo live nhỏ bằng dữ liệu giả lập. User yêu cầu bổ sung cả hai phần mở rộng; tiếp tục checkout hiện tại và để user tự push.

## Thiết kế

- `src/demo_service.py`: một DemoSession có hai agent; state nằm dưới state/web/<mode>/<UUID>, tách browser session/mode và benchmark. Chat mới tạo thread mới; tạo lại agent giữ đúng folder hồ sơ nhưng bỏ history ngắn hạn.
- `app.py`: Streamlit, hai cột answers; nhập user demo, chat mới, tạo lại agent, các nút tình huống mẫu; xem User.md/summary; bảng sáu metrics offline có nguồn và tham số.
- Live chỉ gửi khi user nhập/chọn câu hỏi. Rerun/render không gọi model. Một lượt so sánh gồm hai API calls. Credentials dùng .env/process, không hiển thị hoặc ghi vào evidence.
- Lỗi provider không biến thành câu trả lời offline; hiển thị thông báo gọn, không in raw exception có thể chứa secrets. Một agent lỗi không chặn agent còn lại. Input có thể đã ghi vào memory trước lỗi theo contract hiện tại; thông báo rõ.
- `scripts/check_live.py`: giới thiệu giả lập, tạo lại agent + recall ở thread mới, hỏi một câu kỹ thuật; tối đa sáu lượt generation trong run thành công. State tạm, không đọc profile thật; lưu answers/mode/counters và check results, không lưu config secrets.
- Giữ dữ liệu/expected và benchmark offline nguyên bản. Token và quality vẫn heuristic. Live generation không đồng nghĩa mọi provider đã được kiểm chứng hoặc summary chuyển sang LLM.

## Checklist

- [x] Viết/run test fail cho service và AppTest, triển khai UI/service.
- [x] Kiểm chứng offline: chat mới, correction, restart, user riêng, benchmark, rerun không sinh lượt mới.
- [x] Live boundary test bằng model Runnable, lỗi được xử lý an toàn; kiểm tra cấu hình chỉ in set/missing.
- [x] Đã thử live smoke thành công qua gateway DevQuota, lưu 6 response và ba checks đạt trong PHAN_5_LIVE.json.
- [x] Toàn repo165tests pass, pip check sạch; reviewer xác nhận sửa config refresh/whitespace và prompt live, browser QA/ảnh đã lưu; README/guide/report cập nhật.
- [x] Xác nhận live smoke thành công với model `gpt-6-luna`; key/base URL vẫn chỉ nằm trong `.env` local.

## Lệnh

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-ui.txt
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1
.\.venv\Scripts\python.exe scripts\check_live.py --output docs\PHAN_5_LIVE.json
.\.venv\Scripts\python.exe -m pytest -q --tb=short
```
