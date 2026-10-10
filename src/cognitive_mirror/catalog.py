"""Tool catalog: names, versions, descriptions, contracts and access rules (MCP-002/006/007)."""
from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel

from cognitive_mirror import models as m

ALL_ROLES = frozenset({"agent", "admin", "compliance"})
AGENT_ROLES = frozenset({"agent", "admin"})
GOVERNANCE_ROLES = frozenset({"admin", "compliance"})


@dataclass(frozen=True)
class ToolSpec:
    name: str
    version: str
    title: str
    description: str
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    roles: frozenset[str]
    kind: str = "lightweight"  # lightweight | deep (PRD latency targets: 1.5 s / 5 s)
    read_only: bool = True
    sensitive: bool = False
    core: bool = False


TOOLS: dict[str, ToolSpec] = {s.name: s for s in [
    ToolSpec(
        "mirror_user_intent", "1.0.0", "Mirror user intent",
        "Call FIRST for every new user request. Converts the raw message into structured "
        "intent, explicit and implicit goals, constraints, urgency, ambiguities with "
        "clarification questions, goal conflicts, decision style, a plain-language mirror "
        "summary, business outcomes, and a recommended response strategy "
        "(clarify_first | act | act_with_confirmation | reflect | escalate). Pass "
        "available_memory_refs instead of raw sensitive history.",
        m.MirrorUserIntentInput, m.MirrorUserIntentOutput, AGENT_ROLES, core=True),
    ToolSpec(
        "build_jev_profile", "1.0.0", "Build Jev profile",
        "Builds a Jev (persona, journey, emotion, value, judgment) profile for a user, "
        "stakeholder, scenario or workflow from context, known preferences, recent "
        "interactions and memory refs. Returns persona signals, journey stage, emotion "
        "signals, ranked value drivers, judgment context and autonomy safeguards. Never "
        "infers protected attributes. Set persist=true with consent=true to save it.",
        m.BuildJevProfileInput, m.BuildJevProfileOutput, AGENT_ROLES, read_only=False,
        core=True),
    ToolSpec(
        "recommend_next_action", "1.0.0", "Recommend next action",
        "Recommends the next best agent action from the intent summary (text or the "
        "mirror_user_intent result), Jev profile, business goal, risk level, available "
        "tools and guardrail result. Returns an executable agent_instruction, alternatives, "
        "business impact, risks and whether human approval is required.",
        m.RecommendNextActionInput, m.RecommendNextActionOutput, AGENT_ROLES, core=True),
    ToolSpec(
        "frame_decision", "1.0.0", "Frame decision",
        "Turns a decision question into a decision frame (type, reversibility, stakes, "
        "weighted criteria), scored options including 'gather more information' and "
        "'defer', tradeoffs, a risk register, a recommended option and rationale.",
        m.FrameDecisionInput, m.FrameDecisionOutput, AGENT_ROLES, kind="deep", core=True),
    ToolSpec(
        "assess_business_impact", "1.0.0", "Assess business impact",
        "Maps a request or action to measurable business value: impact category, expected "
        "benefits, metrics with baseline and expected delta, cost or effort, an ROI "
        "hypothesis and a 0-100 priority score.",
        m.AssessBusinessImpactInput, m.AssessBusinessImpactOutput, AGENT_ROLES, core=True),
    ToolSpec(
        "check_guardrails", "1.0.0", "Check guardrails",
        "Call BEFORE any external, irreversible, financial or high-impact action. Detects "
        "PII and secrets (with redactions), regulated advice (medical, legal, financial, "
        "immigration), manipulation patterns and sensitive data, applies the policy "
        "profile, and returns allowed, risk_level, issues, human_approval_required and a "
        "safe alternative.",
        m.CheckGuardrailsInput, m.CheckGuardrailsOutput, ALL_ROLES, core=True),
    ToolSpec(
        "memory_store", "1.0.0", "Store memory",
        "Stores a consented memory item for a subject and returns an opaque memory_ref "
        "(mem_...). PII is redacted on write; items expire after the retention period. "
        "kind=context for short-term context, kind=profile for durable preferences.",
        m.MemoryStoreInput, m.MemoryStoreOutput, AGENT_ROLES, read_only=False),
    ToolSpec(
        "memory_recall", "1.0.0", "Recall memory",
        "Recalls memory items for a subject by refs and/or keyword query, with "
        "staleness-aware confidence and a list of missing or expired refs.",
        m.MemoryRecallInput, m.MemoryRecallOutput, AGENT_ROLES),
    ToolSpec(
        "memory_forget", "1.0.0", "Forget memory",
        "Deletes one memory item, or (admin only) every item for a subject.",
        m.MemoryForgetInput, m.MemoryForgetOutput, AGENT_ROLES, read_only=False),
    ToolSpec(
        "get_shared_context", "1.0.0", "Get shared context",
        "Returns the cognitive context published under session_id by other agents' tool "
        "calls, so specialist agents can share intent, Jev and decision context.",
        m.GetSharedContextInput, m.GetSharedContextOutput, ALL_ROLES),
    ToolSpec(
        "record_feedback", "1.0.0", "Record feedback",
        "Records the outcome and a 1-5 rating for a previous tool call (by request_id) "
        "for evaluation and improvement.",
        m.RecordFeedbackInput, m.RecordFeedbackOutput, AGENT_ROLES, read_only=False),
    ToolSpec(
        "get_tool_schemas", "1.0.0", "Get tool schemas",
        "Returns versioned JSON Schemas for tool inputs and outputs.",
        m.GetToolSchemasInput, m.GetToolSchemasOutput, ALL_ROLES),
    ToolSpec(
        "get_audit_trail", "1.0.0", "Get audit trail",
        "Governance only (admin, compliance): returns redacted audit records by "
        "request_id, trace or tool.",
        m.GetAuditTrailInput, m.GetAuditTrailOutput, GOVERNANCE_ROLES, sensitive=True),
    ToolSpec(
        "list_policy_profiles", "1.0.0", "List policy profiles",
        "Governance only (admin, compliance): returns guardrail policy profiles.",
        m.ListPolicyProfilesInput, m.ListPolicyProfilesOutput, GOVERNANCE_ROLES,
        sensitive=True),
]}

CORE_TOOLS = tuple(name for name, spec in TOOLS.items() if spec.core)
