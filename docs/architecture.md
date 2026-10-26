# Architecture - CognitiveMirror-Jev-MCP v1.1.0

## High-Level Diagram

```
caller (MCP client, browser, or curl)
  │
  ├─── MCP (stdio / streamable-http) ───── 14 tools, versioned JSON Schemas
  │
  ├─── REST ──────────────────────────▶ /health · /v1/schemas ·
  │                POST /v1/tools/{tool} · /v1/approvals/* · /ui
  │
  └─── dispatch (service.py):
        │
        ├─── auth ── validate ── resolve memory ── engine ── audit ── publish
        │
        ├─── engines (deterministic, offline):
        │    ├─── intent.py      — User intent mirroring
        │    ├─── jev.py         — Jev persona/context intelligence
        │    ├─── actions.py     — Recommended next action
        │    ├─── decision.py    — Decision framing
        │    ├─── impact.py      — Business impact assessment
        │    └─── guardrails.py  — Safety verdict
        │
        ├─── jev_live (optional):
        │    └─── one System One cross-check per profile
        │         (TYPESAFE_API_KEY + CM_JEV_MODEL, default jev-latest)
        │
        └─── store:
             │
             ├─── SQLite (default, CM_DB_PATH)
             │    — memories, audit, shared, feedback, approvals
             │    — Same tables on PostgreSQL via CM_DATABASE_URL
             │
             └─── PostgreSQL (optional, CM_DATABASE_URL)
                    — Postgres 16 via docker compose --profile postgres
                    — %s placeholder translation + ON CONFLICT upserts
                    — PRD Phase 2 readiness
```

## Core Components

### 1. `service.py` — Dispatch Layer

The central dispatcher. Sequence:

```
auth
  → validate (API key + policy profile)
  → resolve memory (shared context, consent-gated PII-redacted)
  → engine (intent → jev → actions → decision → impact → guardrails)
  → audit (write record, redacted writes)
  → publish (MCP response + UI-1/UI-2 routing)
```

- Roles: `agent` / `admin` / `compliance`
- Policies: `default` → `strict` → `enterprise`
- Enterprise refuses dev keys
- High-impact paths require explicit approval by design

### 2. `store.py` — Persistence Layer

Dual-backend (SQLite / PostgreSQL) with identical semantics.

- **One placeholder style**: SQL written with `?`; store translates for Postgres (`%s`)
- **Same tables, same semantics** on both backends
- Tables: `memories`, `audit`, `shared`, `feedback`, `approvals`
- `audit_write` uses `INSERT ... ON CONFLICT(request_id) DO UPDATE SET` for Postgres,
  `INSERT OR REPLACE` for SQLite
- Memory: consent-gated, PII-redacted, expiring (expires_at)
- Shared context: TTL-based (CM_SHARED_CONTEXT_TTL_MINUTES, default 240 min)
- Feedback: rating, useful, outcome, comment
- Approvals: id, planned_action, risk_level, reasons, safe_alternative, status,
  decided_by, decision_reason, created_at, decided_at

### 3. `config.py` — Configuration & Settings

- Reads env vars: `CM_DB_PATH`, `CM_DATABASE_URL`, `CM_API_KEYS`,
  `CM_POLICY_PROFILE`, `CM_JEV_CONFIG`, `TYPESAFE_API_KEY`, `CM_JEV_MODEL`,
  `CM_RETENTION_DAYS`, `CM_SHARED_CONTEXT_TTL_MINUTES`, `CM_LLM_TIMEOUT_S`,
  `CM_ALLOWED_HOSTS`
- Validates: `CM_DATABASE_URL` must be `postgresql://` if set
- Settings dataclass: `deployment_mode`, `db_path`, `database_url`,
  `retention_days`, `shared_context_ttl_minutes`, `llm_timeout_s`,
  `allowed_hosts`, `policy_profile`

### 4. `api.py` — REST API (FastAPI)

- `app = FastAPI()` with middleware (auth, CM_REQUIRE_AUTH)
- Endpoints:
  - `GET /health` — `{"status":"ok","version":"1.1.0","tools":14}`
  - `GET /v1/schemas` — Committed JSON Schemas byte-identical to models
  - `POST /v1/tools/{tool}` — Dispatch via `service.call()`
  - `GET /v1/approvals` / `POST /v1/approvals/{id}/decision` — Inbox
  - `GET /ui` — Redirect to UI-1 console
  - `GET /` — Root redirect to `/ui`
- Auth: `X-API-Key` header matched against `CM_API_KEYS`
- Policy profile enforcement per endpoint

### 5. `mcp_server.py` — MCP over Stdio

- 14 tools registered via `mcp>=1.10,<2`
- Transport: stdio (for Claude Desktop and other MCP clients)
- `--transport stdio` flag
- Each tool maps to a `service.call()` dispatch

### 6. `jev_live.py` — Optional Live System One Cross-Check

