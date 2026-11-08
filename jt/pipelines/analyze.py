"""Job analysis: LLM extracts requirements, local code scores fit against the active profile."""
from __future__ import annotations

import json
import time
from typing import Callable

from sqlmodel import select

from .. import db
from ..analysis.fit import score_fit
from ..llm import ask_json
from ..llm.client import LLMError, task_config
from ..models import Job, JobAnalysis, utcnow
from ..schemas import Gap, JobRequirements, MasterProfile, load_profile


def requirements_of(a: JobAnalysis) -> JobRequirements:
    return JobRequirements.model_validate_json(a.data_json)


def gaps_of(a: JobAnalysis) -> list[Gap]:
    return [Gap.model_validate(g) for g in json.loads(a.gaps_json or "[]")]


def _profile_or_none(slug: str | None = None) -> MasterProfile | None:
    try:
        return load_profile(slug)
    except FileNotFoundError:
        return None


def latest_analysis(s, job_id: int) -> JobAnalysis | None:
    return s.exec(select(JobAnalysis).where(JobAnalysis.job_id == job_id)
                  .order_by(JobAnalysis.id.desc())).first()


def analyze_job(job_id: int, force: bool = False, profile: str | None = None) -> JobAnalysis:
    with db.session() as s:
        job = s.get(Job, job_id)
        if not job:
            raise KeyError(f"job {job_id} not found")
        existing = latest_analysis(s, job_id)
        if existing and not force:
            return existing
    req = ask_json("job_analyze", JobRequirements, {"job": job})
    cand = _profile_or_none(profile)
    score, gaps = score_fit(req, cand, job.description) if cand else (0.0, [])
    with db.session() as s:
        a = JobAnalysis(job_id=job_id, data_json=req.model_dump_json(), fit_score=score,
                        gaps_json=json.dumps([g.model_dump() for g in gaps]),
                        provider=task_config("job_analyze").get("provider", ""))
        s.add(a)
        s.commit()
        s.refresh(a)
        return a


def rescore_all(profile: str | None = None) -> int:
    """Recompute fit and gaps for every analysis (run after the profile changes)."""
    cand = _profile_or_none(profile)
    if not cand:
        raise FileNotFoundError("no active profile yet")
    n = 0
    with db.session() as s:
        for a in s.exec(select(JobAnalysis)).all():
            job = s.get(Job, a.job_id)
            score, gaps = score_fit(requirements_of(a), cand, job.description if job else "")
            a.fit_score, a.gaps_json = score, json.dumps([g.model_dump() for g in gaps])
            s.add(a)
            n += 1
        s.commit()
    return n


def pending_job_ids(limit: int | None = None, min_relevance: float = 0.0) -> list[int]:
    with db.session() as s:
        analyzed = {a.job_id for a in s.exec(select(JobAnalysis)).all()}
        jobs = s.exec(select(Job).where(Job.status.not_in(["ignored", "rejected"]))).all()
    ids = [j.id for j in sorted(jobs, key=lambda j: -j.relevance)
           if j.id not in analyzed and j.relevance >= min_relevance]
    return ids[:limit] if limit else ids


def analyze_pending(limit: int | None = None, pace_seconds: float = 5.0,
                    on_event: Callable[[str], None] = print,
                    profile: str | None = None) -> tuple[int, int]:
    """Analyze jobs that have no analysis yet. Stops cleanly on usage-limit errors."""
    done = failed = 0
    ids = pending_job_ids(limit)
    for i, jid in enumerate(ids, 1):
        try:
            a = analyze_job(jid, profile=profile)
            done += 1
            on_event(f"[{i}/{len(ids)}] job {jid}: fit {a.fit_score:.0f}")
        except LLMError as e:
            failed += 1
            on_event(f"[{i}/{len(ids)}] job {jid}: FAILED {e.code}: {e}")
            if e.code in ("usage_limit", "no_extension", "no_bridge", "not_logged_in", "bad_token",
                          "no_api_key", "api_auth", "api_rate_limit"):
                on_event("Stopping: fix the problem above and rerun (finished jobs are kept).")
                break
        if i < len(ids):
            time.sleep(pace_seconds)
    return done, failed


def ranked(limit: int = 50) -> list[tuple[Job, JobAnalysis]]:
    with db.session() as s:
        best: dict[int, JobAnalysis] = {}
        for a in s.exec(select(JobAnalysis).order_by(JobAnalysis.id)).all():
            best[a.job_id] = a
        rows = [(s.get(Job, jid), a) for jid, a in best.items()]
    rows.sort(key=lambda r: -r[1].fit_score)
    return rows[:limit]
