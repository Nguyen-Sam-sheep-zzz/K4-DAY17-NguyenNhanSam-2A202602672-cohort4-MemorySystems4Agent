"""Vietnamese web demo using the real lab agents and isolated demo profiles."""
from dataclasses import replace
import json
from pathlib import Path
import sys

import streamlit as st

ROOT = Path(__file__).resolve().parent
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from benchmark import run_benchmarks
from config import load_config
from demo_service import DemoSession

st.set_page_config(page_title="Day 17 · Memory Lab", page_icon="🧠", layout="wide")
st.caption("DAY 17 / MEMORY SYSTEMS FOR AI AGENT")
st.title("Một cuộc chat kết thúc. Agent còn nhớ gì?")
st.write("So sánh hai cách nhớ: lịch sử trong chat và hồ sơ người dùng kết hợp nén ngữ cảnh.")

try:
    config = load_config(ROOT)
except Exception:
    st.error("Không đọc được cấu hình. Kiểm tra .env và các tham số compact.")
    st.stop()

with st.sidebar:
    st.header("Điều khiển demo")
    mode_label = st.radio("Chế độ", ("Offline", "Live"), key="mode")
    mode = mode_label.lower()
    if mode == "offline":
        st.caption("Chạy theo rule, không gọi API. Phù hợp demo memory và benchmark lặp lại.")
    else:
        st.caption("Mỗi lần gửi gọi model cho cả hai agent. Rerun và đổi tab không gọi API.")
        st.caption(f"Provider: {config.model.provider} · Model: {config.model.model_name}")
        st.caption("API key: " + ("đã cấu hình" if config.model.api_key else "chưa cấu hình"))
    user = st.text_input("Mã người dùng", value="demo_sam", key="user_id")

if "demo_sessions" not in st.session_state:
    st.session_state.demo_sessions = {}
try:
    if mode not in st.session_state.demo_sessions:
        st.session_state.demo_sessions[mode] = DemoSession(config, mode=mode)
    session = st.session_state.demo_sessions[mode]
    effective = replace(config, mode=mode, state_dir=session.config.state_dir)
    if effective != session.config:
        session.restart_agents(config)
    session.set_user(user)
except ValueError:
    st.error("Mã người dùng cần 1–64 ký tự chữ, số, dấu gạch ngang hoặc gạch dưới; hoặc cấu hình live chưa hợp lệ.")
    st.stop()
except Exception:
    st.error("Chưa khởi tạo được live model. Kiểm tra SDK, provider, model và key trong .env.")
    st.stop()

with st.sidebar:
    if st.button("Mở chat mới", key="new_chat", use_container_width=True):
        session.new_chat()
    if st.button("Tạo lại hai agent", key="restart_agents", use_container_width=True):
        try:
            session.restart_agents(config)
        except Exception:
            st.error("Không tạo lại được agent; kiểm tra cấu hình live.")
    st.caption("Chat mới bỏ history cũ. Tạo lại agent giữ file hồ sơ Advanced trong phiên demo này.")
    st.divider()
    st.write("**Ba loại memory**")
    st.caption("History: nhớ trong chat. User.md: nhớ qua chat mới. Summary: nén phần history cũ.")

compare_tab, memory_tab, benchmark_tab, guide_tab = st.tabs(
    ["So sánh hai agent", "Hồ sơ & compact", "Benchmark", "Cách demo"]
)

with compare_tab:
    st.subheader("Gửi cùng một câu hỏi, xem hai câu trả lời")
    sample = None
    sample_columns = st.columns(4)
    for column, label, message in (
        (sample_columns[0], "1. Giới thiệu", "Mình tên Sâm. Mình ở Đà Nẵng. Mình làm backend engineer."),
        (sample_columns[1], "2. Hỏi lại", "Mình tên gì và đang ở đâu?"),
        (sample_columns[2], "3. Đổi nơi ở", "Mình chuyển vào Huế, giờ mình ở Huế. Tuần trước mình ra Hà Nội họp hai ngày."),
    ):
        if column.button(label, use_container_width=True):
            sample = message
    if sample_columns[3].button("Ngữ cảnh dài", disabled=mode == "live", use_container_width=True):
        sample = "Bản tin kỹ thuật để thử nén history, không phải hồ sơ cá nhân. " * 220
    typed = st.chat_input("Nhập câu hỏi hoặc chọn tình huống mẫu…")
    if typed or sample:
        message = typed or sample
        if not message.strip():
            st.warning("Nhập nội dung câu hỏi trước khi gửi.")
        else:
            with st.spinner("Hai agent đang trả lời…"):
                session.send(message)
    st.caption(f"Đang xem user {session.user_id} · {mode_label}. Tokens là ước lượng; tổng lượt tính trong phiên demo và chế độ hiện tại.")
    for column, name in zip(st.columns(2), ("Baseline", "Advanced")):
        with column:
            st.subheader(name)
            st.caption("Giữ toàn bộ history trong chat." if name == "Baseline" else "Hồ sơ bền vững + summary + các lượt gần nhất.")
            stats = session.metrics(name)
            m1, m2 = st.columns(2)
            m1.metric("Lượt thành công", stats["calls"])
            m2.metric("Prompt tokens ước lượng", stats["prompt_tokens"])
            st.caption(f"Output: {stats['agent_tokens']} tokens · Compact: {stats['compactions']} · Hồ sơ: {stats['memory_bytes']} bytes")
            if not session.history():
                st.info("Chưa có lượt chat. Bắt đầu bằng tình huống Giới thiệu.")
            for record in session.history():
                with st.chat_message("user"):
                    message = record["message"]
                    st.markdown(message if len(message) <= 1800 else message[:1800] + "\n\n… (rút gọn phần hiển thị)")
                with st.chat_message("assistant"):
                    if name in record["answers"]:
                        answer = record["answers"][name]
                        st.markdown(answer["response"])
                        st.caption(f"{answer['mode']} · prompt {answer['prompt_tokens']} · output {answer['agent_tokens']}")
                    else:
                        st.error(record["errors"][name])

