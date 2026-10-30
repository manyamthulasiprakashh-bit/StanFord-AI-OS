"""Schemas for task execution results."""

from uuid import UUID

from pydantic import BaseModel, Field

from stanford_ai_os.schemas.task_execution_history import (
    TaskExecutionHistoryRead,
)

__all__ = ["TaskExecutionResult", "TaskExecutionHistoryRead"]


class TaskExecutionResult(BaseModel):
    """Result of a single-pass task execution request."""

    task_id: UUID
    output: str
    provider: str
    model: str
    duration_ms: int = Field(ge=0)


