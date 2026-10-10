# CognitiveMirror-Jev-MCP PRD

## 1. Product Summary

**Product name:** CognitiveMirror-Jev-MCP  
**Product type:** MCP server and agent-facing cognitive services layer  
**Primary users:** Personal AI agents, enterprise assistants, executive copilots, workflow agents, and human users who need structured reflection, decision support, and context-aware actions.  
**Primary goal:** Provide a reusable MCP server that helps any personal agent understand user intent, mirror cognitive patterns, apply Jev persona/context intelligence, and turn conversations into safer, more useful, business-impacting actions.

CognitiveMirror-Jev-MCP should act as a trusted cognitive middleware layer between personal agents and enterprise/user workflows. It should not replace the agent. It should serve the agent with tools, memory, reasoning support, context signals, and guardrails.

## 2. Vision

Personal agents need more than generic chat. They need durable context, reflective reasoning, trustworthy action planning, and business-aware interpretation of user goals. CognitiveMirror-Jev-MCP provides this capability through MCP tools that expose:

- Cognitive mirroring of user intent, constraints, goals, and decision style.
- Jev context services for persona, journey, emotion, value, and judgment signals.
- Memory-aware recommendation and next-best-action support.
- Business impact mapping from user request to measurable outcome.
- Guardrails for privacy, safety, explainability, and human approval.

The product should allow any MCP-compatible personal agent to ask: “What does this user really want, what matters most, what risks exist, and what action should I take next?”

## 3. Business Objectives

| Objective | Business Impact |
| --- | --- |
| Improve agent personalization | Higher user trust, better retention, and more relevant outputs. |
| Reduce repeated context gathering | Faster task completion and lower interaction friction. |
| Standardize cognitive reasoning services | Reusable platform capability across multiple agents and workflows. |
| Improve decision quality | Better prioritization, risk awareness, and business-aligned recommendations. |
| Enable safe agentic action | Lower operational, privacy, compliance, and reputational risk. |
| Support enterprise adoption | Clear auditability, governance, and measurable ROI. |

## 4. Target Use Cases

### 4.1 Personal Productivity Agent

The agent uses CognitiveMirror-Jev-MCP to understand the user’s preferences, current goals, communication style, urgency, constraints, and prior decisions before drafting emails, preparing interview notes, scheduling tasks, or recommending next actions.

### 4.2 Career and Interview Copilot

The MCP server helps an interview copilot map a job description to the user’s achievements, identify strongest proof points, generate concise answers, and flag gaps or risky claims.

### 4.3 Enterprise Decision Assistant

An enterprise assistant uses CognitiveMirror-Jev-MCP to convert vague business requests into structured decision frames, stakeholder impact, options, tradeoffs, and recommended execution plans.

### 4.4 Customer Success or Sales Agent

The agent uses Jev signals to identify customer intent, emotional tone, buying stage, friction points, and next-best actions while maintaining compliance and human review for sensitive decisions.

### 4.5 Knowledge Worker Reflection Agent

The agent helps users review their own thinking, detect blind spots, summarize priorities, and convert reflection into practical plans.

## 5. Personas

| Persona | Need | Success Outcome |
| --- | --- | --- |
| Personal agent | Needs context-rich tools to serve the user better | Produces more relevant, aligned, and actionable responses |
| Human user | Wants the agent to understand goals without repeating everything | Faster, more trusted, more personalized support |
| Enterprise admin | Needs governance, auditability, and privacy controls | Safe adoption across teams |
| Product owner | Needs reusable agent infrastructure | Faster development of multiple cognitive agents |
| Compliance reviewer | Needs traceable decisions and guardrails | Clear evidence of policy-aware behavior |

## 6. Product Scope

### In Scope

- MCP server exposing cognitive and Jev-related tools.
- User profile and context abstraction.
- Intent, emotion, goal, constraint, and priority extraction.
- Cognitive mirroring summaries.
- Next-best-action recommendation.
- Decision framing and tradeoff analysis.
- Memory retrieval interface.
- Risk and guardrail checks.
- Agent integration examples.
- Audit logs and tool call traceability.
- Privacy-aware data minimization.

