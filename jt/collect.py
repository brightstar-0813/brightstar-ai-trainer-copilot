"""Run collectors, filter for relevance / US-remote / recency, and store new jobs."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from . import config, db
from .analysis.eligibility import is_us_remote
from .analysis.taxonomy import is_relevant, relevance
from .models import Job
from .sources.base import RawJob, within_max_age


@dataclass
class CollectStats:
    seen: int = 0
    irrelevant: int = 0
    not_us_remote: int = 0
    too_old: int = 0
    duplicates: int = 0
    new: int = 0
    new_ids: list[int] = field(default_factory=list)


def _default_max_age_days() -> int:
    try:
        return int(config.load_yaml("sources.yaml").get("collect", {}).get("max_age_days", 30))
    except Exception:  # noqa: BLE001
        return 30


def store(
    raw_jobs: Iterable[RawJob],
    keep_irrelevant: bool = False,
    strict: bool = True,
    us_remote_only: bool = True,
    max_age_days: int | None = None,
) -> CollectStats:
    if max_age_days is None:
        max_age_days = _default_max_age_days()
    st = CollectStats()
    with db.session() as s:
        for r in raw_jobs:
            st.seen += 1
            if not r.title or not r.company:
                continue
            if not keep_irrelevant and not is_relevant(r.title, r.description, strict=strict):
                st.irrelevant += 1
                continue
            if us_remote_only and not is_us_remote(r.location, r.description, getattr(r, "workplace", "")):
                st.not_us_remote += 1
                continue
            if not within_max_age(r.posted, max_age_days):
                st.too_old += 1
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
