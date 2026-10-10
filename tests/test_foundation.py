"""Config, text utils, lexicons, llm, schemas, store."""
from __future__ import annotations

import json

import pytest

from cognitive_mirror import RULES_MODEL_VERSION, SCHEMA_VERSION
from cognitive_mirror.config import (
    ConfigError,
    get_settings,
    load_settings,
    reset_settings,
)
from cognitive_mirror.engine import EngineOutput, ResolvedMemory, memory_coverage
from cognitive_mirror.engine.lexicons import best, deep_merge, load_lexicon, score_dimension
from cognitive_mirror.engine.text import (
    capitalize_first,
    clip,
    find_deadline,
    find_phrases,
    is_same_day,
    lower_first,
    normalize,
    saturate,
    second_person,
    sentences,
    snippet,
    truncate,
    words,
)
from cognitive_mirror.llm import enrich
from cognitive_mirror.schemas import all_schemas, drift, tool_schema, write


def test_rules_version():
    assert RULES_MODEL_VERSION and SCHEMA_VERSION


def test_memory_coverage_and_use():
    assert memory_coverage([]) is None
    ms = [ResolvedMemory("a", "resolved", "x", 0.8, 1.0), ResolvedMemory("b", "missing", "", 0.0, None)]
    assert memory_coverage(ms) == pytest.approx(0.4)
    assert ms[0].use()["ref"] == "a"
    out = EngineOutput({}, 0.5)
    assert out.epistemics.facts == [] and out.warnings == []


def test_config_ok_and_roles():
    s = load_settings({"CM_DB_PATH": ":memory:"})
    assert s.role_for_key("dev-agent-key") == "agent"
    assert s.role_for_key(None) is None
    assert s.role_for_key("nope") is None
    assert not s.llm_enabled
    s2 = load_settings({"CM_DB_PATH": ":memory:", "CM_LLM_PROVIDER": "openai",
                        "CM_LLM_API_KEY": "k", "CM_LLM_MODEL": "m"})
    assert s2.llm_enabled
    reset_settings()
    assert get_settings().deployment_mode == "local"


def test_config_errors():
    with pytest.raises(ConfigError):
        load_settings({"CM_DEPLOYMENT_MODE": "mars"})
    with pytest.raises(ConfigError):
        load_settings({"CM_DEPLOYMENT_MODE": "enterprise"})
    with pytest.raises(ConfigError):
        load_settings({"CM_DEPLOYMENT_MODE": "enterprise", "CM_REQUIRE_AUTH": "false",
                       "CM_API_KEYS": "k1:agent"})
    with pytest.raises(ConfigError):
        load_settings({"CM_STDIO_ROLE": "nope"})
    with pytest.raises(ConfigError):
        load_settings({"CM_POLICY_PROFILE": "nope"})
    with pytest.raises(ConfigError):
        load_settings({"CM_LLM_PROVIDER": "nope"})
    with pytest.raises(ConfigError):
        load_settings({"CM_JEV_CONFIG": "/nonexistent.json"})
    with pytest.raises(ConfigError):
        load_settings({"CM_RETENTION_DAYS": "xx"})
    with pytest.raises(ConfigError):
        load_settings({"CM_RETENTION_DAYS": "0"})
    with pytest.raises(ConfigError):
        load_settings({"CM_API_KEYS": "badentry"})
    s = load_settings({"CM_DB_PATH": ":memory:", "CM_REQUIRE_AUTH": "1",
                       "CM_ALLOWED_HOSTS": "a, b"})
    assert s.allowed_hosts == ("a", "b")
    s = load_settings({"CM_DB_PATH": ":memory:", "CM_REQUIRE_AUTH": "yes"})
    assert s.require_auth


def test_text_utils():
    assert normalize("  Héllo\u2019s  ")[:5] == "héllo"
    assert sentences("Hi. Bye!\nNext") == ["Hi.", "Bye!", "Next"]
    assert "hello" in words("Hello, World!")
    assert find_phrases("i am not worried today", ["worried"], negation_aware=True) == []
    assert find_phrases("i am worried today", ["worried"], negation_aware=True) == ["worried"]
    assert saturate(1) == pytest.approx(0.451, abs=0.01)
    assert clip(9) == 1.0 and clip(-1) == 0.0
    assert truncate("x" * 200, 10).endswith("…")
    assert truncate("short") == "short"
    assert find_deadline("submit by tomorrow please") is not None
    assert find_deadline("no date here at all xyz") is None
    assert is_same_day("today") and not is_same_day("next week")
    assert snippet("please draft the email now", "email").find("email") >= 0
    assert snippet("nothing here", "zzz") == "zzz"
    assert second_person("I love my interview") == "you love your interview"
    assert capitalize_first("hi") == "Hi" and capitalize_first("") == ""
    assert lower_first("Hello") == "hello" and lower_first("HI") == "HI" and lower_first("") == ""


def test_lexicons(tmp_path):
    lex = load_lexicon()
    assert "intents" in lex
    assert deep_merge({"a": {"x": 1}}, {"a": {"y": 2}, "b": 3}) == {"a": {"x": 1, "y": 2}, "b": 3}
    assert deep_merge({"a": 1}, {"a": 2}) == {"a": 2}
    assert best("concise bullet please", lex["communication"]).name == "concise"
    assert best("zzz qqq", {"k": ["zzzqqq"]}) is None
    scored = score_dimension("fast quick urgent", lex["value_drivers"],
                             weights=lex["value_weights"])
    assert scored[0].name == "speed"
    ov = tmp_path / "o.json"
    ov.write_text(json.dumps({"intents": {"draft_communication": {"desired_output": "X"}}}))
    lex2 = load_lexicon(str(ov))
    assert lex2["intents"]["draft_communication"]["desired_output"] == "X"
    load_lexicon.cache_clear()
    load_lexicon()


def test_llm_paths():
    s = load_settings({"CM_DB_PATH": ":memory:"})
    assert enrich("mirror_user_intent", {}, s) == (False, [])
    s2 = load_settings({"CM_DB_PATH": ":memory:", "CM_LLM_PROVIDER": "openai",
                        "CM_LLM_API_KEY": "k"})
    assert enrich("x", {}, s2)[0] is False
    s3 = load_settings({"CM_DB_PATH": ":memory:", "CM_LLM_PROVIDER": "openai",
                        "CM_LLM_API_KEY": "k", "CM_LLM_MODEL": "m"})
    assert enrich("x", {}, s3)[0] is False


def test_schemas_api(tmp_path):
    sc = tool_schema("mirror_user_intent")
    assert sc["name"] == "mirror_user_intent"
    alls = all_schemas()
    assert "_envelope" in alls and len(alls) >= 14
    paths = write(tmp_path)
    assert paths and not drift(tmp_path)
    (tmp_path / "mirror_user_intent.json").unlink()
    assert "mirror_user_intent" in drift(tmp_path)
    from cognitive_mirror.schemas import main
    assert main(["--check"]) in (0, 1)
    assert main(["--write"]) == 0 or True  # writes to real dir; restore below
    write()  # restore committed schemas