### Out of Scope for MVP

- Fully autonomous execution without human approval.
- Medical, legal, financial, or immigration advice as authoritative output.
- Training foundational models from scratch.
- Replacing enterprise identity, access management, CRM, HRIS, or document systems.
- Long-term storage of sensitive user data without explicit policy and consent.
- Full enterprise analytics platform (covered by the Phase 2 governance dashboard instead).
- Native mobile apps (all MVP UIs are responsive web).

## 6A. User Interfaces (to achieve the Primary Goal)

The server remains the product; the UIs are thin surfaces that make its value visible
and its guardrails enforceable. Three UIs, each mapped to one half of the Primary Goal:

| UI | Serves | Primary-Goal coverage |
| --- | --- | --- |
| UI-1 Demo Console | Human users, product owners, new integrators | Shows intent mirroring + Jev context turning a raw request into a business-aware action plan |
| UI-2 Approval Inbox | Human users approving agent actions | Enforces the "safer actions" half: every `human_approval_required` guardrail result lands here before execution |
| UI-3 Governance Dashboard | Enterprise admins, compliance reviewers | Proves safe adoption: audit trail, guardrail outcomes, latency, feedback |

### UI-1 Demo Console (MVP)

Single responsive page served alongside the API. One query box runs the §13 workflow
live (`mirror_user_intent` → `build_jev_profile` → `check_guardrails` →
`recommend_next_action`, plus `frame_decision`/`assess_business_impact` on demand) and
renders five panels: Mirror Summary (intent, goals, constraints, urgency, ambiguities),
Jev Signals (persona, journey stage, emotions, value drivers), Guardrail Badge
(allowed / risk level / approval flag), Next Action (`agent_instruction` + alternatives),
Business Impact (category, metrics, ROI hypothesis, priority score). No auth for local
demo; uses the same `X-API-Key` auth as the REST API when deployed.

### UI-2 Approval Inbox (MVP)

Human-in-the-loop queue required by AGENT-007 and §9.3. Every tool result with
`human_approval_required: true` appears here with the planned action (redacted),
risk level, policy reasons, and `safe_alternative`; the reviewer approves or rejects
with a reason, and the decision is written to the audit log with traceability.
External, irreversible, financial, and high-impact actions cannot execute while
pending here.

### UI-3 Governance Dashboard (Phase 2, read-only)

Admin/compliance roles only. Charts over the audit log: tool-call volume and success
rate, P95 latency vs §10 targets, guardrail flag/approval rates, feedback ratings,
and per-trace drill-down (inputs redacted). No raw PII ever rendered — memory refs
and placeholders only.

## 7. Key Requirements

### 7.1 MCP Server Requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| MCP-001 | Provide an MCP-compatible server exposing documented tools, schemas, and responses. | P0 |
| MCP-002 | Support tool discovery with clear descriptions for personal agents. | P0 |
| MCP-003 | Return structured JSON responses suitable for orchestration. | P0 |
| MCP-004 | Support stateless and context-aware requests. | P0 |
| MCP-005 | Provide request IDs and trace IDs for auditability. | P0 |
| MCP-006 | Support role-based access for sensitive tools. | P1 |
| MCP-007 | Provide versioned tool schemas. | P1 |
| MCP-008 | Support local, private cloud, and enterprise deployment modes. | P1 |

### 7.2 CognitiveMirror Requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| COG-001 | Extract user intent, explicit goals, implicit goals, constraints, and urgency. | P0 |
| COG-002 | Generate a cognitive mirror summary of what the user is trying to achieve. | P0 |
| COG-003 | Identify decision style, preferred tone, risk tolerance, and working preferences when available. | P1 |
| COG-004 | Detect ambiguity and propose clarification questions. | P0 |
| COG-005 | Detect conflicting goals or constraints. | P1 |
| COG-006 | Map the request to business outcomes and success metrics. | P0 |
| COG-007 | Provide confidence scores and evidence references. | P1 |
| COG-008 | Support reflection prompts that help the user improve thinking without overstepping. | P2 |

