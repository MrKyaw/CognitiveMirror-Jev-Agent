"""check_guardrails (PRD 8.6, 9.3) plus the redaction used for memory and audit."""
from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from cognitive_mirror.config import POLICY_DIR
from cognitive_mirror.engine import EngineOutput
from cognitive_mirror.engine.text import find_phrases, normalize, truncate
from cognitive_mirror.models import CheckGuardrailsInput, Epistemics

RISK_ORDER = ("low", "medium", "high", "critical")

# ---------------------------------------------------------------- PII and secrets

_PII_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("secret", re.compile(
        r"\b(?:sk|pk|rk|ghp|gho|xox[abp]|AKIA)[-_]?[A-Za-z0-9_\-]{16,}\b"
        r"|(?i:\b(?:password|passwd|pwd|api[_ -]?key|secret|token)\s*[:=]\s*\S{6,})")),
    ("email", re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")),
    ("iban", re.compile(r"\b[A-Z]{2}\d{2}(?:\s?[A-Z0-9]{4}){2,7}(?:\s?[A-Z0-9]{1,4})?\b")),
    ("credit_card", re.compile(r"(?<!\d)(?:\d[ \-]?){12,18}\d(?!\d)")),
    ("ssn", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("sin", re.compile(r"\b\d{3}[ \-]\d{3}[ \-]\d{3}\b")),
    ("date_of_birth", re.compile(
        r"(?i:\b(?:dob|date of birth|born on|birthdate)\b[:\s]*\d{1,4}[/\-.]\d{1,2}[/\-.]\d{1,4})")),
    ("phone", re.compile(
        r"(?<![\w+])(?:\+?\d{1,2}[\s.\-]?)?(?:\(\d{3}\)|\d{3})[\s.\-]?\d{3}[\s.\-]?\d{4}(?!\d)")),
    ("ip_address", re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")),
)
PLACEHOLDERS = {name: f"[REDACTED_{name.upper()}]" for name, _ in _PII_PATTERNS}


def luhn_ok(number: str) -> bool:
    digits = [int(d) for d in number if d.isdigit()]
    if not 13 <= len(digits) <= 19:
        return False
    total = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2:
            d = d * 2 - 9 if d * 2 > 9 else d * 2
        total += d
    return total % 10 == 0


def _mask(value: str) -> str:
    value = value.strip()
    if len(value) <= 4:
        return "*" * len(value)
    return value[:2] + "*" * (len(value) - 4) + value[-2:]


@dataclass(frozen=True)
class Finding:
    type: str
    start: int
    end: int
    value: str


def find_pii(text: str) -> list[Finding]:
    findings: list[Finding] = []
    taken: list[tuple[int, int]] = []
    for name, pattern in _PII_PATTERNS:
        for m in pattern.finditer(text):
            if any(m.start() < e and s < m.end() for s, e in taken):
                continue
            if name == "credit_card" and not luhn_ok(m.group(0)):
                continue
            taken.append((m.start(), m.end()))
            findings.append(Finding(name, m.start(), m.end(), m.group(0)))
    return sorted(findings, key=lambda f: f.start)


def redact(text: str) -> tuple[str, list[Finding]]:
    findings = find_pii(text)
    out, last = [], 0
    for f in findings:
        out.append(text[last:f.start])
        out.append(PLACEHOLDERS[f.type])
        last = f.end
    out.append(text[last:])
    return "".join(out), findings


def redact_obj(obj: Any) -> Any:
    """Recursively redact every string in a JSON-like structure."""
    if isinstance(obj, str):
        return redact(obj)[0]
    if isinstance(obj, dict):
        return {k: redact_obj(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [redact_obj(v) for v in obj]
    return obj


# ---------------------------------------------------------------- action classification

CATEGORY_SEVERITY = {
    "pii": "medium", "credential_exposure": "critical", "special_category_data": "high",
    "external_action": "medium", "irreversible_action": "high", "financial_action": "high",
    "high_impact_communication": "high", "regulated_advice": "high", "manipulation": "critical",
    "security_bypass": "critical", "pii_external_share": "high", "bulk_data": "high",
}

_RULES: dict[str, tuple[str, ...]] = {
    "external_action": (
        "send", "email", "e-mail", "post", "publish", "tweet", "share with", "share it",
        "submit", "forward", "reply to", "message the", "dm", "invite", "book a", "book the",
        "schedule a",
        "upload", "notify", "text them", "call the customer", "contact",
    ),
    "irreversible_action": (
        "delete", "erase", "wipe", "drop table", "terminate", "fire", "cancel the contract",
        "cancel contract", "close the account", "close account", "deactivate", "resign",
        "sign the contract", "sign contract", "accept the offer", "decline the offer",
        "permanently", "purge", "revoke",
    ),
    "financial_action": (
        "pay", "payment", "wire", "transfer", "purchase", "buy", "refund", "invoice", "charge the",
        "trade", "invest", "loan", "withdraw", "deposit", "payroll", "expense", "subscribe",
    ),
    "high_impact_communication": (
        "all employees", "all staff", "all customers", "entire company", "company-wide",
        "press release", "the board", "board of directors", "investors", "public statement",
        "announcement", "layoff", "layoffs", "termination letter", "resignation letter",
        "legal notice", "regulator", "media", "all users", "mass email", "newsletter",
    ),
    "manipulation": (
        "guilt", "guilt-trip", "pressure them", "exploit", "fomo", "fear of missing out",
        "dark pattern", "trick them", "trick the", "manipulate", "while they're upset",
        "while they are upset", "vulnerable", "fake urgency", "fake scarcity", "make them feel bad",
        "shame them", "deceive", "mislead", "lie to",
    ),
    "security_bypass": (
        "disable mfa", "disable 2fa", "bypass", "turn off logging", "disable audit",
        "share my password", "share the password", "share credentials", "escalate privileges",
        "root access", "disable the firewall", "jailbreak",
    ),
    "bulk_data": (
        "all customer data", "entire database", "export all", "full customer list",
        "all records", "dump the database", "scrape", "every user's", "all user data",
    ),
}
_REGULATED: dict[str, tuple[str, ...]] = {
    "medical": ("diagnose", "diagnosis", "medication", "dosage", "dose", "prescription",
                "symptoms", "treatment plan", "medical advice", "is it cancer", "therapy plan"),
    "legal": ("legal advice", "lawsuit", "sue", "contract dispute", "liability", "litigation",
              "is it legal", "legally binding", "court", "custody"),
    "financial": ("investment advice", "invest in", "which stock", "stocks", "portfolio",
                  "retirement savings", "crypto", "tax advice", "mortgage advice", "financial advice",
                  "buy shares"),
    "immigration": ("visa", "immigration", "work permit", "green card", "asylum",
                    "permanent residence", "citizenship application", "express entry", "h-1b",
                    "h1b", "study permit"),
}
_SPECIAL_DATA = (
    "health record", "medical record", "diagnosis", "mental health", "disability", "pregnancy",
    "religion", "religious", "ethnicity", "racial", "sexual orientation", "political affiliation",
    "union membership", "biometric", "genetic", "criminal record", "immigration status",
    "passport", "driver's license", "drivers license", "social security", "sin number",
    "children's data", "minor's data", "salary", "bank statement", "credit score",
)
_MONEY = re.compile(r"(?:[$\u20ac\u00a3]\s?\d[\d,]*(?:\.\d+)?\s?(?:k|m|b)?|\b\d[\d,]*\s?"
                    r"(?:usd|cad|eur|gbp|dollars)\b)", re.IGNORECASE)

_SAFE_ALTERNATIVES = {
    "manipulation": "Remove pressure or deceptive tactics; present the facts and options "
                    "neutrally and let the person decide.",
    "credential_exposure": "Never share credentials; use a secrets manager or a scoped, "
                           "revocable access grant instead.",
    "security_bypass": "Keep security controls in place; ask an administrator to grant the "
                       "minimum access needed through the normal process.",
    "pii_external_share": "Share only the minimum necessary data, redacted or referenced by "
                          "memory_ref, after obtaining explicit consent.",
    "bulk_data": "Use an aggregated or anonymized extract scoped to the specific purpose.",
    "special_category_data": "Avoid using sensitive personal data; if essential, obtain "
                             "explicit consent and human approval first.",
    "regulated_advice": "Provide general educational information only and recommend "
                        "consulting a licensed professional for this decision.",
    "financial_action": "Prepare the transaction details for the user to review and execute "
                        "themselves after approval.",
    "irreversible_action": "Propose a reversible step first (archive, draft, pause) and get "
                           "explicit human approval before the irreversible action.",
    "high_impact_communication": "Draft the communication for review by the owner (and legal "
                                 "or communications if required) before it is sent.",
    "external_action": "Prepare a draft for the user to review and send themselves.",
    "pii": "Redact personal data or replace it with memory references before proceeding.",
}
_ALT_ORDER = ("manipulation", "credential_exposure", "security_bypass", "pii_external_share",
              "bulk_data", "special_category_data", "regulated_advice", "financial_action",
              "irreversible_action", "high_impact_communication", "external_action", "pii")


@lru_cache(maxsize=16)
def load_policy(name: str) -> dict[str, Any]:
    path = POLICY_DIR / f"{name}.json"
    if not path.exists():
        raise KeyError(name)
    return json.loads(path.read_text())


def policy_names() -> list[str]:
    return sorted(p.stem for p in POLICY_DIR.glob("*.json"))


def _max_risk(levels: Iterable[str]) -> str:
    return max(levels, key=RISK_ORDER.index, default="low")


def _issue(code: str, category: str, description: str, reason: str,
           policy: dict[str, Any]) -> dict[str, str]:
    severity = policy["severity_overrides"].get(category, CATEGORY_SEVERITY[category])
    return {"code": code, "category": category, "severity": severity,
            "description": description, "policy_reason": reason}


def _consent(user_context: dict[str, Any], key: str) -> bool:
    consent = user_context.get("consent")
    if isinstance(consent, dict):
        return bool(consent.get(key))
    return bool(consent) if isinstance(consent, bool) else False


def check_guardrails(inp: CheckGuardrailsInput, default_profile: str) -> EngineOutput:
    profile = inp.policy_profile or default_profile
    policy = load_policy(profile)
    action = inp.planned_action
    action_n = normalize(action)
    data_n = normalize(" | ".join(inp.data_used))
    ctx_text = json.dumps(inp.user_context, sort_keys=True, default=str)
    issues: list[dict[str, str]] = []
    redactions: list[dict[str, str]] = []

    sources = [("planned_action", action)] + [(f"data_used[{i}]", d)
                                             for i, d in enumerate(inp.data_used)]
    sources.append(("user_context", ctx_text))
    pii_types: list[str] = []
    for location, text in sources:
        for f in find_pii(text):
            redactions.append({"type": f.type, "location": location,
                               "placeholder": PLACEHOLDERS[f.type],
                               "masked_preview": _mask(f.value)})
            pii_types.append(f.type)
    secrets = [t for t in pii_types if t == "secret"]
    personal = sorted({t for t in pii_types if t != "secret"})
    if secrets:
        issues.append(_issue("credential_detected", "credential_exposure",
                             "Credentials or API secrets appear in the action or data",
                             "Secrets must never be exposed to agents or third parties", policy))
    if personal:
        issues.append(_issue("pii_detected", "pii",
                             f"Personal data detected: {', '.join(personal)}",
                             "Data minimization: redact or reference personal data", policy))

    hits: dict[str, list[str]] = {}
    for category, phrases in _RULES.items():
        found = find_phrases(action_n, phrases, negation_aware=True)
        if category == "bulk_data":
            found += find_phrases(data_n, phrases)
        if found:
            hits[category] = found
    money = _MONEY.search(action)
    if money and "financial_action" not in hits and "external_action" in hits:
        hits["financial_action"] = [money.group(0)]
    descriptions = {
        "external_action": ("external_side_effect", ("Action reaches people or systems outside "
                                                     "the conversation"),
                            "External actions need human approval (AGENT-007)"),
        "irreversible_action": ("irreversible", "Action is hard or impossible to undo",
                                "Irreversible actions require explicit approval"),
        "financial_action": ("financial", "Action moves money or creates a financial commitment",
                             "Financial decisions require human approval (PRD 9.3)"),
        "high_impact_communication": ("high_impact_comms", ("High-impact or broad audience "
                                                            "communication"),
                                      ("High-impact communications require "
                                       "review (PRD 9.3)")),
        "manipulation": ("manipulation", ("Action uses pressure, deception or emotional "
                                          "exploitation"),
                         "No manipulative personalization (JEV-006, PRD 9.3)"),
        "security_bypass": ("security_bypass", "Action weakens security controls",
                            "Security controls must not be bypassed by agents"),
        "bulk_data": ("bulk_data", "Action uses bulk or full-population personal data",
                      "Data minimization: use the smallest necessary dataset"),
    }
    for category, found in hits.items():
        code, desc, reason = descriptions[category]
        issues.append(_issue(code, category, f"{desc} (matched: {', '.join(found[:3])})",
                             reason, policy))

    regulated = {domain: found for domain, terms in _REGULATED.items()
                 if (found := find_phrases(action_n, terms))}
    for domain, found in regulated.items():
        issues.append(_issue(f"regulated_{domain}_advice", "regulated_advice",
                             f"{domain.capitalize()} advice is out of scope as authoritative "
                             f"output (matched: {', '.join(found[:3])})",
                             ("PRD 6: no authoritative medical, legal, financial or "
                              "immigration advice"), policy))

    special = find_phrases(f"{action_n} {data_n}", _SPECIAL_DATA)
    if special:
        issues.append(_issue("special_category_data", "special_category_data",
                             f"Sensitive personal data involved: {', '.join(special[:4])}",
                             "Special-category data needs consent and approval", policy))

    external = "external_action" in hits or "high_impact_communication" in hits
    if external and (personal or special) and not _consent(inp.user_context,
                                                           "share_externally"):
        issues.append(_issue("pii_external_share_without_consent", "pii_external_share",
                             "Personal data would leave the user's control without recorded "
                             "consent", "Consent-aware data use (PRD 10, Privacy)", policy))

    categories = {i["category"] for i in issues}
    risk = _max_risk(i["severity"] for i in issues)
    blocked = sorted(categories & set(policy["block"]))
    threshold = policy["approval_risk_threshold"]
    approval_reasons = sorted(categories & set(policy["require_approval"]))
    if issues and RISK_ORDER.index(risk) >= RISK_ORDER.index(threshold):
        approval_reasons.append(f"risk_level {risk} >= policy threshold {threshold}")
    allowed = not blocked
    approval = bool(approval_reasons) or not allowed
    if blocked:
        approval_reasons.insert(0, f"blocked by policy: {', '.join(blocked)}")
    alt_category = next((c for c in _ALT_ORDER if c in categories), None)
    safe_alternative = _SAFE_ALTERNATIVES[alt_category] if alt_category and (
        approval or not allowed) else None
    redacted_action = redact(action)[0]

    result = {
        "allowed": allowed, "risk_level": risk, "issues": issues,
        "required_redactions": redactions, "human_approval_required": approval,
        "approval_reasons": list(dict.fromkeys(approval_reasons)),
        "safe_alternative": safe_alternative, "policy_profile": profile,
        "redacted_action": redacted_action,
    }
    epistemics = Epistemics(
        facts=[f"Detected {r['type']} in {r['location']}" for r in redactions[:5]]
        + [f"Policy profile '{profile}' blocks: {', '.join(policy['block'])}"],
        assumptions=([] if inp.user_context else
                     ["No user context or consent record provided; treated as no consent"]),
        inferences=[f"{i['category']}: {i['description']}" for i in issues[:5]],
        recommendations=[safe_alternative] if safe_alternative else
        ["No guardrail issues found; proceed and log the action"],
    )
    evidence = [{"source": "planned_action", "quote": truncate(redacted_action, 120)}]
    decision = {"profile": profile, "allowed": allowed, "risk_level": risk,
                "human_approval_required": approval, "blocked_categories": blocked,
                "issue_codes": [i["code"] for i in issues]}
    confidence = 0.9 if issues else 0.75
    return EngineOutput(result, confidence, epistemics, evidence, [], decision)