- One System One call per `build_jev_profile` when `TYPESAFE_API_KEY` set
- Model: `CM_JEV_MODEL` (default `jev-latest`)
- Confidence: live stage wins at ≥ 0.6; overall confidence averages with live decisiveness
- Cost: $0.042/Mtok input-only; reported in warnings
- Any live failure → keeps deterministic result
- Envelope `engine.mode: hybrid` only when live Jev contributed

### 7. Engine Modules (deterministic, offline)

- **`intent.py`** — Mirror user intent: extract entities, policy check, role assignment
- **`jev.py`** — Build Jev profile: persona, context signals, confidence noul
- **`actions.py`** — Recommend next action with business impact
- **`decision.py`** — Frame decision questions
- **`impact.py`** — Assess business impact: priority, customer experience, time-to-value
- **`guardrails.py`** — Safety verdict: `guard_allowed`, `approval`, `human_approval_required`

### 8. `catalog.py` / `models.py` — Versioned JSON Schemas

- One source of truth: Pydantic models generate
  - MCP schemas
  - REST validation
  - Committed `schemas/v1/` files
- `jsonschema>=4.21` pin

### 9. UI Layer

- **UI-1 Demo Console** — Single query box runs full workflow
  - `mirror_user_intent → build_jev_profile → check_guardrails → recommend_next_action`
  - Open at `http://127.0.0.1:8000/ui`
- **UI-2 Approval Inbox** — Queues `human_approval_required` results
  - `GET /v1/approvals` — list pending
  - `POST /v1/approvals/{id}/decision` — approve/reject with reason
  - Audit-logged every decision
  - Double-decide conflict prevented server-side
- Root `/` redirects to `/ui`
- Static `ui.html` serves the console

## Configuration Flow

```
env vars → config.py → Settings dataclass →
  Store(settings.db_path, settings.retention_days,
         settings.shared_context_ttl_minutes,
         settings.database_url) →
  create_app(settings) → FastAPI app
```

## Database Schema (Identical on SQLite & Postgres)

| Table | Key Columns |
|---|---|
| `memories` | ref PRIMARY KEY, subject_id, kind, content, tags, created_at, expires_at |
| `audit` | request_id PRIMARY KEY, trace_id, session_id, tool, tool_version, caller_role, agent_id, status, engine_mode, model_version, input_hash, input_redacted, output_redacted, policy_decision, latency_ms, created_at |
| `shared` | id (SERIAL/AUTOINCREMENT), session_id, tool, request_id, trace_id, caller_role, agent_id, created_at, result |
| `feedback` | feedback_id PRIMARY KEY, request_id, rating, useful, outcome, comment, created_at |
| `approvals` | id PRIMARY KEY, trace_id, planned_action, risk_level, reasons, safe_alternative, status, decided_by, decision_reason, created_at, decided_at |

## Graphify Analysis (graphify-out/GRAPH_REPORT.md)

Key findings from the knowledge graph built on the codebase:

- **472 nodes, 1340 edges, 13 communities**
- **God nodes**: `_Out` (49 edges), `Store` (43 edges), `load_settings()` (34 edges),
  `Service` (28 edges), `mirror_user_intent()` (28 edges)
- **Cross-community bridges** (high betweenness):
  - `Store` (0.113) — connects `load_settings`, `store.py`, `service.py`,
    `test_jev_live.py`, `test_postgres.py`, `mcp_server.py`
  - `load_settings` (0.047) — connects `create_app` to `store.py`, `service.py`,
    `schemas.py`, `Store`
  - `Service` (0.044) — connects `service.py` to `load_settings`, `store.py`,
    `Store`, `test_jev_live.py`, `test_postgres.py`, `mcp_server.py`
- **Low cohesion communities**: `intent.py` (0.07) — candidate for module split
- **Inferred edges**: 55 edges (avg confidence 0.94) — model-reasoned connections needing verification
- **Knowledge gaps**: 3 isolated nodes (`ToolScript`, `compose_smoke.sh script`,
  `cognitive-mirror-jev-mcp`) — possible documentation gaps or missing edges

## Evolution Roadmap

| Version | Changes |
|---|---|
| **1.0** (done) | Tools, guardrails, audit, console, inbox, live-Jev option |
| **1.1** (done) | PostgreSQL backend, CI workflow, changelog |
| **Next** | UI-3 governance dashboard, evaluation harness, feedback learning |

## Sources of Truth (do not re-read all contents)

- `src/cognitive_mirror/` — The canonical source code (store.py, service.py, config.py, engines)
- `graphify-out/graph.json` — Code structure graph (rebuild with `graphify . --code-only`)
- `graphify-out/GRAPH_REPORT.md` — Community reports, god nodes, surprising connections
- `CHANGELOG.md` — Release history and changes
- `test_results.md` — Current test outcomes and coverage numbers
- `.env.example` — Configuration defaults
- `Dockerfile` / `docker-compose.yml` — Container deployment

Run `graphify . --code-only` to rebuild the graph after code changes (no API cost).
Run `graphify cluster-only .` to refresh community reports.