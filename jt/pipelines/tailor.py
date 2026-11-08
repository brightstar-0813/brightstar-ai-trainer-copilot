"""Resume tailoring: gap questions -> user answers -> tailored resume -> humanize -> verify -> render."""
from __future__ import annotations

import json
import re

from sqlmodel import select

from .. import config, db
from ..analysis.ats import coverage, job_keywords
from ..llm import ask_json
from ..llm.client import LLMError, render_prompt
from ..models import GapQuestion, Job, TailoredResume
from ..render.resume import render_all
from ..schemas import (GapQuestions, HumanizedResume, MasterProfile, ResumeContent, load_profile)
from .analyze import analyze_job, gaps_of, latest_analysis, requirements_of

_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?%?")


# ---------------------------------------------------------------- fact guard (pure, unit-tested)
def verify_resume(resume: ResumeContent, profile: MasterProfile, answers_text: str = "") -> list[str]:
    """Flag content that cannot be traced to the profile or the candidate's answers."""
    corpus = profile.corpus() + " " + answers_text.lower()
    corpus_nums = {n.rstrip("%").replace(",", "") for n in _NUM.findall(corpus)}
    warnings: list[str] = []

    def known(text: str) -> bool:
        t = re.sub(r"[^a-z0-9 ]", "", text.lower()).strip()
        return not t or t in re.sub(r"[^a-z0-9 ]", " ", corpus)

    for r in resume.experience:
        if not known(r.company):
            warnings.append(f"Employer not in profile: {r.company}")
        for b in r.bullets:
            for n in _NUM.findall(b):
                bare = n.rstrip("%").replace(",", "")
                if len(bare) >= 2 and bare not in corpus_nums:
                    warnings.append(f"Number '{n}' not found in profile/answers: \"{b[:70]}...\"")
    for e in resume.education:
        if not known(e.school):
            warnings.append(f"School not in profile: {e.school}")
    for label, items in (("License", resume.licenses), ("Certification", resume.certifications)):
        for c in items:
            key = re.sub(r"\(.*?\)", "", c).strip()
            if key and not known(key.split(",")[0]):
                warnings.append(f"{label} not in profile: {c}")
    return warnings


def resume_text(r: ResumeContent) -> str:
    skill_bits = list(r.skills)
    for g in r.skill_groups or []:
        skill_bits += [g.category, *g.items]
    parts = [
        r.headline,
        r.summary,
        " ".join(skill_bits),
        " ".join(r.licenses),
        " ".join(r.certifications),
        " ".join(r.additional),
    ]
    for e in r.experience:
        parts += [e.title, e.company, *e.bullets]
    for p in r.projects:
        parts += [p.name, p.description]
    for e in r.education:
        parts += [e.degree, e.field, e.school, *e.details]
    return "\n".join(parts).lower()


# ---------------------------------------------------------------- questions
def generate_questions(job_id: int, regenerate: bool = False,
                       profile: str | None = None) -> list[GapQuestion]:
    with db.session() as s:
        existing = s.exec(select(GapQuestion).where(GapQuestion.job_id == job_id)).all()
        if existing and not regenerate:
            return list(existing)
        job = s.get(Job, job_id)
        analysis = latest_analysis(s, job_id)
    if analysis is None:
        analysis = analyze_job(job_id, profile=profile)
    gaps = gaps_of(analysis)[:12]
    if not gaps:
        return []
    out = ask_json("gap_questions", GapQuestions, {
        "job": job, "requirements": requirements_of(analysis), "gaps": gaps,
        "profile_yaml": load_profile(profile).to_yaml()})
    with db.session() as s:
        for old in s.exec(select(GapQuestion).where(GapQuestion.job_id == job_id)).all():
            s.delete(old)
        rows = [GapQuestion(job_id=job_id, gap=q.gap, question=q.question) for q in out.questions]
        s.add_all(rows)
        s.commit()
        for r in rows:
            s.refresh(r)
        return rows


def answer_question(question_id: int, answer: str) -> None:
    with db.session() as s:
        q = s.get(GapQuestion, question_id)
        q.answer = answer.strip()
        s.add(q)
        s.commit()


def answered(job_id: int) -> list[GapQuestion]:
    with db.session() as s:
        rows = s.exec(select(GapQuestion).where(GapQuestion.job_id == job_id)).all()
    return [q for q in rows if q.answer.strip()]


# ---------------------------------------------------------------- tailoring
def tailor_job(job_id: int, humanize: bool = True, profile: str | None = None) -> TailoredResume:
    cand = load_profile(profile)
    with db.session() as s:
        job = s.get(Job, job_id)
        analysis = latest_analysis(s, job_id)
    if analysis is None:
        analysis = analyze_job(job_id, profile=profile)
    req = requirements_of(analysis)
    answers = answered(job_id)
    ctx = {"job": job, "requirements": req, "profile_yaml": cand.to_yaml(), "answers": answers}

    resume = ask_json("resume_tailor", ResumeContent, ctx)
    changes: list[str] = []
    if humanize:
        try:
            h = ask_json("humanize", HumanizedResume, {"resume_json": resume.model_dump_json(indent=1)})
            resume, changes = h.resume, h.changes
        except LLMError:
            changes = ["humanize pass skipped (LLM error)"]

    answers_text = " ".join(f"{q.question} {q.answer}" for q in answers)
    warnings = verify_resume(resume, cand, answers_text)
    kws = job_keywords(req.keywords, job.description)
    ratio, present, missing = coverage(kws, resume_text(resume))
    meta = {"ats_coverage": round(ratio * 100), "keywords_present": present, "keywords_missing": missing,
            "warnings": warnings, "llm_unverified": resume.unverified_claims, "humanize_changes": changes,
            "fit_score": analysis.fit_score}

    from ..llm.prefs import preferred_resume_accent, preferred_resume_template

    outdir = config.OUTPUT_DIR / "resumes" / str(job_id)
    paths = render_all(
        resume,
        outdir,
        stem="resume",
        template_id=preferred_resume_template(),
        accent_id=preferred_resume_accent() or None,
    )
    prompt_path = outdir / "resume_prompt.md"
    prompt_path.write_text(export_prompt(job, req, cand, answers), encoding="utf-8")
    (outdir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    with db.session() as s:
        row = TailoredResume(job_id=job_id, resume_json=json.dumps({"resume": resume.model_dump(), "meta": meta}),
                             docx_path=paths["docx"], pdf_path=paths["pdf"], prompt_path=str(prompt_path))
        s.add(row)
        s.commit()
        s.refresh(row)
        return row


def export_prompt(job: Job, req, profile: MasterProfile, answers: list[GapQuestion]) -> str:
    """A self-contained prompt the user can paste into any LLM to regenerate or tweak the resume."""
    base = render_prompt("resume_tailor", job=job, requirements=req, profile_yaml=profile.to_yaml(), answers=answers)
    return (base + "\n\nFULL JOB DESCRIPTION\n" + job.description +
            "\n\nOUTPUT: A complete one-page resume in Markdown, followed by a list of any claims you could not "
            "trace to the candidate profile or answers.\n")


def latest_resume(job_id: int) -> TailoredResume | None:
    with db.session() as s:
        return s.exec(select(TailoredResume).where(TailoredResume.job_id == job_id)
                      .order_by(TailoredResume.id.desc())).first()
