from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import socket
import subprocess
import sys

import pytest

from agent_advanced import AdvancedAgent
from agent_baseline import BaselineAgent
from config import LabConfig, load_config
from memory_store import estimate_tokens
from model_provider import ProviderConfig


@pytest.fixture
def config(tmp_path):
    model = ProviderConfig("openai", "test-model", 0)
    return LabConfig(tmp_path, tmp_path / "data", tmp_path / "state", 500, 4, model, model)


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def reject(*args, **kwargs):
        raise AssertionError("Agent tests must not open a network connection")
    monkeypatch.setattr(socket.socket, "connect", reject)
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")


@pytest.mark.parametrize("agent_class", [BaselineAgent, AdvancedAgent])
def test_both_remember_in_current_thread(config, agent_class):
    agent = agent_class(config, force_offline=True)
    agent.reply("lan", "one", "Mình tên là Lan. Mình ở Hải Phòng.")
    reply = agent.reply("lan", "one", "Mình tên gì và đang ở đâu?")
    assert "Lan" in reply["response"] and "Hải Phòng" in reply["response"]
    assert reply["mode"] == "offline"


def test_baseline_forgets_new_thread_and_never_creates_profile(config):
    agent = BaselineAgent(config, force_offline=True)
    agent.reply("lan", "one", "Mình tên là Lan.")
    response = agent.reply("lan", "two", "Mình tên gì?")["response"]
    assert "Lan" not in response
    assert "chưa" in response.lower()
    assert not (config.state_dir / "profiles").exists()
    assert "Lan" not in BaselineAgent(config, True).reply("lan", "one", "Mình tên gì?")["response"]


def test_advanced_remembers_across_threads_and_new_instance(config):
    agent = AdvancedAgent(config, True)
    agent.reply("lan", "one", "Mình tên là Lan. Mình ở Huế.")
    assert "Lan" in agent.reply("lan", "two", "Mình tên gì?")["response"]
    restarted = AdvancedAgent(config, True)
    assert "Huế" in restarted.reply("lan", "three", "Mình đang ở đâu?")["response"]
    assert restarted.profile_store.facts("lan")["name"] == "Lan"


@pytest.mark.parametrize("agent_class", [BaselineAgent, AdvancedAgent])
def test_correction_and_temporary_trip_do_not_reintroduce_old_location(config, agent_class):
    agent = agent_class(config, True)
    agent.reply("lan", "one", "Mình ở Đà Nẵng và đang làm backend engineer.")
    agent.reply("lan", "one", "Mình chuyển vào Huế. Mình không còn làm backend engineer nữa, giờ chuyển sang MLOps engineer.")
    agent.reply("lan", "one", "Hôm nay mình ở Hà Nội để họp hai ngày.")
    response = agent.reply("lan", "one", "Mình đang ở đâu và làm nghề gì?")["response"]
    assert "Huế" in response and "MLOps engineer" in response
    assert "Hà Nội" not in response and "backend engineer" not in response


@pytest.mark.parametrize("agent_class", [BaselineAgent, AdvancedAgent])
def test_same_thread_cannot_be_shared_by_different_users(config, agent_class):
    agent = agent_class(config, True)
    agent.reply("lan", "shared", "Mình tên là Lan.")
    before = agent.token_usage("shared")
    with pytest.raises(ValueError, match="user"):
        agent.reply("hai", "shared", "Mình tên là Hải.")
    assert agent.token_usage("shared") == before
    assert "Lan" not in agent.reply("hai", "other", "Mình tên gì?")["response"]


@pytest.mark.parametrize("agent_class", [BaselineAgent, AdvancedAgent])
def test_unknown_question_does_not_echo_suggested_facts(config, agent_class):
    agent = agent_class(config, True)
    response = agent.reply("lan", "new", "Bạn biết DũngCT là ai không? Mình có ở Huế và làm MLOps engineer không?")["response"]
    assert "DũngCT" not in response and "Huế" not in response and "MLOps engineer" not in response


@pytest.mark.parametrize("agent_class", [BaselineAgent, AdvancedAgent])
def test_recent_message_can_be_recalled_without_persistent_profile_fields(config, agent_class):
    agent = agent_class(config, True)
    agent.reply("lan", "one", "Mã dự án hôm nay là ATLAS-7.")
    assert "ATLAS-7" in agent.reply("lan", "one", "Mình vừa nói gì ở lượt trước?")["response"]
    assert "ATLAS-7" not in agent.reply("lan", "two", "Mình vừa nói gì ở lượt trước?")["response"]


