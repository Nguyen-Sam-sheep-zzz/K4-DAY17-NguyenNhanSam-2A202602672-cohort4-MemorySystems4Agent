from __future__ import annotations

from pathlib import Path

from agent_advanced import AdvancedAgent
from agent_baseline import BaselineAgent
from config import LabConfig
from memory_store import CompactMemoryManager, UserProfileStore
from model_provider import ProviderConfig


def make_config(tmp_path: Path):
    model = ProviderConfig("openai", "test-model", 0)
    return LabConfig(tmp_path, tmp_path / "data", tmp_path / "state", 500, 4, model, model)


def test_user_markdown_read_write_edit(tmp_path: Path) -> None:
    store = UserProfileStore(tmp_path / "profiles")
    store.write_text("sam", "Mình ở Đà Nẵng.")
    assert store.read_text("sam") == "Mình ở Đà Nẵng."
    assert store.edit_text("sam", "Đà Nẵng", "Huế")
    assert UserProfileStore(tmp_path / "profiles").read_text("sam") == "Mình ở Huế."


def test_compact_trigger(tmp_path: Path) -> None:
    manager = CompactMemoryManager(threshold_tokens=200, keep_messages=2)
    for index in range(5):
        manager.append("thread", "user", f"Lượt {index}: " + "Ngữ cảnh rất dài. " * 200)
    assert manager.compaction_count("thread") > 0
    assert len(manager.context("thread")["messages"]) == 2


def test_cross_session_recall(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    baseline, advanced = BaselineAgent(config, True), AdvancedAgent(config, True)
    for agent in (baseline, advanced):
        agent.reply("lan", "one", "Mình tên là Lan. Đồ uống yêu thích là trà đào.")
    question = "Mình tên gì và đồ uống yêu thích là gì?"
    assert "Lan" not in baseline.reply("lan", "two", question)["response"]
    response = advanced.reply("lan", "two", question)["response"]
    assert "Lan" in response and "trà đào" in response


def test_compact_reduces_prompt_load_on_long_thread(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    baseline, advanced = BaselineAgent(config, True), AdvancedAgent(config, True)
    for index in range(20):
        message = f"Lượt {index}: " + "pipeline logging và deployment " * 100
        for agent in (baseline, advanced):
            agent.reply("lan", "long", message)
    assert advanced.compaction_count("long") > 0
    assert advanced.prompt_token_usage("long") < baseline.prompt_token_usage("long") * 0.6
