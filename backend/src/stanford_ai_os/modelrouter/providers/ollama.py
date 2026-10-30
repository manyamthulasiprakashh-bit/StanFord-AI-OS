"""Ollama provider implementation."""

from __future__ import annotations

import httpx

from stanford_ai_os.config import Settings
from stanford_ai_os.modelrouter.providers.base import (
    ModelProvider,
    ProviderConnectionError,
    ProviderResponseError,
    ProviderTimeoutError,
)
from stanford_ai_os.modelrouter.types import ModelRequest, ModelResponse


class OllamaProvider(ModelProvider):
    """Generate text using Ollama's local HTTP API."""

    def __init__(self, settings: Settings) -> None:
        self._base_url = settings.ollama_base_url.rstrip("/")
        self._default_model = settings.ollama_model
        self._timeout = settings.model_timeout_seconds

    def generate(self, request: ModelRequest) -> ModelResponse:
        model = request.model or self._default_model
        payload: dict[str, object] = {
            "model": model,
            "prompt": request.prompt,
            "stream": False,
        }
        if request.system is not None:
            payload["system"] = request.system

        url = f"{self._base_url}/api/generate"

        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.post(url, json=payload)
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError("Ollama request timed out") from exc
        except httpx.HTTPError as exc:
            raise ProviderConnectionError("Could not connect to Ollama") from exc

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ProviderResponseError(
                f"Ollama returned HTTP {exc.response.status_code}"
            ) from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise ProviderResponseError("Ollama returned invalid JSON") from exc

        text = data.get("response")
        if not isinstance(text, str):
            raise ProviderResponseError("Ollama response did not contain generated text")

        returned_model = data.get("model", model)
        if not isinstance(returned_model, str) or not returned_model:
            returned_model = model

        return ModelResponse(text=text, provider="ollama", model=returned_model)
