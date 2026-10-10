"""Typed tool contracts (PRD sections 8 and 14).

Every tool has an ``*Input`` and ``*Output`` model. Field names follow the PRD exactly so
agents can rely on them; additional fields are additive. These models are the single source
of truth for the MCP tool signatures, the REST API and the exported JSON Schemas.
"""
from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Score = Annotated[float, Field(ge=0.0, le=1.0)]

RiskLevel = Literal["low", "medium", "high", "critical"]
UrgencyLevel = Literal["low", "medium", "high", "critical"]
JourneyStage = Literal["exploring", "deciding", "executing", "following_up", "recovering"]
StrategyMode = Literal["clarify_first", "act", "act_with_confirmation", "reflect", "escalate"]
ActionType = Literal[
    "clarify", "draft", "plan", "research", "schedule", "communicate", "decide",
    "reflect", "recall", "escalate", "summarize", "explain",
]


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class _Out(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ToolInput(_In):
    trace_id: str | None = Field(
        default=None, pattern=r"^[A-Za-z0-9._:\-]{1,128}$",
        description="Caller trace ID to correlate a multi-step workflow; generated if omitted.")
    session_id: str | None = Field(
        default=None, pattern=r"^[A-Za-z0-9._:\-]{1,128}$",
        description="Shared session for multi-agent orchestration; results are published to "
                    "get_shared_context under this ID.")


# --------------------------------------------------------------------------- shared parts

class Evidence(_Out):
    source: str = Field(description="Where the signal came from, e.g. user_message, "
                                    "conversation_context, memory:mem_..., known_preferences")
    quote: str = Field(description="Matched phrase or snippet (PII redacted)")


class Signal(_Out):
    name: str
    score: Score
    evidence: list[str] = Field(default_factory=list)


class Epistemics(_Out):
    """Separates facts, assumptions, inferences and recommendations (PRD 9.2)."""
    facts: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    inferences: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class MemoryUse(_Out):
    ref: str
    status: Literal["resolved", "missing", "expired", "out_of_scope"]
    confidence: Score
    age_days: float | None = None


# --------------------------------------------------------------------------- 8.1 mirror

class MirrorUserIntentInput(ToolInput):
    user_message: str = Field(min_length=1, max_length=20000,
                              description="Raw user request as received by the agent")
    conversation_context: list[str] = Field(
        default_factory=list, max_length=50,
        description="Recent conversation turns (short-term context only)")
    available_memory_refs: list[str] = Field(
        default_factory=list, max_length=50,
        description="Opaque memory references (mem_...) instead of raw sensitive data")
    agent_goal: str | None = Field(default=None, max_length=2000,
                                   description="What the calling agent is trying to accomplish")
    subject_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9._:\-]{1,128}$",
                                   description="User/subject that owns the memory refs")


class IntentLabel(_Out):
    label: str
    confidence: Score
    evidence: list[str] = Field(default_factory=list)


class Constraint(_Out):
    type: Literal["time", "budget", "scope", "quality", "format", "policy", "resource"]
    text: str


class Urgency(_Out):
    level: UrgencyLevel
    score: Score
    signals: list[str] = Field(default_factory=list)
    deadline_text: str | None = None


class Ambiguity(_Out):
    issue: str
    clarification_question: str
    blocking: bool = Field(description="True if acting without an answer is likely wrong")


class Conflict(_Out):
    between: list[str] = Field(min_length=2, max_length=2)
    description: str
    resolution_hint: str


class BusinessOutcome(_Out):
    outcome: str
    metric: str


class ResponseStrategy(_Out):
    mode: StrategyMode
    rationale: str
    steps: list[str]


