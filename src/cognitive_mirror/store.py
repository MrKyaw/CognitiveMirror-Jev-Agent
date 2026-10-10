"""SQLite persistence: memory, audit, shared context, feedback (PRD 9.1, 9.3, 10)."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


class Store:
    def __init__(self, db_path: Path | str, retention_days: int = 30,
                 shared_ttl_minutes: int = 240) -> None:
        self.db_path = Path(db_path)
        self.retention_days = retention_days
        self.shared_ttl = shared_ttl_minutes
        self._mem_conn: sqlite3.Connection | None = None
        if str(db_path) == ":memory:":
            self._mem_conn = sqlite3.connect(":memory:", check_same_thread=False)
            self._mem_conn.row_factory = sqlite3.Row
        else:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        if self._mem_conn is not None:
            return self._mem_conn
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self) -> None:
        with self._connect() as conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS memories(
              ref TEXT PRIMARY KEY, subject_id TEXT NOT NULL, kind TEXT NOT NULL,
              content TEXT NOT NULL, tags TEXT NOT NULL DEFAULT '[]',
              created_at TEXT NOT NULL, expires_at TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS idx_mem_subject ON memories(subject_id);
            CREATE TABLE IF NOT EXISTS audit(
              request_id TEXT PRIMARY KEY, trace_id TEXT NOT NULL, session_id TEXT,
              tool TEXT NOT NULL, tool_version TEXT NOT NULL, caller_role TEXT NOT NULL,
              agent_id TEXT, status TEXT NOT NULL, error_code TEXT, engine_mode TEXT NOT NULL,
              model_version TEXT NOT NULL, input_hash TEXT NOT NULL,
              input_redacted TEXT NOT NULL, output_redacted TEXT,
              policy_decision TEXT, latency_ms REAL NOT NULL, created_at TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS idx_audit_trace ON audit(trace_id);
            CREATE TABLE IF NOT EXISTS shared(
              id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL, tool TEXT NOT NULL,
              request_id TEXT NOT NULL, trace_id TEXT NOT NULL, caller_role TEXT NOT NULL,
              agent_id TEXT, created_at TEXT NOT NULL, result TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS idx_shared_session ON shared(session_id);
            CREATE TABLE IF NOT EXISTS feedback(
              feedback_id TEXT PRIMARY KEY, request_id TEXT NOT NULL, rating INTEGER NOT NULL,
              useful INTEGER NOT NULL, outcome TEXT NOT NULL, comment TEXT NOT NULL DEFAULT '',
              created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS approvals(
              id TEXT PRIMARY KEY, trace_id TEXT NOT NULL DEFAULT '',
              planned_action TEXT NOT NULL, risk_level TEXT NOT NULL DEFAULT 'medium',
              reasons TEXT NOT NULL DEFAULT '[]', safe_alternative TEXT,
              status TEXT NOT NULL DEFAULT 'pending', decided_by TEXT,
              decision_reason TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL,
              decided_at TEXT);
            CREATE INDEX IF NOT EXISTS idx_approvals_status ON approvals(status);
            """)

    # ------------------------------------------------------------- memories
    def memory_store(self, subject_id: str, content: str, kind: str, redactions: list[str],
                     ttl_days: int | None, tags: list[str]) -> tuple[str, str]:
        ref = "mem_" + uuid.uuid4().hex[:12]
        now = _utcnow()
        days = ttl_days if ttl_days is not None else self.retention_days
        expires = _iso(now + timedelta(days=days))
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO memories(ref,subject_id,kind,content,tags,created_at,expires_at)"
                " VALUES(?,?,?,?,?,?,?)",
                (ref, subject_id, kind, content, json.dumps(tags), _iso(now), expires))
        return ref, expires

    def memory_get(self, ref: str, subject_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM memories WHERE ref=?", (ref,)).fetchone()
        if row is None or row["subject_id"] != subject_id:
            return None
        return dict(row)

    def memory_recall(self, subject_id: str, query: str, refs: list[str],
                      kind: str, limit: int) -> tuple[list[dict[str, Any]], list[str]]:
        q = query.lower().strip()
        with self._connect() as conn:
            if refs:
                holders = ",".join("?" for _ in refs)
                rows = conn.execute(
                    f"SELECT * FROM memories WHERE ref IN ({holders})", refs).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM memories WHERE subject_id=? ORDER BY created_at DESC LIMIT 200",
                    (subject_id,)).fetchall()
        items = [dict(r) for r in rows
                 if r["subject_id"] == subject_id and (kind == "any" or r["kind"] == kind)]
        now = _utcnow()
        live = [r for r in items if datetime.fromisoformat(r["expires_at"]) > now]
        if q and not refs:
            scored = sorted(live, key=lambda r: (
                0 if q in (r["content"] or "").lower() else 1, r["created_at"]), reverse=False)
            live = scored
        missing = [r for r in refs if r not in {x["ref"] for x in items}]
        return live[:limit], missing

    def memory_forget(self, subject_id: str, ref: str | None) -> int:
        with self._connect() as conn:
            if ref is None:
                cur = conn.execute("DELETE FROM memories WHERE subject_id=?", (subject_id,))
            else:
                cur = conn.execute("DELETE FROM memories WHERE ref=? AND subject_id=?",
                                   (ref, subject_id))
            return cur.rowcount

    # ------------------------------------------------------------- audit / shared / feedback
    def audit_write(self, record: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO audit(request_id,trace_id,session_id,tool,tool_version,"
                "caller_role,agent_id,status,error_code,engine_mode,model_version,input_hash,"
                "input_redacted,output_redacted,policy_decision,latency_ms,created_at)"
                " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (record["request_id"], record["trace_id"], record.get("session_id"),
                 record["tool"], record["tool_version"], record["caller_role"],
                 record.get("agent_id"), record["status"], record.get("error_code"),
                 record["engine_mode"], record["model_version"], record["input_hash"],
                 json.dumps(record["input_redacted"], default=str),
                 json.dumps(record.get("output_redacted"), default=str)
                 if record.get("output_redacted") is not None else None,
                 json.dumps(record.get("policy_decision"), default=str)
                 if record.get("policy_decision") is not None else None,
                 record["latency_ms"], record["created_at"]))

    def audit_query(self, request_id: str | None, trace_id: str | None,
                    tool: str | None, limit: int) -> list[dict[str, Any]]:
        query = "SELECT * FROM audit WHERE 1=1"
        args: list[Any] = []
        if request_id:
            query += " AND request_id=?"
            args.append(request_id)
        if trace_id:
            query += " AND trace_id=?"
            args.append(trace_id)
        if tool:
            query += " AND tool=?"
            args.append(tool)
        query += " ORDER BY created_at DESC LIMIT ?"
        args.append(limit)
        with self._connect() as conn:
            rows = conn.execute(query, args).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            for key in ("input_redacted", "output_redacted", "policy_decision"):
                if d[key] is not None:
                    d[key] = json.loads(d[key])
            out.append(d)
        return out

    def audit_has(self, request_id: str) -> bool:
        with self._connect() as conn:
            row = conn.execute("SELECT 1 FROM audit WHERE request_id=?",
                               (request_id,)).fetchone()
        return row is not None

    def shared_publish(self, session_id: str, entry: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO shared(session_id,tool,request_id,trace_id,caller_role,agent_id,"
                "created_at,result) VALUES(?,?,?,?,?,?,?,?)",
                (session_id, entry["tool"], entry["request_id"], entry["trace_id"],
                 entry["caller_role"], entry.get("agent_id"), entry["created_at"],
                 json.dumps(entry["result"], default=str)))

    def shared_get(self, session_id: str | None) -> list[dict[str, Any]]:
        if not session_id:
            return []
        cutoff = _iso(_utcnow() - timedelta(minutes=self.shared_ttl))
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM shared WHERE session_id=? AND created_at>=? ORDER BY id ASC LIMIT 50",
                (session_id, cutoff)).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["result"] = json.loads(d["result"])
            out.append(d)
        return out

    def feedback_write(self, request_id: str, rating: int, useful: bool,
                       outcome: str, comment: str) -> str:
        fid = "fb_" + uuid.uuid4().hex[:12]
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO feedback(feedback_id,request_id,rating,useful,outcome,comment,"
                "created_at) VALUES(?,?,?,?,?,?,?)",
                (fid, request_id, rating, 1 if useful else 0, outcome, comment, _iso(_utcnow())))
        return fid

    # ------------------------------------------------------------- approvals (UI-2 inbox)
    def approval_create(self, planned_action: str, risk_level: str, trace_id: str,
                        reasons: list[str], safe_alternative: str | None) -> dict[str, Any]:
        from cognitive_mirror.engine.guardrails import redact

        redacted, _findings = redact(planned_action)
        aid = "appr_" + uuid.uuid4().hex[:12]
        now = _iso(_utcnow())
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO approvals(id,trace_id,planned_action,risk_level,reasons,"
                "safe_alternative,status,created_at) VALUES(?,?,?,?,?,?,?,?)",
                (aid, trace_id, redacted, risk_level, json.dumps(reasons),
                 safe_alternative, "pending", now))
        row = self.approval_get(aid)
        assert row is not None  # just inserted above
        return row

    def approval_get(self, approval_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM approvals WHERE id=?", (approval_id,)).fetchone()
        if row is None:
            return None
        d = dict(row)
        d["reasons"] = json.loads(d["reasons"])
        return d

    def approval_list(self, status: str | None) -> list[dict[str, Any]]:
        with self._connect() as conn:
            if status:
                rows = conn.execute(
                    "SELECT * FROM approvals WHERE status=? ORDER BY created_at DESC LIMIT 100",
                    (status,)).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM approvals ORDER BY created_at DESC LIMIT 100").fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["reasons"] = json.loads(d["reasons"])
            out.append(d)
        return out

    def approval_decide(self, approval_id: str, decision: str, reason: str,
                        decided_by: str) -> dict[str, Any] | None:
        row = self.approval_get(approval_id)
        if row is None:
            return None
        if row["status"] != "pending":
            raise ValueError(f"Approval {approval_id} is already {row['status']}")
        now = _iso(_utcnow())
        with self._connect() as conn:
            conn.execute(
                "UPDATE approvals SET status=?,decided_by=?,decision_reason=?,decided_at=? "
                "WHERE id=?",
                (decision, decided_by, reason, now, approval_id))
        return self.approval_get(approval_id)


def input_hash(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def new_request_id() -> str:
    return "req_" + uuid.uuid4().hex


def now_ms() -> float:
    return time.time() * 1000.0
