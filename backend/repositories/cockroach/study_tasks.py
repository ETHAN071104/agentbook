from __future__ import annotations

from typing import Any, cast
from uuid import UUID

from sqlalchemy import text

from backend.domain import (
    DEFAULT_WORKSPACE_ID,
    StudyTask,
    StudyTaskEvent,
    StudyTaskEventType,
    StudyTaskPriority,
    StudyTaskStatus,
    new_record_id,
)
from backend.repositories.cockroach.connection import connection_scope
from backend.repositories.cockroach.helpers import iso, new_public_identity, utc_now
from backend.repositories.interfaces import RepositoryConflictError


def _task(row: Any) -> StudyTask:
    return StudyTask(
        id=int(row["public_id"]),
        title=str(row["title"]),
        description=str(row["description"]),
        topic=str(row["topic"]),
        status=cast(StudyTaskStatus, str(row["status"])),
        priority=cast(StudyTaskPriority, str(row["priority"])),
        due_at=iso(row["due_at"]) if row["due_at"] is not None else None,
        completed_at=(
            iso(row["completed_at"])
            if row["completed_at"] is not None
            else None
        ),
        archived_at=(
            iso(row["archived_at"])
            if row["archived_at"] is not None
            else None
        ),
        created_at=iso(row["created_at"]),
        updated_at=iso(row["updated_at"]),
        version=int(row["version"]),
    )


def _event(row: Any) -> StudyTaskEvent:
    previous = row["previous_status"]
    return StudyTaskEvent(
        id=str(row["id"]),
        task_id=int(row["task_public_id"]),
        event_type=cast(StudyTaskEventType, str(row["event_type"])),
        previous_status=(
            cast(StudyTaskStatus, str(previous))
            if previous is not None
            else None
        ),
        new_status=cast(StudyTaskStatus, str(row["new_status"])),
        created_at=iso(row["created_at"]),
    )


