"""API + MCP server + examples."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from cognitive_mirror.api import _role_from_headers, create_app
from cognitive_mirror.config import load_settings
from cognitive_mirror.examples import enterprise_agent, personal_agent


@pytest.fixture()
def client():
    settings = load_settings({"CM_DB_PATH": ":memory:"})
    return TestClient(create_app(settings))


def test_health_and_schemas(client):
    r = client.get("/health")
    assert r.status_code == 200 and "mirror_user_intent" in r.json()["tools"]
    assert client.get("/v1/schemas").status_code == 200
    assert client.get("/v1/schemas/mirror_user_intent").status_code == 200
    assert client.get("/v1/schemas/nope").status_code == 404


def test_tool_auth_and_calls(client):
    assert client.post("/v1/tools/mirror_user_intent", json={"user_message": "hi"}).status_code \
        == 401
    r = client.post("/v1/tools/mirror_user_intent", json={"user_message": "Summarize fully"},
                    headers={"X-API-Key": "dev-agent-key"})
    assert r.status_code == 200 and "result" in r.json()
    r = client.post("/v1/tools/mirror_user_intent", json={"user_message": ""},
                    headers={"Authorization": "Bearer dev-agent-key"})
    assert r.status_code == 422
    r = client.post("/v1/tools/nope_tool", json={}, headers={"X-API-Key": "dev-agent-key"})
    assert r.status_code == 404
    r = client.post("/v1/tools/get_audit_trail", json={},
                    headers={"X-API-Key": "dev-agent-key"})
    assert r.status_code == 403
    # invalid json body + non-dict payload + agent header
    r = client.post("/v1/tools/mirror_user_intent", content=b"not json",
                    headers={"X-API-Key": "dev-agent-key",
                             "Content-Type": "application/json"})
    assert r.status_code in (200, 422)
    r = client.post("/v1/tools/mirror_user_intent", json=[1, 2],
                    headers={"X-API-Key": "dev-agent-key"})
    assert r.status_code == 422
    r = client.post("/v1/tools/mirror_user_intent",
                    json={"user_message": "Summarize the quarterly report fully",
                          "session_id": "s1"},
                    headers={"X-API-Key": "dev-admin-key", "X-Agent-ID": "a1"})
    assert r.status_code == 200


def test_allowed_hosts():
    settings = load_settings({"CM_DB_PATH": ":memory:", "CM_ALLOWED_HOSTS": "example.com"})
    c = TestClient(create_app(settings))
    r = c.post("/v1/tools/mirror_user_intent", json={"user_message": "hi all there folks"},
               headers={"X-API-Key": "dev-agent-key", "Host": "evil.com"})
    assert r.status_code == 403
    r = c.get("/health")
    assert r.status_code == 200


def test_no_auth_mode():
    settings = load_settings({"CM_DB_PATH": ":memory:", "CM_REQUIRE_AUTH": "false"})
    assert _role_from_headers(settings, None, None) == "agent"
    assert _role_from_headers(settings, "dev-agent-key", None) == "agent"
    assert _role_from_headers(settings, None, "Bearer dev-agent-key") == "agent"
    c = TestClient(create_app(settings))
    assert c.post("/v1/tools/mirror_user_intent",
                  json={"user_message": "Summarize fully"}).status_code == 200


def test_mcp_wrappers():
    from cognitive_mirror import mcp_server as ms
    from cognitive_mirror.config import load_settings as ls
    ms.configure(ls({"CM_DB_PATH": ":memory:"}))
    assert ms.t_mirror("Draft an email to my manager for real")["result"]
    assert ms.t_jev("interview context")["result"]
    assert ms.t_next("draft email")["result"]
    assert ms.t_frame("Should we renew the contract?")["result"]
    assert ms.t_impact("save time on reports")["result"]
    assert ms.t_guard("Summarize notes")["result"]
    stored = ms.t_mstore("u9", "hello world note", consent=True)
    ref = stored["result"]["memory_ref"]
    assert ref
    assert ms.t_mrecall("u9", query="hello")["result"]["items"]
    assert ms.t_mforget("u9", ref=ref)["result"]["deleted"] == 1
    assert ms.t_shared("none")["result"]["entries"] == []
    got = ms.t_mirror("Summarize the report fully now", session_id="mcp1")
    fb = ms.t_feedback(got["request_id"], 5)
    assert fb["result"]["recorded"]
    assert ms.t_schemas("mirror_user_intent")["result"]
    assert ms.t_schemas()["result"]
    import pytest as _pt
    with _pt.raises(AssertionError):
        ms.SERVICE = None
        ms._call("mirror_user_intent", {})
    ms.configure(ls({"CM_DB_PATH": ":memory:"}))
    # governance wrappers are forbidden for agent role -> error envelopes, still covered
    assert ms.t_audit()["error"]["code"] == "forbidden"
    assert ms.t_policies()["error"]["code"] == "forbidden"


def test_examples():
    p = personal_agent.run_demo()
    assert p["action"]["result"]["agent_instruction"]
    e = enterprise_agent.run_demo()
    assert e["decision"]["result"]["recommended_option"]
    assert e["guard"]["result"]
