from __future__ import annotations

from dataclasses import dataclass, field
from importlib import import_module


PROVIDERS = ("openai", "custom", "gemini", "anthropic", "ollama", "openrouter")


@dataclass
class ProviderConfig:
    """Settings only: creating config never imports an SDK or calls an API."""

    provider: str
    model_name: str
    temperature: float
    api_key: str | None = field(default=None, repr=False)
    base_url: str | None = None


def normalize_provider(value: str) -> str:
    """Normalize known aliases and reject unsupported providers early."""
    aliases = {
        "anthorpic": "anthropic",
        "google": "gemini",
        "google-genai": "gemini",
        "openai-compatible": "custom",
    }
    provider = value.strip().lower()
    provider = aliases.get(provider, provider)
    if provider not in PROVIDERS:
        raise ValueError(f"Unsupported provider. Choose: {', '.join(PROVIDERS)}")
    return provider


def build_chat_model(config: ProviderConfig):
    """Create a live SDK adapter lazily; this function does not generate text."""
    provider = normalize_provider(config.provider)
    if provider == "custom" and not config.base_url:
        raise ValueError("CUSTOM_BASE_URL is required for the custom provider.")
    if provider not in ("custom", "ollama") and not config.api_key:
        raise ValueError(f"An API key is required for the {provider} provider.")

    adapters = {
        "openai": ("langchain_openai", "ChatOpenAI"),
        "custom": ("langchain_openai", "ChatOpenAI"),
        "gemini": ("langchain_google_genai", "ChatGoogleGenerativeAI"),
        "anthropic": ("langchain_anthropic", "ChatAnthropic"),
        "ollama": ("langchain_ollama", "ChatOllama"),
        "openrouter": ("langchain_openrouter", "ChatOpenRouter"),
    }
    module_name, class_name = adapters[provider]
    try:
        model_class = getattr(import_module(module_name), class_name)
    except ImportError as exc:
        package = module_name.replace("_", "-")
        raise RuntimeError(
            f"Provider SDK unavailable. Install with: python -m pip install {package}"
        ) from exc

    kwargs = {"model": config.model_name, "temperature": config.temperature}
    if provider != "ollama":
        kwargs["api_key"] = config.api_key or "not-required"
    if config.base_url:
        kwargs["base_url"] = config.base_url
    if provider == "gemini":
        # This lab's Gemini adapter uses the Developer API, not ambient ADC.
        kwargs["vertexai"] = False
    return model_class(**kwargs)
