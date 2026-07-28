"""Add workspace-scoped persisted study tasks and lifecycle events."""

from alembic import op


revision = "0004_persisted_study_tasks"
down_revision = "0003_guest_sessions"
branch_labels = None
depends_on = None


UPGRADE_STATEMENTS = (
    """
    CREATE TABLE study_tasks (
        id UUID PRIMARY KEY,
        workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
        public_id INT8 NOT NULL,
        title STRING NOT NULL,
        description STRING NOT NULL DEFAULT '',
        topic STRING NOT NULL DEFAULT '',
        status STRING NOT NULL DEFAULT 'pending',
        priority STRING NOT NULL DEFAULT 'normal',
        due_at TIMESTAMPTZ,
        completed_at TIMESTAMPTZ,
        archived_at TIMESTAMPTZ,
        creation_idempotency_key STRING,
        creation_fingerprint STRING,
        created_at TIMESTAMPTZ NOT NULL,
        updated_at TIMESTAMPTZ NOT NULL,
        version INT8 NOT NULL DEFAULT 1,
        CONSTRAINT uq_study_tasks_workspace_public
            UNIQUE (workspace_id, public_id),
        CONSTRAINT uq_study_tasks_workspace_idempotency
            UNIQUE (workspace_id, creation_idempotency_key),
        CONSTRAINT uq_study_tasks_id_workspace
            UNIQUE (id, workspace_id),
        CONSTRAINT ck_study_tasks_title
            CHECK (length(trim(title)) > 0 AND length(title) <= 200),
        CONSTRAINT ck_study_tasks_description
            CHECK (length(description) <= 2000),
        CONSTRAINT ck_study_tasks_topic
            CHECK (length(topic) <= 200),
        CONSTRAINT ck_study_tasks_status
            CHECK (status IN ('pending', 'completed', 'cancelled', 'archived')),
        CONSTRAINT ck_study_tasks_priority
            CHECK (priority IN ('low', 'normal', 'high')),
        CONSTRAINT ck_study_tasks_version
            CHECK (version > 0),
        CONSTRAINT ck_study_tasks_updated_at
            CHECK (updated_at >= created_at),
        CONSTRAINT ck_study_tasks_completed
            CHECK (
                (status = 'completed' AND completed_at IS NOT NULL)
                OR
                (status = 'archived')
                OR
                (status IN ('pending', 'cancelled') AND completed_at IS NULL)
            ),
        CONSTRAINT ck_study_tasks_archived
            CHECK (
                (status = 'archived' AND archived_at IS NOT NULL)
                OR
                (status <> 'archived' AND archived_at IS NULL)
            ),
        CONSTRAINT ck_study_tasks_idempotency_pair
            CHECK (
                (creation_idempotency_key IS NULL
                    AND creation_fingerprint IS NULL)
                OR
                (creation_idempotency_key IS NOT NULL
                    AND length(creation_idempotency_key) BETWEEN 16 AND 200
                    AND creation_fingerprint IS NOT NULL
                    AND length(creation_fingerprint) = 64)
            )
    )
    """,
    """
    CREATE INDEX idx_study_tasks_workspace_status_due
    ON study_tasks (workspace_id, status, due_at, updated_at DESC)
    """,
    """
    CREATE INDEX idx_study_tasks_workspace_pending_due
    ON study_tasks (workspace_id, due_at, updated_at DESC)
    WHERE status = 'pending'
    """,
    """
    CREATE TABLE study_task_events (
        id UUID PRIMARY KEY,
        workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
        task_id UUID NOT NULL,
        event_type STRING NOT NULL,
        previous_status STRING,
        new_status STRING NOT NULL,
        created_at TIMESTAMPTZ NOT NULL,
        CONSTRAINT fk_study_task_events_owned_task
            FOREIGN KEY (task_id, workspace_id)
            REFERENCES study_tasks (id, workspace_id)
            ON DELETE CASCADE,
        CONSTRAINT ck_study_task_events_type
            CHECK (
                event_type IN (
                    'study_task_created',
                    'study_task_updated',
                    'study_task_completed',
                    'study_task_reopened',
                    'study_task_cancelled',
                    'study_task_archived'
                )
            ),
        CONSTRAINT ck_study_task_events_previous_status
            CHECK (
                previous_status IS NULL
                OR previous_status IN (
                    'pending', 'completed', 'cancelled', 'archived'
                )
            ),
        CONSTRAINT ck_study_task_events_new_status
            CHECK (
                new_status IN (
                    'pending', 'completed', 'cancelled', 'archived'
                )
            )
    )
    """,
    """
    CREATE INDEX idx_study_task_events_workspace_task
    ON study_task_events (workspace_id, task_id, created_at DESC)
    """,
)


def upgrade() -> None:
    for statement in UPGRADE_STATEMENTS:
        op.execute(statement)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS study_task_events")
    op.execute("DROP TABLE IF EXISTS study_tasks")