with memory_tab:
    st.subheader("User.md — hồ sơ của người dùng hiện tại")
    st.caption("Facts được trích bằng rule và cập nhật khi có correction. Mỗi phiên trình duyệt/chế độ có folder demo riêng.")
    profile = session.profile_text()
    st.code(profile or "Chưa có hồ sơ. Hãy giới thiệu tên và nơi ở.", language="markdown")
    if profile:
        st.download_button("Tải hồ sơ demo", profile, file_name="User.md", mime="text/markdown")
    context = session.compact_context()
    st.subheader("Summary — phần history đã nén trong chat hiện tại")
    st.code(context["summary"] or "Chưa cần compact trong chat hiện tại.", language="text")
    st.caption(f"Ngưỡng: {session.config.compact_threshold_tokens} tokens · Giữ gần nhất: {session.config.compact_keep_messages} messages · Hiện giữ: {len(context['messages'])} messages")
    with st.expander("Xem các lượt còn trong context"):
        st.json(context["messages"])

with benchmark_tab:
    st.subheader("Benchmark offline trên dữ liệu gốc")
    st.caption("Chạy độc lập với chat demo, kể cả đang chọn Live. Recall/quality theo chuỗi expected_contains; không phải LLM judge. Tokens gồm training + recall, không phải hóa đơn API.")
    if st.button("Chạy hai bộ benchmark offline", key="run_benchmark"):
        with st.spinner("Đang chạy Standard và Long-Context Stress…"):
            st.session_state.benchmark_result = run_benchmarks(replace(config, mode="offline"))
    payload = st.session_state.get("benchmark_result")
    if payload:
        st.caption(f"Cấu hình lần chạy: threshold {payload['compact_threshold_tokens']} · keep {payload['compact_keep_messages']} · state tạm riêng")
        for suite in payload["suites"]:
            st.write(f"**{suite['name']}** · {suite['turns']} lượt user, {suite['recall_questions']} câu recall")
            rows = [{
                "Agent": r["agent_name"], "Output tokens": r["agent_tokens_only"],
                "Prompt tokens": r["prompt_tokens_processed"], "Recall qua chat mới": f"{r['recall_score']:.0%}",
                "Quality heuristic": f"{r['response_quality']:.0%}", "Memory growth (bytes)": r["memory_growth_bytes"],
                "Compactions": r["compactions"],
            } for r in suite["rows"]]
            st.dataframe(rows, hide_index=True, use_container_width=True)
        st.download_button("Tải kết quả và bằng chứng JSON", json.dumps(payload, ensure_ascii=False, indent=2),
                           file_name="benchmark_offline.json", mime="application/json")
    else:
        st.info("Bấm Chạy để tạo kết quả mới bằng hai bộ dữ liệu của lab.")

with guide_tab:
    st.subheader("Demo trong ba phút")
    st.markdown("""1. Chọn **Giới thiệu**, rồi **Hỏi lại**: cả hai agent nhớ trong cùng chat.
2. Bấm **Mở chat mới**, rồi **Hỏi lại**: Advanced đọc hồ sơ; Baseline thiếu thông tin.
3. Chọn **Đổi nơi ở**, rồi **Tạo lại hai agent** và **Hỏi lại**: Advanced nhớ Huế, bỏ qua chuyến đi Hà Nội.
4. Đổi mã user sang `demo_hai`, hỏi tên: hồ sơ hai người tách biệt.
5. Ở Offline, gửi **Ngữ cảnh dài**, xem summary/compact; chạy hai bảng benchmark.
6. Chọn **Live** để gửi câu kỹ thuật tới model thật; giới thiệu lại vì hồ sơ offline/live được tách riêng.
""")
    st.caption("Live dùng provider/model/key từ .env, không hiển thị key. Memory extraction/summary vẫn chạy bằng rule. Folder demo còn trên đĩa, nhưng refresh trình duyệt hoặc restart server mở phiên riêng; nút Tạo lại agent kiểm chứng đọc hồ sơ từ đúng folder hiện tại. Đây là demo local, không có đăng nhập/phân quyền cho triển khai public.")