class MirrorUserIntentOutput(_Out):
    primary_intent: IntentLabel
    secondary_intents: list[IntentLabel]
    explicit_goals: list[str]
    implicit_goals: list[str]
    constraints: list[Constraint]
    urgency: Urgency
    ambiguities: list[Ambiguity]
    conflicts: list[Conflict]
    decision_style: str | None
    preferred_tone: str | None
    risk_tolerance: Literal["low", "medium", "high", "unknown"]
    working_preferences: list[str]
    desired_output: str
    mirror_summary: str
    business_outcomes: list[BusinessOutcome]
    reflection_prompts: list[str]
    recommended_agent_response_strategy: ResponseStrategy
    memory_used: list[MemoryUse]
    confidence: Score


# --------------------------------------------------------------------------- 8.2 jev

class Subject(_In):
    id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9._:\-]{1,128}$")
    type: Literal["user", "stakeholder", "scenario", "workflow"] = "user"
    role: str | None = Field(default=None, max_length=200)
    name: str | None = Field(default=None, max_length=200)


class BuildJevProfileInput(ToolInput):
    subject: Subject = Field(default_factory=Subject)
    context: str = Field(default="", max_length=20000)
    known_preferences: dict[str, str] = Field(default_factory=dict, max_length=50)
    recent_interactions: list[str] = Field(default_factory=list, max_length=50)
    memory_refs: list[str] = Field(default_factory=list, max_length=50)
    persist: bool = Field(default=False, description="Store the profile as durable memory")
    consent: bool = Field(default=False, description="Explicit consent to persist the profile")


class PersonaSignals(_Out):
    role: str | None
    expertise_level: Literal["novice", "intermediate", "expert", "unknown"]
    goals: list[str]
    communication_preference: Literal["concise", "detailed", "formal", "casual", "unknown"]
    current_context: str


class JourneyStageResult(_Out):
    stage: JourneyStage
    confidence: Score
    evidence: list[str]


class JudgmentContext(_Out):
    judgment_need: str
    key_questions: list[str]
    options_hint: list[str]
    risks: list[str]
    recommended_next_steps: list[str]
    stakeholder_impact: list[str]


class BuildJevProfileOutput(_Out):
    persona_signals: PersonaSignals
    journey_stage: JourneyStageResult
    emotion_signals: list[Signal]
    value_drivers: list[Signal]
    judgment_context: JudgmentContext
    autonomy_safeguards: list[str]
    ignored_sensitive_attributes: list[str]
    memory_used: list[MemoryUse]
    profile_ref: str | None
    confidence: Score


# --------------------------------------------------------------------------- 8.3 next action

class RecommendNextActionInput(ToolInput):
    intent_summary: str | dict[str, Any] = Field(
        default="", description="Text summary or the result of mirror_user_intent")
    jev_profile: dict[str, Any] | None = Field(
        default=None, description="Result of build_jev_profile, if available")
    business_goal: str | None = Field(default=None, max_length=2000)
    risk_level: RiskLevel | None = None
    available_tools: list[str] = Field(default_factory=list, max_length=100)
    guardrail_result: dict[str, Any] | None = Field(
        default=None, description="Result of check_guardrails for the planned workflow")


class Action(_Out):
    action: str
    type: ActionType
    tool: str | None
    description: str


class ImpactSummary(_Out):
    category: str
    summary: str
    metric: str


class RecommendNextActionOutput(_Out):
    recommended_action: Action
    alternative_actions: list[Action]
    business_impact: ImpactSummary
    risks: list[str]
    human_approval_required: bool
    approval_reason: str | None
    agent_instruction: str


# --------------------------------------------------------------------------- 8.4 decision

class FrameDecisionInput(ToolInput):
    decision_question: str = Field(min_length=1, max_length=5000)
    context: str = Field(default="", max_length=20000)
    constraints: list[str] = Field(default_factory=list, max_length=30)
    success_metrics: list[str] = Field(default_factory=list, max_length=30)
    options: list[str] = Field(default_factory=list, max_length=10,
                               description="Candidate options, if the caller already has them")


class Criterion(_Out):
    name: str
    weight: Score
    source: Literal["success_metric", "constraint", "default"]


