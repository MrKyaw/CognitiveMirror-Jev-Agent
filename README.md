# CognitiveMirror-Jev-MCP

![version](https://img.shields.io/badge/version-1.0.0-blue)
![tests](https://img.shields.io/badge/tests-passing-brightgreen)
![coverage](https://img.shields.io/badge/coverage-100%25-brightgreen)
![lint](https://img.shields.io/badge/ruff-clean-brightgreen)
![docker](https://img.shields.io/badge/docker-healthy-blue)

A reusable **cognitive services layer** for personal and enterprise AI agents —
delivered as an MCP server, a REST API, and a web UI in a single container.

Any MCP-compatible agent can ask: *"What does this user really want, what matters
most, what risks exist, and what action should I take next?"* — and get back
structured intent, Jev persona/context intelligence, decision support, business
impact, and safety guardrails.

Implements [`CognitiveMirror-Jev-MCP_PRD.md`](CognitiveMirror-Jev-MCP_PRD.md).

---

## Contents

- [Why it exists](#why-it-exists)
- [How it works](#how-it-works)
- [Quickstart](#quickstart)
- [Web UIs](#web-uis)
- [Tools reference](#tools-reference)
- [Agent skills](#agent-skills)
- [Configuration](#configuration)
- [Testing](#testing)
- [Container & Docker Hub](#container--docker-hub)
- [Project structure](#project-structure)
- [Roadmap](#roadmap)

---

## Why it exists

Personal agents need more than generic chat. They need durable context, reflective
reasoning, trustworthy action planning, and business-aware interpretation of user
goals. CognitiveMirror-Jev-MCP sits **between the agent and the workflow** as
cognitive middleware — it never replaces the agent; it serves it with tools,
memory, reasoning support, context signals, and guardrails.

| Business objective | What the product does |
|---|---|
| Improve personalization | Mirrors intent, constraints, goals, decision style |
| Reduce repeated context gathering | Memory refs + shared session context across agents |
| Standardize reasoning services | One versioned tool catalog for every agent |
| Improve decision quality | Options, tradeoffs, risks, recommendations |
| Enable safe action | PII redaction, policy profiles, human-approval gates |
| Support enterprise adoption | Audit logs, role-based access, measurable ROI signals |

---

## How it works

```
user request
  └─► personal / enterprise agent (any MCP client)
        ├─► mirror_user_intent      → intent, goals, constraints, urgency, ambiguities
        ├─► build_jev_profile       → persona, journey, emotion, value, judgment
        │     ├─ deterministic lexicon engine (always, offline)
        │     └─ live System One jev cross-check (optional, TYPESAFE_API_KEY set)
        ├─► check_guardrails        → allowed? risk? approval needed? safe alternative?
        ├─► recommend_next_action   → executable instruction + impact + approval flag
        ├─► frame_decision / assess_business_impact   (as needed)
        └─► respond, log outcome, record feedback
```

**Two Jev layers (§7.3).** The deterministic engine always runs offline. When
`TYPESAFE_API_KEY` is set, `build_jev_profile` additionally runs one System One
fan-out call (journey-stage choice + confidence noul, `CM_JEV_MODEL`, default
`jev-latest`): the stage moves only on ≥ 0.6 live confidence and overall
confidence blends with live decisiveness. Cost is input-only ($0.042/Mtok) and
reported in warnings. Any live failure falls back silently — the envelope reads
`engine.mode: hybrid` only when live Jev contributed, `deterministic` otherwise.

---

## Quickstart

**Local (Python 3.12):**

```bash
uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -r requirements-dev.txt
export PYTHONPATH=$PWD/src
make test          # unit tests — 100% coverage enforced
make serve         # REST API on :8000
make mcp           # MCP over stdio (Claude Desktop, etc.)
make demo          # personal + enterprise agent walkthroughs
```

**Docker (recommended):**

```bash
docker compose up -d --build --wait
bash tools/compose_smoke.sh     # → smoke OK
```

Then open [`http://127.0.0.1:8000/ui`](http://127.0.0.1:8000/ui).

**Call the API directly:**

```bash
curl -X POST 127.0.0.1:8000/v1/tools/mirror_user_intent \
  -H 'X-API-Key: dev-agent-key' -H 'Content-Type: application/json' \
  -d '{"user_message":"Draft a follow-up email to my hiring manager for tomorrow"}'
```

**Claude Desktop (MCP stdio):**

```json
{"mcpServers": {"cognitive-mirror": {
  "command": ".venv/bin/python",
  "args": ["-m", "cognitive_mirror.mcp_server", "--transport", "stdio"],
  "cwd": "/path/to/CognitiveMirror-Jev-MCP"
}}}
```

---

## Web UIs

Served by the same container — no extra service. Root `/` redirects to `/ui`.

| UI | URL | Purpose |
|---|---|---|
| UI-1 Demo Console | [`/ui`](http://127.0.0.1:8000/ui) tab 1 | One query box runs the full workflow live; renders mirror summary, Jev signals, guardrail badge, next action, decision, business impact |
| UI-2 Approval Inbox | [`/ui`](http://127.0.0.1:8000/ui) tab 2 | Human-in-the-loop queue for every `human_approval_required` result — approve/reject with reason, audit-logged; `GET /v1/approvals`, `POST /v1/approvals/{id}/decision` |

---

## Tools reference

**Core (every agent workflow):**

| Tool | Returns |
|---|---|
| `mirror_user_intent` | intent labels, explicit/implicit goals, constraints, urgency, ambiguities + clarifications, conflicts, mirror summary, response strategy |
| `build_jev_profile` | persona signals, journey stage, emotions, value drivers, judgment context, autonomy safeguards |
| `recommend_next_action` | recommended action, alternatives, business impact, risks, approval flag, agent instruction |
| `frame_decision` | decision frame, scored options, tradeoffs, risk register, recommendation + rationale |
| `assess_business_impact` | category, benefits, metrics with baseline/delta, cost/effort, ROI hypothesis, 0–100 priority |
| `check_guardrails` | allowed, risk level, issues, redactions, approval flag, safe alternative |

**Support:** `memory_store` · `memory_recall` · `memory_forget` (consent-gated, PII-redacted, expiring) ·
`get_shared_context` (multi-agent sessions) · `record_feedback` · `get_tool_schemas` (versioned) ·
`get_audit_trail` + `list_policy_profiles` (admin/compliance only).

Role model: `agent` · `admin` · `compliance`. Policy profiles: `default` → `strict` → `enterprise`.

---

## Agent skills

Copy-pasteable guides in [`skills/`](skills/) — intent mirroring first,
Jev profiling, decision support, guardrails & governance — plus [`test_cases.md`](test_cases.md)
and [`test_results.md`](test_results.md).

---

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `CM_DEPLOYMENT_MODE` | `local` | `local` / `private_cloud` / `enterprise` (enterprise refuses dev keys) |
| `CM_DB_PATH` | `data/cognitive_mirror.db` | SQLite: memory, audit, shared context, approvals |
| `CM_API_KEYS` | dev keys | `<key>:<agent\|admin\|compliance>` pairs |
| `CM_REQUIRE_AUTH` | `true` | Require API keys on REST |
| `CM_POLICY_PROFILE` | `default` | `default` / `strict` / `enterprise` |
| `CM_JEV_CONFIG` | — | Optional Jev dimension override JSON |
| `TYPESAFE_API_KEY` | — | Optional: enables live System One / Jev cross-check |
| `CM_JEV_MODEL` | `jev-latest` | Live Jev model |
| `CM_LLM_PROVIDER` | `none` | Optional LLM enricher (off by default) |
| `CM_ALLOWED_HOSTS` | — | Host allowlist (DNS-rebinding protection) |

See [`.env.example`](.env.example) for the full list.

---

## Testing

100% statement + branch coverage is enforced (`--cov-fail-under=100`).

| Command | Scope |
|---|---|
| `make test` | Unit suite — 54 passed |
| `make e2e` | PRD workflows + MCP discovery — 3 passed |
| `make perf` | Lightweight < 1.5 s, deep < 5 s, 20-way concurrency — 3 passed |
| `make container-test` | Live container smoke + checks — 2 passed |
| `make lint` | Ruff clean |
| `PYTHONPATH=src python -m cognitive_mirror.schemas --check` | Schema drift check |

---

## Container & Docker Hub

```bash
make docker-build && make up && make compose-smoke && make down
```

Publish / run from Docker Hub:

```bash
docker build -t <yourhub>/cognitive-mirror-jev-mcp:1.0.0 .
docker push <yourhub>/cognitive-mirror-jev-mcp:1.0.0
docker run -d -p 8000:8000 -e CM_API_KEYS=... -v cm-data:/app/data \
  <yourhub>/cognitive-mirror-jev-mcp:1.0.0
```

Health: `GET /health` · Smoke: `tools/compose_smoke.sh` · Data persists in the `cm-data` volume.

---

## Project structure

```
src/cognitive_mirror/
  api.py  mcp_server.py  service.py  store.py      # delivery + dispatch + persistence
  catalog.py  models.py  schemas.py  config.py     # contracts, schemas, settings
  engine/  intent.py  jev.py  actions.py  decision.py  impact.py  guardrails.py
  jev_live.py                                       # optional System One cross-check
  ui.html                                           # UI-1 console + UI-2 inbox
  examples/  personal_agent.py  enterprise_agent.py
skills/  tests/  tools/  test_cases.md  test_results.md
CognitiveMirror-Jev-MCP_PRD.md  README.md  LICENSE
Dockerfile  docker-compose.yml  pyproject.toml  requirements.txt  .env.example  Makefile
```

---

## Roadmap

- **Phase 1 (done):** schemas, 6 core tools, guardrails, audit, Demo Console, Approval Inbox, live-Jev option, reference demos
- **Phase 2:** RBAC hardening, configurable policies, UI-3 Governance Dashboard, evaluation harness, multi-agent examples
- **Phase 3:** advanced Jev scoring, feedback learning, workflow playbooks, marketplace packaging

## License

Apache-2.0 — see [LICENSE](LICENSE). See [CONTRIBUTING.md](CONTRIBUTING.md) for the development workflow and [SECURITY.md](SECURITY.md) for reporting vulnerabilities.
