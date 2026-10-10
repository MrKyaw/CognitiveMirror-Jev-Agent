"""Latency/concurrency targets from PRD 10 (run with `make perf`)."""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor

import pytest

pytestmark = pytest.mark.perf

from cognitive_mirror.config import load_settings
from cognitive_mirror.engine.lexicons import load_lexicon
from cognitive_mirror.service import Service
from cognitive_mirror.store import Store


def _svc() -> Service:
    s = load_settings({"CM_DB_PATH": ":memory:"})
    return Service(s, Store(":memory:"), load_lexicon())


def test_lightweight_latency():
    svc = _svc()
    start = time.perf_counter()
    out = svc.call("mirror_user_intent", {"user_message": "Summarize the report fully now"},
                   "agent")
    assert "error" not in out
    assert time.perf_counter() - start < 1.5


def test_deep_latency():
    svc = _svc()
    start = time.perf_counter()
    out = svc.call("frame_decision", {
        "decision_question": "Should we renew the contract or switch?"}, "agent")
    assert "error" not in out
    assert time.perf_counter() - start < 5.0


def test_concurrent_calls():
    svc = _svc()
    with ThreadPoolExecutor(max_workers=8) as pool:
        futs = [pool.submit(svc.call, "check_guardrails",
                            {"planned_action": f"Summarize notes batch {i}"}, "agent")
                for i in range(20)]
        outs = [f.result(timeout=30) for f in futs]
    assert all("error" not in o for o in outs)
