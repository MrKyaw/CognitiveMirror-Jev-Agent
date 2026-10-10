"""UI-1 console + UI-2 approval inbox (PRD 6A)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from cognitive_mirror.api import create_app
from cognitive_mirror.config import load_settings


@pytest.fixture()
def client():
    return TestClient(create_app(load_settings({"CM_DB_PATH": ":memory:"})))



def test_root_and_ui(client):
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 307 and r.headers["location"] == "/ui"
    r = client.get("/ui")
    assert r.status_code == 200 and "Demo Console" in r.text and "Approval Inbox" in r.text


def test_approval_auth(client):
    assert client.post("/v1/approvals", json={}).status_code == 401
    assert client.get("/v1/approvals").status_code == 401
    assert client.post("/v1/approvals/x/decision", json={}).status_code == 401


def test_approval_validation(client):
    key = {"X-API-Key": "dev-agent-key"}
    assert client.post("/v1/approvals", json={}, headers=key).status_code == 422
    r = client.post("/v1/approvals", json={"planned_action": "x", "risk_level": "nope"},
                    headers=key)
    assert r.status_code == 422
    assert client.get("/v1/approvals?status=nope", headers=key).status_code == 422
    r = client.post("/v1/approvals", content=b"not json",
                    headers={**key, "Content-Type": "application/json"})
    assert r.status_code == 422
    assert client.post("/v1/approvals", json=[1], headers=key).status_code == 422


def test_approval_flow(client):
    key = {"X-API-Key": "dev-agent-key"}
    r = client.post("/v1/approvals", json={"planned_action": "Email a@b.com the offer",
                                           "risk_level": "high", "trace_id": "tr_ui",
                                           "reasons": ["external_action"],
                                           "safe_alternative": "Draft first"},
                    headers=key)
    assert r.status_code == 201
    item = r.json()
    assert item["status"] == "pending"
    assert "[REDACTED_EMAIL]" in item["planned_action"]
    aid = item["id"]
    # non-list reasons fall back to []
    r = client.post("/v1/approvals", json={"planned_action": "Summarize notes",
                                           "reasons": "oops"}, headers=key)
    assert r.status_code == 201
    r = client.get("/v1/approvals", headers=key)
    assert len(r.json()["items"]) == 2
    r = client.get("/v1/approvals?status=pending", headers=key)
    assert len(r.json()["items"]) == 2
    # decide
    r = client.post(f"/v1/approvals/{aid}/decision",
                    json={"decision": "approved", "reason": "looks good"}, headers=key)
    assert r.status_code == 200 and r.json()["status"] == "approved"
    assert client.get("/v1/approvals?status=pending", headers=key).json()["items"]
    # audit trail picked up the decision (admin role)
    admin = {"X-API-Key": "dev-admin-key"}
    trail = client.post("/v1/tools/get_audit_trail", json={"tool": "approval_decision"},
                        headers=admin).json()
    assert trail["result"]["count"] >= 1
    # decide twice -> conflict; bad decision -> 422; unknown id -> 404
    r = client.post(f"/v1/approvals/{aid}/decision", json={"decision": "rejected"},
                    headers=key)
    assert r.status_code == 409
    r = client.post(f"/v1/approvals/{aid}/decision", json={"decision": "maybe"}, headers=key)
    assert r.status_code == 422
    assert client.post("/v1/approvals/appr_missing/decision",
                       json={"decision": "approved"}, headers=key).status_code == 404
    r = client.post(f"/v1/approvals/{aid}/decision", content=b"xx",
                    headers={**key, "Content-Type": "application/json"})
    assert r.status_code == 422
    assert client.post(f"/v1/approvals/{aid}/decision", json=[1], headers=key).status_code \
        == 422


def test_approval_host_block():
    settings = load_settings({"CM_DB_PATH": ":memory:", "CM_ALLOWED_HOSTS": "example.com"})
    c = TestClient(create_app(settings))
    key = {"X-API-Key": "dev-agent-key", "Host": "evil.com"}
    assert c.post("/v1/approvals", json={"planned_action": "x"}, headers=key).status_code \
        == 403
    assert c.get("/v1/approvals", headers=key).status_code == 403
    assert c.post("/v1/approvals/a/decision", json={}, headers=key).status_code == 403


def test_approval_no_auth_mode():
    settings = load_settings({"CM_DB_PATH": ":memory:", "CM_REQUIRE_AUTH": "false"})
    c = TestClient(create_app(settings))
    r = c.post("/v1/approvals", json={"planned_action": "Summarize notes"})
    assert r.status_code == 201
