"""Tests for the NVIDIA provider using mocked HTTP responses."""

from unittest.mock import MagicMock, patch

import httpx
import pytest
from pydantic import SecretStr

from stanford_ai_os.config import Settings
from stanford_ai_os.modelrouter.providers.base import (
    ProviderAuthenticationError,
    ProviderConfigurationError,
    ProviderConnectionError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderTimeoutError,
)
from stanford_ai_os.modelrouter.providers.nvidia import NvidiaProvider
from stanford_ai_os.modelrouter.router import ModelRouter, UnsupportedProviderError
from stanford_ai_os.modelrouter.types import ModelRequest


def _settings(**overrides) -> Settings:
    values = {
        "nvidia_api_key": SecretStr("test-secret-key"),
        "nvidia_base_url": "https://example.test/v1",
        "nvidia_model": "test-model",
        "model_timeout_seconds": 9.5,
    }
    values.update(overrides)
    return Settings(**values)


@pytest.fixture
def provider() -> NvidiaProvider:
    return NvidiaProvider(_settings())


def _mock_client(response: MagicMock) -> MagicMock:
    client = MagicMock()
    client.__enter__.return_value = client
    client.post.return_value = response
    return client


def test_missing_api_key_raises_configuration_error() -> None:
    settings = _settings(nvidia_api_key=None)
    with pytest.raises(ProviderConfigurationError):
        NvidiaProvider(settings)


def test_router_selects_nvidia() -> None:
    settings = _settings(model_provider="nvidia")
    provider = ModelRouter(settings).get_provider()
    assert isinstance(provider, NvidiaProvider)


def test_unsupported_provider_raises() -> None:
    settings = _settings(model_provider="unknown")
    with pytest.raises(UnsupportedProviderError):
        ModelRouter(settings).get_provider()


def test_request_url_method_and_headers(provider: NvidiaProvider) -> None:
    response = MagicMock()
    response.json.return_value = {
        "choices": [{"message": {"content": "ok"}}],
        "model": "test-model",
    }
    response.raise_for_status.return_value = None

    with patch("stanford_ai_os.modelrouter.providers.nvidia.httpx.Client") as client_cls:
        client = _mock_client(response)
        client_cls.return_value = client
        provider.generate(ModelRequest(prompt="Question"))

    client.post.assert_called_once()
    args, kwargs = client.post.call_args
    assert args[0] == "https://example.test/v1/chat/completions"
    assert kwargs["headers"]["Authorization"] == "Bearer test-secret-key"
    assert kwargs["headers"]["Content-Type"] == "application/json"


def test_payload_and_model_override(provider: NvidiaProvider) -> None:
    response = MagicMock()
    response.json.return_value = {
        "choices": [{"message": {"content": "ok"}}],
        "model": "override-model",
    }
    response.raise_for_status.return_value = None

    with patch("stanford_ai_os.modelrouter.providers.nvidia.httpx.Client") as client_cls:
        client = _mock_client(response)
        client_cls.return_value = client
        result = provider.generate(
            ModelRequest(prompt="Question", system="System instructions", model="override-model")
        )

    payload = client.post.call_args.kwargs["json"]
    assert payload["model"] == "override-model"
    assert payload["stream"] is False
    assert payload["messages"] == [
        {"role": "system", "content": "System instructions"},
        {"role": "user", "content": "Question"},
    ]
    assert result.text == "ok"
    assert result.provider == "nvidia"
    assert result.model == "override-model"


def test_default_model_used(provider: NvidiaProvider) -> None:
    response = MagicMock()
    response.json.return_value = {"choices": [{"message": {"content": "ok"}}]}
    response.raise_for_status.return_value = None

    with patch("stanford_ai_os.modelrouter.providers.nvidia.httpx.Client") as client_cls:
        client = _mock_client(response)
        client_cls.return_value = client
        result = provider.generate(ModelRequest(prompt="Question"))

    payload = client.post.call_args.kwargs["json"]
    assert payload["model"] == "test-model"
    assert payload["messages"] == [{"role": "user", "content": "Question"}]
    assert result.model == "test-model"


