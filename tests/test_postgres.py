"""PostgreSQL backend (CM_DATABASE_URL). Fakes keep unit runs offline; the live
test runs in CI against the postgres service (or skips without CM_TEST_POSTGRES_URL)."""
from __future__ import annotations

import os
import sys

import pytest

from cognitive_mirror.config import ConfigError, load_settings
from cognitive_mirror.engine.lexicons import load_lexicon
from cognitive_mirror.service import Service
from cognitive_mirror.store import Store

PG_URL = "postgresql://cm:cm@localhost:5432/cm"


class FakeCursor:
    def __init__(self, conn: FakeConn) -> None:
        self._conn = conn
        self.rowcount = conn.rowcount

    def execute(self, sql: str, args=()) -> FakeCursor:
        self._conn.statements.append((sql, list(args)))
        return self

    def fetchone(self):
        return self._conn.pop_one()

    def fetchall(self):
        return self._conn.rows


class FakeConn:
    def __init__(self, ones=None, rows=None, rowcount: int = 1) -> None:
        self.statements: list[tuple[str, list]] = []
        self._ones = list(ones or [])
        self.rows = rows or []
        self.rowcount = rowcount

    def pop_one(self):
        return self._ones.pop(0) if self._ones else None

    def execute(self, sql: str, args=()) -> FakeCursor:
        return FakeCursor(self).execute(sql, args)

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> bool:
        return False


@pytest.fixture()
def pg_store(monkeypatch):
    fake = FakeConn()
    monkeypatch.setattr(Store, "_connect", lambda self: fake)
    store = Store(":memory:", db_url=PG_URL)
    return store, fake


def test_pg_init_schema(pg_store):
    _store, fake = pg_store
    ddl = " ".join(sql for sql, _ in fake.statements)
    assert "SERIAL PRIMARY KEY" in ddl
    assert "AUTOINCREMENT" not in ddl
    assert "?" not in ddl


def test_pg_memory_roundtrip(pg_store):
    store, fake = pg_store
    store.memory_store("u", "hello", "context", [], None, ["t"])
    assert "%s" in fake.statements[-1][0]
    fake._ones.append({"ref": "mem_1", "subject_id": "u", "kind": "context",
                       "content": "hello", "tags": "[]",
                       "created_at": "2026-01-01T00:00:00+00:00",
                       "expires_at": "2027-01-01T00:00:00+00:00"})
    assert store.memory_get("mem_1", "u")["content"] == "hello"
    fake.rows = [{"ref": "mem_1", "subject_id": "u", "kind": "context", "content": "hello",
                  "tags": "[]", "created_at": "2026-01-01T00:00:00+00:00",
                  "expires_at": "2027-01-01T00:00:00+00:00"}]
    live, missing = store.memory_recall("u", "hello", [], "any", 10)
    assert live and missing == []
    assert store.memory_forget("u", "mem_1") == 1


def test_pg_audit_upsert(pg_store):
    store, fake = pg_store
    store.audit_write({"request_id": "req_x", "trace_id": "t", "session_id": None,
                       "tool": "mirror_user_intent", "tool_version": "1.0.0",
                       "caller_role": "agent", "agent_id": None, "status": "ok",
                       "error_code": None, "engine_mode": "deterministic",
                       "model_version": "m", "input_hash": "h", "input_redacted": {},
                       "output_redacted": None, "policy_decision": None,
                       "latency_ms": 1.0, "created_at": "2026-01-01T00:00:00+00:00"})
    assert "ON CONFLICT(request_id) DO UPDATE SET" in fake.statements[-1][0]


def test_pg_approvals(pg_store):
    store, fake = pg_store
    pending = {"id": "appr_1", "trace_id": "", "planned_action": "x", "risk_level": "high",
               "reasons": "[]", "safe_alternative": None, "status": "pending",
               "decided_by": None, "decision_reason": "",
               "created_at": "2026-01-01T00:00:00+00:00", "decided_at": None}
    decided = dict(pending, status="approved")
    fake._ones.append(dict(pending))
    created = store.approval_create("Do the thing", "high", "", [], None)
    assert created["id"] == "appr_1"
    fake._ones.append(dict(pending))
    fake._ones.append(dict(decided))
    out = store.approval_decide("appr_1", "approved", "ok", "admin")
    assert out["status"] == "approved"


def test_pg_service_resolve_out_of_scope(monkeypatch):
    other = {"subject_id": "other", "expires_at": "2027-01-01"}
    fake = FakeConn(ones=[dict(other), dict(other)])
    monkeypatch.setattr(Store, "_connect", lambda self: fake)
    settings = load_settings({"CM_DB_PATH": ":memory:"})
    svc = Service(settings, Store(":memory:", db_url=PG_URL), load_lexicon())
    out = svc.call("mirror_user_intent",
                   {"user_message": "Summarize my notes please for real",
                    "available_memory_refs": ["mem_x"], "subject_id": "u"}, "agent")
    assert out["result"]["memory_used"][0]["status"] == "out_of_scope"


def test_pg_missing_driver(monkeypatch):
    monkeypatch.setitem(sys.modules, "psycopg", None)
    monkeypatch.setitem(sys.modules, "psycopg.rows", None)
    with pytest.raises(RuntimeError, match="psycopg is not installed"):
        Store(":memory:", db_url=PG_URL)


def test_pg_connect_failure(monkeypatch):
    import psycopg

    def _down(*args, **kwargs):
        raise ConnectionError("db is down")

    monkeypatch.setattr(psycopg, "connect", _down)
    with pytest.raises(ConnectionError, match="db is down"):
        Store(":memory:", db_url=PG_URL)


def test_config_database_url():
    s = load_settings({"CM_DB_PATH": ":memory:", "CM_DATABASE_URL": PG_URL})
    assert s.database_url == PG_URL
    assert load_settings({"CM_DB_PATH": ":memory:"}).database_url == ""
    with pytest.raises(ConfigError, match="postgresql://"):
        load_settings({"CM_DB_PATH": ":memory:", "CM_DATABASE_URL": "mysql://x"})


@pytest.mark.postgres()
def test_pg_live():
    url = os.environ.get("CM_TEST_POSTGRES_URL", "")
    if not url:
        pytest.skip("CM_TEST_POSTGRES_URL not set")
    store = Store(":memory:", db_url=url)
    ref, _ = store.memory_store("live", "hello postgres", "context", [], None, [])
    assert store.memory_get(ref, "live")["content"] == "hello postgres"
    store.audit_write({"request_id": "req_live", "trace_id": "t", "session_id": None,
                       "tool": "mirror_user_intent", "tool_version": "1.0.0",
                       "caller_role": "agent", "agent_id": None, "status": "ok",
                       "error_code": None, "engine_mode": "deterministic",
                       "model_version": "m", "input_hash": "h", "input_redacted": {},
                       "output_redacted": None, "policy_decision": None,
                       "latency_ms": 1.0, "created_at": "2026-01-01T00:00:00+00:00"})
    assert store.audit_has("req_live")
    store.memory_forget("live", ref)
