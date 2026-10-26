# Agents & Walkthroughs

## Overview

CognitiveMirror-Jev-MCP provides reusable agents for personal and enterprise decision support. The system follows a deterministic-first approach: rule/lexicon engines are the source of truth; live models only cross-check. The system is fully usable air-gapped.

## Agent Flow (§13 PRD)

The canonical agent workflow is:

1. **`mirror_user_intent`** — Reflect a raw user message into structured intent, including entity extraction, policy check, and role assignment.

2. **`build_jev_profile`** — Build a Jev (Just Evaluation) persona/profile with context intelligence. Offline lexicon engine always runs. With `TYPESAFE_API_KEY` set, one System One cross-check is performed per profile (`CM_JEV_MODEL`, default `jev-latest`). Live stage wins only at ≥ 0.6 confidence; overall confidence averages with live decisiveness.

3. **`check_guardrails`** — Safety verdict on the proposed action. Returns `guard_allowed` boolean and `approval` status.

4. **`recommend_next_action`** — Given the mirrored intent, Jev profile, and guardrail result, recommend the next action with business impact assessment.

5. **`frame_decision`** / **`assess_business_impact`** — When the decision warrants it, frame a decision question and assess business impact (priority, customer impact, time-to-value).

6. **Approval flow** — If `human_approval_required` is returned, the result is queued in the UI-2 Approval Inbox (`GET /v1/approvals`, `POST /v1/approvals/{id}/decision`). Audit-logged. Double-decide conflict is prevented server-side.

## Roles

- `agent` — Standard agent role, dev-key eligible (except enterprise profile)
- `admin` — Can approve/reject in inbox
- `compliance` — Policy enforcement, audit visibility

## UIs

- **UI-1 Demo Console** — Full workflow from one query box. Runs `mirror_user_intent → build_jev_profile → check_guardrails → recommend_next_action` in sequence.
- **UI-2 Approval Inbox** — Queues every `human_approval_required` result for approve/reject with reason.

## Walkthroughs

- **Personal agent** (`examples/personal_agent.py`) — Productivity: mirror → jev → guardrail → next action.
- **Enterprise agent** (`examples/enterprise_agent.py`) — Decision: frame_decision → assess_business_impact → guardrail → approve.

## Key Abstractions (from graphify graph)

- **`Store`** — Cross-community bridge (betweenness 0.113). Connectes `load_settings`, `store.py`, `service.py`, `test_jev_live.py`, `test_postgres.py`, `mcp_server.py`.
- **`Service`** — Core dispatch (betweenness 0.044). Connectes `service.py` to `load_settings`, `store.py`, `Store`, `test_jev_live.py`, `test_postgres.py`, `mcp_server.py`.
- **`load_settings`** — Cross-community bridge (betweenness 0.047). Connectes `create_app` to `store.py`, `service.py`, `schemas.py`, `Store`.
- **`intent.py`** — Community 0 (57 nodes, cohesion 0.07). Low cohesion suggests potential module split.
- **`models.py`** — Community 2 (56 nodes). Core data models: `Action`, `AuditRecord`, `BuildJevProfileOutput`, `BusinessOutcome`, etc.

## Graph Sources of Truth

- `graphify-out/graph.json` — Full graph (472 nodes, 1340 edges, 13 communities)
- `graphify-out/GRAPH_REPORT.md` — Community reports, god nodes, surprising connections, suggested questions
- `graphify-out/graph.html` — Interactive visualization

Run `graphify . --code-only` to rebuild after code changes (no API cost).
Run `graphify cluster-only .` to refresh community reports.