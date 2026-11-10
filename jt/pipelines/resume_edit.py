"""Save Word-like resume edits back into teaching models and tailored resumes."""
from __future__ import annotations

import json
from pathlib import Path

from sqlmodel import select

from .. import config, db
from ..llm.prefs import preferred_resume_accent, preferred_resume_template
from ..models import TailoredResume
from ..render.html_parse import ResumeHtmlParseError, parse_resume_html
from ..render.resume import render_all
from ..schemas import (
    ResumeContent,
    ResumeEducation,
    ResumeProject,
    ResumeRole,
    SkillGroup,
    SuggestedBenchmark,
)
from .samples import load_suggestion_dir, write_suggestion_artifacts


def resume_from_edited_html(html: str) -> ResumeContent:
    """Parse edited resume HTML into ResumeContent (raises ResumeHtmlParseError)."""
    return parse_resume_html(html)


def apply_resume_to_suggestion(s: SuggestedBenchmark, r: ResumeContent) -> SuggestedBenchmark:
    """Copy editable resume fields onto a teaching model; keep coach-only metadata."""
    out = s.model_copy(deep=True)
    out.persona_name = (r.name or out.persona_name or "").strip()
    out.contact = (r.contact or "").strip()
    sample = out.sample
    sample.headline = r.headline or sample.headline
    sample.about = r.summary or sample.about
    sample.skills = list(r.skills or [])
    sample.skill_groups = [
        SkillGroup(category=g.category, items=list(g.items))
        for g in (r.skill_groups or [])
        if g.category and g.items
    ]
    sample.experience = [
        ResumeRole(
            company=e.company,
            title=e.title,
            start=e.start,
            end=e.end,
            location=e.location,
            bullets=list(e.bullets or []),
        )
        for e in (r.experience or [])
    ]
    sample.education = [
        ResumeEducation(
            school=e.school,
            degree=e.degree,
            field=e.field,
            dates=e.dates,
            details=list(e.details or []),
        )
        for e in (r.education or [])
    ]
    sample.licenses = list(r.licenses or [])
    sample.certifications = list(r.certifications or [])
    sample.licenses_certs = []
    projects = [
        ResumeProject(name=p.name, description=p.description, link=p.link or "")
        for p in (r.projects or [])
        if (p.name or "").strip()
    ]
    if projects:
        sample.projects = projects
    # TargetedSample requires >=1 project; keep previous if editor cleared them.
    return out


def save_teaching_resume_edit(folder: Path | str, html: str) -> dict[str, str]:
    """Parse edited HTML, update suggestion.json, and rewrite DOCX/HTML/PDF/MD."""
    folder = Path(folder)
    resume = resume_from_edited_html(html)
    suggestion = apply_resume_to_suggestion(load_suggestion_dir(folder), resume)
    return write_suggestion_artifacts(suggestion, out=folder)


def save_tailored_resume_edit(job_id: int, html: str) -> TailoredResume:
    """Parse edited HTML, append a new TailoredResume row, and rewrite files."""
    resume = resume_from_edited_html(html)
    with db.session() as s:
        row = s.exec(
            select(TailoredResume)
            .where(TailoredResume.job_id == job_id)
            .order_by(TailoredResume.id.desc())
        ).first()
        if row is None:
            raise LookupError(f"No tailored resume for job {job_id}")
        payload = json.loads(row.resume_json)
        meta = payload.get("meta") or {}
        # Preserve teaching/unverified notes from the prior draft when the editor
        # does not surface them.
        prior = payload.get("resume") or {}
        if not resume.unverified_claims and prior.get("unverified_claims"):
            resume.unverified_claims = list(prior.get("unverified_claims") or [])
        outdir = config.OUTPUT_DIR / "resumes" / str(job_id)
        paths = render_all(
            resume,
            outdir,
            stem="resume",
            template_id=preferred_resume_template(),
            accent_id=preferred_resume_accent() or None,
        )
        new_row = TailoredResume(
            job_id=job_id,
            resume_json=json.dumps({"resume": resume.model_dump(), "meta": meta}),
            docx_path=paths["docx"],
            pdf_path=paths["pdf"],
            prompt_path=row.prompt_path,
        )
        s.add(new_row)
        s.commit()
        s.refresh(new_row)
        return new_row


__all__ = [
    "ResumeHtmlParseError",
    "apply_resume_to_suggestion",
    "resume_from_edited_html",
    "save_teaching_resume_edit",
    "save_tailored_resume_edit",
]
