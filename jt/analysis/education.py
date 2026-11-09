"""Degree ranking and resume education selection for multi-degree candidates."""
from __future__ import annotations

import re
from typing import Iterable, Sequence

from ..schemas import Education, JobRequirements, MasterProfile

# Higher = more advanced terminal credential. Professional doctorates sit with research PhDs.
_DEGREE_PATTERNS: list[tuple[int, re.Pattern[str]]] = [
    (6, re.compile(r"\b(post[- ]?doc|postdoctoral)\b", re.I)),
    (5, re.compile(
        r"\b(ph\.?\s*d\.?|dphil|doctorate|doctoral|edd|th\.?\s*d\.?)\b", re.I)),
    (5, re.compile(r"\b(j\.?\s*d\.?|m\.?\s*d\.?|d\.?\s*o\.?|pharm\.?\s*d\.?|d\.?\s*d\.?\s*s\.?|dvm)\b", re.I)),
    (3, re.compile(r"\b(m\.?\s*s\.?|m\.?\s*sc\.?|m\.?\s*a\.?|mba|m\.?\s*eng\.?|mfa|mph|meng|llm)\b", re.I)),
    (3, re.compile(r"\bmaster'?s?\b", re.I)),
    (2, re.compile(r"\b(b\.?\s*s\.?|b\.?\s*sc\.?|b\.?\s*a\.?|b\.?\s*eng\.?|bfa|bba|llb)\b", re.I)),
    (2, re.compile(r"\bbachelor'?s?\b", re.I)),
    (1, re.compile(r"\b(associate|a\.?\s*s\.?|a\.?\s*a\.?)\b", re.I)),
]

_MAX_RESUME_DEGREES = 4


def degree_rank(degree: str) -> int:
    """Return a comparable rank for a degree string (0 = unknown)."""
    text = (degree or "").strip()
    if not text:
        return 0
    for rank, pat in _DEGREE_PATTERNS:
        if pat.search(text):
            return rank
    return 0


def required_degree_rank(education_required: str) -> int:
    """Highest degree bar stated by the posting (0 if none / unclear)."""
    return degree_rank(education_required or "")


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(t) > 2}


def _field_relevance(field: str, domain: str, keywords: Iterable[str]) -> float:
    field_toks = _tokens(field)
    if not field_toks:
        return 0.0
    want = _tokens(domain) | {t for k in keywords for t in _tokens(k)}
    if not want:
        return 0.0
    overlap = field_toks & want
    if not overlap:
        # soft stem-ish containment for phrases like "computer science" vs "cs"
        joined = " ".join(field_toks)
        if any(w in joined for w in want if len(w) >= 4):
            return 0.5
        return 0.0
    return len(overlap) / max(len(field_toks), 1)


def _end_key(edu: Education) -> str:
    return (edu.end or edu.start or "").strip()


def select_education(
    education: Sequence[Education],
    *,
    education_required: str = "",
    domain: str = "",
    keywords: Sequence[str] | None = None,
    limit: int = _MAX_RESUME_DEGREES,
) -> list[Education]:
    """Pick which degrees to surface on a tailored one-page resume.

    Profile truth may hold many degrees. A resume should keep:
    - the highest credential(s)
    - the progressive ladder toward that terminal degree (same/related field)
    - any extra degree whose field matches the job domain or keywords
    Unrelated lower degrees are dropped when over the limit.
    """
    entries = [e for e in education if (e.school or e.degree or e.field)]
    if not entries:
        return []
    kws = list(keywords or [])
    bar = required_degree_rank(education_required)

    ranked = sorted(
        entries,
        key=lambda e: (degree_rank(e.degree), _field_relevance(e.field, domain, kws), _end_key(e)),
        reverse=True,
    )
    terminal = ranked[0]
    terminal_rank = degree_rank(terminal.degree)
    terminal_field = _tokens(terminal.field)
    terminal_end = _end_key(terminal)

    keep: list[Education] = []
    seen: set[int] = set()

    def add(edu: Education) -> None:
        i = id(edu)
        if i in seen:
            return
        seen.add(i)
        keep.append(edu)

    # Always keep every degree at the terminal rank (e.g. dual PhDs / JD+MD).
    for e in ranked:
        if degree_rank(e.degree) == terminal_rank and terminal_rank > 0:
            add(e)
        elif terminal_rank == 0 and e is terminal:
            add(e)

    def ladder_score(e: Education) -> tuple:
        """Prefer same/related field, then most recent prior degree at this rank."""
        related = 1 if (_tokens(e.field) & terminal_field) or not terminal_field else 0
        end = _end_key(e)
        prior = 1 if (not terminal_end or not end or end <= terminal_end) else 0
        return (related, prior, end)

    # Progressive ladder: at most one entry per lower rank (BS, then MS, …).
    for rank in range(terminal_rank - 1, 0, -1):
        candidates = [e for e in entries if degree_rank(e.degree) == rank]
        if not candidates:
            continue
        candidates.sort(key=ladder_score, reverse=True)
        add(candidates[0])

    # Job-relevant extras (second bachelor's / MBA / domain master's, etc.).
    for e in ranked:
        if _field_relevance(e.field, domain, kws) >= 0.34:
            add(e)
        elif bar and degree_rank(e.degree) >= bar:
            add(e)

    # Prefer reverse-chronological, then higher rank.
    keep.sort(key=lambda e: (_end_key(e), degree_rank(e.degree)), reverse=True)

    if len(keep) > limit:
        # Never drop the terminal credential(s); prefer ladder + relevant extras.
        terminals = [e for e in keep if degree_rank(e.degree) == terminal_rank]
        rest = [e for e in keep if degree_rank(e.degree) != terminal_rank]
        rest.sort(
            key=lambda e: (
                _field_relevance(e.field, domain, kws),
                1 if (_tokens(e.field) & terminal_field) else 0,
                degree_rank(e.degree),
                _end_key(e),
            ),
            reverse=True,
        )
        room = max(0, limit - len(terminals))
        keep = terminals + rest[:room]
        keep.sort(key=lambda e: (_end_key(e), degree_rank(e.degree)), reverse=True)

    return keep


def profile_for_resume(profile: MasterProfile, req: JobRequirements | None = None) -> MasterProfile:
    """Copy of the master profile with education trimmed for resume drafting."""
    if req is None:
        selected = select_education(profile.education)
    else:
        selected = select_education(
            profile.education,
            education_required=req.education_required,
            domain=req.domain,
            keywords=req.keywords,
        )
    if selected == list(profile.education):
        return profile
    return profile.model_copy(update={"education": selected})
