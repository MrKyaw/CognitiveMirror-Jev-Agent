# Cognitive Mirroring

## When to use
Call FIRST for every new user request, before acting or answering.

## Tool
`mirror_user_intent` — converts a raw message into intent, goals, constraints, urgency, ambiguities, conflicts, mirror summary, business outcomes, and a response strategy (`clarify_first | act | act_with_confirmation | reflect | escalate`).

## Inputs
- `user_message` (required): raw request text
- `conversation_context`: last few turns only, no full history dumps
- `available_memory_refs`: opaque `mem_...` refs, never raw sensitive data
- `subject_id`: owner of the memory refs
- `trace_id` / `session_id`: correlate workflow / share across agents

## How to act on the result
- `mode == clarify_first` → ask the returned clarification questions, do not act yet
- `mode == act_with_confirmation` → prepare the draft, call `check_guardrails`, wait for approval
- `mode == escalate` → crisis language path: respond with care, stop the task flow
- Always surface `assumptions` when ambiguities exist; quote `evidence` for key claims

## Example (REST)
```bash
curl -X POST localhost:8000/v1/tools/mirror_user_intent \
  -H 'X-API-Key: dev-agent-key' -H 'Content-Type: application/json' \
  -d '{"user_message":"Draft a follow-up email to my hiring manager for tomorrow",
       "trace_id":"tr_demo","session_id":"s1"}'
```