def test_advanced_repeated_compact_keeps_recall_and_counts(config):
    agent = AdvancedAgent(config, True)
    agent.reply("lan", "one", "Mình tên là Lan. Mình ở Huế.")
    for _ in range(10):
        agent.reply("lan", "one", "Thông tin kỹ thuật: " + "pipeline logging " * 180)
    response = agent.reply("lan", "one", "Mình tên gì và đang ở đâu?")
    assert "Lan" in response["response"] and "Huế" in response["response"]
    assert response["compactions"] > 1
    assert len(agent.compact_memory.context("one")["messages"]) <= config.compact_keep_messages
    assert agent.memory_file_size("lan") > 0


@pytest.mark.parametrize("agent_class", [BaselineAgent, AdvancedAgent])
def test_accounting_is_per_thread_and_output_not_input(config, agent_class):
    agent = agent_class(config, True)
    assert agent.token_usage("absent") == agent.prompt_token_usage("absent") == 0
    first = agent.reply("lan", "one", "Ngữ cảnh dài. " * 200)
    second = agent.reply("lan", "one", "Tiếp tục.")
    assert first["agent_tokens"] == estimate_tokens(first["response"])
    assert agent.token_usage("one") == first["agent_tokens"] + second["agent_tokens"]
    assert agent.prompt_token_usage("one") == first["prompt_tokens"] + second["prompt_tokens"]
    assert first["prompt_tokens"] > first["agent_tokens"]
    assert first["token_source"] == "heuristic"


def test_offline_style_uses_three_bullets_from_memory(config):
    agent = AdvancedAgent(config, True)
    agent.reply("lan", "one", "Mình tên là Lan. Mình ở Huế. Mình đang làm data engineer. Mình muốn trả lời ngắn gọn theo 3 bullet.")
    response = agent.reply("lan", "two", "Nhắc lại tên, nghề nghiệp, nơi ở và style của mình.")["response"]
    assert len(response.splitlines()) == 3
    assert all(line.startswith("- ") for line in response.splitlines())
    assert "Lan" in response and "data engineer" in response and "Huế" in response and "3 bullet" in response


@pytest.mark.parametrize("agent_class", [BaselineAgent, AdvancedAgent])
def test_recall_without_question_mark_does_not_poison_name_or_pet(config, agent_class):
    agent = agent_class(config, True)
    agent.reply("lan", "one", "Mình tên là Lan. Mình nuôi một bé mèo tên Mít. Mình muốn câu trả lời ngắn gọn.")
    response = agent.reply("lan", "one", "Nhắc lại giúp mình tên và style trả lời mình thích.")["response"]
    assert "Lan" in response
    response = agent.reply("lan", "one", "Nhắc lại giúp mình: tên và mình nuôi con gì.")["response"]
    assert "Lan" in response and "mèo tên Mít" in response
    if agent_class is AdvancedAgent:
        assert agent.profile_store.facts("lan")["name"] == "Lan"
        assert agent.profile_store.facts("lan")["pet"] == "mèo tên Mít"


@pytest.mark.parametrize("agent_class", [BaselineAgent, AdvancedAgent])
@pytest.mark.parametrize("question,expected", [
    ("Giúp mình nhắc lại xem mình ở Hà Nội hay Huế.", "Đà Nẵng"),
    ("Bạn còn nhớ mình tên là Mai không.", "Lan"),
])
def test_recall_with_polite_prefix_or_suggested_name_never_becomes_new_fact(config, agent_class, question, expected):
    agent = agent_class(config, True)
    agent.reply("lan", "one", "Mình tên là Lan. Mình ở Đà Nẵng.")
    response = agent.reply("lan", "one", question)["response"]
    assert expected in response
    followup = agent.reply("lan", "one", "Mình tên gì và đang ở đâu?")["response"]
    assert "Lan" in followup and "Đà Nẵng" in followup
    assert "Mai" not in followup and "Hà Nội" not in followup


@pytest.mark.parametrize("agent_class", [BaselineAgent, AdvancedAgent])
@pytest.mark.parametrize("user,thread,message", [("../escape", "one", "hi"), ("lan", "", "hi"), ("lan", "one", " ")])
def test_invalid_request_is_rejected_before_mutation(config, agent_class, user, thread, message):
    agent = agent_class(config, True)
    with pytest.raises(ValueError):
        agent.reply(user, thread, message)
    assert agent.token_usage(thread) == 0