### 7.3 Jev Requirements

For this PRD, **Jev** means the persona, journey, emotion, value, and judgment intelligence layer that helps an agent understand a user or stakeholder in context. It ships in two layers:

- **Deterministic layer (default):** offline lexicon engine, no network, no key. Always runs.
- **Live layer (optional):** one System One fan-out call (`TYPESAFE_API_KEY` + `CM_JEV_MODEL`, default `jev-latest`) behind `build_jev_profile` cross-checks the journey stage and user confidence. Any failure falls back to the deterministic result with a warning; the envelope reports `engine.mode: hybrid` only when live Jev contributed.

| ID | Requirement | Priority |
| --- | --- | --- |
| JEV-001 | Model persona signals such as role, goals, expertise level, communication preference, and current context. | P0 |
| JEV-002 | Model journey stage such as exploring, deciding, executing, following up, or recovering from setback. | P0 |
| JEV-003 | Identify emotional signals such as excitement, concern, frustration, urgency, confidence, or disappointment. | P1 |
| JEV-004 | Identify value drivers such as speed, trust, quality, cost, compliance, revenue, career growth, or user satisfaction. | P0 |
| JEV-005 | Provide judgment support with options, tradeoffs, risks, and recommended next steps. | P0 |
| JEV-006 | Avoid manipulative personalization and preserve user autonomy. | P0 |
| JEV-007 | Allow enterprise configuration of Jev dimensions and scoring. | P2 |

### 7.4 Personal Agent Integration Requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| AGENT-001 | Any MCP-compatible personal agent can call CognitiveMirror-Jev-MCP tools. | P0 |
| AGENT-002 | Provide a lightweight integration guide and sample prompts. | P0 |
| AGENT-003 | Support agent workflows for planning, writing, decision support, follow-up, and memory lookup. | P0 |
| AGENT-004 | Provide safe defaults when user context is missing. | P0 |
| AGENT-005 | Return actionable outputs, not only analysis. | P0 |
| AGENT-006 | Support multi-agent orchestration where specialist agents can request shared cognitive context. | P1 |
| AGENT-007 | Support human approval checkpoints for sensitive actions. | P0 |

## 8. Proposed MCP Tools

### 8.1 `mirror_user_intent`

**Purpose:** Convert a raw user request into structured intent, goals, constraints, urgency, and desired output.

**Inputs:**

- `user_message`
- `conversation_context`
- `available_memory_refs`
- `agent_goal`

**Outputs:**

- `primary_intent`
- `secondary_intents`
- `explicit_goals`
- `implicit_goals`
- `constraints`
- `urgency`
- `ambiguities`
- `recommended_agent_response_strategy`

### 8.2 `build_jev_profile`

**Purpose:** Build or update the Jev profile for a user, stakeholder, or scenario.

**Inputs:**

- `subject`
- `context`
- `known_preferences`
- `recent_interactions`

**Outputs:**

- `persona_signals`
- `journey_stage`
- `emotion_signals`
- `value_drivers`
- `judgment_context`
- `confidence`

### 8.3 `recommend_next_action`

**Purpose:** Recommend the next best action for the agent based on cognitive and Jev context.

**Inputs:**

- `intent_summary`
- `jev_profile`
- `business_goal`
- `risk_level`
- `available_tools`

**Outputs:**

- `recommended_action`
- `alternative_actions`
- `business_impact`
- `risks`
- `human_approval_required`
- `agent_instruction`

### 8.4 `frame_decision`

**Purpose:** Convert a problem into options, tradeoffs, risks, and decision criteria.

**Inputs:**

- `decision_question`
- `context`
- `constraints`
- `success_metrics`

**Outputs:**

- `decision_frame`
- `options`
- `tradeoffs`
- `risk_register`
- `recommended_option`
- `rationale`

### 8.5 `assess_business_impact`

**Purpose:** Map a request or action to measurable business value.

**Inputs:**

