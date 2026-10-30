"""Schemas for persisted task execution history."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class TaskExecutionHistoryRead(BaseModel):
    """Read-only representation of a persisted execution attempt."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    task_id: UUID
    status: str
    provider: str | None
    model: str | None
    duration_ms: int | None
    error_category: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