def test_mode_is_explicit_and_invalid_mode_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_MODE", "offline")
    assert load_config(tmp_path).mode == "offline"
    monkeypatch.setenv("LLM_MODE", "live")
    assert load_config(tmp_path).mode == "live"
    monkeypatch.setenv("LLM_MODE", "unexpected")
    with pytest.raises(ValueError, match="LLM_MODE"):
        load_config(tmp_path)


@pytest.mark.parametrize("agent_class,module", [(BaselineAgent, "agent_baseline"), (AdvancedAgent, "agent_advanced")])
def test_force_offline_prevents_sdk_build_even_when_config_is_live(config, monkeypatch, agent_class, module):
    def reject_build(*args):
        raise AssertionError("Offline must not build a live model")
    monkeypatch.setattr(module + ".build_chat_model", reject_build)
    assert agent_class(replace(config, mode="live"), True).reply("lan", "one", "Xin chào.")["mode"] == "offline"


@pytest.mark.parametrize("agent_class,module", [(BaselineAgent, "agent_baseline"), (AdvancedAgent, "agent_advanced")])
def test_live_path_uses_memory_prompt_without_real_api(config, monkeypatch, agent_class, module):
    AIMessage = pytest.importorskip("langchain_core.messages").AIMessage
    RunnableLambda = pytest.importorskip("langchain_core.runnables").RunnableLambda
    prompts = []
    def fake_endpoint(messages):
        prompts.append(messages)
        return AIMessage(content="Phản hồi kiểm tra endpoint.")
    monkeypatch.setattr(module + ".build_chat_model", lambda config: RunnableLambda(fake_endpoint))
    agent = agent_class(replace(config, mode="live"))
    agent.reply("lan", "one", "Mình tên là Lan.")
    result = agent.reply("lan", "two", "Mình tên gì?")
    context = "\n".join(item["content"] for item in prompts[-1])
    assert ("Lan" in context) == (agent_class is AdvancedAgent)
    assert result["mode"] == "live"
    assert result["response"] == "Phản hồi kiểm tra endpoint."
    assert result["prompt_tokens"] == sum(estimate_tokens(item["content"]) for item in prompts[-1])


@pytest.mark.parametrize("agent_class,module", [(BaselineAgent, "agent_baseline"), (AdvancedAgent, "agent_advanced")])
def test_live_failure_does_not_silently_return_offline_response(config, monkeypatch, agent_class, module):
    RunnableLambda = pytest.importorskip("langchain_core.runnables").RunnableLambda
    def failure(messages):
        raise RuntimeError("Endpoint failed")
    monkeypatch.setattr(module + ".build_chat_model", lambda config: RunnableLambda(failure))
    agent = agent_class(replace(config, mode="live"))
    with pytest.raises(RuntimeError, match="Endpoint failed"):
        agent.reply("lan", "one", "Mình tên là Lan.")
    assert agent.token_usage("one") == 0


@pytest.mark.parametrize("dataset", ["conversations.json", "advanced_long_context.json"])
def test_public_recall_questions_do_not_mutate_profile(config, dataset):
    root = Path(__file__).resolve().parents[1]
    conversations = json.loads((root / "data" / dataset).read_text(encoding="utf-8"))
    agent = AdvancedAgent(config, True)
    for conversation in conversations:
        for turn in conversation["turns"]:
            agent.reply(conversation["user_id"], conversation["id"], turn)
        before = agent.profile_store.read_text(conversation["user_id"])
        for index, question in enumerate(conversation["recall_questions"]):
            reply = agent.reply(conversation["user_id"], f"recall-{conversation['id']}-{index}", question["question"])
            for expected in question["expected_contains"]:
                assert expected in reply["response"]
        assert agent.profile_store.read_text(conversation["user_id"]) == before


def test_terminal_demo_shows_short_term_cross_thread_correction_and_restart():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, str(root / "scripts" / "demo_agents.py"), "--json"],
        cwd=root, capture_output=True, text=True, encoding="utf-8", timeout=20,
    )
    assert result.returncode == 0, result.stderr
    demo = json.loads(result.stdout)
    assert demo["mode"] == "offline"
    cases = demo["cases"]
    assert len(cases) == 5
    assert "Sâm" in cases[0]["answers"]["Baseline"]
    assert "Sâm" not in cases[1]["answers"]["Baseline"]
    assert "Sâm" in cases[1]["answers"]["Advanced"]
    assert "Huế" in cases[2]["answers"]["Advanced"]
    assert "MLOps engineer" in cases[2]["answers"]["Advanced"]
    assert "Sâm" in cases[3]["answers"]["Advanced"]
    assert "Sâm" not in cases[3]["answers"]["Baseline"]
    assert "Sâm" not in cases[4]["answers"]["Advanced"]
