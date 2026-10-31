"""Shared test configuration."""

import os

# Provide deterministic authentication configuration for the test suite. These
# values are test-only and are not secrets.
os.environ.setdefault("STANFORD_AI_OS_SECRET_KEY", "test-secret-key-at-least-32-characters")
os.environ.setdefault("STANFORD_AI_OS_ADMIN_USERNAME", "admin")
os.environ.setdefault("STANFORD_AI_OS_ADMIN_PASSWORD", "test-admin-password")


import pytest


@pytest.fixture(autouse=True)
def reset_login_rate_limits():
    from stanford_ai_os.db.session import dispose_shared_engine
    from stanford_ai_os.services.auth_service import (
        reset_execution_rate_limits,
        reset_login_rate_limits,
    )

    reset_login_rate_limits()
    reset_execution_rate_limits()
    yield
    reset_login_rate_limits()
    reset_execution_rate_limits()
    dispose_shared_engine()
