# CognitiveMirror-Jev-MCP

![ci](https://github.com/MrKyaw/CognitiveMirror-Jev-MCP/actions/workflows/ci.yml/badge.svg)
![license](https://img.shields.io/badge/license-Apache--2.0-blue)

Cognitive middleware for personal and enterprise agents, shipped as one
container: an MCP server, a REST API, and a web UI.

Agents call it to turn a raw user request into structured intent, Jev
persona/context signals, a recommended next action with business impact, and a
safety verdict — before they respond or act. Specified in
[`CognitiveMirror-Jev-MCP_PRD.md`](CognitiveMirror-Jev-MCP_PRD.md).

## Contents

- [Architecture](#architecture)
- [Quickstart](#quickstart)
- [Interface](#interface)
- [Configuration](#configuration)
- [Verification](#verification)
- [Repository layout](#repository-layout)
- [Design decisions](#design-decisions)
- [Roadmap](#roadmap)
- [License](#license)

## Architecture

```
caller (MCP client, browser, or curl)
  ├─ MCP (stdio / streamable-http) ── 14 tools, versioned JSON Schemas
  ├─ REST ── /health · /v1/schemas · POST /v1/tools/{tool} · /v1/approvals/* · /ui
  └─ dispatch (service.py): auth → validate → resolve memory → engine → audit → publish
        ├─ engines (deterministic, offline): intent · jev · actions · decision · impact · guardrails
        ├─ jev_live (optional): one System One fan-out cross-check per profile
        └─ store: SQLite by default, PostgreSQL via CM_DATABASE_URL
```

The canonical agent flow (§13): `mirror_user_intent` → `build_jev_profile` →
`check_guardrails` → `recommend_next_action`, plus `frame_decision` /
`assess_business_impact` when the decision warrants it. Worked examples live in
[`src/cognitive_mirror/examples/`](src/cognitive_mirror/examples/); agent-facing
guides in [`skills/`](skills/).

Two Jev layers (§7.3): the lexicon engine always runs offline. With
`TYPESAFE_API_KEY` set, each profile additionally gets one System One call
(journey-stage choice + confidence noul, `CM_JEV_MODEL`, default `jev-latest`).
The live stage wins only at ≥ 0.6 confidence; overall confidence averages with
live decisiveness; cost ($0.042/Mtok input-only) is reported in warnings. Any
live failure keeps the deterministic result — the envelope reads
`engine.mode: hybrid` only when live Jev contributed.

## Quickstart

Prerequisites: Python 3.12 (local) or Docker (recommended).

```bash
# local
uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -r requirements-dev.txt
export PYTHONPATH=$PWD/src
make test          # unit suite, 100% coverage enforced
make serve         # REST on 127.0.0.1:8000
make mcp           # MCP over stdio
make demo          # personal + enterprise walkthroughs

# container
docker compose up -d --build --wait
bash tools/compose_smoke.sh
```

Then open `http://127.0.0.1:8000/ui`.

PostgreSQL instead of SQLite:

```bash
CM_DATABASE_URL=postgresql://cm:cm@db:5432/cm docker compose --profile postgres up -d --build --wait
```

Claude Desktop:

```json
{"mcpServers": {"cognitive-mirror": {
  "command": ".venv/bin/python",
  "args": ["-m", "cognitive_mirror.mcp_server", "--transport", "stdio"],
  "cwd": "/path/to/CognitiveMirror-Jev-MCP"
}}}
```

## Interface

**Core tools** (every workflow): `mirror_user_intent` ·
`build_jev_profile` · `recommend_next_action` · `frame_decision` ·
`assess_business_impact` · `check_guardrails`.

**Support**: `memory_store` · `memory_recall` · `memory_forget`
(consent-gated, PII-redacted, expiring) · `get_shared_context` ·
`record_feedback` · `get_tool_schemas` · `get_audit_trail` and
`list_policy_profiles` (admin/compliance only).

Roles: `agent` · `admin` · `compliance`. Policies: `default` → `strict` →
`enterprise`. Full contracts: [`test_cases.md`](test_cases.md); measured
results: [`test_results.md`](test_results.md).

**UIs** (same container, `/` redirects to `/ui`): UI-1 Demo Console runs the
full workflow from one query box; UI-2 Approval Inbox queues every
`human_approval_required` result for approve/reject with reason
(`GET /v1/approvals`, `POST /v1/approvals/{id}/decision`, audit-logged).

Direct call example:

```bash
curl -X POST 127.0.0.1:8000/v1/tools/mirror_user_intent \
  -H 'X-API-Key: dev-agent-key' -H 'Content-Type: application/json' \
  -d '{"user_message":"Draft a follow-up email to my hiring manager for tomorrow"}'
```

## Configuration

| Variable | Default | Notes |
|---|---|---|
| `CM_DB_PATH` | `data/cognitive_mirror.db` | SQLite store |
| `CM_DATABASE_URL` | — | `postgresql://…` selects Postgres instead |
| `CM_API_KEYS` | dev keys | `<key>:<role>` pairs; enterprise mode refuses dev keys |
| `CM_POLICY_PROFILE` | `default` | `default` / `strict` / `enterprise` |
| `CM_JEV_CONFIG` | — | Jev dimension override JSON |
| `TYPESAFE_API_KEY` | — | Enables the live System One cross-check |
| `CM_JEV_MODEL` | `jev-latest` | Live model |
| `CM_ALLOWED_HOSTS` | — | Host allowlist |

Full list: [`.env.example`](.env.example). Never commit `.env`.

## Verification

100% statement + branch coverage is enforced in CI and locally
(`--cov-fail-under=100`). Current state: 62 unit tests green, e2e 3, perf 3
(< 1.5 s lightweight, < 5 s deep, 20-way concurrency), live-Postgres 1,
container 2, Ruff clean, committed schemas byte-identical to models.

```bash
make test && make e2e && make perf && make lint
PYTHONPATH=src python -m cognitive_mirror.schemas --check
CM_TEST_POSTGRES_URL=postgresql://… make postgres-test
```

CI (`.github/workflows/ci.yml`) repeats all of this plus a Docker build,
smoke, and container tests on every push and PR.

## Repository layout

```
src/cognitive_mirror/  api · mcp_server · service · store · jev_live · ui.html
                       catalog · models · schemas · config · engine/ · examples/
skills/                per-workflow agent guides
tests/                 unit · e2e · perf · postgres · container
test_cases.md  test_results.md  CHANGELOG.md
Dockerfile  docker-compose.yml  pyproject.toml  Makefile
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the change workflow and
[SECURITY.md](SECURITY.md) for vulnerability reporting.

## Design decisions

- **Deterministic first.** Rule/lexicon engines are the source of truth; live
  models only cross-check. The system is fully usable air-gapped.
- **Contracts before transports.** Pydantic models generate the MCP schemas,
  the REST validation, and the committed `schemas/v1/` files from one place.
- **One placeholder style.** SQL is written once with `?`; the store
  translates for Postgres. Same tables, same semantics, both backends.
- **Advisory guardrails, enforced workflow.** The server judges and redacts;
  the calling agent (or the inbox human) decides. High-impact paths require
  explicit approval by design, not by convention.
- **No PII at rest in the clear.** Writes are redacted, reads are refs, audit
  is redacted, enterprise refuses dev keys.

## Roadmap

- **1.0** (done): tools, guardrails, audit, console, inbox, live-Jev option
- **1.1** (done): Postgres backend, CI, changelog
- Next: UI-3 governance dashboard, evaluation harness, feedback learning

## License

Apache-2.0 — see [LICENSE](LICENSE).
