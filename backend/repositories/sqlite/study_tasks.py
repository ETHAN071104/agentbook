from __future__ import annotations

from typing import Any, cast
from uuid import uuid4

from backend.domain import (
    DEFAULT_WORKSPACE_ID,
    StudyTask,
    StudyTaskEvent,
    StudyTaskEventType,
    StudyTaskPriority,
    StudyTaskStatus,
)
from backend.repositories.interfaces import RepositoryConflictError
from backend.repositories.sqlite.foundation import initialize_foundation_schema


def _now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def _connection_scope():
    from backend.rag.database import get_connection

    return get_connection()


def _task(row: Any) -> StudyTask:
    return StudyTask(
        id=int(row["id"]),
        title=str(row["title"]),
        description=str(row["description"]),
        topic=str(row["topic"]),
        status=cast(StudyTaskStatus, str(row["status"])),
        priority=cast(StudyTaskPriority, str(row["priority"])),
        due_at=str(row["due_at"]) if row["due_at"] is not None else None,
        completed_at=(
            str(row["completed_at"])
            if row["completed_at"] is not None
            else None
        ),
        archived_at=(
            str(row["archived_at"])
            if row["archived_at"] is not None
            else None
        ),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
        version=int(row["version"]),
    )


def _event(row: Any) -> StudyTaskEvent:
    previous = row["previous_status"]
    return StudyTaskEvent(
        id=str(row["id"]),
        task_id=int(row["task_id"]),
        event_type=cast(StudyTaskEventType, str(row["event_type"])),
        previous_status=(
            cast(StudyTaskStatus, str(previous))
            if previous is not None
            else None
        ),
        new_status=cast(StudyTaskStatus, str(row["new_status"])),
        created_at=str(row["created_at"]),
    )


