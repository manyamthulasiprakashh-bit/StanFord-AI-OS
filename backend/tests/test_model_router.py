"""Tests for model provider selection."""

import pytest

from stanford_ai_os.config import Settings
from stanford_ai_os.modelrouter.providers.base import ModelProvider
from stanford_ai_os.modelrouter.providers.ollama import OllamaProvider
from stanford_ai_os.modelrouter.router import (
    ModelRouter,
    UnsupportedProviderError,
    get_model_router,
)


def test_default_provider_is_ollama() -> None:
    settings = Settings(_env_file=None)
    router = ModelRouter(settings)
    provider = router.get_provider()
    assert isinstance(provider, OllamaProvider)
    assert isinstance(provider, ModelProvider)


def test_router_uses_overridden_settings() -> None:
    settings = Settings(ollama_model="custom-model", _env_file=None)
    provider = ModelRouter(settings).get_provider()
    assert provider._default_model == "custom-model"


def test_unsupported_provider_raises() -> None:
    settings = Settings(model_provider="unknown", _env_file=None)
    router = ModelRouter(settings)
    with pytest.raises(UnsupportedProviderError):
        router.get_provider()


def test_get_model_router_helper() -> None:
    router = get_model_router(Settings(model_provider="ollama", _env_file=None))
    assert isinstance(router.get_provider(), OllamaProvider)
