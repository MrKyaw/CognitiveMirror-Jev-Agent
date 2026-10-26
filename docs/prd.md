# PRD Summary - CognitiveMirror-Jev-MCP v1.1.0

## Core Requirements (from PRD.md)

| # | Requirement | Status |
|---|---|---|
| 1 | 100% working, tested, production-grade | ✅ 62 unit tests at 100% coverage; e2e/perf/postgres/container all green |
| 2 | Fulfilling PRD.md acceptance criteria | ✅ All criteria met |
| 3 | Deployable via Docker | ✅ `docker compose up -d --build --wait` healthy; 14 tools live |
| 4 | No confidential info in repo | ✅ .env never committed; API keys via env vars only |
| 5 | Human-written output | ✅ No AI-generated footers or co-author strings in source |
| 6 | GitHub repo | ✅ https://github.com/MrKyaw/CognitiveMirror-Jev-MCP |

## Architecture (§13)

### Two Jev Layers (§7.3)

- **Offline lexicon engine** — Always runs deterministic, no API key needed. Source of truth.
- **Optional live System One cross-check** — With `TYPESAFE_API_KEY` set, each profile gets one System One call (`journey-stage choice + confidence noul`, `CM_JEV_MODEL`, default `jev-latest`). Cost: $0.042/Mtok input-only; reported in warnings. Any live failure keeps the deterministic result. Envelope reads `engine.mode: hybrid` only when live Jev contributed.

### Persistence (PRD §9.1, 9.3, 10)

- **SQLite** — Default via `CM_DB_PATH=data/cognitive_mirror.db`. Memory, audit, shared context, approvals, feedback.
- **PostgreSQL** — Optional via `CM_DATABASE_URL=postgresql://...`. Same tables and semantics; `%s` placeholder translation and `ON CONFLICT` upserts handled in the store layer. `docker compose --profile postgres up` spins up Postgres 16.

### API & MCP (PRD §6, §13)

- **REST API** — FastAPI on 127.0.0.1:8000. Health: `GET /health`. Tool calls: `POST /v1/tools/{tool}`.
- **MCP stdio** — 14 tools over stdio for Claude Desktop and other MCP clients.
- **Authentication** — `CM_API_KEYS` (<key>:<role> pairs). Enterprise mode refuses dev keys.

### UIs (PRD §13)

- **UI-1 Demo Console** — Full workflow from one query box.
- **UI-2 Approval Inbox** — Queue every `human_approval_required` result for approve/reject with reason. `GET /v1/approvals`, `POST /v1/approvals/{id}/decision`, audit-logged.

### Engines (deterministic, offline)

- `intent` — User intent mirroring
- `jev` — Jev persona/context intelligence
- `actions` — Recommended next action
- `decision` — Decision framing
- `impact` — Business impact assessment
- `guardrails` — Safety verdict

### Optional Live

- `jev_live` — System One cross-check per profile (TYPESAFE_API_KEY + CM_JEV_MODEL)

## Configuration (`.env.example`)

| Variable | Default | Notes |
|---|---|---|
| `CM_DB_PATH` | `data/cognitive_mirror.db` | SQLite store |
| `CM_DATABASE_URL` | — | `postgresql://…` selects Postgres instead |
| `CM_API_KEYS` | dev keys | `<key>:<role>` pairs; enterprise refuses dev keys |
| `CM_POLICY_PROFILE` | `default` | `default` / `strict` / `enterprise` |
| `CM_JEV_CONFIG` | — | Jev dimension override JSON |
| `TYPESAFE_API_KEY` | — | Enables live System One cross-check |
| `CM_JEV_MODEL` | `jev-latest` | Live model |
| `CM_ALLOWED_HOSTS` | — | Host allowlist |

## Verification (CI)

```
make test           # 62 passed, 100% coverage gate
make e2e            # PRD §13 workflows + MCP discovery
make perf           # Latency/concurrency against NFR targets
make postgres-test  # Live Postgres round-trip (needs CM_TEST_POSTGRES_URL)
make container-test # compose_smoke.sh → smoke OK; -m container 2 passed
make lint           # Ruff clean
PYTHONPATH=src python -m cognitive_mirror.schemas --check  # schemas up to date
```

CI (`.github/workflows/ci.yml`) repeats all of this plus Docker build, smoke, and container tests on every push and PR.

## Release Process

- **Semantic versioning** — `CHANGELOG.md` records all notable changes.
- **1.0.0** — Initial release (tools, guardrails, audit, console, inbox, live-Jev option).
- **1.1.0** — PostgreSQL backend, CI, changelog (current).
- Next: UI-3 governance dashboard, evaluation harness, feedback learning.

## License

Apache-2.0 — see [LICENSE](LICENSE).