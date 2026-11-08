"""Master profile import and LinkedIn profile optimization."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import yaml
from sqlmodel import select

from .. import db
from ..llm import ask_json
from ..models import JobAnalysis
from ..schemas import ImportedProfile, MasterProfile, ProfileAdvice, load_profile, save_profile
from .analyze import gaps_of, requirements_of


def read_document(path: Path) -> str:
    """Plain text from .txt/.md/.docx/.pdf."""
    suffix = path.suffix.lower()
    if suffix in (".txt", ".md"):
        return path.read_text(encoding="utf-8", errors="ignore")
    if suffix == ".docx":
        from docx import Document
        d = Document(str(path))
        lines = [p.text for p in d.paragraphs]
        for t in d.tables:
            for row in t.rows:
                lines.append(" | ".join(c.text for c in row.cells))
        return "\n".join(lines)
    if suffix == ".pdf":
        from pypdf import PdfReader
        return "\n".join((pg.extract_text() or "") for pg in PdfReader(str(path)).pages)
    raise ValueError(f"unsupported file type: {suffix}")


def import_profile(resume_path: Path | None = None, linkedin_text: str = "") -> tuple[MasterProfile, list[str]]:
    resume_text = read_document(resume_path) if resume_path else ""
    if not resume_text and not linkedin_text:
        raise ValueError("give a resume file and/or LinkedIn text")
    layout = json.dumps(MasterProfile().model_dump(), indent=1)
    out = ask_json("resume_import", ImportedProfile, {
        "resume_text": resume_text, "linkedin_text": linkedin_text, "layout": layout})
    profile = MasterProfile.model_validate(out.profile)
    return profile, out.missing_evidence_questions


def market_data() -> dict:
    """Aggregate keywords, domains and the candidate's most frequent gaps across analyzed jobs."""
    kw, dom, gaps = Counter(), Counter(), Counter()
    n = 0
    with db.session() as s:
        latest: dict[int, JobAnalysis] = {}
        for a in s.exec(select(JobAnalysis).order_by(JobAnalysis.id)).all():
            latest[a.job_id] = a
    for a in latest.values():
        n += 1
        req = requirements_of(a)
        kw.update(k.lower() for k in req.keywords)
        if req.domain:
            dom[req.domain.lower()] += 1
        for g in gaps_of(a):
            if g.kind == "keyword":
                gaps.update(k for k in g.keywords)
            else:
                gaps[g.requirement] += 1
    return {"n_jobs": n, "top_keywords": [k for k, _ in kw.most_common(25)], "keyword_counts": kw.most_common(25),
            "top_domains": [d for d, _ in dom.most_common(6)], "top_gaps": gaps.most_common(12),
            "top_requirements": top_requirements(latest.values())}


def top_requirements(analyses, limit: int = 12) -> list[str]:
    c: Counter = Counter()
    for a in analyses:
        for r in requirements_of(a).must_haves:
            c[r.text.strip().lower()[:90]] += 1
    return [t for t, _ in c.most_common(limit)]


def optimize_profile(profile: str | None = None) -> ProfileAdvice:
    cand = load_profile(profile)
    md = market_data()
    return ask_json("profile_optimize", ProfileAdvice, {
        "profile_yaml": cand.to_yaml(), "n_jobs": md["n_jobs"], "top_keywords": md["top_keywords"],
        "top_domains": md["top_domains"], "top_gaps": md["top_gaps"]})


def advice_to_markdown(a: ProfileAdvice) -> str:
    def bl(items): return "\n".join(f"- {i}" for i in items) or "- (none)"
    return (
        "# LinkedIn profile advice\n\n## Headline options\n" + bl(a.headline_options) +
        "\n\n## About\n" + a.about + "\n\n## Featured\n" + bl(a.featured) +
        "\n\n## Skills order\n" + "\n".join(f"{i}. {s}" for i, s in enumerate(a.skills_order, 1)) +
        "\n\n## Experience edits\n" + bl(a.experience_edits) +
        "\n\n## Certifications to get\n" + bl(a.certifications_to_get) +
        "\n\n## Projects to build\n" + bl(a.projects_to_build) +
        "\n\n## Quick wins\n" + bl(a.quick_wins) + "\n")


def merge_answers_into_profile(answers: dict[str, str], profile: str | None = None) -> MasterProfile:
    """Append answered evidence to the profile's achievements so later tailoring can use it."""
    p = load_profile(profile)
    for q, a in answers.items():
        if a.strip():
            p.achievements.append(f"{a.strip()}  (answer to: {q})")
    save_profile(p, slug=profile, activate=False)
    return p


def dump_yaml(p: MasterProfile) -> str:
    return yaml.safe_dump(p.model_dump(), allow_unicode=True, sort_keys=False)
