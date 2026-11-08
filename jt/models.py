"""SQLModel tables."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Job(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    source: str = Field(index=True)  # linkedin | greenhouse | lever | ashby | page
    external_id: str = Field(index=True)
    dedupe_key: str = Field(index=True)
    title: str
    company: str
    location: str = ""
    pay: str = ""
    url: str = ""
    description: str = ""
    posted: str = ""
    applicants: str = ""
    relevance: float = 0.0
    status: str = Field(default="new", index=True)  # new|shortlisted|applied|rejected|ignored
    collected_at: datetime = Field(default_factory=utcnow)


class JobAnalysis(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    job_id: int = Field(index=True, foreign_key="job.id")
    data_json: str  # validated JobRequirements JSON
    fit_score: float = 0.0
    gaps_json: str = "[]"
    provider: str = ""
    created_at: datetime = Field(default_factory=utcnow)


class GapQuestion(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    job_id: int = Field(index=True, foreign_key="job.id")
    gap: str
    question: str
    answer: str = ""
    created_at: datetime = Field(default_factory=utcnow)


class TailoredResume(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    job_id: int = Field(index=True, foreign_key="job.id")
    resume_json: str
    docx_path: str = ""
    pdf_path: str = ""
    prompt_path: str = ""
    accepted: bool = False
    created_at: datetime = Field(default_factory=utcnow)


class LLMCall(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    task: str = Field(index=True)
    provider: str
    prompt: str
    reply: str = ""
    ok: bool = False
    error: str = ""
    duration_s: float = 0.0
    created_at: datetime = Field(default_factory=utcnow)


class Application(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    job_id: int = Field(index=True, foreign_key="job.id")
    stage: str = "applied"  # applied|assessment|interview|offer|rejected
    notes: str = ""
    updated_at: datetime = Field(default_factory=utcnow)
