"""Service dispatch, store, memory flows."""
from __future__ import annotations


def test_core_dispatch(svc):
    m = svc.call("mirror_user_intent", {"user_message": "Draft an email to my manager"}, "agent")
    assert m["result"]["primary_intent"]["label"]
    assert m["engine"]["mode"] == "deterministic"
    j = svc.call("build_jev_profile", {"context": "interview prep, senior engineer"}, "agent")
    assert j["result"]["journey_stage"]["stage"]
    n = svc.call("recommend_next_action", {"intent_summary": "draft email"}, "agent")
    assert n["result"]["agent_instruction"]
    d = svc.call("frame_decision", {"decision_question": "Should we renew?"}, "agent")
    assert d["result"]["recommended_option"]
    i = svc.call("assess_business_impact", {"request": "save time on reports"}, "agent")
    assert i["result"]["priority_score"] >= 0
    g = svc.call("check_guardrails", {"planned_action": "Summarize notes"}, "agent")
    assert g["result"]["allowed"]


def test_errors(svc):
    assert svc.call("mirror_user_intent", {"user_message": "hi"}, None)["error"]["code"] == \
        "unauthorized"
    assert svc.call("nope_tool", {}, "agent")["error"]["code"] == "unknown_tool"
    assert svc.call("get_audit_trail", {}, "agent")["error"]["code"] == "forbidden"
    bad = svc.call("mirror_user_intent", {"user_message": ""}, "agent")
    assert bad["error"]["code"] == "invalid_input"
    nf = svc.call("get_tool_schemas", {"tool": "nope"}, "agent")
    assert nf["error"]["code"] == "not_found"
    fb = svc.call("memory_forget", {"subject_id": "u"}, "agent")
    assert fb["error"]["code"] == "forbidden"


def test_memory_roundtrip(svc):
    no_consent = svc.call("memory_store", {"subject_id": "u1", "content": "hello"}, "agent")
    assert no_consent["result"]["stored"] is False
    yes = svc.call("memory_store", {"subject_id": "u1", "content": "Contact a@b.com",
                                    "consent": True, "tags": ["t"]}, "agent")
    ref = yes["result"]["memory_ref"]
    assert yes["result"]["redactions"] == ["email"]
    rec = svc.call("memory_recall", {"subject_id": "u1", "query": "contact"}, "agent")
    assert rec["result"]["items"]
    by_ref = svc.call("memory_recall", {"subject_id": "u1", "refs": [ref]}, "agent")
    assert by_ref["result"]["items"][0]["ref"] == ref
    missing = svc.call("memory_recall", {"subject_id": "u1", "refs": ["mem_missing"]}, "agent")
    assert missing["result"]["missing_refs"] == ["mem_missing"]
    empty = svc.call("memory_recall", {"subject_id": "nobody", "query": "x"}, "agent")
    assert empty["result"]["note"]
    # intent with memory refs resolved/expired/missing/out_of_scope
    m = svc.call("mirror_user_intent", {"user_message": "summarize my notes please for real",
                                        "available_memory_refs": [ref],
                                        "subject_id": "u1"}, "agent")
    assert m["result"]["memory_used"][0]["status"] == "resolved"
    m2 = svc.call("mirror_user_intent", {"user_message": "summarize my notes please for real",
                                         "available_memory_refs": ["mem_nope"],
                                         "subject_id": "u1"}, "agent")
    assert m2["result"]["memory_used"][0]["status"] == "missing"
    m3 = svc.call("mirror_user_intent", {"user_message": "summarize my notes please for real",
                                         "available_memory_refs": [ref],
                                         "subject_id": "other"}, "agent")
    assert m3["result"]["memory_used"][0]["status"] == "out_of_scope"
    fg = svc.call_as("memory_forget", {"subject_id": "u1", "ref": ref}, "agent")
    assert fg["result"]["deleted"] == 1
    fg_all_denied = svc.call_as("memory_forget", {"subject_id": "u1"}, "agent")
    assert fg_all_denied["error"]["code"] == "forbidden"
    svc.call("memory_store", {"subject_id": "u1", "content": "x", "consent": True}, "agent")
    fg_all = svc.call_as("memory_forget", {"subject_id": "u1"}, "admin")
    assert fg_all["result"]["deleted"] >= 1