class CockroachStudyTaskRepository:
    def __init__(self, workspace_id: str = DEFAULT_WORKSPACE_ID) -> None:
        self.workspace_id = workspace_id

    @staticmethod
    def _insert_event(
        connection: Any,
        *,
        workspace_id: UUID,
        task_id: UUID,
        event_type: StudyTaskEventType,
        previous_status: str | None,
        new_status: str,
        created_at: Any,
    ) -> None:
        connection.execute(
            text(
                """
                INSERT INTO study_task_events (
                    id, workspace_id, task_id, event_type,
                    previous_status, new_status, created_at
                ) VALUES (
                    :id, :workspace_id, :task_id, :event_type,
                    :previous_status, :new_status, :created_at
                )
                """
            ),
            {
                "id": new_record_id(),
                "workspace_id": workspace_id,
                "task_id": task_id,
                "event_type": event_type,
                "previous_status": previous_status,
                "new_status": new_status,
                "created_at": created_at,
            },
        )

    def create_task(
        self,
        *,
        title: str,
        description: str,
        topic: str,
        priority: str,
        due_at: str | None,
        idempotency_key: str,
        request_fingerprint: str,
    ) -> tuple[StudyTask, bool]:
        workspace_id = UUID(self.workspace_id)
        record_id, public_id = new_public_identity()
        created_at = utc_now()
        with connection_scope() as connection:
            row = connection.execute(
                text(
                    """
                    INSERT INTO study_tasks (
                        id, workspace_id, public_id, title, description, topic,
                        status, priority, due_at, completed_at, archived_at,
                        creation_idempotency_key, creation_fingerprint,
                        created_at, updated_at, version
                    ) VALUES (
                        :id, :workspace_id, :public_id, :title, :description,
                        :topic, 'pending', :priority, :due_at, NULL, NULL,
                        :idempotency_key, :fingerprint, :created_at, :created_at, 1
                    )
                    ON CONFLICT (workspace_id, creation_idempotency_key)
                    DO NOTHING
                    RETURNING *
                    """
                ),
                {
                    "id": record_id,
                    "workspace_id": workspace_id,
                    "public_id": public_id,
                    "title": title,
                    "description": description,
                    "topic": topic,
                    "priority": priority,
                    "due_at": due_at,
                    "idempotency_key": idempotency_key,
                    "fingerprint": request_fingerprint,
                    "created_at": created_at,
                },
            ).mappings().one_or_none()
            created = row is not None
            if row is None:
                row = connection.execute(
                    text(
                        """
                        SELECT * FROM study_tasks
                        WHERE workspace_id = :workspace_id
                          AND creation_idempotency_key = :idempotency_key
                        FOR UPDATE
                        """
                    ),
                    {
                        "workspace_id": workspace_id,
                        "idempotency_key": idempotency_key,
                    },
                ).mappings().one()
                if str(row["creation_fingerprint"]) != request_fingerprint:
                    raise RepositoryConflictError(
                        "The idempotency key was used for different task input."
                    )
            else:
                self._insert_event(
                    connection,
                    workspace_id=workspace_id,
                    task_id=UUID(str(row["id"])),
                    event_type="study_task_created",
                    previous_status=None,
                    new_status="pending",
                    created_at=created_at,
                )
        return _task(row), created

    def get_task(self, task_id: int) -> StudyTask | None:
        with connection_scope() as connection:
            row = connection.execute(
                text(
                    """
                    SELECT * FROM study_tasks
                    WHERE workspace_id = :workspace_id
                      AND public_id = :public_id
                    """
                ),
                {
                    "workspace_id": UUID(self.workspace_id),
                    "public_id": int(task_id),
                },
            ).mappings().one_or_none()
        return _task(row) if row is not None else None

    def list_tasks(
        self,
        *,
        status: str | None,
        due_before: str | None,
        due_after: str | None,
        include_archived: bool,
        limit: int,
    ) -> list[StudyTask]:
        clauses = ["workspace_id = :workspace_id"]
        parameters: dict[str, object] = {
            "workspace_id": UUID(self.workspace_id),
            "limit": int(limit),
        }
        if status is not None:
            clauses.append("status = :status")
            parameters["status"] = status
        elif not include_archived:
            clauses.append("status <> 'archived'")
        if due_before is not None:
            clauses.append("due_at IS NOT NULL AND due_at <= :due_before")
            parameters["due_before"] = due_before
        if due_after is not None:
            clauses.append("due_at IS NOT NULL AND due_at >= :due_after")
            parameters["due_after"] = due_after
        statement = text(
            "SELECT * FROM study_tasks WHERE "
            + " AND ".join(clauses)
            + """
              ORDER BY
                CASE status
                    WHEN 'pending' THEN 0
                    WHEN 'completed' THEN 1
                    WHEN 'cancelled' THEN 2
                    ELSE 3
                END,
                CASE WHEN due_at IS NULL THEN 1 ELSE 0 END,
                due_at ASC,
                updated_at DESC,
                public_id DESC
              LIMIT :limit
            """
        )
        with connection_scope() as connection:
            rows = connection.execute(statement, parameters).mappings().all()
        return [_task(row) for row in rows]

    def update_task(
        self,
        task_id: int,
        *,
        title: str | None,
        description: str | None,
        topic: str | None,
        priority: str | None,
        due_at: str | None,
        due_at_provided: bool,
    ) -> tuple[StudyTask | None, bool]:
        workspace_id = UUID(self.workspace_id)
        with connection_scope() as connection:
            row = connection.execute(
                text(
                    """
                    SELECT * FROM study_tasks
                    WHERE workspace_id = :workspace_id
                      AND public_id = :public_id
                    FOR UPDATE
                    """
                ),
                {"workspace_id": workspace_id, "public_id": int(task_id)},
            ).mappings().one_or_none()
            if row is None:
                return None, False
            current = _task(row)
            if current.status == "archived":
                raise RepositoryConflictError("Archived tasks cannot be edited.")
            values: dict[str, object | None] = {}
            if title is not None and title != current.title:
                values["title"] = title
            if description is not None and description != current.description:
                values["description"] = description
            if topic is not None and topic != current.topic:
                values["topic"] = topic
            if priority is not None and priority != current.priority:
                values["priority"] = priority
            if due_at_provided and due_at != current.due_at:
                values["due_at"] = due_at
            if not values:
                return current, False
            assignments: list[str] = []
            parameters: dict[str, object | None] = {
                "workspace_id": workspace_id,
                "public_id": int(task_id),
                "updated_at": utc_now(),
            }
            for column in ("title", "description", "topic", "priority", "due_at"):
                if column in values:
                    assignments.append(f"{column} = :{column}")
                    parameters[column] = values[column]
            assignments.extend(
                ["updated_at = :updated_at", "version = version + 1"]
            )
            updated = connection.execute(
                text(
                    "UPDATE study_tasks SET "
                    + ", ".join(assignments)
                    + """
                      WHERE workspace_id = :workspace_id
                        AND public_id = :public_id
                      RETURNING *
                    """
                ),
                parameters,
            ).mappings().one()
            self._insert_event(
                connection,
                workspace_id=workspace_id,
                task_id=UUID(str(updated["id"])),
                event_type="study_task_updated",
                previous_status=current.status,
                new_status=current.status,
                created_at=parameters["updated_at"],
            )
        return _task(updated), True

    def complete_task(self, task_id: int) -> tuple[StudyTask | None, bool]:
        return self._transition(
            task_id,
            target="completed",
            allowed={"pending"},
            event_type="study_task_completed",
        )

    def reopen_task(self, task_id: int) -> tuple[StudyTask | None, bool]:
        return self._transition(
            task_id,
            target="pending",
            allowed={"completed", "cancelled"},
            event_type="study_task_reopened",
        )

    def cancel_task(self, task_id: int) -> tuple[StudyTask | None, bool]:
        return self._transition(
            task_id,
            target="cancelled",
            allowed={"pending"},
            event_type="study_task_cancelled",
        )

    def archive_task(self, task_id: int) -> tuple[StudyTask | None, bool]:
        return self._transition(
            task_id,
            target="archived",
            allowed={"pending", "completed", "cancelled"},
            event_type="study_task_archived",
        )

    def _transition(
        self,
        task_id: int,
        *,
        target: StudyTaskStatus,
        allowed: set[str],
        event_type: StudyTaskEventType,
    ) -> tuple[StudyTask | None, bool]:
        workspace_id = UUID(self.workspace_id)
        with connection_scope() as connection:
            row = connection.execute(
                text(
                    """
                    SELECT * FROM study_tasks
                    WHERE workspace_id = :workspace_id
                      AND public_id = :public_id
                    FOR UPDATE
                    """
                ),
                {"workspace_id": workspace_id, "public_id": int(task_id)},
            ).mappings().one_or_none()
            if row is None:
                return None, False
            current = _task(row)
            if current.status == target:
                return current, False
            if current.status not in allowed:
                raise RepositoryConflictError(
                    f"Cannot transition task from {current.status} to {target}."
                )
            changed_at = utc_now()
            completed_at: object | None = row["completed_at"]
            archived_at: object | None = row["archived_at"]
            if target == "completed":
                completed_at = changed_at
            elif target == "pending":
                completed_at = None
            if target == "archived":
                archived_at = changed_at
            updated = connection.execute(
                text(
                    """
                    UPDATE study_tasks
                    SET status = :target,
                        completed_at = :completed_at,
                        archived_at = :archived_at,
                        updated_at = :updated_at,
                        version = version + 1
                    WHERE workspace_id = :workspace_id
                      AND public_id = :public_id
                      AND status = :previous_status
                    RETURNING *
                    """
                ),
                {
                    "target": target,
                    "completed_at": completed_at,
                    "archived_at": archived_at,
                    "updated_at": changed_at,
                    "workspace_id": workspace_id,
                    "public_id": int(task_id),
                    "previous_status": current.status,
                },
            ).mappings().one()
            self._insert_event(
                connection,
                workspace_id=workspace_id,
                task_id=UUID(str(updated["id"])),
                event_type=event_type,
                previous_status=current.status,
                new_status=target,
                created_at=changed_at,
            )
        return _task(updated), True

    def list_events(self, task_id: int) -> list[StudyTaskEvent]:
        with connection_scope() as connection:
            rows = connection.execute(
                text(
                    """
                    SELECT event.id, task.public_id AS task_public_id,
                           event.event_type, event.previous_status,
                           event.new_status, event.created_at
                    FROM study_task_events AS event
                    JOIN study_tasks AS task
                      ON task.id = event.task_id
                     AND task.workspace_id = event.workspace_id
                    WHERE event.workspace_id = :workspace_id
                      AND task.public_id = :public_id
                    ORDER BY event.created_at ASC, event.id ASC
                    """
                ),
                {
                    "workspace_id": UUID(self.workspace_id),
                    "public_id": int(task_id),
                },
            ).mappings().all()
        return [_event(row) for row in rows]
