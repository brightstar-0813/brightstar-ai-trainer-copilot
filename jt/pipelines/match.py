"""One-off JD + resume/profile screen: fit, ATS coverage, top-0.1% recruiter verdict."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Optional

from sqlmodel import select

from .. import config, db
from ..analysis.ats import coverage, job_keywords
from ..analysis.fit import score_fit
from ..llm import ask_json
from ..models import Job, JobAnalysis
from ..schemas import (
    Gap,
    JobRequirements,
    MasterProfile,
    MatchReport,
    TopTierScreen,
    load_profile,
)
from .profile import import_profile, read_document

BANDS = (
    (80.0, "Strong"),
    (60.0, "Interview"),
    (40.0, "Stretch"),
    (0.0, "Reject"),
)


def screen_band(fit_score: float) -> str:
    for threshold, label in BANDS:
        if fit_score >= threshold:
            return label
    return "Reject"


def fit_percentile(fit_score: float) -> Optional[float]:
    """Percentile of this fit among existing JobAnalysis scores (higher is better). None if none."""
    with db.session() as s:
        scores = [a.fit_score for a in s.exec(select(JobAnalysis)).all()]
    if not scores:
        return None
    below = sum(1 for x in scores if x < fit_score)
    return round(100.0 * below / len(scores), 1)


def _resolve_jd(
    jd: str = "",
    jd_file: Path | None = None,
    job_id: int | None = None,
) -> SimpleNamespace:
    title, company, location, pay, source, description = "", "", "", "", "paste", ""
    if job_id is not None:
        with db.session() as s:
            job = s.get(Job, job_id)
            if not job:
                raise KeyError(f"job {job_id} not found")
            title, company = job.title, job.company
            location, pay, source = job.location, job.pay or "", job.source
            description = job.description or ""
    if jd_file is not None:
        description = read_document(jd_file)
        source = source if job_id is not None else "jd_file"
    if jd and jd.strip():
        description = jd.strip()
        source = source if job_id is not None else "paste"
    if not description.strip():
        raise ValueError("provide --jd, --jd-file, or --job-id with a description")
    if not title:
        title = "Pasted job"
    return SimpleNamespace(
        title=title,
        company=company or "Unknown",
        location=location,
        pay=pay,
        source=source,
        description=description,
    )


def _resolve_profile(
    resume: Path | None = None,
    resume_text: str = "",
    profile: str | None = None,
) -> tuple[MasterProfile, str, str]:
    """Return (profile, candidate_source, corpus_extra_text)."""
    if resume is not None:
        text = read_document(resume)
        cand, _qs = import_profile(resume)
        return cand, f"resume:{resume.name}", text
    if resume_text.strip():
        tmp = config.OUTPUT_DIR / "matches" / "_tmp_resume.txt"
        tmp.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(resume_text, encoding="utf-8")
        try:
            cand, _qs = import_profile(tmp)
        finally:
            tmp.unlink(missing_ok=True)
        return cand, "resume:paste", resume_text
    from ..schemas import resolve_profile_slug
    slug = resolve_profile_slug(profile)
    cand = load_profile(slug)
    return cand, f"profile:{slug}", ""


def report_to_markdown(report: MatchReport) -> str:
    screen = report.screen
    lines = [
        "# Top 0.1% screen report",
        "",
        f"**JD:** {report.jd_title} @ {report.jd_company}",
        f"**Candidate:** {report.candidate_source}",
        "",
        f"- Fit: **{report.fit_score:.0f}/100** ({report.screen_band})",
        f"- ATS coverage: **{report.ats_coverage:.0f}%**",
    ]
    if report.percentile is not None:
        lines.append(f"- Fit percentile vs analyzed jobs: **{report.percentile:.0f}th**")
    if screen:
        lines += [
            "",
            "## Top 0.1% verdict",
            f"- Tier: **{screen.tier_label}** (top-tier: {screen.is_top_tier}, confidence: {screen.confidence})",
            "",
            screen.verdict,
            "",
            "### Strengths",
            *([f"- {x}" for x in screen.strengths] or ["- (none)"]),
            "",
            "### Gaps vs top 0.1% bar",
            *([f"- {x}" for x in screen.gaps_vs_bar] or ["- (none)"]),
            "",
            "### ATS risks",
            *([f"- {x}" for x in screen.ats_risks] or ["- (none)"]),
            "",
            "### Recruiter notes",
            *([f"- {x}" for x in screen.recruiter_notes] or ["- (none)"]),
            "",
            "### Priority actions",
            *([f"- {x}" for x in screen.priority_actions] or ["- (none)"]),
        ]
    lines += [
        "",
        "## Keyword coverage",
        f"- Present: {', '.join(report.keywords_present) or '(none)'}",
        f"- Missing: {', '.join(report.keywords_missing) or '(none)'}",
        "",
        "## Profile gaps vs JD",
        *([f"- [{g.kind}] {g.requirement}" for g in report.gaps] or ["- (none)"]),
        "",
    ]
    return "\n".join(lines)


def screen_match(
    jd: str = "",
    jd_file: Path | None = None,
    job_id: int | None = None,
    resume: Path | None = None,
    resume_text: str = "",
    profile: str | None = None,
) -> MatchReport:
    job = _resolve_jd(jd=jd, jd_file=jd_file, job_id=job_id)
    cand, candidate_source, extra_text = _resolve_profile(
        resume=resume, resume_text=resume_text, profile=profile)

    req = ask_json("job_analyze", JobRequirements, {"job": job})
    fit, gaps = score_fit(req, cand, job.description)
    band = screen_band(fit)
    kws = job_keywords(req.keywords, job.description)
    corpus = cand.corpus()
    if extra_text:
        corpus = f"{corpus}\n{extra_text.lower()}"
    ratio, present, missing = coverage(kws, corpus)
    ats_pct = round(100.0 * ratio, 1)
    percentile = fit_percentile(fit)

    screen = ask_json(
        "match_screen",
        TopTierScreen,
        {
            "job": job,
            "requirements": req,
            "fit_score": fit,
            "screen_band": band,
            "ats_coverage": ats_pct,
            "keywords_present": present,
            "keywords_missing": missing,
            "gaps": gaps,
            "profile_yaml": cand.to_yaml(),
        },
    )

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = config.OUTPUT_DIR / "matches" / stamp
    out_dir.mkdir(parents=True, exist_ok=True)

    report = MatchReport(
        fit_score=fit,
        ats_coverage=ats_pct,
        screen_band=band,
        percentile=percentile,
        keywords_present=present,
        keywords_missing=missing,
        gaps=gaps,
        requirements=req,
        screen=screen,
        jd_title=job.title,
        jd_company=job.company,
        candidate_source=candidate_source,
        report_dir=str(out_dir),
    )
    (out_dir / "report.json").write_text(report.model_dump_json(indent=2), encoding="utf-8")
    (out_dir / "report.md").write_text(report_to_markdown(report), encoding="utf-8")
    (out_dir / "jd.txt").write_text(job.description, encoding="utf-8")
    return report
