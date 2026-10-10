"""Text utilities: normalization, phrase matching with negation, sentences, deadlines."""
from __future__ import annotations

import math
import re
from collections.abc import Iterable
from functools import lru_cache

NEGATORS = frozenset({
    "not", "no", "never", "dont", "don't", "isnt", "isn't", "arent", "aren't", "wasnt",
    "wasn't", "hardly", "nor", "neither", "without", "nothing",
})
_WORD = re.compile(r"[a-z0-9']+")
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")
_SPACE = re.compile(r"\s+")

_MONTH = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?"
_DAY = r"(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)"
DEADLINE = re.compile(
    r"\b(?:by|before|until|due|no later than|on)\s+(?:the\s+)?(?:"
    r"end of (?:the )?(?:day|week|month|quarter|year)|eod|eow|eom|tomorrow|tonight|today|"
    r"this " + _DAY + r"|next " + _DAY + r"|" + _DAY + r"|next week|next month|"
    r"\d{1,2}(?::\d{2})?\s?(?:am|pm)|" + _MONTH + r"\s+\d{1,2}(?:st|nd|rd|th)?|"
    r"\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}(?:/\d{2,4})?)"
    r"|\bwithin\s+(?:the\s+next\s+)?\d+\s+(?:minutes?|hours?|days?|weeks?|months?)"
    r"|\bin\s+\d+\s+(?:hours?|days?|weeks?)",
    re.IGNORECASE,
)
_SAME_DAY = re.compile(r"\b(today|tonight|eod|end of (?:the )?day|\d+\s+hours?|minutes?)\b",
                       re.IGNORECASE)


def normalize(text: str) -> str:
    text = text.replace("\u2019", "'").replace("\u2018", "'").replace("\u201c", '"')
    text = text.replace("\u201d", '"')
    return _SPACE.sub(" ", text).strip().lower()


def sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENT_SPLIT.split(text or "") if s and s.strip()]


def words(text: str) -> list[str]:
    return _WORD.findall(normalize(text))


@lru_cache(maxsize=4096)
def _phrase_re(phrase: str) -> re.Pattern[str]:
    return re.compile(r"(?<![a-z0-9])" + re.escape(phrase.strip().lower())
                      + r"(?![a-z0-9]|-[a-z])")


def _negated(text: str, start: int) -> bool:
    preceding = _WORD.findall(text[max(0, start - 40):start])[-3:]
    return any(w in NEGATORS for w in preceding)


def find_phrases(text: str, phrases: Iterable[str], negation_aware: bool = False) -> list[str]:
    """Phrases (in input order) that occur in already-normalized ``text``.

    With ``negation_aware`` a phrase only counts if at least one occurrence is not preceded
    by a negator within three words ("not worried" is not concern).
    """
    found: list[str] = []
    for phrase in phrases:
        if phrase in found:
            continue
        for match in _phrase_re(phrase).finditer(text):
            if not negation_aware or not _negated(text, match.start()):
                found.append(phrase)
                break
    return found


def saturate(hits: float, k: float = 0.6) -> float:
    """Map a hit count to (0, 1): 1 hit = 0.45, 2 = 0.70, 3 = 0.83."""
    return round(1.0 - math.exp(-k * max(hits, 0.0)), 3)


def clip(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return round(min(hi, max(lo, value)), 3)


def truncate(text: str, limit: int = 160) -> str:
    text = _SPACE.sub(" ", text).strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "\u2026"


def find_deadline(text: str) -> str | None:
    match = DEADLINE.search(text or "")
    return match.group(0).strip() if match else None


def is_same_day(deadline: str) -> bool:
    return bool(_SAME_DAY.search(deadline))


def snippet(original: str, phrase: str, width: int = 50) -> str:
    """Short excerpt of ``original`` around ``phrase`` for evidence."""
    match = _phrase_re(phrase).search(normalize(original))
    if not match:
        return truncate(phrase, width)
    flat = _SPACE.sub(" ", original).strip()
    lo = max(0, match.start() - width // 2)
    hi = min(len(flat), match.end() + width // 2)
    return ("\u2026" if lo else "") + flat[lo:hi].strip() + ("\u2026" if hi < len(flat) else "")


_PERSON = {"i": "you", "me": "you", "my": "your", "mine": "yours", "myself": "yourself",
           "i'm": "you're", "im": "you're", "i've": "you've", "i'll": "you'll", "i'd": "you'd",
           "we": "you", "our": "your", "ours": "yours", "us": "you", "we're": "you're"}
_PERSON_RE = re.compile(r"\b(" + "|".join(sorted(map(re.escape, _PERSON), key=len,
                                                 reverse=True)) + r")\b", re.IGNORECASE)


def second_person(text: str) -> str:
    """Rewrite first-person phrasing for mirroring: 'my interview' -> 'your interview'."""
    return _PERSON_RE.sub(lambda m: _PERSON[m.group(1).lower()], text)


def capitalize_first(text: str) -> str:
    return text[:1].upper() + text[1:] if text else text


def lower_first(text: str) -> str:
    if len(text) > 1 and text[1].isupper():
        return text
    return text[:1].lower() + text[1:] if text else text
