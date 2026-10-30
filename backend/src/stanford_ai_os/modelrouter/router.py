"""Model provider selection for Stanford-AI OS."""

from stanford_ai_os.config import Settings, get_settings
from stanford_ai_os.modelrouter.providers.base import ModelProvider
from stanford_ai_os.modelrouter.providers.nvidia import NvidiaProvider
from stanford_ai_os.modelrouter.providers.ollama import OllamaProvider


class UnsupportedProviderError(ValueError):
    """Raised when configured provider is not supported."""


class ModelRouter:
    """Small factory for selecting a configured model provider."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def get_provider(self) -> ModelProvider:
        provider_name = self._settings.model_provider.strip().lower()
        if provider_name == "ollama":
            return OllamaProvider(self._settings)
        if provider_name == "nvidia":
            return NvidiaProvider(self._settings)
        raise UnsupportedProviderError(f"Unsupported model provider: {provider_name}")


def get_model_router(settings: Settings | None = None) -> ModelRouter:
    """Return a model router using the given or configured settings."""

    return ModelRouter(settings)
