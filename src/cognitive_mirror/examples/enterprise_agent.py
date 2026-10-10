"""Enterprise decision assistant demo: decision -> impact -> guardrail."""
from __future__ import annotations

from cognitive_mirror.config import load_settings
from cognitive_mirror.engine.lexicons import load_lexicon
from cognitive_mirror.service import Service
from cognitive_mirror.store import Store


def run_demo(db_path: str = ":memory:") -> dict:
    settings = load_settings({"CM_DB_PATH": db_path})
    store = Store(settings.db_path, settings.retention_days, settings.shared_context_ttl_minutes)
    service = Service(settings, store, load_lexicon())
    trace = "tr_demo_enterprise"
    decision = service.call("frame_decision", {
        "decision_question": "Should we renew the support tooling contract or switch vendors?",
        "context": "Renewal due next month; team complains about response time",
        "constraints": ["Budget under $50k per year", "Must stay SOC 2 compliant"],
        "success_metrics": ["Response time under 2h", "Cost per seat"],
        "trace_id": trace, "session_id": "demo_enterprise"}, "agent")
    impact = service.call("assess_business_impact", {
        "request": "Switch support vendors for faster response",
        "target_workflow": "customer support", "stakeholders": ["support team", "customers"],
        "baseline": {"hours_per_week": 20}, "trace_id": trace,
        "session_id": "demo_enterprise"}, "agent")
    guard = service.call("check_guardrails", {
        "planned_action": "Email all customers about the vendor switch next week",
        "data_used": ["customer list"], "trace_id": trace}, "agent")
    return {"decision": decision, "impact": impact, "guard": guard}


def main() -> int:  # pragma: no cover - demo entrypoint
    out = run_demo("data/cognitive_mirror.db")
    print(f"recommended={out['decision']['result']['recommended_option']} "
          f"stakes={out['decision']['result']['decision_frame']['stakes']}")
    print(f"impact={out['impact']['result']['impact_category']} "
          f"priority={out['impact']['result']['priority_score']}")
    print(f"guard_allowed={out['guard']['result']['allowed']} "
          f"approval={out['guard']['result']['human_approval_required']}")
    return 0


if __name__ == "__main__":  # pragma: no cover - demo entrypoint
    raise SystemExit(main())
