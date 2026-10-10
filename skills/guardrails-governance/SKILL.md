# Guardrails & Governance

## When to use
BEFORE any external, irreversible, financial, or high-impact action — and whenever personal data is involved.

## Tools
- `check_guardrails` — PII/secret detection with redactions, regulated-advice flags (medical/legal/financial/immigration), manipulation + security-bypass blocks, policy-profile enforcement. Returns `allowed`, `risk_level`, `issues`, `human_approval_required`, `safe_alternative`.
- `memory_store` / `memory_recall` / `memory_forget` — consent-gated (`consent: true` to store); PII redacted on write; refs expire per retention. Forgetting ALL of a subject's memory needs `admin`.
- `get_shared_context` — read context published under a `session_id` by other agents.
- `record_feedback` — rate a prior call by `request_id` (1–5).
- `get_audit_trail` / `list_policy_profiles` — `admin`/`compliance` roles only.

## Policy profiles
`default` (personal-agent baseline) → `strict` (regulated) → `enterprise` (governance). Override per call with `policy_profile`.

## Example (REST)
```bash
curl -X POST localhost:8000/v1/tools/check_guardrails \
  -H 'X-API-Key: dev-agent-key' -H 'Content-Type: application/json' \
  -d '{"planned_action":"Email all customers the new pricing",
       "data_used":["customer list"]}'
# If human_approval_required == true, do not execute — present safe_alternative instead.
```
