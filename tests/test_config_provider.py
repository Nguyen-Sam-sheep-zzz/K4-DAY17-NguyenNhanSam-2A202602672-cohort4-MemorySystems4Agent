"""Part 1: real config/files and SDK constructors; never generate via an API."""
from __future__ import annotations

import os
from pathlib import Path
import socket
import subprocess
import sys

import pytest

from config import load_config
from model_provider import ProviderConfig, build_chat_model, normalize_provider


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch):
    prefixes = ("LLM_", "JUDGE_", "COMPACT_", "OPENAI_", "CUSTOM_", "GEMINI_",
                "GOOGLE_", "ANTHROPIC_", "OLLAMA_", "OPENROUTER_")
    for name in list(os.environ):
        if name.startswith(prefixes):
            monkeypatch.delenv(name)
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")

    def reject_network(*args, **kwargs):
        raise AssertionError("Part 1 tests must not open network connections")

    monkeypatch.setattr(socket.socket, "connect", reject_network)


def test_offline_config_creates_state_without_key(tmp_path):
    config = load_config(tmp_path)
    assert config.base_dir == tmp_path.resolve()
    assert config.data_dir == tmp_path / "data"
    assert config.state_dir == tmp_path / "state"
    assert config.state_dir.is_dir()
    assert config.model.api_key is None
    assert config.compact_threshold_tokens > 0
    assert config.compact_keep_messages > 0


