"""Live System One / Jev cross-check (PRD 7.3). Fake SDK, no network."""
from __future__ import annotations

import sys
import types

import pytest

from cognitive_mirror.config import load_settings
from cognitive_mirror.engine.lexicons import load_lexicon
from cognitive_mirror.jev_live import apply_jev_live
from cognitive_mirror.models import BuildJevProfileInput
from cognitive_mirror.service import Service
from cognitive_mirror.store import Store


class _NS:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def _fake_sdk(response=None, error=None):
    mod = types.ModuleType("typesafe_sdk")

    class Choice:
        def __init__(self, **kw):
            self.__dict__.update(kw)

    class Noul:
        def __init__(self, **kw):
            self.__dict__.update(kw)

    class TypeSafeClient:
        def __init__(self, api_key=None):
            assert api_key == "live-key"

        def system_one(self, state, questions, model=None):
            assert set(questions) == {"journey", "user_confident"}
            assert model == "jev-latest"
            if error is not None:
                raise error
            return response

    mod.Choice, mod.Noul, mod.TypeSafeClient = Choice, Noul, TypeSafeClient
    return mod


def _settings():
    return load_settings({"CM_DB_PATH": ":memory:", "TYPESAFE_API_KEY": "live-key"})


def _parsed():
    return BuildJevProfileInput(context="deciding between offers")


def _result(stage="exploring", conf=0.5):
    return {"journey_stage": {"stage": stage, "confidence": 0.4, "evidence": []},
            "confidence": conf}


def test_disabled_without_key():
    s = load_settings({"CM_DB_PATH": ":memory:"})
    warnings: list[str] = []
    assert apply_jev_live(_parsed(), _result(), [], warnings, s) is False
    assert warnings == []
    assert s.jev_model == "jev-latest" and s.typesafe_api_key == ""


def test_config_live_keys():
    s = load_settings({"CM_DB_PATH": ":memory:", "TYPESAFE_API_KEY": "k",
                       "CM_JEV_MODEL": "jev-1.13.0"})
    assert s.typesafe_api_key == "k" and s.jev_model == "jev-1.13.0"


def test_import_error(monkeypatch):
    monkeypatch.setitem(sys.modules, "typesafe_sdk", None)
    warnings: list[str] = []
    assert apply_jev_live(_parsed(), _result(), [], warnings, _settings()) is False
    assert "not installed" in warnings[0]


def test_api_error(monkeypatch):
    monkeypatch.setitem(sys.modules, "typesafe_sdk",
                        _fake_sdk(error=RuntimeError("boom")))
    warnings: list[str] = []
    assert apply_jev_live(_parsed(), _result(), [], warnings, _settings()) is False
    assert "boom" in warnings[0]


def test_override(monkeypatch):
    resp = _NS(answers={"journey": _NS(choice="deciding", confidence=0.85),
                        "user_confident": _NS(noul=0.9)},
               usage=_NS(input_tokens=2000, output_tokens=0))
    monkeypatch.setitem(sys.modules, "typesafe_sdk", _fake_sdk(resp))
    result, evidence, warnings = _result(), [], []
    assert apply_jev_live(_parsed(), result, evidence, warnings, _settings()) is True
    assert result["journey_stage"]["stage"] == "deciding"
    assert "moved journey stage exploring -> deciding" in warnings[0]
    assert result["confidence"] == pytest.approx(0.65)
    assert any("2000 input tokens" in w for w in warnings)
    assert evidence and warnings


def test_confirm_same_stage(monkeypatch):
    resp = _NS(answers={"journey": _NS(choice="exploring", confidence=0.9)}, usage=None)
    monkeypatch.setitem(sys.modules, "typesafe_sdk", _fake_sdk(resp))
    result, evidence, warnings = _result(), [], []
    assert apply_jev_live(_parsed(), result, evidence, warnings, _settings()) is True
    assert result["journey_stage"]["stage"] == "exploring"
    assert result["confidence"] == 0.5
    assert evidence[0]["quote"] == "journey exploring confirmed"


def test_low_conf_no_override(monkeypatch):
    resp = _NS(answers={"journey": _NS(choice="deciding", confidence=0.4),
                        "user_confident": _NS(noul=0.5)},
               usage=_NS(input_tokens=0, output_tokens=0))
    monkeypatch.setitem(sys.modules, "typesafe_sdk", _fake_sdk(resp))
    result, evidence, warnings = _result(), [], []
    assert apply_jev_live(_parsed(), result, evidence, warnings, _settings()) is True
    assert result["journey_stage"]["stage"] == "exploring"
    assert result["confidence"] == pytest.approx(0.25)


def test_missing_answers(monkeypatch):
    resp = _NS(answers={}, usage=None)
    monkeypatch.setitem(sys.modules, "typesafe_sdk", _fake_sdk(resp))
    result, evidence, warnings = _result(), [], []
    assert apply_jev_live(_parsed(), result, evidence, warnings, _settings()) is True
    assert result["journey_stage"]["stage"] == "exploring"


def test_service_hybrid_mode(monkeypatch):
    resp = _NS(answers={"journey": _NS(choice="exploring", confidence=0.9)},
               usage=_NS(input_tokens=10, output_tokens=0))
    monkeypatch.setitem(sys.modules, "typesafe_sdk", _fake_sdk(resp))
    settings = _settings()
    svc = Service(settings, Store(":memory:"), load_lexicon())
    out = svc.call("build_jev_profile", {"context": "hello"}, "agent")
    assert out["engine"]["mode"] == "hybrid"
    assert out["engine"]["enriched"] is True
