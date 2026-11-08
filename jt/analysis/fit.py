"""Fit score of a master profile against structured job requirements."""
from __future__ import annotations

from ..schemas import Gap, JobRequirements, MasterProfile, Requirement
from .ats import coverage, job_keywords, keyword_present
from .taxonomy import has_term

W_MUST, W_KEYWORDS, W_DOMAIN = 0.5, 0.3, 0.2


def requirement_met(req: Requirement, corpus: str) -> bool:
    kws = [k for k in req.keywords if k.strip()]
    if not kws:
        return keyword_present(req.text.lower()[:60], corpus)
    hits = sum(1 for k in kws if keyword_present(k, corpus))
    return hits >= max(1, (len(kws) + 1) // 2)


def domain_match(domain: str, profile: MasterProfile, corpus: str) -> float:
    if not domain or domain.lower() in ("general", "generalist", ""):
        return 1.0
    declared = [d.lower() for d in profile.domains]
    if any(domain.lower() in d or d in domain.lower() for d in declared):
        return 1.0
    return 0.5 if has_term(corpus, domain) else 0.0


def score_fit(req: JobRequirements, profile: MasterProfile, description: str = "") -> tuple[float, list[Gap]]:
    corpus = profile.corpus()
    gaps: list[Gap] = []

    musts = req.must_haves
    met = [r for r in musts if requirement_met(r, corpus)]
    must_ratio = len(met) / len(musts) if musts else 1.0
    for r in musts:
        if r not in met:
            gaps.append(Gap(requirement=r.text, kind="must", keywords=r.keywords))
    for r in req.nice_to_haves:
        if not requirement_met(r, corpus):
            gaps.append(Gap(requirement=r.text, kind="nice", keywords=r.keywords))

    kws = job_keywords(req.keywords, description)
    kw_ratio, _, missing = coverage(kws, corpus)
    covered_by_gaps = {k for g in gaps for k in g.keywords}
    leftover = [k for k in missing if k not in covered_by_gaps][:8]
    if leftover:
        gaps.append(Gap(requirement="Keywords missing from your profile: " + ", ".join(leftover),
                        kind="keyword", keywords=leftover))

    dom = domain_match(req.domain, profile, corpus)
    score = 100 * (W_MUST * must_ratio + W_KEYWORDS * kw_ratio + W_DOMAIN * dom)
    return round(score, 1), gaps
