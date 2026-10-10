# Jev Profiling

## When to use
When you need persona, journey-stage, emotion, value-driver, and judgment context before responding — personalization, sales/customer, interview prep, coaching.

## Tool
`build_jev_profile` — builds a Jev profile for a user, stakeholder, scenario, or workflow.

## Inputs
- `subject`: `{type: user|stakeholder|scenario|workflow, role?, name?}`
- `context`: current situation text
- `known_preferences`: plain prefs only — protected attributes (health, religion, ethnicity, politics, …) are ignored and listed in `ignored_sensitive_attributes`
- `recent_interactions`, `memory_refs`
- `persist: true` requires `consent: true`, else the profile is returned without storing (`profile_ref: null` + warning)

## Rules (JEV-006)
- Never infer protected attributes; never use manipulative tactics — `autonomy_safeguards` are always returned
- Low `confidence` → call `mirror_user_intent` for the live request before acting

## Live System One cross-check (optional)
- Set `TYPESAFE_API_KEY` (and optionally `CM_JEV_MODEL`, default `jev-latest`): `build_jev_profile` additionally runs one System One fan-out call (journey-stage choice + confidence noul) and blends the signals — journey stage moves only on ≥ 0.6 live confidence, overall confidence is averaged with live decisiveness
- Cost is input-only ($0.042/Mtok) and reported in `warnings`; the envelope shows `engine.mode: hybrid` when live Jev contributed, `deterministic` otherwise
- Any live failure (no key, no SDK, network, auth) keeps the deterministic result with a warning — the call never fails for this reason

## Example (REST)
```bash
curl -X POST localhost:8000/v1/tools/build_jev_profile \
  -H 'X-API-Key: dev-agent-key' -H 'Content-Type: application/json' \
  -d '{"subject":{"type":"user","role":"software engineer"},
       "context":"Interview follow-up; worried about seeming unfocused"}'
```
