from __future__ import annotations

from typing import Literal

from pydantic import Field

from backend.api.public_ids import PublicId
from backend.api.schemas import ApiModel
from backend.api.study_task_schemas import (
    StudyTaskPriorityValue,
    StudyTaskResponse,
    StudyTaskStatusValue,
)


AgentToolName = Literal[
    "get_weak_topics",
    "get_recent_mistakes",
    "search_study_materials",
    "get_current_study_plan",
]
AgentSuggestedUiAction = Literal[
    "open_weak_topics",
    "open_recent_quiz",
    "open_document",
    "open_study_plan",
    "start_quiz",
    "open_study_tasks",
    "none",
]
AgentWriteAction = Literal["create_study_task", "complete_study_task"]


class AgentQueryRequest(ApiModel):
    message: str = Field(min_length=1, max_length=2000)


class AgentEvidenceResponse(ApiModel):
    summary: list[str] = Field(default_factory=list)
    related_document_public_ids: list[PublicId] = Field(default_factory=list)
    related_quiz_attempt_public_ids: list[PublicId] = Field(default_factory=list)
    weak_topics_used: list[str] = Field(default_factory=list)


class AgentTaskPreviewResponse(ApiModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    topic: str = Field(default="", max_length=200)
    status: StudyTaskStatusValue
    priority: StudyTaskPriorityValue
    due_at: str | None = None


class AgentWriteProposalResponse(ApiModel):
    proposal_id: str = Field(pattern=r"^[a-f0-9-]{36}$")
    action: AgentWriteAction
    display_title: str = Field(min_length=1, max_length=200)
    display_summary: str = Field(min_length=1, max_length=500)
    task_preview: AgentTaskPreviewResponse
    evidence_summary: str = Field(default="", max_length=500)
    expires_at: str
    confirmation_required: Literal[True] = True
    risk_level: Literal["low"] = "low"


class AgentQueryResponse(ApiModel):
    answer: str = Field(min_length=1, max_length=3000)
    tools_used: list[AgentToolName] = Field(default_factory=list, max_length=4)
    evidence: AgentEvidenceResponse
    suggested_ui_action: AgentSuggestedUiAction
    confirmation_required: bool = False
    proposal: AgentWriteProposalResponse | None = None


class AgentActionConfirmationRequest(ApiModel):
    confirm: Literal[True]


class AgentActionConfirmationResponse(ApiModel):
    executed: Literal[True]
    action: AgentWriteAction
    task: StudyTaskResponse
    message: str = Field(min_length=1, max_length=500)
    suggested_ui_action: Literal["open_study_tasks"] = "open_study_tasks"
