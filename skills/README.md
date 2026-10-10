# Skills

Agent-facing guides for calling CognitiveMirror-Jev-MCP tools in the right order.

| Skill | Use when | Key tools |
|---|---|---|
| [cognitive-mirroring](cognitive-mirroring/SKILL.md) | Every new user request — structure intent first | `mirror_user_intent` |
| [jev-profiling](jev-profiling/SKILL.md) | You need persona / journey / emotion / value signals | `build_jev_profile` |
| [decision-support](decision-support/SKILL.md) | Recommend actions, frame decisions, show impact | `recommend_next_action`, `frame_decision`, `assess_business_impact` |
| [guardrails-governance](guardrails-governance/SKILL.md) | Before external/irreversible/financial actions; audit + memory consent | `check_guardrails`, `memory_*`, `get_audit_trail`, `list_policy_profiles` |

Standard flow: mirror → jev → guardrails → next action (+ decision/impact as needed).
All calls need `X-API-Key` (REST) or stdio role (MCP); pass `trace_id` to correlate a workflow and `session_id` to share context across agents.
