"""Tests for the Ollama provider using mocked HTTP responses."""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from stanford_ai_os.config import Settings
from stanford_ai_os.modelrouter.providers.ollama import (
    OllamaProvider,
    ProviderConnectionError,
    ProviderResponseError,
    ProviderTimeoutError,
)
from stanford_ai_os.modelrouter.types import ModelRequest


@pytest.fixture
def provider() -> OllamaProvider:
    settings = Settings(
        ollama_base_url="http://example.test",
        ollama_model="default-model",
        model_timeout_seconds=12.5,
    )
    return OllamaProvider(settings)


def _mock_client(response: MagicMock) -> MagicMock:
    client = MagicMock()
    client.__enter__.return_value = client
    client.post.return_value = response
    return client


def test_successful_response(provider: OllamaProvider) -> None:
    response = MagicMock()
    response.json.return_value = {"response": "Hello from Ollama", "model": "returned-model"}
    response.raise_for_status.return_value = None

    with patch("stanford_ai_os.modelrouter.providers.ollama.httpx.Client") as client_cls:
        client_cls.return_value = _mock_client(response)
        result = provider.generate(ModelRequest(prompt="Hi"))

    assert result.text == "Hello from Ollama"
    assert result.provider == "ollama"
    assert result.model == "returned-model"


def test_system_and_prompt_serialization(provider: OllamaProvider) -> None:
    response = MagicMock()
    response.json.return_value = {"response": "ok", "model": "default-model"}
    response.raise_for_status.return_value = None

    with patch("stanford_ai_os.modelrouter.providers.ollama.httpx.Client") as client_cls:
        client = _mock_client(response)
        client_cls.return_value = client
        provider.generate(ModelRequest(prompt="Question", system="System instructions"))

    payload = client.post.call_args.kwargs["json"]
    assert payload["prompt"] == "Question"
    assert payload["system"] == "System instructions"
    assert payload["stream"] is False


def test_model_override(provider: OllamaProvider) -> None:
    response = MagicMock()
    response.json.return_value = {"response": "ok", "model": "override-model"}
    response.raise_for_status.return_value = None

    with patch("stanford_ai_os.modelrouter.providers.ollama.httpx.Client") as client_cls:
        client = _mock_client(response)
        client_cls.return_value = client
        result = provider.generate(ModelRequest(prompt="Question", model="override-model"))

    payload = client.post.call_args.kwargs["json"]
    assert payload["model"] == "override-model"
    assert result.model == "override-model"


def test_default_model_used_when_not_overridden(provider: OllamaProvider) -> None:
    response = MagicMock()
    response.json.return_value = {"response": "ok"}
    response.raise_for_status.return_value = None

    with patch("stanford_ai_os.modelrouter.providers.ollama.httpx.Client") as client_cls:
        client = _mock_client(response)
        client_cls.return_value = client
        result = provider.generate(ModelRequest(prompt="Question"))

    payload = client.post.call_args.kwargs["json"]
    assert payload["model"] == "default-model"
    assert result.model == "default-model"


def test_connection_error(provider: OllamaProvider) -> None:
    with patch("stanford_ai_os.modelrouter.providers.ollama.httpx.Client") as client_cls:
        client = _mock_client(MagicMock())
        client.post.side_effect = httpx.ConnectError("connection failed")
        client_cls.return_value = client
        with pytest.raises(ProviderConnectionError):
            provider.generate(ModelRequest(prompt="Question"))


def test_timeout_error(provider: OllamaProvider) -> None:
    with patch("stanford_ai_os.modelrouter.providers.ollama.httpx.Client") as client_cls:
        client = _mock_client(MagicMock())
        client.post.side_effect = httpx.ReadTimeout("timed out")
        client_cls.return_value = client
        with pytest.raises(ProviderTimeoutError):
            provider.generate(ModelRequest(prompt="Question"))


def test_http_status_error(provider: OllamaProvider) -> None:
    response = MagicMock()
    response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "bad status", request=MagicMock(), response=MagicMock(status_code=500)
    )

    with patch("stanford_ai_os.modelrouter.providers.ollama.httpx.Client") as client_cls:
        client = _mock_client(response)
        client_cls.return_value = client
        with pytest.raises(ProviderResponseError):
            provider.generate(ModelRequest(prompt="Question"))


def test_malformed_json(provider: OllamaProvider) -> None:
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.side_effect = ValueError("bad json")

    with patch("stanford_ai_os.modelrouter.providers.ollama.httpx.Client") as client_cls:
        client = _mock_client(response)
        client_cls.return_value = client
        with pytest.raises(ProviderResponseError):
            provider.generate(ModelRequest(prompt="Question"))


def test_missing_response_field(provider: OllamaProvider) -> None:
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"model": "default-model"}

    with patch("stanford_ai_os.modelrouter.providers.ollama.httpx.Client") as client_cls:
        client = _mock_client(response)
        client_cls.return_value = client
        with pytest.raises(ProviderResponseError):
            provider.generate(ModelRequest(prompt="Question"))


def test_configurable_timeout(provider: OllamaProvider) -> None:
    response = MagicMock()
    response.json.return_value = {"response": "ok", "model": "default-model"}
    response.raise_for_status.return_value = None

    with patch("stanford_ai_os.modelrouter.providers.ollama.httpx.Client") as client_cls:
        client = _mock_client(response)
        client_cls.return_value = client
        provider.generate(ModelRequest(prompt="Question"))

    client_cls.assert_called_once_with(timeout=12.5)
