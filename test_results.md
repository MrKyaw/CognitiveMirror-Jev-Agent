# Test Results — 2026-10-10 (production slice: CI + PostgreSQL)

Environment: Python 3.12.8, `requirements-dev.txt` venv, `PYTHONPATH=src`.

## Unit suite (`make test`)

- **62 passed, 6 deselected** (perf ×3 + container ×2 + postgres ×1), 0 failed
- **Coverage: 100%** — 1,975 statements, 496 branches, 0 missed (`--cov-fail-under=100` met)
- Per-module: every file under `src/cognitive_mirror` at 100%, incl. dual-backend
  `store.py` and `CM_DATABASE_URL` settings (see `reports/coverage.json`)

## E2E / perf / Postgres / container

| Target | Result |
|---|---|
| `make e2e` (`-m e2e`) | 3 passed — personal 8-step workflow, enterprise guardrail→decision→impact, MCP 14-tool discovery |
| `make perf` (`-m perf`) | 3 passed — lightweight < 1.5 s, deep < 5 s, 20-way concurrency |
| `make postgres-test` (`-m postgres`) | 1 passed live against Postgres 16 Docker (`CM_TEST_POSTGRES_URL`); skips without it |
| `make container-test` | `compose_smoke.sh` → `smoke OK`; `-m container` 2 passed against live `:8000` |

## E2E / perf / container

| Target | Result |
|---|---|
| `make e2e` (`-m e2e`) | 3 passed — personal 8-step workflow, enterprise guardrail→decision→impact, MCP 14-tool discovery |
| `make perf` (`-m perf`) | 3 passed — lightweight < 1.5 s, deep < 5 s, 20-way concurrency |
| `make container-test` | `compose_smoke.sh` → `smoke OK`; `-m container` 2 passed against live `:8000` |

## Lint + schemas

- `make lint` (`ruff check src tests tools`): **All checks passed**
- `python -m cognitive_mirror.schemas --check`: **schemas up to date**

## Container

- `docker build -t cognitive-mirror-jev-mcp:local .`: success
- `docker compose up -d --build --wait`: `Healthy`
- Smoke `POST /v1/tools/mirror_user_intent` → `prepare_interview` 0.451, engine `deterministic/cm-rules-1.0`
