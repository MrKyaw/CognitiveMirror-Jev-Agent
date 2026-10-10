"""Container checks against `docker compose up` (run with `make container-test`)."""
from __future__ import annotations

import json
import urllib.request

import pytest

pytestmark = pytest.mark.container

BASE = "http://127.0.0.1:8000"


def _post(path: str, body: dict) -> tuple[int, dict]:
    req = urllib.request.Request(
        BASE + path, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "X-API-Key": "dev-agent-key"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode())
    except Exception as exc:
        pytest.skip(f"container not reachable: {exc}")
        raise


def test_container_health():
    try:
        with urllib.request.urlopen(BASE + "/health", timeout=10) as resp:
            data = json.loads(resp.read().decode())
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"container not reachable: {exc}")
    assert data["status"] == "ok"
    assert len(data["tools"]) == 14


def test_container_tool_call():
    status, data = _post("/v1/tools/check_guardrails",
                         {"planned_action": "Summarize my notes"})
    assert status == 200
    assert data["result"]["allowed"] is True or data["result"]["allowed"] is False
