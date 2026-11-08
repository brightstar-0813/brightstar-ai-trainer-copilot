"""Run collectors, filter for relevance, and store new jobs."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from . import db
from .analysis.taxonomy import is_relevant, relevance
from .models import Job
from .sources.base import RawJob


@dataclass
class CollectStats:
    seen: int = 0
    irrelevant: int = 0
    duplicates: int = 0
    new: int = 0
    new_ids: list[int] = field(default_factory=list)


def store(raw_jobs: Iterable[RawJob], keep_irrelevant: bool = False, strict: bool = True) -> CollectStats:
    st = CollectStats()
    with db.session() as s:
        for r in raw_jobs:
            st.seen += 1
            if not r.title or not r.company:
                continue
            if not keep_irrelevant and not is_relevant(r.title, r.description, strict=strict):
                st.irrelevant += 1
                continue
            job = Job(
                source=r.source, external_id=r.external_id,
                dedupe_key=db.make_dedupe_key(r.company, r.title),
                title=r.title, company=r.company, location=r.location, pay=r.pay, url=r.url,
                description=r.description, posted=r.posted, applicants=r.applicants,
                relevance=relevance(r.title, r.description))
            saved, created = db.upsert_job(s, job)
            if created:
                st.new += 1
                st.new_ids.append(saved.id)
            else:
                st.duplicates += 1
    return st
