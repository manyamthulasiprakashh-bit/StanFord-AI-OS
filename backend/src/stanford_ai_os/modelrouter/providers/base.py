"""Provider contract and provider-neutral exceptions."""

from abc import ABC, abstractmethod

from stanford_ai_os.modelrouter.types import ModelRequest, ModelResponse


class ProviderError(Exception):
    """Base class for provider-neutral model errors."""


class ProviderConfigurationError(ProviderError):
    """Raised when a provider is not configured correctly."""


class ProviderConnectionError(ProviderError):
    """Raised when the provider cannot be reached."""


class ProviderTimeoutError(ProviderError):
    """Raised when a provider request exceeds the configured timeout."""


class ProviderAuthenticationError(ProviderError):
    """Raised when provider authentication fails."""


class ProviderRateLimitError(ProviderError):
    """Raised when a provider rate limit is exceeded."""


class ProviderResponseError(ProviderError):
    """Raised when a provider returns an unusable response."""


class ModelProvider(ABC):
    """Abstract contract implemented by every model provider.

    Providers translate a provider-neutral ``ModelRequest`` into their own API
    format and normalize the result into a ``ModelResponse``.
    """

    @abstractmethod
    def generate(self, request: ModelRequest) -> ModelResponse:
        """Generate text for the given request."""
