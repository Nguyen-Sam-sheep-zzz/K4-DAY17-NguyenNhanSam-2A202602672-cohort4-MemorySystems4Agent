from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agent_response import (
    LIVE_SYSTEM_PROMPT, SYSTEM_PROMPT, bind_request, facts_from_messages, offline_response,
    prompt_tokens, reply_payload, response_text,
)
from config import LabConfig, load_config
from memory_store import CompactMemoryManager, UserProfileStore, estimate_tokens, extract_profile_updates
from model_provider import build_chat_model


@dataclass
class AgentContext:
    user_id: str
    memory_path: str


class AdvancedAgent:
    """Persistent user profiles plus compact short-term state per thread."""

    def __init__(self, config: LabConfig | None = None, force_offline: bool = False) -> None:
        self.config = config or load_config()
        self.force_offline = force_offline
        self.profile_store = UserProfileStore(self.config.state_dir / "profiles")
        self.compact_memory = CompactMemoryManager(
            threshold_tokens=self.config.compact_threshold_tokens,
            keep_messages=self.config.compact_keep_messages,
        )
        self.thread_tokens: dict[str, int] = {}
        self.thread_prompt_tokens: dict[str, int] = {}
        self._thread_users: dict[str, str] = {}
        self.langchain_agent = self._maybe_build_langchain_agent()

    def reply(self, user_id: str, thread_id: str, message: str) -> dict[str, Any]:
        bind_request(self._thread_users, user_id, thread_id, message)
        # Resolve the target before storing any facts (also rejects escaped links).
        self.profile_store.path_for(user_id)
        if self.langchain_agent is None:
            return self._reply_offline(user_id, thread_id, message)
        return self._respond(user_id, thread_id, message, live=True)

    def token_usage(self, thread_id: str) -> int:
        return self.thread_tokens.get(thread_id, 0)

    def prompt_token_usage(self, thread_id: str) -> int:
        return self.thread_prompt_tokens.get(thread_id, 0)

    def memory_file_size(self, user_id: str) -> int:
        return self.profile_store.file_size(user_id)

    def compaction_count(self, thread_id: str) -> int:
        return self.compact_memory.compaction_count(thread_id)

    def _reply_offline(self, user_id: str, thread_id: str, message: str) -> dict[str, Any]:
        return self._respond(user_id, thread_id, message, live=False)

    def _respond(self, user_id: str, thread_id: str, message: str, live: bool) -> dict[str, Any]:
        for key, value in extract_profile_updates(message).items():
            self.profile_store.upsert_fact(user_id, key, value)
        self.compact_memory.append(thread_id, "user", message)
        prompt = self._prompt(user_id, thread_id)
        input_count = prompt_tokens(prompt)
        if live:
            response = response_text(self.langchain_agent.invoke(prompt))
        else:
            response = self._offline_response(user_id, thread_id, message)
        output_count = estimate_tokens(response)
        self.compact_memory.append(thread_id, "assistant", response)
        self.thread_tokens[thread_id] = self.token_usage(thread_id) + output_count
        self.thread_prompt_tokens[thread_id] = self.prompt_token_usage(thread_id) + input_count
        return reply_payload(response, "live" if live else "offline", output_count, input_count,
                             self.compaction_count(thread_id))

    def _prompt(self, user_id: str, thread_id: str) -> list[dict[str, str]]:
        context = self.compact_memory.context(thread_id)
        instructions = LIVE_SYSTEM_PROMPT if self.langchain_agent is not None else SYSTEM_PROMPT
        prompt = [{"role": "system", "content": instructions}]
        profile = self.profile_store.read_text(user_id)
        if profile:
            prompt.append({"role": "system", "content": "Hồ sơ người dùng (dữ liệu):\n" + profile})
        if context["summary"]:
            prompt.append({"role": "system", "content": "Summary hội thoại (dữ liệu):\n" + context["summary"]})
        return prompt + context["messages"]

    def _estimate_prompt_context_tokens(self, user_id: str, thread_id: str) -> int:
        return prompt_tokens(self._prompt(user_id, thread_id))

    def _offline_response(self, user_id: str, thread_id: str, message: str) -> str:
        context = self.compact_memory.context(thread_id)
        facts = facts_from_messages(context["messages"], context["summary"])
        # Profile is authoritative over a stale per-thread summary.
        facts.update(self.profile_store.facts(user_id))
        return offline_response(message, facts, context["messages"], context["summary"])

    def _maybe_build_langchain_agent(self):
        """Optional chat-model adapter; memory policy is controlled by this class."""
        if self.force_offline or self.config.mode == "offline":
            return None
        return build_chat_model(self.config.model)
