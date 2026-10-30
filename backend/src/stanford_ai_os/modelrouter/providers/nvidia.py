"""NVIDIA-hosted model provider implementation."""

from __future__ import annotations

import httpx

from stanford_ai_os.config import Settings
from stanford_ai_os.modelrouter.providers.base import (
    ModelProvider,
    ProviderAuthenticationError,
    ProviderConfigurationError,
    ProviderConnectionError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderTimeoutError,
)
from stanford_ai_os.modelrouter.types import ModelRequest, ModelResponse


class NvidiaProvider(ModelProvider):
    """Generate text using an OpenAI-compatible NVIDIA hosted API."""

    def __init__(self, settings: Settings) -> None:
        api_key = settings.nvidia_api_key
        self._api_key = api_key.get_secret_value() if api_key is not None else None
        if not self._api_key:
            raise ProviderConfigurationError("NVIDIA API key is not configured")

        self._base_url = settings.nvidia_base_url.rstrip("/")
        self._default_model = settings.nvidia_model
        self._timeout = settings.model_timeout_seconds

    def generate(self, request: ModelRequest) -> ModelResponse:
        model = request.model or self._default_model
        messages: list[dict[str, str]] = []
        if request.system is not None:
            messages.append({"role": "system", "content": request.system})
        messages.append({"role": "user", "content": request.prompt})

        payload: dict[str, object] = {
            "model": model,
            "messages": messages,
            "stream": False,
        }
        url = f"{self._base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.post(url, json=payload, headers=headers)
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError("NVIDIA request timed out") from exc
        except httpx.HTTPError as exc:
            raise ProviderConnectionError("Could not connect to NVIDIA") from exc

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            if status_code in (401, 403):
                raise ProviderAuthenticationError(
                    f"NVIDIA authentication failed with HTTP {status_code}"
                ) from exc
            if status_code == 429:
                raise ProviderRateLimitError("NVIDIA rate limit exceeded") from exc
            raise ProviderResponseError(f"NVIDIA returned HTTP {status_code}") from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise ProviderResponseError("NVIDIA returned invalid JSON") from exc

        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ProviderResponseError("NVIDIA response did not contain choices")

        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        if not isinstance(message, dict):
            raise ProviderResponseError("NVIDIA response did not contain a message")

        text = message.get("content")
        if not isinstance(text, str):
            raise ProviderResponseError("NVIDIA response did not contain generated text")

        returned_model = data.get("model", model)
        if not isinstance(returned_model, str) or not returned_model:
            returned_model = model

        return ModelResponse(text=text, provider="nvidia", model=returned_model)
