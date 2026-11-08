"""AI-trainer taxonomy helpers: term matching and job relevance."""
from __future__ import annotations

import re
from functools import lru_cache

from .. import config


def _tax() -> dict:
    return config.load_yaml("taxonomy.yaml")


def has_term(text: str, term: str) -> bool:
    """Whole-word / phrase match, case-insensitive."""
    return re.search(r"(?<![a-z0-9])" + re.escape(term.lower()) + r"(?![a-z0-9])", text.lower()) is not None


@lru_cache(maxsize=1)
def all_terms() -> list[str]:
    tax = _tax()
    terms: set[str] = set(tax.get("tools_and_signals", []))
    for group in ("domains", "task_types"):
        for canonical, syns in tax.get(group, {}).items():
            terms.add(canonical)
            terms.update(syns)
    return sorted(terms)


def terms_in(text: str) -> list[str]:
    return [t for t in all_terms() if has_term(text, t)]


def domains_in(text: str) -> list[str]:
    out = []
    for canonical, syns in _tax().get("domains", {}).items():
        if has_term(text, canonical) or any(has_term(text, s) for s in syns):
            out.append(canonical)
    return out


def _hits(text: str, keywords: list[str]) -> int:
    return sum(1 for k in keywords if has_term(text, k))


def _title_hit(title: str) -> bool:
    rel = _tax().get("relevance", {})
    return _hits(title, rel.get("strong_title_keywords", []) + rel.get("title_keywords", [])) > 0


def _excluded(title: str) -> bool:
    rel = _tax().get("relevance", {})
    if _hits(title, rel.get("strong_title_keywords", [])):
        return False
    return _hits(title, rel.get("exclude_title_keywords", [])) > 0


def relevance(title: str, description: str) -> float:
    """0..1 relevance of a posting to AI-trainer work (title hits weigh more)."""
    rel = _tax().get("relevance", {})
    t_hits = _hits(title, rel.get("strong_title_keywords", []) + rel.get("title_keywords", []))
    b_hits = _hits(description, rel.get("body_keywords", []))
    return round(min(1.0, 0.5 * min(t_hits, 2) + 0.1 * min(b_hits, 5)), 2)


def is_relevant(title: str, description: str, strict: bool = True) -> bool:
    if _excluded(title):
        return False
    if _title_hit(title):
        return True
    if strict:
        return False
    rel = _tax().get("relevance", {})
    return _hits(description, rel.get("body_keywords", [])) >= int(rel.get("relaxed_body_hits", 2))
