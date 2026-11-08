"""ATS keyword coverage: how many of a job's keywords appear in a resume/profile text."""
from __future__ import annotations

from rapidfuzz import fuzz

from .taxonomy import has_term, terms_in


def job_keywords(requirements_keywords: list[str], description: str) -> list[str]:
    """LLM-extracted keywords plus taxonomy terms found in the description (deduplicated)."""
    seen, out = set(), []
    for k in [*requirements_keywords, *terms_in(description)]:
        k = k.strip().lower()
        if k and k not in seen:
            seen.add(k)
            out.append(k)
    return out


def keyword_present(keyword: str, text: str) -> bool:
    if has_term(text, keyword):
        return True
    # tolerate plural / small spelling variants for longer terms
    if len(keyword) >= 6:
        return fuzz.partial_ratio(keyword, text.lower()) >= 92
    return False


def coverage(keywords: list[str], text: str) -> tuple[float, list[str], list[str]]:
    """Return (ratio, present, missing)."""
    if not keywords:
        return 1.0, [], []
    present = [k for k in keywords if keyword_present(k, text)]
    missing = [k for k in keywords if k not in present]
    return len(present) / len(keywords), present, missing