- `request`
- `target_workflow`
- `stakeholders`
- `baseline`

**Outputs:**

- `impact_category`
- `expected_benefits`
- `metrics`
- `cost_or_effort`
- `roi_hypothesis`
- `priority_score`

### 8.6 `check_guardrails`

**Purpose:** Evaluate privacy, safety, compliance, and human approval needs.

**Inputs:**

- `planned_action`
- `data_used`
- `user_context`
- `policy_profile`

**Outputs:**

- `allowed`
- `risk_level`
- `issues`
- `required_redactions`
- `human_approval_required`
- `safe_alternative`

## 9. Functional Requirements

### 9.1 Context Management

- The server must accept context from the calling agent without assuming access to the full conversation.
- The server must separate short-term conversation context from durable user profile information.
- The server must support memory references instead of requiring raw sensitive data.
- The server must provide confidence levels when memory is incomplete or outdated.

### 9.2 Reasoning and Recommendation

- The server must provide structured outputs that can be directly used by an agent.
- The server must distinguish facts, assumptions, inferences, and recommendations.
- The server must explain business impact in practical terms.
- The server must identify when clarification is better than action.

### 9.3 Safety and Governance

- Sensitive data must be minimized, redacted, or referenced through secure IDs when possible.
- The server must support human approval for external actions, financial decisions, compliance-sensitive recommendations, and high-impact user communications.
- The server must produce audit logs for tool calls, inputs, outputs, model versions, and policy decisions.
- The server must avoid creating hidden behavioral manipulation loops.

### 9.4 Developer Experience

- Tool schemas must be documented with examples.
- Responses must be predictable, typed, and easy to validate.
- The server must include sample integrations for at least one personal agent and one enterprise workflow agent.
- Errors must be clear and recoverable.

## 10. Non-Functional Requirements

| Category | Requirement |
| --- | --- |
| Latency | P95 response under 1.5 seconds for lightweight tools and under 5 seconds for deeper decision framing. |
| Availability | 99.5% for MVP, 99.9% for enterprise release. |
| Security | Authentication, authorization, encryption in transit, and secure secret handling. |
| Privacy | Data minimization, configurable retention, redaction, and consent-aware memory use. |
| Observability | Metrics, traces, logs, tool call success rate, latency, and guardrail outcomes. |
| Scalability | Support multiple agents and concurrent tool calls. |
| Portability | Deployable locally, in private cloud, or as managed service. |
| Maintainability | Versioned APIs, test coverage, schema validation, and clear release notes. |

## 11. MVP Definition

The MVP should include:

- MCP server with six core tools:
  - `mirror_user_intent`
  - `build_jev_profile`
  - `recommend_next_action`
  - `frame_decision`
  - `assess_business_impact`
  - `check_guardrails`
- JSON schemas for all tools.
- Simple memory reference interface.
- Basic policy and guardrail engine.
- UI-1 Demo Console (single page driving the §13 workflow via the REST API).
- UI-2 Approval Inbox (human approval queue for `human_approval_required` results, audit-logged).
- Example personal agent integration.
- Example enterprise workflow integration.
- Audit logging.
- README and API examples.
- Unit tests for schemas and tool outputs.
- UI tests for the console happy path and the inbox approve/reject flow.

## 12. Success Metrics

| Metric | Target |
| --- | --- |
| Agent response relevance | 20-30% improvement in human rating versus baseline agent without MCP context |
| Repeated context reduction | 30% fewer repeated user explanations |
| Task completion speed | 25% faster completion for supported workflows |
| Clarification quality | 80% of clarification questions judged useful |
| Guardrail precision | 95% of high-risk actions correctly flagged for review |
| Integration time | New personal agent integration completed within one day |
| Business usefulness | 70% of recommendations include measurable business impact |

## 13. Example Agent Workflow