class DecisionFrame(_Out):
    question: str
    decision_type: Literal["binary", "selection", "timing", "resource_allocation"]
    reversibility: Literal["reversible", "hard_to_reverse"]
    stakes: Literal["low", "medium", "high"]
    criteria: list[Criterion]
    constraints: list[str]


class DecisionOption(_Out):
    id: str
    name: str
    description: str
    scores: dict[str, float]
    total_score: Score
    pros: list[str]
    cons: list[str]


class Tradeoff(_Out):
    between: list[str] = Field(min_length=2, max_length=2)
    description: str


class RiskEntry(_Out):
    risk: str
    option_id: str | None
    likelihood: Literal["low", "medium", "high"]
    impact: Literal["low", "medium", "high"]
    mitigation: str


class FrameDecisionOutput(_Out):
    decision_frame: DecisionFrame
    options: list[DecisionOption]
    tradeoffs: list[Tradeoff]
    risk_register: list[RiskEntry]
    recommended_option: str
    rationale: str


# --------------------------------------------------------------------------- 8.5 impact

class AssessBusinessImpactInput(ToolInput):
    request: str = Field(min_length=1, max_length=10000)
    target_workflow: str | None = Field(default=None, max_length=500)
    stakeholders: list[str] = Field(default_factory=list, max_length=50)
    baseline: dict[str, float | str] = Field(
        default_factory=dict, max_length=30,
        description="Known baseline values, e.g. {'hours_per_week': 6}")


class ImpactMetric(_Out):
    metric: str
    baseline: float | str | None
    expected_delta: str
    target: float | None
    confidence: Score
    evidence: str


class CostOrEffort(_Out):
    level: Literal["low", "medium", "high"]
    estimate: str
    drivers: list[str]


class StakeholderImpact(_Out):
    stakeholder: str
    impact: str


class AssessBusinessImpactOutput(_Out):
    impact_category: str
    secondary_categories: list[str]
    expected_benefits: list[str]
    metrics: list[ImpactMetric]
    cost_or_effort: CostOrEffort
    roi_hypothesis: str
    priority_score: int = Field(ge=0, le=100)
    stakeholder_impact: list[StakeholderImpact]


# --------------------------------------------------------------------------- 8.6 guardrails

class CheckGuardrailsInput(ToolInput):
    planned_action: str = Field(min_length=1, max_length=10000)
    data_used: list[str] = Field(default_factory=list, max_length=100,
                                 description="Data items or labels the action will use")
    user_context: dict[str, Any] = Field(
        default_factory=dict,
        description="e.g. {'consent': {'share_externally': false}, 'jurisdiction': 'CA'}")
    policy_profile: str | None = Field(default=None, pattern=r"^[a-z_]{1,40}$",
                                       description="default | strict | enterprise")


class GuardrailIssue(_Out):
    code: str
    category: str
    severity: RiskLevel
    description: str
    policy_reason: str


class Redaction(_Out):
    type: str
    location: str
    placeholder: str
    masked_preview: str


class CheckGuardrailsOutput(_Out):
    allowed: bool
    risk_level: RiskLevel
    issues: list[GuardrailIssue]
    required_redactions: list[Redaction]
    human_approval_required: bool
    approval_reasons: list[str]
    safe_alternative: str | None
    policy_profile: str
    redacted_action: str


# --------------------------------------------------------------------------- memory & support

class MemoryStoreInput(ToolInput):
    subject_id: str = Field(pattern=r"^[A-Za-z0-9._:\-]{1,128}$")
    content: str = Field(min_length=1, max_length=10000)
    kind: Literal["context", "profile"] = Field(
        default="context", description="context = short-term; profile = durable preference")
    consent: bool = Field(default=False, description="Must be true to store anything")
    ttl_days: int | None = Field(default=None, ge=1, le=3650)
    tags: list[str] = Field(default_factory=list, max_length=20)


class MemoryStoreOutput(_Out):
    stored: bool
    memory_ref: str | None
    kind: str
    expires_at: str | None
    redactions: list[str]
    reason: str | None


