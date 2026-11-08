"""Database engine and helpers."""
from __future__ import annotations

import re
from contextlib import contextmanager
from typing import Iterator

from rapidfuzz import fuzz
from sqlmodel import Session, SQLModel, create_engine, select

from . import config
from .models import Job

_engine = None


def get_engine():
    global _engine
    if _engine is None:
        config.ensure_dirs()
        _engine = create_engine(f"sqlite:///{config.DB_PATH}", connect_args={"check_same_thread": False})
        SQLModel.metadata.create_all(_engine)
    return _engine


@contextmanager
def session() -> Iterator[Session]:
    with Session(get_engine(), expire_on_commit=False) as s:
        yield s


def normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def make_dedupe_key(company: str, title: str) -> str:
    return f"{normalize(company)}|{normalize(title)}"


def upsert_job(s: Session, job: Job) -> tuple[Job, bool]:
    """Insert a job unless a duplicate exists. Returns (job, created)."""
    existing = s.exec(
        select(Job).where(Job.source == job.source, Job.external_id == job.external_id)
    ).first()
    if existing:
        return existing, False
    same = s.exec(select(Job).where(Job.dedupe_key == job.dedupe_key)).all()
    for other in same:
        if not job.description or not other.description:
            return other, False
        if fuzz.token_set_ratio(job.description[:2000], other.description[:2000]) >= 90:
            return other, False
    s.add(job)
    s.commit()
    s.refresh(job)
    return job, True
