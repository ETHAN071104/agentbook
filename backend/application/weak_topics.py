from __future__ import annotations

from dataclasses import dataclass

from backend.application.dependencies import (
    ApplicationDependencies,
    get_application_dependencies,
)


MAX_WEAK_TOPICS = 5
MAX_RECENT_DAYS = 365


@dataclass(frozen=True)
class WeakTopic:
    topic: str
    weakness_score: float
    recent_incorrect_count: int
    skipped_count: int
    active_signal_evidence_count: int
    latest_observed_at: str
    source_document_ids: tuple[int, ...]
    evidence_summary: str
    recommended_next_action: str


def get_weak_topics(
    *,
    limit: int = 5,
    recent_days: int | None = 30,
    dependencies: ApplicationDependencies | None = None,
) -> list[WeakTopic]:
    """Return safe weakness summaries for the request-resolved workspace."""
    if not 1 <= limit <= MAX_WEAK_TOPICS:
        raise ValueError(
            f"Weak-topic limit must be between 1 and {MAX_WEAK_TOPICS}."
        )
    if (
        recent_days is not None
        and not 1 <= recent_days <= MAX_RECENT_DAYS
    ):
        raise ValueError(
            "Recent-history days must be between 1 and "
            f"{MAX_RECENT_DAYS}, or None."
        )

    resolved = dependencies or get_application_dependencies()
    if str(resolved.quizzes.workspace_id) != str(resolved.workspace_id):
        raise RuntimeError(
            "Quiz repository is not scoped to the resolved workspace."
        )

    rows = resolved.quizzes.list_weak_topics(
        limit=limit,
        recent_days=recent_days,
    )
    return [_weak_topic_from_row(row) for row in rows]


def _weak_topic_from_row(row: dict[str, object]) -> WeakTopic:
    topic = str(row["topic"]).strip()
    incorrect = int(row["incorrect_count"])
    skipped = int(row["skipped_count"])
    signal_count = int(row["active_signal_occurrences"])
    document_ids = tuple(
        sorted(
            {
                int(value)
                for value in row["source_document_public_ids"]
                if int(value) > 0
            }
        )
    )
    evidence_summary = (
        f"{incorrect} recent incorrect, {skipped} skipped, and "
        f"{signal_count} active knowledge-gap signal occurrences."
    )
    if skipped > incorrect:
        next_action = (
            "Review the cited source material, then retry a short quiz "
            "on this topic."
        )
    else:
        next_action = (
            "Review cited sources and complete a focused practice quiz "
            "on this topic."
        )
    return WeakTopic(
        topic=topic,
        weakness_score=round(float(row["weakness_score"]), 6),
        recent_incorrect_count=incorrect,
        skipped_count=skipped,
        active_signal_evidence_count=signal_count,
        latest_observed_at=str(row["last_observed_at"]),
        source_document_ids=document_ids,
        evidence_summary=evidence_summary,
        recommended_next_action=next_action,
    )
