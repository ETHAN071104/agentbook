from __future__ import annotations

import hashlib
import json
import re

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TypeVar

from backend.application.dependencies import (
    ApplicationDependencies,
    get_application_dependencies,
)
from backend.domain import (
    STUDY_TASK_PRIORITIES,
    STUDY_TASK_STATUSES,
    StudyTask,
    StudyTaskPriority,
    StudyTaskStatus,
)
from backend.repositories.interfaces import RepositoryConflictError


MAX_TASK_TITLE = 200
MAX_TASK_DESCRIPTION = 2000
MAX_TASK_TOPIC = 200
MAX_TASK_LIST = 100
IDEMPOTENCY_KEY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{15,199}$")
T = TypeVar("T")


class StudyTaskError(RuntimeError):
    pass


class StudyTaskNotFoundError(StudyTaskError):
    pass


class StudyTaskConflictError(StudyTaskError):
    pass


class StudyTaskValidationError(StudyTaskError):
    pass


@dataclass(frozen=True)
class CreateStudyTaskCommand:
    title: str
    description: str = ""
    topic: str = ""
    priority: StudyTaskPriority = "normal"
    due_at: str | datetime | None = None


@dataclass(frozen=True)
class UpdateStudyTaskCommand:
    fields: frozenset[str]
    title: str | None = None
    description: str | None = None
    topic: str | None = None
    priority: StudyTaskPriority | None = None
    due_at: str | datetime | None = None


@dataclass(frozen=True)
class StudyTaskSummary:
    items: tuple[StudyTask, ...]
    total: int


def _clean_required(value: object, *, label: str, maximum: int) -> str:
    cleaned = str(value).strip()
    if not cleaned:
        raise StudyTaskValidationError(f"{label} is required.")
    if len(cleaned) > maximum:
        raise StudyTaskValidationError(
            f"{label} must contain at most {maximum} characters."
        )
    return cleaned


def _clean_optional(
    value: object | None,
    *,
    label: str,
    maximum: int,
) -> str:
    cleaned = "" if value is None else str(value).strip()
    if len(cleaned) > maximum:
        raise StudyTaskValidationError(
            f"{label} must contain at most {maximum} characters."
        )
    return cleaned


def normalize_task_timestamp(value: str | datetime | None) -> str | None:
    if value is None:
        return None
    try:
        parsed = (
            value
            if isinstance(value, datetime)
            else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        )
    except (TypeError, ValueError) as error:
        raise StudyTaskValidationError(
            "Task timestamps must use a valid ISO 8601 value."
        ) from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise StudyTaskValidationError(
            "Task timestamps must include a timezone."
        )
    return parsed.astimezone(timezone.utc).isoformat()


