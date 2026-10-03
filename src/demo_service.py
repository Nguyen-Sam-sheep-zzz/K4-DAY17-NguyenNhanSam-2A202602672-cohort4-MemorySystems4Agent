"""Stateful comparison service; rendering never generates a response."""
from __future__ import annotations

from contextlib import nullcontext
from dataclasses import replace
from typing import Any
from uuid import uuid4

from agent_advanced import AdvancedAgent
from agent_baseline import BaselineAgent
from agent_response import bind_request
from config import LabConfig


class DemoSession:
    def __init__(self, config: LabConfig, mode: str = "offline") -> None:
        if mode not in ("offline", "live"):
            raise ValueError("mode must be offline or live")
        self.config = replace(config, mode=mode,
                              state_dir=config.state_dir / "web" / mode / uuid4().hex)
        self.user_id = "demo_sam"
        self.thread_id = uuid4().hex
        self._history: dict[str, list[dict[str, Any]]] = {}
        self._totals = {name: {"calls": 0, "agent_tokens": 0, "prompt_tokens": 0, "compactions": 0}
                        for name in ("Baseline", "Advanced")}
        self.agents = self._build_agents()

    def _build_agents(self, config: LabConfig | None = None):
        active = config or self.config
        offline = active.mode == "offline"
        return {"Baseline": BaselineAgent(active, force_offline=offline),
                "Advanced": AdvancedAgent(active, force_offline=offline)}

    def new_chat(self) -> None:
        self.thread_id = uuid4().hex

    def set_user(self, user_id: str) -> None:
        bind_request({}, user_id, "validation", "validation")
        if user_id != self.user_id:
            self.user_id = user_id
            self.new_chat()

    def restart_agents(self, config: LabConfig | None = None) -> None:
        # Build first: a failed live configuration leaves existing agents usable.
        active = replace(config, mode=self.config.mode, state_dir=self.config.state_dir) if config else self.config
        agents = self._build_agents(active)
        self.config = active
        self.agents = agents
        self.new_chat()

    def history(self) -> list[dict[str, Any]]:
        return list(self._history.get(self.thread_id, []))

    def send(self, message: str) -> dict[str, Any]:
        bind_request({}, self.user_id, self.thread_id, message)
        record: dict[str, Any] = {"message": message, "answers": {}, "errors": {}}
        if self.config.mode == "live":
            from langsmith import tracing_context
            tracing = tracing_context(enabled=False)
        else:
            tracing = nullcontext()
        # The request goes only to the selected provider, not external trace logs.
        with tracing:
            for name, agent in self.agents.items():
                before_compactions = agent.compaction_count(self.thread_id)
                try:
                    result = agent.reply(self.user_id, self.thread_id, message)
                except Exception:
                    # Do not render provider exception bodies (keys/URLs/input).
                    record["errors"][name] = (
                        "Không tạo được câu trả lời. Kiểm tra cấu hình model, key, kết nối hoặc quota. "
                        "Input có thể đã được ghi vào memory; lượt này chưa tính là thành công."
                    )
                else:
                    record["answers"][name] = result
                    self._totals[name]["calls"] += 1
                    for key in ("agent_tokens", "prompt_tokens"):
                        self._totals[name][key] += result[key]
                finally:
                    self._totals[name]["compactions"] += agent.compaction_count(self.thread_id) - before_compactions
        self._history.setdefault(self.thread_id, []).append(record)
        return record

    def metrics(self, agent_name: str) -> dict[str, int]:
        stats = dict(self._totals[agent_name])
        stats["memory_bytes"] = self.agents["Advanced"].memory_file_size(self.user_id) if agent_name == "Advanced" else 0
        return stats

    def profile_text(self) -> str:
        return self.agents["Advanced"].profile_store.read_text(self.user_id)

    def compact_context(self) -> dict[str, Any]:
        return self.agents["Advanced"].compact_memory.context(self.thread_id)