class MemoryRecallInput(ToolInput):
    subject_id: str = Field(pattern=r"^[A-Za-z0-9._:\-]{1,128}$")
    query: str = Field(default="", max_length=2000)
    refs: list[str] = Field(default_factory=list, max_length=50)
    kind: Literal["context", "profile", "any"] = "any"
    limit: int = Field(default=10, ge=1, le=100)


class MemoryItem(_Out):
    ref: str
    kind: str
    content: str
    tags: list[str]
    created_at: str
    expires_at: str
    age_days: float
    confidence: Score
    relevance: Score


class MemoryRecallOutput(_Out):
    items: list[MemoryItem]
    missing_refs: list[str]
    coverage_confidence: Score
    note: str


class MemoryForgetInput(ToolInput):
    subject_id: str = Field(pattern=r"^[A-Za-z0-9._:\-]{1,128}$")
    ref: str | None = Field(default=None, description="Omit to forget everything for subject "
                                                      "(admin role required)")


class MemoryForgetOutput(_Out):
    deleted: int
    subject_id: str


class GetSharedContextInput(ToolInput):
    pass


class SharedEntry(_Out):
    tool: str
    request_id: str
    trace_id: str
    caller_role: str
    agent_id: str | None
    created_at: str
    result: dict[str, Any]


class GetSharedContextOutput(_Out):
    session_id: str | None
    entries: list[SharedEntry]
    latest_by_tool: dict[str, dict[str, Any]]


class RecordFeedbackInput(ToolInput):
    request_id: str = Field(pattern=r"^req_[0-9a-f]{32}$")
    rating: int = Field(ge=1, le=5)
    useful: bool = True
    outcome: Literal["accepted", "edited", "rejected", "unknown"] = "unknown"
    comment: str = Field(default="", max_length=2000)


class RecordFeedbackOutput(_Out):
    recorded: bool
    feedback_id: str
    request_found: bool


class GetToolSchemasInput(ToolInput):
    tool: str | None = None


class GetToolSchemasOutput(_Out):
    schema_version: str
    tools: dict[str, dict[str, Any]]


class GetAuditTrailInput(ToolInput):
    request_id: str | None = Field(default=None, pattern=r"^req_[0-9a-f]{32}$")
    filter_trace_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9._:\-]{1,128}$")
    tool: str | None = None
    limit: int = Field(default=50, ge=1, le=500)


class AuditRecord(_Out):
    request_id: str
    trace_id: str
    session_id: str | None
    tool: str
    tool_version: str
    caller_role: str
    agent_id: str | None
    status: str
    error_code: str | None
    engine_mode: str
    model_version: str
    input_hash: str
    input_redacted: dict[str, Any]
    output_redacted: dict[str, Any] | None
    policy_decision: dict[str, Any] | None
    latency_ms: float
    created_at: str


class GetAuditTrailOutput(_Out):
    records: list[AuditRecord]
    count: int


class ListPolicyProfilesInput(ToolInput):
    pass


class ListPolicyProfilesOutput(_Out):
    active_profile: str
    profiles: dict[str, dict[str, Any]]


# --------------------------------------------------------------------------- envelope & errors

class EngineInfo(_Out):
    mode: Literal["deterministic", "hybrid"]
    model_version: str
    enriched: bool = False


class Envelope(_Out):
    request_id: str
    trace_id: str
    session_id: str | None
    tool: str
    tool_version: str
    schema_version: str
    engine: EngineInfo
    result: dict[str, Any]
    epistemics: Epistemics
    confidence: Score
    evidence: list[Evidence]
    warnings: list[str]
    latency_ms: float


class ErrorBody(_Out):
    code: Literal["invalid_input", "unknown_tool", "unauthorized", "forbidden",
                  "not_found", "internal_error"]
    message: str
    recoverable: bool
    hint: str
    details: list[dict[str, Any]] = Field(default_factory=list)


class ErrorEnvelope(_Out):
    request_id: str
    trace_id: str
    tool: str
    error: ErrorBody
