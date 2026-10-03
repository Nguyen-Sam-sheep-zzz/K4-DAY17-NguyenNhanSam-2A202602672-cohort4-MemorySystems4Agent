from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agent_response import (
    LIVE_SYSTEM_PROMPT, SYSTEM_PROMPT, bind_request, facts_from_messages, offline_response,
    prompt_tokens, reply_payload, response_text,
)
from config import LabConfig, load_config
from memory_store import estimate_tokens
from model_provider import build_chat_model


@dataclass
class SessionState:
    messages: list[dict[str, str]] = field(default_factory=list)
    token_usage: int = 0
    prompt_tokens_processed: int = 0


class BaselineAgent:
    """Full history per thread; no persistent profile and no compaction."""

    def __init__(self, config: LabConfig | None = None, force_offline: bool = False) -> None:
        self.config = config or load_config()
        self.force_offline = force_offline
        self.sessions: dict[str, SessionState] = {}
        self._thread_users: dict[str, str] = {}
        self.langchain_agent = self._maybe_build_langchain_agent()

    def reply(self, user_id: str, thread_id: str, message: str) -> dict[str, Any]:
        bind_request(self._thread_users, user_id, thread_id, message)
        if self.langchain_agent is None:
            return self._reply_offline(thread_id, message)
        return self._respond(thread_id, message, live=True)

    def token_usage(self, thread_id: str) -> int:
        state = self.sessions.get(thread_id)
        return state.token_usage if state else 0

    def prompt_token_usage(self, thread_id: str) -> int:
        state = self.sessions.get(thread_id)
        return state.prompt_tokens_processed if state else 0

    def compaction_count(self, thread_id: str) -> int:
        return 0

    def _reply_offline(self, thread_id: str, message: str) -> dict[str, Any]:
        return self._respond(thread_id, message, live=False)

    def _respond(self, thread_id: str, message: str, live: bool) -> dict[str, Any]:
        state = self.sessions.setdefault(thread_id, SessionState())
        state.messages.append({"role": "user", "content": message})
        prompt = [{"role": "system", "content": LIVE_SYSTEM_PROMPT if live else SYSTEM_PROMPT}] + list(state.messages)
        input_count = prompt_tokens(prompt)
        if live:
            response = response_text(self.langchain_agent.invoke(prompt))
        else:
            facts = facts_from_messages(state.messages)
            response = offline_response(message, facts, state.messages)
        output_count = estimate_tokens(response)
        state.messages.append({"role": "assistant", "content": response})
        state.token_usage += output_count
        state.prompt_tokens_processed += input_count
        return reply_payload(response, "live" if live else "offline", output_count, input_count, 0)

    def _maybe_build_langchain_agent(self):
        """Optional chat-model adapter; thread state is owned by this class."""
        if self.force_offline or self.config.mode == "offline":
            return None
        return build_chat_model(self.config.model)