def _fingerprint(
    *,
    title: str,
    description: str,
    topic: str,
    priority: str,
    due_at: str | None,
) -> str:
    canonical = json.dumps(
        {
            "description": description,
            "due_at": due_at,
            "priority": priority,
            "title": title,
            "topic": topic,
        },
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class StudyTaskService:
    def __init__(
        self,
        dependencies: ApplicationDependencies | None = None,
    ) -> None:
        self.dependencies = dependencies or get_application_dependencies()
        self.repository = self.dependencies.study_tasks
        if str(self.repository.workspace_id) != str(self.dependencies.workspace_id):
            raise RuntimeError(
                "Study Task repository scope does not match the "
                "authenticated workspace."
            )

    def _run_mutation(self, operation: Callable[[], T]) -> T:
        return self.dependencies.unit_of_work().run(
            lambda _unit_of_work: operation()
        )

    def create_task(
        self,
        command: CreateStudyTaskCommand,
        *,
        idempotency_key: str,
    ) -> tuple[StudyTask, bool]:
        cleaned_key = idempotency_key.strip()
        if not IDEMPOTENCY_KEY_PATTERN.fullmatch(cleaned_key):
            raise StudyTaskValidationError(
                "Idempotency-Key must contain 16 to 200 safe characters."
            )
        prepared = self.prepare_create_task(command)
        fingerprint = _fingerprint(
            title=prepared.title,
            description=prepared.description,
            topic=prepared.topic,
            priority=prepared.priority,
            due_at=prepared.due_at if isinstance(prepared.due_at, str) else None,
        )
        try:
            return self._run_mutation(
                lambda: self.repository.create_task(
                    title=prepared.title,
                    description=prepared.description,
                    topic=prepared.topic,
                    priority=prepared.priority,
                    due_at=(
                        prepared.due_at
                        if isinstance(prepared.due_at, str)
                        else None
                    ),
                    idempotency_key=cleaned_key,
                    request_fingerprint=fingerprint,
                )
            )
        except RepositoryConflictError as error:
            raise StudyTaskConflictError(
                "The idempotency key was already used for different task input."
            ) from error

    def prepare_create_task(
        self,
        command: CreateStudyTaskCommand,
    ) -> CreateStudyTaskCommand:
        """Normalize and validate task input without performing a write."""
        title = _clean_required(
            command.title,
            label="Task title",
            maximum=MAX_TASK_TITLE,
        )
        description = _clean_optional(
            command.description,
            label="Task description",
            maximum=MAX_TASK_DESCRIPTION,
        )
        topic = _clean_optional(
            command.topic,
            label="Task topic",
            maximum=MAX_TASK_TOPIC,
        )
        priority = str(command.priority).strip().lower()
        if priority not in STUDY_TASK_PRIORITIES:
            raise StudyTaskValidationError("Task priority is invalid.")
        due_at = normalize_task_timestamp(command.due_at)
        return CreateStudyTaskCommand(
            title=title,
            description=description,
            topic=topic,
            priority=priority,
            due_at=due_at,
        )

    def get_task(self, task_id: int) -> StudyTask:
        task = self.repository.get_task(task_id)
        if task is None:
            raise StudyTaskNotFoundError("Study task was not found.")
        return task

    def list_tasks(
        self,
        *,
        status: StudyTaskStatus | None = None,
        due_before: str | datetime | None = None,
        due_after: str | datetime | None = None,
        include_archived: bool = False,
        limit: int = 50,
    ) -> StudyTaskSummary:
        if status is not None and status not in STUDY_TASK_STATUSES:
            raise StudyTaskValidationError("Task status filter is invalid.")
        if not 1 <= limit <= MAX_TASK_LIST:
            raise StudyTaskValidationError(
                f"Task list limit must be between 1 and {MAX_TASK_LIST}."
            )
        before = normalize_task_timestamp(due_before)
        after = normalize_task_timestamp(due_after)
        if before is not None and after is not None and after > before:
            raise StudyTaskValidationError(
                "due_after must not be later than due_before."
            )
        items = self.repository.list_tasks(
            status=status,
            due_before=before,
            due_after=after,
            include_archived=include_archived or status == "archived",
            limit=limit,
        )
        return StudyTaskSummary(items=tuple(items), total=len(items))

    def update_task(
        self,
        task_id: int,
        command: UpdateStudyTaskCommand,
    ) -> StudyTask:
        allowed = {"title", "description", "topic", "priority", "due_at"}
        if not command.fields or not command.fields <= allowed:
            raise StudyTaskValidationError(
                "Provide at least one supported task field to update."
            )
        title = None
        if "title" in command.fields:
            if command.title is None:
                raise StudyTaskValidationError("Task title cannot be null.")
            title = _clean_required(
                command.title,
                label="Task title",
                maximum=MAX_TASK_TITLE,
            )
        description = (
            _clean_optional(
                command.description,
                label="Task description",
                maximum=MAX_TASK_DESCRIPTION,
            )
            if "description" in command.fields
            else None
        )
        topic = (
            _clean_optional(
                command.topic,
                label="Task topic",
                maximum=MAX_TASK_TOPIC,
            )
            if "topic" in command.fields
            else None
        )
        priority: str | None = None
        if "priority" in command.fields:
            if command.priority is None:
                raise StudyTaskValidationError("Task priority cannot be null.")
            priority = str(command.priority).strip().lower()
            if priority not in STUDY_TASK_PRIORITIES:
                raise StudyTaskValidationError("Task priority is invalid.")
        due_at = (
            normalize_task_timestamp(command.due_at)
            if "due_at" in command.fields
            else None
        )
        try:
            task, _changed = self._run_mutation(
                lambda: self.repository.update_task(
                    task_id,
                    title=title,
                    description=description,
                    topic=topic,
                    priority=priority,
                    due_at=due_at,
                    due_at_provided="due_at" in command.fields,
                )
            )
        except RepositoryConflictError as error:
            raise StudyTaskConflictError(
                "Archived tasks cannot be edited."
            ) from error
        if task is None:
            raise StudyTaskNotFoundError("Study task was not found.")
        return task

    def complete_task(self, task_id: int) -> StudyTask:
        return self._transition("complete_task", task_id)

    def reopen_task(self, task_id: int) -> StudyTask:
        return self._transition("reopen_task", task_id)

    def cancel_task(self, task_id: int) -> StudyTask:
        return self._transition("cancel_task", task_id)

    def archive_task(self, task_id: int) -> StudyTask:
        return self._transition("archive_task", task_id)

    def _transition(self, operation: str, task_id: int) -> StudyTask:
        method = getattr(self.repository, operation)
        try:
            task, _changed = self._run_mutation(lambda: method(task_id))
        except RepositoryConflictError as error:
            raise StudyTaskConflictError(
                "The requested task status transition is not allowed."
            ) from error
        if task is None:
            raise StudyTaskNotFoundError("Study task was not found.")
        return task