class SQLiteStudyTaskRepository:
    def __init__(self, workspace_id: str = DEFAULT_WORKSPACE_ID) -> None:
        self.workspace_id = workspace_id

    @staticmethod
    def _insert_event(
        connection: Any,
        *,
        workspace_id: str,
        task_id: int,
        event_type: StudyTaskEventType,
        previous_status: str | None,
        new_status: str,
        created_at: str,
    ) -> None:
        connection.execute(
            """
            INSERT INTO study_task_events (
                id, workspace_id, task_id, event_type,
                previous_status, new_status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid4()),
                workspace_id,
                task_id,
                event_type,
                previous_status,
                new_status,
                created_at,
            ),
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
        initialize_foundation_schema()
        with _connection_scope() as connection:
            existing = connection.execute(
                """
                SELECT * FROM study_tasks
                WHERE workspace_id = ? AND creation_idempotency_key = ?
                """,
                (self.workspace_id, idempotency_key),
            ).fetchone()
            if existing is not None:
                if str(existing["creation_fingerprint"]) != request_fingerprint:
                    raise RepositoryConflictError(
                        "The idempotency key was used for different task input."
                    )
                return _task(existing), False
            created_at = _now()
            cursor = connection.execute(
                """
                INSERT INTO study_tasks (
                    workspace_id, title, description, topic, status, priority,
                    due_at, completed_at, archived_at,
                    creation_idempotency_key, creation_fingerprint,
                    created_at, updated_at, version
                ) VALUES (?, ?, ?, ?, 'pending', ?, ?, NULL, NULL, ?, ?, ?, ?, 1)
                """,
                (
                    self.workspace_id,
                    title,
                    description,
                    topic,
                    priority,
                    due_at,
                    idempotency_key,
                    request_fingerprint,
                    created_at,
                    created_at,
                ),
            )
            task_id = int(cursor.lastrowid)
            self._insert_event(
                connection,
                workspace_id=self.workspace_id,
                task_id=task_id,
                event_type="study_task_created",
                previous_status=None,
                new_status="pending",
                created_at=created_at,
            )
            row = connection.execute(
                "SELECT * FROM study_tasks WHERE id = ? AND workspace_id = ?",
                (task_id, self.workspace_id),
            ).fetchone()
            assert row is not None
            return _task(row), True

    def get_task(self, task_id: int) -> StudyTask | None:
        initialize_foundation_schema()
        with _connection_scope() as connection:
            row = connection.execute(
                """
                SELECT * FROM study_tasks
                WHERE workspace_id = ? AND id = ?
                """,
                (self.workspace_id, int(task_id)),
            ).fetchone()
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
        initialize_foundation_schema()
        clauses = ["workspace_id = ?"]
        parameters: list[object] = [self.workspace_id]
        if status is not None:
            clauses.append("status = ?")
            parameters.append(status)
        elif not include_archived:
            clauses.append("status <> 'archived'")
        if due_before is not None:
            clauses.append("due_at IS NOT NULL AND due_at <= ?")
            parameters.append(due_before)
        if due_after is not None:
            clauses.append("due_at IS NOT NULL AND due_at >= ?")
            parameters.append(due_after)
        parameters.append(int(limit))
        sql = (
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
                id DESC
              LIMIT ?
            """
        )
        with _connection_scope() as connection:
            rows = connection.execute(sql, tuple(parameters)).fetchall()
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
        initialize_foundation_schema()
        with _connection_scope() as connection:
            row = connection.execute(
                """
                SELECT * FROM study_tasks
                WHERE workspace_id = ? AND id = ?
                """,
                (self.workspace_id, int(task_id)),
            ).fetchone()
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
            parameters: list[object | None] = []
            for column in ("title", "description", "topic", "priority", "due_at"):
                if column in values:
                    assignments.append(f"{column} = ?")
                    parameters.append(values[column])
            changed_at = _now()
            assignments.extend(["updated_at = ?", "version = version + 1"])
            parameters.extend([changed_at, self.workspace_id, int(task_id)])
            connection.execute(
                "UPDATE study_tasks SET "
                + ", ".join(assignments)
                + " WHERE workspace_id = ? AND id = ?",
                tuple(parameters),
            )
            self._insert_event(
                connection,
                workspace_id=self.workspace_id,
                task_id=int(task_id),
                event_type="study_task_updated",
                previous_status=current.status,
                new_status=current.status,
                created_at=changed_at,
            )
            updated = connection.execute(
                """
                SELECT * FROM study_tasks
                WHERE workspace_id = ? AND id = ?
                """,
                (self.workspace_id, int(task_id)),
            ).fetchone()
            assert updated is not None
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
        initialize_foundation_schema()
        with _connection_scope() as connection:
            row = connection.execute(
                """
                SELECT * FROM study_tasks
                WHERE workspace_id = ? AND id = ?
                """,
                (self.workspace_id, int(task_id)),
            ).fetchone()
            if row is None:
                return None, False
            current = _task(row)
            if current.status == target:
                return current, False
            if current.status not in allowed:
                raise RepositoryConflictError(
                    f"Cannot transition task from {current.status} to {target}."
                )
            changed_at = _now()
            completed_at = current.completed_at
            archived_at = current.archived_at
            if target == "completed":
                completed_at = changed_at
            elif target == "pending":
                completed_at = None
            if target == "archived":
                archived_at = changed_at
            connection.execute(
                """
                UPDATE study_tasks
                SET status = ?, completed_at = ?, archived_at = ?,
                    updated_at = ?, version = version + 1
                WHERE workspace_id = ? AND id = ? AND status = ?
                """,
                (
                    target,
                    completed_at,
                    archived_at,
                    changed_at,
                    self.workspace_id,
                    int(task_id),
                    current.status,
                ),
            )
            self._insert_event(
                connection,
                workspace_id=self.workspace_id,
                task_id=int(task_id),
                event_type=event_type,
                previous_status=current.status,
                new_status=target,
                created_at=changed_at,
            )
            updated = connection.execute(
                """
                SELECT * FROM study_tasks
                WHERE workspace_id = ? AND id = ?
                """,
                (self.workspace_id, int(task_id)),
            ).fetchone()
            assert updated is not None
            return _task(updated), True

    def list_events(self, task_id: int) -> list[StudyTaskEvent]:
        initialize_foundation_schema()
        with _connection_scope() as connection:
            rows = connection.execute(
                """
                SELECT event.id, event.task_id, event.event_type,
                       event.previous_status, event.new_status, event.created_at
                FROM study_task_events AS event
                JOIN study_tasks AS task
                  ON task.id = event.task_id
                 AND task.workspace_id = event.workspace_id
                WHERE event.workspace_id = ? AND task.id = ?
                ORDER BY event.created_at ASC, event.id ASC
                """,
                (self.workspace_id, int(task_id)),
            ).fetchall()
        return [_event(row) for row in rows]
