from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Header, Path, Query, Response

from backend.api.errors import ApiError, map_exception
from backend.api.public_ids import PublicIdInput
from backend.api.study_task_schemas import (
    StudyTaskCreateRequest,
    StudyTaskListResponse,
    StudyTaskResponse,
    StudyTaskStatusValue,
    StudyTaskUpdateRequest,
)
from backend.application.study_tasks import (
    CreateStudyTaskCommand,
    StudyTaskConflictError,
    StudyTaskNotFoundError,
    StudyTaskService,
    StudyTaskValidationError,
    UpdateStudyTaskCommand,
)
from backend.domain import StudyTask


router = APIRouter(prefix="/api/study/tasks", tags=["study-tasks"])


def study_task_response(task: StudyTask) -> StudyTaskResponse:
    return StudyTaskResponse(
        id=task.id,
        title=task.title,
        description=task.description,
        topic=task.topic,
        status=task.status,
        priority=task.priority,
        due_at=task.due_at,
        completed_at=task.completed_at,
        archived_at=task.archived_at,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


def _raise_task_error(error: Exception) -> None:
    if isinstance(error, StudyTaskNotFoundError):
        raise ApiError(
            status_code=404,
            code="RESOURCE_NOT_FOUND",
            reason="Study task was not found.",
            next_action="Refresh the task list.",
            retryable=False,
        ) from error
    if isinstance(error, StudyTaskConflictError):
        raise ApiError(
            status_code=409,
            code="RESOURCE_CONFLICT",
            reason=str(error),
            next_action="Refresh the task and retry the action.",
            retryable=False,
        ) from error
    if isinstance(error, StudyTaskValidationError):
        raise ApiError(
            status_code=422,
            code="VALIDATION_ERROR",
            reason=str(error),
            next_action="Correct the task input and try again.",
            retryable=False,
        ) from error
    raise map_exception(
        error,
        fallback_code="INTERNAL_ERROR",
        context="study_tasks",
    ) from error


@router.post("", response_model=StudyTaskResponse, status_code=201)
def create_task(
    payload: StudyTaskCreateRequest,
    response: Response,
    idempotency_key: Annotated[
        str | None,
        Header(alias="Idempotency-Key", max_length=200),
    ] = None,
) -> StudyTaskResponse:
    if idempotency_key is None:
        raise ApiError(
            status_code=422,
            code="VALIDATION_ERROR",
            reason="An Idempotency-Key header is required.",
            next_action="Retry task creation with an operation key.",
            retryable=False,
        )
    try:
        task, created = StudyTaskService().create_task(
            CreateStudyTaskCommand(
                title=payload.title,
                description=payload.description,
                topic=payload.topic,
                priority=payload.priority,
                due_at=payload.due_at,
            ),
            idempotency_key=idempotency_key,
        )
        response.status_code = 201 if created else 200
        return study_task_response(task)
    except Exception as error:
        _raise_task_error(error)
        raise AssertionError("unreachable")


@router.get("", response_model=StudyTaskListResponse)
def list_tasks(
    status: Annotated[StudyTaskStatusValue | None, Query()] = None,
    due_before: Annotated[datetime | None, Query()] = None,
    due_after: Annotated[datetime | None, Query()] = None,
    include_archived: Annotated[bool, Query()] = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> StudyTaskListResponse:
    try:
        summary = StudyTaskService().list_tasks(
            status=status,
            due_before=due_before,
            due_after=due_after,
            include_archived=include_archived,
            limit=limit,
        )
        return StudyTaskListResponse(
            items=[study_task_response(task) for task in summary.items],
            total=summary.total,
        )
    except Exception as error:
        _raise_task_error(error)
        raise AssertionError("unreachable")


@router.get("/{task_id}", response_model=StudyTaskResponse)
def get_task(
    task_id: Annotated[PublicIdInput, Path()],
) -> StudyTaskResponse:
    try:
        return study_task_response(StudyTaskService().get_task(task_id))
    except Exception as error:
        _raise_task_error(error)
        raise AssertionError("unreachable")


@router.patch("/{task_id}", response_model=StudyTaskResponse)
def update_task(
    task_id: Annotated[PublicIdInput, Path()],
    payload: StudyTaskUpdateRequest,
) -> StudyTaskResponse:
    try:
        task = StudyTaskService().update_task(
            task_id,
            UpdateStudyTaskCommand(
                fields=frozenset(payload.model_fields_set),
                title=payload.title,
                description=payload.description,
                topic=payload.topic,
                priority=payload.priority,
                due_at=payload.due_at,
            ),
        )
        return study_task_response(task)
    except Exception as error:
        _raise_task_error(error)
        raise AssertionError("unreachable")


def _transition(task_id: int, operation: str) -> StudyTaskResponse:
    try:
        service = StudyTaskService()
        task = getattr(service, operation)(task_id)
        return study_task_response(task)
    except Exception as error:
        _raise_task_error(error)
        raise AssertionError("unreachable")


@router.post("/{task_id}/complete", response_model=StudyTaskResponse)
def complete_task(
    task_id: Annotated[PublicIdInput, Path()],
) -> StudyTaskResponse:
    return _transition(task_id, "complete_task")


@router.post("/{task_id}/reopen", response_model=StudyTaskResponse)
def reopen_task(
    task_id: Annotated[PublicIdInput, Path()],
) -> StudyTaskResponse:
    return _transition(task_id, "reopen_task")


@router.post("/{task_id}/cancel", response_model=StudyTaskResponse)
def cancel_task(
    task_id: Annotated[PublicIdInput, Path()],
) -> StudyTaskResponse:
    return _transition(task_id, "cancel_task")


@router.post("/{task_id}/archive", response_model=StudyTaskResponse)
def archive_task(
    task_id: Annotated[PublicIdInput, Path()],
) -> StudyTaskResponse:
    return _transition(task_id, "archive_task")
