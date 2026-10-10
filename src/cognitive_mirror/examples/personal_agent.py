"""Personal productivity agent demo: mirror -> jev -> guardrail -> next action."""
from __future__ import annotations

import os

from cognitive_mirror.config import load_settings
from cognitive_mirror.engine.lexicons import load_lexicon
from cognitive_mirror.service import Service
from cognitive_mirror.store import Store


def run_demo(db_path: str = ":memory:") -> dict:
    settings = load_settings({**dict(os.environ), "CM_DB_PATH": db_path})
    store = Store(settings.db_path, settings.retention_days, settings.shared_context_ttl_minutes,
                  settings.database_url)
    service = Service(settings, store, load_lexicon())
    trace = "tr_demo_personal"
    mirror = service.call("mirror_user_intent", {
        "user_message": "Draft a concise follow-up email to my hiring manager about tomorrow's "
                        "interview. I am worried I seemed unfocused.",
        "trace_id": trace, "session_id": "demo_personal"}, "agent")
    jev = service.call("build_jev_profile", {
        "subject": {"type": "user", "role": "software engineer"},
        "context": "Interview follow-up; user is concerned about focus",
        "trace_id": trace, "session_id": "demo_personal"}, "agent")
    guard = service.call("check_guardrails", {
        "planned_action": "Draft a follow-up email to the hiring manager",
        "data_used": ["interview notes"], "trace_id": trace}, "agent")
    action = service.call("recommend_next_action", {
        "intent_summary": mirror["result"], "jev_profile": jev["result"],
        "business_goal": "Advance to the offer stage",
        "available_tools": ["gmail", "calendar"],
        "guardrail_result": guard["result"], "trace_id": trace,
        "session_id": "demo_personal"}, "agent")
    return {"mirror": mirror, "jev": jev, "guard": guard, "action": action}


def main() -> int:  # pragma: no cover - demo entrypoint
    out = run_demo("data/cognitive_mirror.db")
    print(f"intent={out['mirror']['result']['primary_intent']['label']} "
          f"conf={out['mirror']['confidence']}")
    print(f"journey={out['jev']['result']['journey_stage']['stage']}")
    print(f"approval_required={out['action']['result']['human_approval_required']}")
    print(f"instruction={out['action']['result']['agent_instruction']}")
    return 0


if __name__ == "__main__":  # pragma: no cover - demo entrypoint
    raise SystemExit(main())
