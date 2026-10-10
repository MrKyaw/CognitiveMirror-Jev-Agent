# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.0.0/); versions follow
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [1.1.0] - 2026-10-10

### Added
- PostgreSQL backend via `CM_DATABASE_URL` (SQLite remains the default).
  Same tables and semantics on both backends; `%s` placeholder translation
  and `ON CONFLICT` upserts handled in the store layer.
- `docker compose --profile postgres up` spins up Postgres 16 for local
  evaluation of the new backend.
- Live-Postgres test (`-m postgres`, `CM_TEST_POSTGRES_URL`); CI runs it
  against a postgres service.
- CI workflow (`.github/workflows/ci.yml`): unit suite with 100% gate,
  e2e/perf/postgres, Ruff, schema check, Docker build + smoke + container tests.
- `CHANGELOG.md`.

## [1.0.0] - 2026-10-09

### Added
- Initial release: MCP server with 6 core + 8 support tools.
- Deterministic offline engines (intent, Jev, actions, decision, impact, guardrails).
- Optional live System One / Jev cross-check on `build_jev_profile`.
- REST API, Demo Console (UI-1) and Approval Inbox (UI-2).
- SQLite persistence, audit log, versioned JSON Schemas, reference demos.
- Full test suite at 100% statement + branch coverage.