def test_memory_expiry(svc, store):
    yes = svc.call("memory_store", {"subject_id": "exp", "content": "old note",
                                    "consent": True, "ttl_days": 1}, "agent")
    ref = yes["result"]["memory_ref"]
    with store._connect() as conn:
        conn.execute("UPDATE memories SET expires_at='2000-01-01T00:00:00+00:00' WHERE ref=?",
                     (ref,))
    m = svc.call("mirror_user_intent", {"user_message": "summarize my notes please for real",
                                        "available_memory_refs": [ref],
                                        "subject_id": "exp"}, "agent")
    assert m["result"]["memory_used"][0]["status"] == "expired"


def test_jev_persist_and_shared(svc):
    j = svc.call("build_jev_profile", {"context": "hello", "persist": True}, "agent")
    assert "consent" in j["warnings"][0]
    j2 = svc.call("build_jev_profile", {"subject": {"id": "u2"}, "context": "hello",
                                        "persist": True, "consent": True}, "agent")
    assert j2["result"]["profile_ref"].startswith("mem_")
    s = svc.call("mirror_user_intent", {"user_message": "Plan the launch for real please",
                                        "session_id": "sess1"}, "agent")
    assert s["session_id"] == "sess1"
    sh = svc.call("get_shared_context", {"session_id": "sess1"}, "agent")
    assert sh["result"]["entries"]
    assert "mirror_user_intent" in sh["result"]["latest_by_tool"]
    assert svc.call("get_shared_context", {}, "agent")["result"]["entries"] == []


def test_feedback_audit_policies(svc):
    m = svc.call("mirror_user_intent", {"user_message": "Summarize the report fully"}, "agent")
    rid = m["request_id"]
    fb = svc.call("record_feedback", {"request_id": rid, "rating": 5}, "agent")
    assert fb["result"]["request_found"] is True
    fb2 = svc.call("record_feedback", {"request_id": "req_" + "a" * 32, "rating": 2}, "agent")
    assert fb2["result"]["request_found"] is False
    assert fb2["warnings"]
    sc = svc.call("get_tool_schemas", {}, "agent")
    assert "mirror_user_intent" in sc["result"]["tools"]
    sc1 = svc.call("get_tool_schemas", {"tool": "mirror_user_intent"}, "agent")
    assert list(sc1["result"]["tools"]) == ["mirror_user_intent"]
    at = svc.call_as("get_audit_trail", {"limit": 5}, "admin")
    assert at["result"]["count"] >= 1
    at2 = svc.call_as("get_audit_trail", {"request_id": rid}, "admin")
    assert at2["result"]["count"] == 1
    lp = svc.call_as("list_policy_profiles", {}, "compliance")
    assert lp["result"]["active_profile"] == "default"
    # store-level filters
    recs = svc.store.audit_query(None, m["trace_id"], "mirror_user_intent", 5)
    assert recs
    assert svc.store.audit_has(rid)
    assert not svc.store.audit_has("req_" + "b" * 32)


def test_store_direct(store):
    ref, _exp = store.memory_store("s", "content here", "context", [], None, [])
    assert store.memory_get(ref, "s")["ref"] == ref
    assert store.memory_get(ref, "other") is None
    assert store.memory_get("mem_nope", "s") is None
    live, missing = store.memory_recall("s", "", [], "context", 10)
    assert live and missing == []
    live, _ = store.memory_recall("s", "content", [], "any", 10)
    assert live[0]["ref"] == ref
    assert store.memory_forget("s", ref) == 1
    assert store.memory_forget("s", "mem_nope") == 0
    fid = store.feedback_write("req_" + "c" * 32, 4, True, "accepted", "ok")
    assert fid.startswith("fb_")
    assert store.shared_get(None) == []
    store.shared_publish("ss", {"tool": "t", "request_id": "r", "trace_id": "t",
                                "caller_role": "agent", "agent_id": None,
                                "created_at": "2000-01-01T00:00:00+00:00", "result": {}})
    assert store.shared_get("ss") == []
