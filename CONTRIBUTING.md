# Contributing

## Setup

```bash
uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -r requirements-dev.txt
export PYTHONPATH=$PWD/src
cp .env.example .env   # never commit .env
```

## Before opening a PR

1. `make test` — must pass with 100% coverage (`--cov-fail-under=100`).
2. `make lint` — Ruff must be clean.
3. `PYTHONPATH=src python -m cognitive_mirror.schemas --check` — committed JSON Schemas must match the models; regenerate with `make schemas` if you changed a contract.
4. Update `test_cases.md` / `test_results.md` if you added or changed behavior.

## Conventions

- Tool contracts in `src/cognitive_mirror/models.py` are the source of truth; the MCP server, REST API, and `schemas/v1/` are generated from them.
- Engines under `src/cognitive_mirror/engine/` stay deterministic and offline. Optional live calls go behind explicit env-gated modules with a fallback, like `jev_live.py`.
- Never commit `.env`, `data/`, or real API keys. Tests use synthetic fixtures only.
