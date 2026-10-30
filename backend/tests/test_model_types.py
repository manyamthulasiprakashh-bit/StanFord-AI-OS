"""Tests for provider-neutral model types."""

import pytest
from pydantic import ValidationError

from stanford_ai_os.modelrouter.types import ModelRequest, ModelResponse


def test_model_request_requires_prompt() -> None:
    with pytest.raises(ValidationError):
        ModelRequest(prompt="")


def test_model_request_defaults() -> None:
    request = ModelRequest(prompt="Hello")
    assert request.system is None
    assert request.model is None


def test_model_request_accepts_optional_fields() -> None:
    request = ModelRequest(prompt="Hello", system="Be concise", model="qwen3:4b")
    assert request.system == "Be concise"
    assert request.model == "qwen3:4b"


def test_model_response_requires_fields() -> None:
    response = ModelResponse(text="Hi", provider="ollama", model="qwen3:4b")
    assert response.text == "Hi"
    assert response.provider == "ollama"
    assert response.model == "qwen3:4b"
