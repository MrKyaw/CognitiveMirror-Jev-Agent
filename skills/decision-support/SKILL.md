# Decision Support

## When to use
After mirroring intent: turn understanding into an executable next step, a framed decision, and a measurable impact case.

## Tools
- `recommend_next_action` — next best action from intent summary + Jev profile + business goal + guardrail result. Returns `agent_instruction`, alternatives, business impact, and `human_approval_required`.
- `frame_decision` — options with weighted scores, tradeoffs, risk register, recommended option + rationale.
- `assess_business_impact` — impact category, benefits, metrics with baseline/delta, cost/effort, ROI hypothesis, 0–100 priority score.

## Flow
1. Pass the `mirror_user_intent` result as `intent_summary` (dict or text) and the Jev result as `jev_profile`.
2. Pass the `check_guardrails` result as `guardrail_result` — approval flags flow through automatically.
3. For decisions, provide `success_metrics` + `constraints`; for impact, provide `baseline` numbers so deltas become targets.

## Example (REST)
```bash
curl -X POST localhost:8000/v1/tools/recommend_next_action \
  -H 'X-API-Key: dev-agent-key' -H 'Content-Type: application/json' \
  -d '{"intent_summary":"Draft follow-up email to hiring manager",
       "business_goal":"Advance to offer stage",
       "available_tools":["gmail","calendar"]}'
```
