from dataclasses import replace
from pathlib import Path
import socket
import sys

import pytest

from config import load_config

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def config(tmp_path, monkeypatch):
    connect = socket.socket.connect
    def deny(sock, address):
        if isinstance(address, tuple) and address[0] in ("127.0.0.1", "::1"):
            return connect(sock, address)  # Windows asyncio socketpair for AppTest.
        raise AssertionError("UI tests cannot access the network")
    monkeypatch.setattr(socket.socket, "connect", deny)
    return replace(load_config(tmp_path), data_dir=ROOT / "data", mode="offline")


def make_session(config, mode="offline"):
    from demo_service import DemoSession
    return DemoSession(config, mode=mode)


def test_new_chat_forgets_only_baseline_and_restart_keeps_profile(config):
    session = make_session(config)
    session.send("Mình tên Sâm. Mình ở Đà Nẵng.")
    session.new_chat()
    replies = session.send("Mình tên gì và đang ở đâu?")["answers"]
    assert "Sâm" not in replies["Baseline"]["response"]
    assert "Sâm" in replies["Advanced"]["response"]
    session.send("Mình chuyển vào Huế, giờ mình ở Huế.")
    session.restart_agents()
    replies = session.send("Mình tên gì và đang ở đâu?")["answers"]
    assert "Sâm" not in replies["Baseline"]["response"]
    assert "Sâm" in replies["Advanced"]["response"]
    assert "Huế" in replies["Advanced"]["response"]
    assert "Huế" in session.profile_text()


def test_changing_users_opens_new_chat_and_isolates_memory(config):
    session = make_session(config)
    session.send("Mình tên Sâm.")
    old_thread = session.thread_id
    session.set_user("demo_hai")
    assert session.thread_id != old_thread
    replies = session.send("Mình tên gì?")["answers"]
    assert all("Sâm" not in r["response"] for r in replies.values())
    assert session.profile_text() == ""
    session.set_user("demo_sam")
    assert "Sâm" in session.send("Mình tên gì?")["answers"]["Advanced"]["response"]


def test_separate_browser_sessions_do_not_share_profiles(config):
    one, two = make_session(config), make_session(config)
    one.send("Mình tên Sâm.")
    assert one.config.state_dir != two.config.state_dir
    assert "Sâm" not in two.send("Mình tên gì?")["answers"]["Advanced"]["response"]


def test_invalid_requests_do_not_change_session_or_files(config):
    session = make_session(config)
    old_thread = session.thread_id
    with pytest.raises(ValueError):
        session.set_user("../invalid")
    with pytest.raises(ValueError):
        session.send("   ")
    assert session.thread_id == old_thread
    assert not session.history()
    assert session.profile_text() == ""


def test_service_metrics_count_successful_calls_across_chat_and_restart(config):
    session = make_session(config)
    first = session.send("Mình tên Sâm.")
    session.new_chat()
    second = session.send("Mình tên gì?")
    session.restart_agents()
    for name in ("Baseline", "Advanced"):
        stats = session.metrics(name)
        assert stats["calls"] == 2
        assert stats["prompt_tokens"] == first["answers"][name]["prompt_tokens"] + second["answers"][name]["prompt_tokens"]
    assert session.history() == []


def test_live_service_uses_model_and_never_silently_returns_offline(config, monkeypatch):
    messages = pytest.importorskip("langchain_core.messages")
    runnables = pytest.importorskip("langchain_core.runnables")
    # External boundary only: the production service/agents/profile/accounting run.
    model = runnables.RunnableLambda(lambda prompt: messages.AIMessage(content="Réponse live du modèle"))
    monkeypatch.setattr("agent_baseline.build_chat_model", lambda conf: model)
    monkeypatch.setattr("agent_advanced.build_chat_model", lambda conf: model)
    session = make_session(config, "live")
    result = session.send("Explique la mémoire.")
    assert all(reply["mode"] == "live" and "Réponse live" in reply["response"] for reply in result["answers"].values())
    assert all(session.metrics(name)["calls"] == 1 for name in result["answers"])


def test_provider_failure_is_redacted_and_does_not_stop_other_agent(config, monkeypatch):
    messages = pytest.importorskip("langchain_core.messages")
    runnables = pytest.importorskip("langchain_core.runnables")
    def fail(prompt):
        raise RuntimeError("private-credential-value https://secret-endpoint")
    monkeypatch.setattr("agent_baseline.build_chat_model", lambda conf: runnables.RunnableLambda(fail))
    monkeypatch.setattr("agent_advanced.build_chat_model", lambda conf: runnables.RunnableLambda(lambda prompt: messages.AIMessage(content="live success")))
    session = make_session(config, "live")
    result = session.send("Mình tên Sâm.")
    assert "private-credential" not in str(result)
    assert "secret-endpoint" not in str(result)
    assert "Baseline" in result["errors"]
    assert "Baseline" not in result["answers"]
    assert result["answers"]["Advanced"]["response"] == "live success"
    assert session.metrics("Baseline")["calls"] == 0
    assert session.metrics("Advanced")["calls"] == 1


