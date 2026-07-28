from __future__ import annotations

from typing import Any, Literal

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator


ToolName = Literal[
    "get_weak_topics",
    "get_recent_mistakes",
    "search_study_materials",
    "get_current_study_plan",
]
AnswerMode = Literal["general", "personalized"]
PlannerMode = Literal["answer_only", "read_only_tools", "propose_write"]
WriteAction = Literal["create_study_task", "complete_study_task"]
WriteRiskLevel = Literal["low"]
SuggestedUiAction = Literal[
    "open_weak_topics",
    "open_recent_quiz",
    "open_document",
    "open_study_plan",
    "start_quiz",
    "open_study_tasks",
    "none",
]

ALLOWED_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "get_weak_topics",
        "get_recent_mistakes",
        "search_study_materials",
        "get_current_study_plan",
    }
)


class AgentModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class WeakTopicsArguments(AgentModel):
    limit: int = Field(default=5, ge=1, le=5)
    recent_days: int | None = Field(default=30, ge=1, le=365)


class RecentMistakesArguments(AgentModel):
    limit: int = Field(default=5, ge=1, le=10)


class SearchStudyMaterialsArguments(AgentModel):
    query: str = Field(min_length=2, max_length=300)
    limit: int = Field(default=5, ge=1, le=5)


class CurrentStudyPlanArguments(AgentModel):
    available_minutes: int = Field(default=30, ge=10, le=240)
    max_items: int = Field(default=5, ge=1, le=5)


class CreateStudyTaskCandidate(AgentModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    topic: str = Field(default="", max_length=200)
    due_at: str | None = Field(default=None, max_length=80)
    priority: Literal["low", "normal", "high"] = "normal"


class CompleteStudyTaskCandidate(AgentModel):
    query: str = Field(min_length=1, max_length=200)


class ProposedToolCall(AgentModel):
    tool_name: str = Field(min_length=1, max_length=64)
    arguments: dict[str, Any] = Field(default_factory=dict)


class PlannerDecision(AgentModel):
    mode: PlannerMode
    selected_tools: list[ProposedToolCall] = Field(default_factory=list, max_length=4)
    proposed_action: str | None = Field(default=None, max_length=64)
    candidate_arguments: dict[str, Any] = Field(default_factory=dict)
    user_rationale: str = Field(default="", max_length=300)
    reasoning_summary: str = Field(default="", max_length=160)

    @field_validator("reasoning_summary")
    @classmethod
    def one_short_sentence(cls, value: str) -> str:
        if len(re.findall(r"[.!?](?:\s|$)", value)) > 1:
            raise ValueError("Reasoning summary must be at most one sentence.")
        return value


class ValidatedToolCall(AgentModel):
    tool_name: ToolName
    arguments: dict[str, Any]


class ValidatedPlan(AgentModel):
    mode: PlannerMode
    selected_tools: list[ValidatedToolCall] = Field(default_factory=list, max_length=4)
    proposed_action: WriteAction | None = None
    candidate_arguments: dict[str, Any] = Field(default_factory=dict)
    user_rationale: str = Field(default="", max_length=300)
    reasoning_summary: str = Field(default="", max_length=160)
    used_fallback: bool = False


class ToolResult(AgentModel):
    tool_name: ToolName
    success: bool
    data: dict[str, Any] = Field(default_factory=dict)
    safe_summary: str = Field(max_length=500)
    warning: str | None = Field(default=None, max_length=300)
    evidence_count: int = Field(ge=0)


class AgentEvidence(BaseModel):
    summary: tuple[str, ...] = ()
    related_document_public_ids: tuple[int, ...] = ()
    related_quiz_attempt_public_ids: tuple[int, ...] = ()
    weak_topics_used: tuple[str, ...] = ()


class AgentTaskPreview(AgentModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    topic: str = Field(default="", max_length=200)
    status: Literal["pending", "completed", "cancelled", "archived"]
    priority: Literal["low", "normal", "high"]
    due_at: str | None = None


class AgentWriteProposal(AgentModel):
    proposal_id: str = Field(pattern=r"^[a-f0-9-]{36}$")
    action: WriteAction
    display_title: str = Field(min_length=1, max_length=200)
    display_summary: str = Field(min_length=1, max_length=500)
    task_preview: AgentTaskPreview
    evidence_summary: str = Field(default="", max_length=500)
    expires_at: str
    confirmation_required: Literal[True] = True
    risk_level: WriteRiskLevel = "low"


class LearningAgentResult(BaseModel):
    answer: str
    tools_used: tuple[ToolName, ...] = ()
    evidence: AgentEvidence
    suggested_ui_action: SuggestedUiAction = "none"
    confirmation_required: bool = False
    proposal: AgentWriteProposal | None = None