def test_optional_system_omitted(provider: NvidiaProvider) -> None:
    response = MagicMock()
    response.json.return_value = {"choices": [{"message": {"content": "ok"}}]}
    response.raise_for_status.return_value = None

    with patch("stanford_ai_os.modelrouter.providers.nvidia.httpx.Client") as client_cls:
        client = _mock_client(response)
        client_cls.return_value = client
        provider.generate(ModelRequest(prompt="Question"))

    payload = client.post.call_args.kwargs["json"]
    assert all(message["role"] != "system" for message in payload["messages"])


def test_authentication_failure(provider: NvidiaProvider) -> None:
    response = MagicMock()
    response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "unauthorized", request=MagicMock(), response=MagicMock(status_code=401)
    )

    with patch("stanford_ai_os.modelrouter.providers.nvidia.httpx.Client") as client_cls:
        client = _mock_client(response)
        client_cls.return_value = client
        with pytest.raises(ProviderAuthenticationError):
            provider.generate(ModelRequest(prompt="Question"))


def test_rate_limit(provider: NvidiaProvider) -> None:
    response = MagicMock()
    response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "rate limited", request=MagicMock(), response=MagicMock(status_code=429)
    )

    with patch("stanford_ai_os.modelrouter.providers.nvidia.httpx.Client") as client_cls:
        client = _mock_client(response)
        client_cls.return_value = client
        with pytest.raises(ProviderRateLimitError):
            provider.generate(ModelRequest(prompt="Question"))


def test_other_http_failure(provider: NvidiaProvider) -> None:
    response = MagicMock()
    response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "server error", request=MagicMock(), response=MagicMock(status_code=500)
    )

    with patch("stanford_ai_os.modelrouter.providers.nvidia.httpx.Client") as client_cls:
        client = _mock_client(response)
        client_cls.return_value = client
        with pytest.raises(ProviderResponseError):
            provider.generate(ModelRequest(prompt="Question"))


def test_connection_failure(provider: NvidiaProvider) -> None:
    with patch("stanford_ai_os.modelrouter.providers.nvidia.httpx.Client") as client_cls:
        client = _mock_client(MagicMock())
        client.post.side_effect = httpx.ConnectError("connection failed")
        client_cls.return_value = client
        with pytest.raises(ProviderConnectionError):
            provider.generate(ModelRequest(prompt="Question"))


def test_timeout(provider: NvidiaProvider) -> None:
    with patch("stanford_ai_os.modelrouter.providers.nvidia.httpx.Client") as client_cls:
        client = _mock_client(MagicMock())
        client.post.side_effect = httpx.ReadTimeout("timed out")
        client_cls.return_value = client
        with pytest.raises(ProviderTimeoutError):
            provider.generate(ModelRequest(prompt="Question"))


def test_malformed_json(provider: NvidiaProvider) -> None:
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.side_effect = ValueError("bad json")

    with patch("stanford_ai_os.modelrouter.providers.nvidia.httpx.Client") as client_cls:
        client = _mock_client(response)
        client_cls.return_value = client
        with pytest.raises(ProviderResponseError):
            provider.generate(ModelRequest(prompt="Question"))


def test_missing_choices(provider: NvidiaProvider) -> None:
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"model": "test-model"}

    with patch("stanford_ai_os.modelrouter.providers.nvidia.httpx.Client") as client_cls:
        client = _mock_client(response)
        client_cls.return_value = client
        with pytest.raises(ProviderResponseError):
            provider.generate(ModelRequest(prompt="Question"))


def test_invalid_message(provider: NvidiaProvider) -> None:
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"choices": [{"message": {"content": 123}}]}

    with patch("stanford_ai_os.modelrouter.providers.nvidia.httpx.Client") as client_cls:
        client = _mock_client(response)
        client_cls.return_value = client
        with pytest.raises(ProviderResponseError):
            provider.generate(ModelRequest(prompt="Question"))


def test_configurable_timeout(provider: NvidiaProvider) -> None:
    response = MagicMock()
    response.json.return_value = {
        "choices": [{"message": {"content": "ok"}}],
        "model": "test-model",
    }
    response.raise_for_status.return_value = None

    with patch("stanford_ai_os.modelrouter.providers.nvidia.httpx.Client") as client_cls:
        client = _mock_client(response)
        client_cls.return_value = client
        provider.generate(ModelRequest(prompt="Question"))

    client_cls.assert_called_once_with(timeout=9.5)