def test_dotenv_is_local_and_process_environment_wins(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text(
        "LLM_PROVIDER=custom\nLLM_MODEL=file-model\n"
        "CUSTOM_BASE_URL=http://localhost:9999/v1\n"
        "COMPACT_THRESHOLD_TOKENS=1500\nCOMPACT_KEEP_MESSAGES=4\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("LLM_MODEL", "process-model")
    config = load_config(tmp_path)
    assert config.model.provider == "custom"
    assert config.model.model_name == "process-model"
    assert config.model.base_url == "http://localhost:9999/v1"
    assert config.compact_threshold_tokens == 1500
    assert config.compact_keep_messages == 4
    assert "CUSTOM_BASE_URL" not in os.environ


def test_judge_defaults_to_main_and_can_override_model(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "primary-model")
    monkeypatch.setenv("OPENAI_API_KEY", "dummy-main")
    config = load_config(tmp_path)
    assert config.judge_model == config.model
    monkeypatch.setenv("JUDGE_MODEL", "judge-model")
    config = load_config(tmp_path)
    assert config.judge_model.model_name == "judge-model"
    assert config.model.model_name == "primary-model"
    assert config.judge_model.api_key == "dummy-main"


def test_judge_other_provider_gets_own_credentials(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "dummy-main")
    monkeypatch.setenv("JUDGE_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "dummy-google")
    config = load_config(tmp_path)
    assert config.judge_model.provider == "gemini"
    assert config.judge_model.api_key == "dummy-google"
    assert config.model.api_key == "dummy-main"
    monkeypatch.setenv("JUDGE_API_KEY", "dummy-judge-override")
    assert load_config(tmp_path).judge_model.api_key == "dummy-judge-override"


@pytest.mark.parametrize("provider,key_var,url_var", [
    ("openai", "OPENAI_API_KEY", "OPENAI_BASE_URL"),
    ("custom", "CUSTOM_API_KEY", "CUSTOM_BASE_URL"),
    ("gemini", "GEMINI_API_KEY", "GEMINI_BASE_URL"),
    ("anthropic", "ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL"),
    ("openrouter", "OPENROUTER_API_KEY", "OPENROUTER_BASE_URL"),
])
def test_provider_uses_corresponding_key_and_url(tmp_path, monkeypatch, provider, key_var, url_var):
    monkeypatch.setenv("LLM_PROVIDER", provider)
    monkeypatch.setenv(key_var, "dummy-key")
    monkeypatch.setenv(url_var, "http://localhost:9999")
    config = load_config(tmp_path)
    assert config.model.provider == provider
    assert config.model.api_key == "dummy-key"
    assert config.model.base_url == "http://localhost:9999"


@pytest.mark.parametrize("value,expected", [
    (" OpenAI ", "openai"), ("anthorpic", "anthropic"),
    ("google", "gemini"), ("google-genai", "gemini"),
    ("openai-compatible", "custom"), ("ollama", "ollama"),
    ("openrouter", "openrouter"), ("anthropic", "anthropic"),
])
def test_provider_normalization(value, expected):
    assert normalize_provider(value) == expected


@pytest.mark.parametrize("value", ["", "unknown"])
def test_unknown_provider_is_rejected(value):
    with pytest.raises(ValueError, match="provider"):
        normalize_provider(value)


@pytest.mark.parametrize("variable,value", [
    ("COMPACT_THRESHOLD_TOKENS", "0"), ("COMPACT_THRESHOLD_TOKENS", "-5"),
    ("COMPACT_KEEP_MESSAGES", "0"), ("COMPACT_KEEP_MESSAGES", "2.5"),
    ("LLM_TEMPERATURE", "nan"), ("LLM_TEMPERATURE", "-1"),
    ("JUDGE_TEMPERATURE", "oops"),
])
def test_invalid_settings_fail_before_creating_state(tmp_path, monkeypatch, variable, value):
    monkeypatch.setenv(variable, value)
    with pytest.raises(ValueError, match=variable):
        load_config(tmp_path)
    assert not (tmp_path / "state").exists()


def test_config_repr_does_not_expose_key():
    config = ProviderConfig("openai", "test-model", 0, api_key="dummy-secret-marker")
    assert "dummy-secret-marker" not in repr(config)


@pytest.mark.parametrize("provider", ["openai", "gemini", "anthropic", "openrouter"])
def test_live_cloud_adapter_requires_key(provider):
    with pytest.raises(ValueError, match="key"):
        build_chat_model(ProviderConfig(provider, "test-model", 0))


def test_custom_adapter_requires_endpoint():
    with pytest.raises(ValueError, match="BASE_URL"):
        build_chat_model(ProviderConfig("custom", "test-model", 0))


def test_missing_sdk_has_install_hint():
    env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1] / "src"))
    # -S excludes site-packages: exercise a genuinely absent SDK, not a fake.
    result = subprocess.run(
        [sys.executable, "-S", "-c",
         "from model_provider import ProviderConfig, build_chat_model; "
         "build_chat_model(ProviderConfig('openai', 'test-model', 0, 'dummy-key'))"],
        env=env, capture_output=True, text=True, timeout=15,
    )
    assert result.returncode != 0
    assert "RuntimeError" in result.stderr
    assert "pip install langchain-openai" in result.stderr


@pytest.mark.parametrize("provider,module,class_name,model_name", [
    ("openai", "langchain_openai", "ChatOpenAI", "gpt-4o-mini"),
    ("custom", "langchain_openai", "ChatOpenAI", "local-model"),
    ("gemini", "langchain_google_genai", "ChatGoogleGenerativeAI", "gemini-2.5-flash"),
    ("anthropic", "langchain_anthropic", "ChatAnthropic", "claude-sonnet-4-5"),
    ("ollama", "langchain_ollama", "ChatOllama", "llama3.2"),
    ("openrouter", "langchain_openrouter", "ChatOpenRouter", "openai/gpt-4o-mini"),
])
def test_real_sdk_constructor_without_network(provider, module, class_name, model_name):
    sdk = pytest.importorskip(module)
    endpoint = "http://localhost:11434/v1" if provider == "custom" else None
    key = None if provider in ("custom", "ollama") else "dummy-not-real-key"
    config = ProviderConfig(provider, model_name, 0, key, endpoint)
    model = build_chat_model(config)
    assert isinstance(model, getattr(sdk, class_name))
    actual_name = getattr(model, "model_name", getattr(model, "model", None))
    assert actual_name == model_name
    if provider == "custom":
        assert model.openai_api_base == endpoint
