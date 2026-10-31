"""Stanford-AI OS backend configuration."""

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings.

    Values can be overridden with environment variables prefixed with
    ``STANFORD_AI_OS_`` (for example ``STANFORD_AI_OS_ENVIRONMENT=production``).
    """

    model_config = SettingsConfigDict(
        env_prefix="STANFORD_AI_OS_",
        env_file=".env",
        extra="ignore",
        protected_namespaces=(),
    )

    app_name: str = "Stanford-AI OS"
    environment: str = "development"
    database_url: str = "sqlite:///./stanford_ai_os.db"

    model_provider: str = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:4b"

    nvidia_api_key: SecretStr | None = None
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"
    nvidia_model: str = "meta/llama-3.3-70b-instruct"
    model_timeout_seconds: float = Field(default=60.0, gt=0)

    secret_key: str | None = None
    admin_username: str = "admin"
    admin_password: str | None = None
    access_token_expire_minutes: int = Field(default=60, gt=0)
    login_rate_limit_attempts: int = Field(default=5, ge=1)
    login_rate_limit_window_seconds: int = Field(default=300, gt=0)

    execution_rate_limit_attempts: int = Field(default=10, ge=1)
    execution_rate_limit_window_seconds: int = Field(default=60, gt=0)

    cors_allowed_origins: str = ""


def get_settings() -> Settings:
    """Return a settings instance.

    A new instance is created on each call. This keeps configuration simple and
    ensures tests can change values through environment variables.
    """

    return Settings()
