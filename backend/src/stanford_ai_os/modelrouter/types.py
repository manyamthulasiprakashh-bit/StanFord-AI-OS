"""Provider-neutral model request and response types."""

from pydantic import BaseModel, Field


class ModelRequest(BaseModel):
    """A request to generate text from a language model."""

    prompt: str = Field(min_length=1)
    system: str | None = None
    model: str | None = None


class ModelResponse(BaseModel):
    """A normalized response from a language model provider."""

    text: str
    provider: str
    model: str
