from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


StudyTaskStatus = Literal["pending", "completed", "cancelled", "archived"]
StudyTaskPriority = Literal["low", "normal", "high"]
StudyTaskEventType = Literal[
    "study_task_created",
    "study_task_updated",
    "study_task_completed",
    "study_task_reopened",
    "study_task_cancelled",
    "study_task_archived",
]

STUDY_TASK_STATUSES: frozenset[str] = frozenset(
    {"pending", "completed", "cancelled", "archived"}
)
STUDY_TASK_PRIORITIES: frozenset[str] = frozenset(
    {"low", "normal", "high"}
)


@dataclass(frozen=True)
class StudyTask:
    id: int
    title: str
    description: str
    topic: str
    status: StudyTaskStatus
    priority: StudyTaskPriority
    due_at: str | None
    completed_at: str | None
    archived_at: str | None
    created_at: str
    updated_at: str
    version: int


@dataclass(frozen=True)
class StudyTaskEvent:
    id: str
    task_id: int
    event_type: StudyTaskEventType
    previous_status: StudyTaskStatus | None
    new_status: StudyTaskStatus
    created_at: str
