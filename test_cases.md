# Test Cases

Coverage requirement: 100% (`make test` enforces `--cov-fail-under=100`).

## How to run

| Command | What it runs |
|---|---|
| `make test` | Full unit suite (default markers exclude `perf`, `container`, `postgres`; `e2e` included) |
| `make e2e` | PRD §13 workflows + MCP discovery (`-m e2e`) |
| `make perf` | PRD §10 latency/concurrency (`-m perf`) |
| `make postgres-test` | Live PostgreSQL round-trip, needs `CM_TEST_POSTGRES_URL` (`-m postgres`) |
| `make container-test` | Live container checks (`tools/compose_smoke.sh` + `-m container`) |
| `make lint` | `ruff check src tests tools` |
| `PYTHONPATH=src python -m cognitive_mirror.schemas --check` | Schema drift check |

## Case map

| File | Cases | Covers (PRD) |
|---|---|---|
| `test_foundation.py` | version constants, memory coverage/use, settings valid + 10 invalid configs, text utils (normalize/sentences/phrases/negation/deadlines/snippets), lexicon merge/scoring/override, LLM enricher 3 modes, schema write/drift | §7 config, §10 portability, MCP-007 |
| `test_engines_core.py` | goal/constraint extraction, urgency 6 paths, intent classification 4 paths, mirror 10 scenarios (brief/vague/schedule/decision/reflect/crisis/frustration/memory/conflict), PII/luhn/mask/redact, policy load, guardrail 12 scenarios (PII, secrets, financial, irreversible, manipulation, bypass, bulk, regulated ×4, special-category, consent) | COG-001..008, §8.1, §8.6, §9.3 |
| `test_engines_rest.py` | Jev profile 6 paths (role/expertise/journey/manipulation/memory/empty/recovering), next-action 6 paths, decision 5 types, impact 4 paths | JEV-001..006, §8.2–8.5 |
| `test_service.py` | 6 core tools dispatch, 5 error codes, memory store/recall/forget round-trip + expiry + cross-subject scope, Jev persist ±consent, shared sessions, feedback found/missing, schemas single/all/unknown, audit query, policies, store direct ops | MCP-001..005, AGENT-001..007, §9.1–9.2 |
| `test_api_mcp.py` | health, schemas ×3, auth (missing/invalid/Bearer), invalid JSON, non-dict body, forbidden role, agent header, allowed-hosts block, no-auth mode, all 14 MCP wrappers, both example demos | MCP-001/002/006, §10 security |
| `test_edge.py` | malformed auth, host allowlist pass, dict-shape edge inputs, mask short/overlap/luhn-skip, money→financial inference, baseline-miss, goals/constraints limits, urgency floor, unscored question, duplicate phrases, file-backed store | branch-closure to 100% |
| `test_postgres.py` | pg DDL/translation via fakes, upsert, approvals, missing driver, connect failure, URL validation, live round-trip (skipped without `CM_TEST_POSTGRES_URL`) | Phase 2 readiness, §9.1 |
| `test_ui.py` | root redirect, UI page, approval auth/validation, full create→list→decide→audit flow, double-decide conflict, unknown id, host block, no-auth mode | §6A UI-1/UI-2, §9.3 approval gates |
| `test_jev_live.py` | live Jev off (no key), missing SDK, API error, stage override/confirm/low-conf/missing answers, confidence blending, cost warning, hybrid envelope, new settings keys | §7.3 live layer |
| `test_e2e.py` | personal-agent 8-step workflow, enterprise guardrail→decision→impact, MCP 14-tool discovery | §13, acceptance criteria |
| `test_perf.py` | lightweight < 1.5 s, deep < 5 s, 20-way concurrency | §10 latency/scalability |
| `test_container.py` | container `/health` (14 tools), live tool call | §10 availability/portability |