def ui(config, monkeypatch):
    AppTest = pytest.importorskip("streamlit.testing.v1").AppTest
    monkeypatch.setattr("config.load_config", lambda base=None: config)
    return AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()


def send_ui(at, text):
    at.chat_input[0].set_value(text).run()
    assert not at.exception
    return at


def test_web_offline_chat_new_thread_restart_and_rerun(config, monkeypatch):
    at = ui(config, monkeypatch)
    assert not at.exception
    send_ui(at, "Mình tên Sâm. Mình ở Đà Nẵng.")
    at.button(key="new_chat").click().run()
    send_ui(at, "Mình tên gì và đang ở đâu?")
    text = "\n".join(m.value for m in at.markdown)
    assert "Tên: chưa có thông tin" in text
    assert "Tên: Sâm" in text
    assert "Sâm" in at.code[0].value
    calls = [m.value for m in at.metric if m.label == "Lượt thành công"]
    assert calls == ["2", "2"]
    at.run()
    assert [m.value for m in at.metric if m.label == "Lượt thành công"] == calls
    at.button(key="restart_agents").click().run()
    send_ui(at, "Mình tên gì?")
    assert "Tên: Sâm" in "\n".join(m.value for m in at.markdown)


def test_web_benchmark_runs_offline_without_polluting_demo_profile(config, monkeypatch):
    at = ui(config, monkeypatch)
    send_ui(at, "Mình tên Sâm.")
    at.button(key="run_benchmark").click().run()
    assert not at.exception
    assert len(at.dataframe) == 2
    assert "Sâm" in at.code[0].value
    assert [m.value for m in at.metric if m.label == "Lượt thành công"] == ["1", "1"]


def test_web_live_mode_switch_alone_does_not_generate(config, monkeypatch):
    messages = pytest.importorskip("langchain_core.messages")
    runnables = pytest.importorskip("langchain_core.runnables")
    def invoke(prompt):
        return messages.AIMessage(content="live answer generated")
    model = runnables.RunnableLambda(invoke)
    monkeypatch.setattr("agent_baseline.build_chat_model", lambda conf: model)
    monkeypatch.setattr("agent_advanced.build_chat_model", lambda conf: model)
    at = ui(config, monkeypatch)
    at.radio(key="mode").set_value("Live").run()
    assert not at.exception
    assert [m.value for m in at.metric if m.label == "Lượt thành công"] == ["0", "0"]
    send_ui(at, "Giải thích short-term memory.")
    assert "live answer generated" in "\n".join(m.value for m in at.markdown)
    at.run()
    assert [m.value for m in at.metric if m.label == "Lượt thành công"] == ["1", "1"]


def test_web_reloads_updated_live_model_without_losing_profile(config, monkeypatch):
    messages = pytest.importorskip("langchain_core.messages")
    runnables = pytest.importorskip("langchain_core.runnables")
    def build(conf):
        return runnables.RunnableLambda(lambda prompt: messages.AIMessage(content="Model thực dùng: " + conf.model_name))
    monkeypatch.setattr("agent_baseline.build_chat_model", build)
    monkeypatch.setattr("agent_advanced.build_chat_model", build)
    at = ui(config, monkeypatch)
    at.radio(key="mode").set_value("Live").run()
    send_ui(at, "Mình tên Sâm.")
    changed = replace(config, model=replace(config.model, model_name="new-model", api_key="new-private-key"))
    monkeypatch.setattr("config.load_config", lambda base=None: changed)
    at.button(key="restart_agents").click().run()
    send_ui(at, "Mình tên gì?")
    assert "Model thực dùng: new-model" in "\n".join(m.value for m in at.markdown)
    assert "Sâm" in at.code[0].value
    assert "new-private-key" not in str(at)


def test_web_rejects_whitespace_without_crashing_or_creating_calls(config, monkeypatch):
    at = ui(config, monkeypatch)
    at.chat_input[0].set_value("   ").run()
    assert not at.exception
    assert [m.value for m in at.metric if m.label == "Lượt thành công"] == ["0", "0"]
    assert at.warning
