from __future__ import annotations

from dataclasses import dataclass, replace
import math
import os
from pathlib import Path

from dotenv import dotenv_values

from model_provider import ProviderConfig, normalize_provider


DEFAULT_MODELS = {
    "openai": "gpt-4o-mini",
    "custom": "local-model",
    "gemini": "gemini-2.5-flash",
    "anthropic": "claude-sonnet-4-5",
    "ollama": "llama3.2",
    "openrouter": "openai/gpt-4o-mini",
}


@dataclass
class LabConfig:
    """Shared paths, compact policy and independent main/judge settings."""

    base_dir: Path
    data_dir: Path
    state_dir: Path
    compact_threshold_tokens: int
    compact_keep_messages: int
    model: ProviderConfig
    judge_model: ProviderConfig
    mode: str = "offline"


def _text(env: dict[str, str], name: str, default: str | None = None) -> str | None:
    value = env.get(name, "").strip()
    return value or default


def _positive_int(env: dict[str, str], name: str, default: int) -> int:
    try:
        value = int(env.get(name, str(default)))
    except ValueError:
        raise ValueError(f"{name} must be a positive integer.") from None
    if value <= 0:
        raise ValueError(f"{name} must be a positive integer.")
    return value


def _temperature(env: dict[str, str], name: str, default: float = 0.0) -> float:
    try:
        value = float(env.get(name, str(default)))
    except ValueError:
        raise ValueError(f"{name} must be a finite non-negative number.") from None
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{name} must be a finite non-negative number.")
    return value


def _provider_config(env: dict[str, str], provider: str, temperature: float) -> ProviderConfig:
    prefix = provider.upper()
    key = _text(env, f"{prefix}_API_KEY")
    if provider == "gemini":
        key = key or _text(env, "GOOGLE_API_KEY")
    default_url = "http://localhost:11434" if provider == "ollama" else None
    return ProviderConfig(
        provider=provider,
        model_name=DEFAULT_MODELS[provider],
        temperature=temperature,
        api_key=key,
        base_url=_text(env, f"{prefix}_BASE_URL", default_url),
    )


def load_config(base_dir: Path | None = None) -> LabConfig:
    """Read this repo's .env without mutating the process; env takes precedence.

    Missing credentials are valid for offline use. SDKs and live credentials
    are checked only when build_chat_model() is explicitly called.
    """
    root = (base_dir or Path(__file__).resolve().parent.parent).resolve()
    file_env = dotenv_values(root / ".env", encoding="utf-8")
    env = {name: value for name, value in file_env.items() if value is not None}
    env.update(os.environ)

    mode = _text(env, "LLM_MODE", "offline").lower()
    if mode not in ("offline", "live"):
        raise ValueError("LLM_MODE must be offline or live.")

    threshold = _positive_int(env, "COMPACT_THRESHOLD_TOKENS", 2000)
    keep_messages = _positive_int(env, "COMPACT_KEEP_MESSAGES", 6)
    provider = normalize_provider(_text(env, "LLM_PROVIDER", "openai"))
    model = _provider_config(env, provider, _temperature(env, "LLM_TEMPERATURE"))
    model.model_name = _text(env, "LLM_MODEL", model.model_name)

    judge_provider = normalize_provider(_text(env, "JUDGE_PROVIDER", provider))
    judge = replace(model) if judge_provider == provider else _provider_config(env, judge_provider, 0.0)
    judge.model_name = _text(env, "JUDGE_MODEL", judge.model_name)
    judge.temperature = _temperature(env, "JUDGE_TEMPERATURE", judge.temperature)
    judge.api_key = _text(env, "JUDGE_API_KEY", judge.api_key)
    judge.base_url = _text(env, "JUDGE_BASE_URL", judge.base_url)

    state_dir = root / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    return LabConfig(
        base_dir=root,
        data_dir=root / "data",
        state_dir=state_dir,
        compact_threshold_tokens=threshold,
        compact_keep_messages=keep_messages,
        model=model,
        judge_model=judge,
        mode=mode,
    )
