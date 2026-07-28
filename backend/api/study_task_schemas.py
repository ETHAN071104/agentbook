from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from backend.api.public_ids import PublicId
from backend.api.schemas import ApiModel


StudyTaskStatusValue = Literal["pending", "completed", "cancelled", "archived"]
StudyTaskPriorityValue = Literal["low", "normal", "high"]


class StudyTaskCreateRequest(ApiModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    topic: str = Field(default="", max_length=200)
    priority: StudyTaskPriorityValue = "normal"
    due_at: datetime | None = None


class StudyTaskUpdateRequest(ApiModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    topic: str | None = Field(default=None, max_length=200)
    priority: StudyTaskPriorityValue | None = None
    due_at: datetime | None = None


class StudyTaskResponse(ApiModel):
    id: PublicId
    title: str
    description: str
    topic: str
    status: StudyTaskStatusValue
    priority: StudyTaskPriorityValue
    due_at: str | None
    completed_at: str | None
    archived_at: str | None
    created_at: str
    updated_at: str


class StudyTaskListResponse(ApiModel):
    items: list[StudyTaskResponse]
    total: int = Field(ge=0)