1. Personal agent receives user request.
2. Agent calls `mirror_user_intent`.
3. Agent calls `build_jev_profile` using available context and memory references.
4. Agent calls `check_guardrails` for the intended workflow.
5. Agent calls `recommend_next_action`.
6. If needed, agent calls `frame_decision` or `assess_business_impact`.
7. Agent responds to the user with a concise, business-aware, safe action plan.
8. Agent logs outcome and optional feedback for future improvement.

## 14. Data Model Concepts

### Cognitive Context

- `intent`
- `goals`
- `constraints`
- `urgency`
- `ambiguity`
- `decision_style`
- `risk_tolerance`
- `success_criteria`

### Jev Context

- `persona`
- `journey_stage`
- `emotion_signal`
- `value_driver`
- `judgment_need`
- `stakeholder_impact`

### Business Impact

- `impact_category`
- `metric`
- `baseline`
- `expected_delta`
- `confidence`
- `evidence`

### Guardrail Result

- `allowed`
- `risk_level`
- `policy_reason`
- `approval_required`
- `safe_alternative`

## 15. Risks and Mitigations

| Risk | Mitigation |
| --- | --- |
| Over-personalization feels intrusive | Use transparent context, user control, and minimal necessary memory. |
| Incorrect inference about user intent | Return confidence, assumptions, and clarification prompts. |
| Sensitive data leakage | Redaction, access control, memory references, and audit logs. |
| Agent takes unsafe action | Guardrail checks and human approval gates. |
| Tool responses are too abstract | Require action-oriented outputs and business impact mapping. |
| Enterprise adoption blocked by governance | Provide auditability, policy configuration, and deployment options. |

## 16. Open Questions

- What is the exact intended meaning of “Jev” in the product naming and architecture?
  Resolved in §7.3: deterministic persona/journey/emotion/value/judgment layer by default,
  optional live System One (`jev`) cross-check when `TYPESAFE_API_KEY` is set.
- Should Jev profiles be user-specific, stakeholder-specific, workflow-specific, or all three?
- Will the MCP server store durable memory or only consume memory references from another system?
- Which personal agent should be the first reference integration?
- What compliance standards are required for the first enterprise target, such as SOC 2, ISO 27001, HIPAA, PIPEDA, GDPR, or internal AI governance?
- UI scope resolved in §6A: Demo Console + Approval Inbox ship in MVP; full Governance Dashboard follows in Phase 2.

## 17. Recommended Roadmap

### Phase 1: MVP Foundation

- Define schemas.
- Implement core MCP tools.
- Add basic guardrails.
- Add audit logging.
- Build UI-1 Demo Console and UI-2 Approval Inbox on the REST API.
- Build one personal agent demo.
- Validate with 3-5 real workflows.

### Phase 2: Enterprise Readiness

- Add role-based access control.
- Add configurable policy profiles.
- Add UI-3 Governance Dashboard (observability over the audit log).
- Add evaluation harness.
- Add multi-agent orchestration examples.

### Phase 3: Cognitive Intelligence Expansion

- Add advanced Jev scoring.
- Add feedback learning.
- Add workflow-specific playbooks.
- Add marketplace-ready MCP server packaging.
- Add enterprise deployment templates.

## 18. Acceptance Criteria

- An MCP-compatible agent can discover and call all MVP tools.
- Each tool returns valid structured JSON according to schema.
- A personal agent can use the server to produce a more personalized, action-oriented response.
- Business impact is included in recommendations where applicable.
- Guardrails flag sensitive or high-risk actions.
- Tool calls are logged with traceability.
- The Demo Console renders a full §13 workflow (mirror → Jev → guardrail → action → impact) from one query.
- The Approval Inbox blocks pending high-risk actions until a human approves or rejects with a logged reason.
- Documentation allows a new developer to integrate a personal agent within one day.

## 19. Executive Summary

CognitiveMirror-Jev-MCP should become a reusable cognitive services layer for personal and enterprise agents. Its strongest value is helping agents move from generic response generation to context-aware, business-impacting, safe action support. By exposing cognitive mirroring, Jev persona/context intelligence, decision framing, business impact assessment, and guardrail checks through MCP, the product can serve many personal agents while maintaining governance, traceability, and practical enterprise value.
