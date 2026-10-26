# Skills & Agent Guides

Per-workflow agent guides live under `skills/`. Each guide walks through a specific agent workflow from start to finish, including the expected tool calls, Jev profiles, guardrail checks, and approval flows.

## Available Skill Guides

### `skills/personal_agent.md`
Personal productivity agent demo: mirror → jev → guardrail → next action.
- Uses `mirror_user_intent` → `build_jev_profile` → `check_guardrails` → `recommend_next_action`
- Default `:memory:` SQLite backend
- Demonstrates UI-1 Demo Console flow
- Output: structured intent, Jev profile, guardrail verdict, recommended action with business impact

### `skills/enterprise_agent.md`
Enterprise decision assistant demo: decision → impact → guardrail.
- Uses `frame_decision` → `assess_business_impact` → `check_guardrails`
- Demonstrates UI-2 Approval Inbox flow when `human_approval_required` is returned
- Includes business impact metrics (priority, customer experience, time-to-value)
- Shows double-decide conflict prevention

### `skills/mcp_client.md`
MCP client setup and direct tool calls.
- Claude Desktop configuration (mcpServers manifest)
- Direct `curl` calls to REST API
- MCP over stdio with `make mcp`
- Authentication via `X-API-Key` header

### `skills/postgres_setup.md`
PostgreSQL backend setup and evaluation.
- `CM_DATABASE_URL=postgresql://cm:cm@db:5432/cm docker compose --profile postgres up -d --build --wait`
- Live test: `CM_TEST_POSTGRES_URL=postgresql://... make postgres-test`
- Migration from SQLite: data export/import considerations
- Schema parity: same tables, `%s` → `%s` translation in store layer

### `skills/container_smoke.md`
Container smoke test and health verification.
- `bash tools/compose_smoke.sh` → `smoke OK`
- Health check: `GET /health` → `ok 1.1.0 | tools: 14`
- Smoke endpoints: `/v1/tools/mirror_user_intent`, `/ui`, `/approvals`

## Skill Guide Structure

Each `skills/*.md` follows the same template:

1. **Prerequisites** — Environment vars, Docker status, API keys
2. **Step-by-step walkthrough** — Tool calls in order, with expected inputs/outputs
3. **Jev profile** — Dimensions, offline vs live mode
4. **Guardrail check** — What triggers `human_approval_required`
5. **Approval flow** — Inbox queue, decision, audit log
6. **Expected output** — Final mirror/jev/recommendation result structure
7. **Troubleshooting** — Common errors and fixes

## Adding a New Skill

To add a new skill guide:

1. Create `skills/<name>.md` following the template above
2. Add the guide to `docs/skills.md` table of contents
3. Run `make test` to verify no regressions
4. Commit with message: `Add <name> skill guide`

## Graph-Informed Skills

Based on graphify analysis (graphify-out/GRAPH_REPORT.md), the most central skills to focus on are:

- **Store-mediated skills** — `memory_store`, `memory_recall`, `memory_forget` (Community 6, god node with 43 edges)
- **Service-mediated skills** — Any workflow that goes through `Service` dispatch (Community 4, betweenness 0.044)
- **Settings-mediated skills** — Configuration-dependent flows (Community 1, betweenness 0.047)
- **Intent-rich skills** — `mirror_user_intent`, `frame_decision` (Community 0, 57 nodes but low cohesion 0.07 — candidate for module split)

## Running Skill Guides

```bash
# Run a specific skill demo
PYTHONPATH=src .venv/bin/python src/cognitive_mirror/examples/personal_agent.py

# Or run via make
make demo  # Runs both personal_agent.py and enterprise_agent.py
```

## Sources of Truth

- `skills/` directory — The canonical skill guides (add/edit here, not in docs/)
- `graphify-out/GRAPH_REPORT.md` — Community structure and key connectors (updates with `graphify cluster-only .`)
- `test_results.md` — Current test outcomes and coverage numbers