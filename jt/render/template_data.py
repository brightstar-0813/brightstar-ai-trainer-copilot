"""Map Job Copilot ResumeContent → Bid bot template JSON shape."""
from __future__ import annotations

import re
from typing import Any

from ..schemas import ResumeContent


def sample_preview_data() -> dict[str, Any]:
    """Generic Bid-bot-style sample used for Overview template preview."""
    return {
        "name": "Alex Rivera",
        "headline": "Senior Software Engineer",
        "location": "Austin, Texas, United States",
        "phone": "+1 (555) 010-2048",
        "email": "alex.rivera@email.com",
        "linkedin": "https://linkedin.com/in/alexrivera",
        "profile": (
            "Senior engineer with 10+ years delivering CRM platforms, integrations, "
            "and release automation for enterprise teams."
        ),
        "technicalSummary": [
            "Designed multi-cloud CRM architecture used by 2,400+ agents with 99.9% uptime.",
            "Led integration programs covering REST, SOAP, ETL, and event-driven patterns.",
            "Cut release cycle time 40% by introducing CI/CD and automated tests.",
        ],
        "skills": [
            {"category": "Languages", "items": "Apex, JavaScript, TypeScript, SQL"},
            {"category": "Platform", "items": "Salesforce, Lightning Web Components, Flow"},
            {"category": "Integrations", "items": "REST, SOAP, Platform Events, Data Loader"},
        ],
        "experience": [
            {
                "company": "Northstar Digital",
                "location": "Austin, TX",
                "title": "Senior Software Engineer",
                "dates": "Jan 2021 – Present",
                "bullets": [
                    "Rebuilt service console workflows in Lightning, reducing handle time 18%.",
                    "Implemented bulk-safe Apex services handling 1.2M nightly records.",
                ],
            },
            {
                "company": "Harbor & Co.",
                "location": "Dallas, TX",
                "title": "Software Engineer",
                "dates": "Mar 2017 – Dec 2020",
                "bullets": [
                    "Delivered REST integrations between CRM, billing, and warehouse systems.",
                    "Mentored four engineers on design reviews and production diagnostics.",
                ],
            },
        ],
        "education": [
            {
                "school": "University of Texas at Austin",
                "degree": "B.S. Computer Science",
                "year": "2014 - 2018",
                "location": "Austin, Texas",
            }
        ],
        "certifications": [
            "Salesforce Certified Administrator",
            "Salesforce Certified Platform Developer I",
        ],
        "projects": [],
    }

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_URL = re.compile(r"(?i)(https?://|www\.|linkedin\.com)")
_PHONE = re.compile(r"^\+?[\d().\s-]{7,}$")


def parse_contact_line(contact: str) -> dict[str, str]:
    """Split a single contact line (loc | email | phone | url) into fields."""
    out: dict[str, str] = {}
    for part in re.split(r"\s*\|\s*", contact or ""):
        text = part.strip()
        if not text:
            continue
        if _EMAIL.match(text) or ("@" in text and " " not in text):
            out["email"] = text.replace("mailto:", "")
        elif _URL.search(text):
            out["linkedin"] = text
        elif _PHONE.match(text.replace(" ", "")):
            out["phone"] = text
        elif "location" not in out:
            out["location"] = text
        else:
            out.setdefault("phone", text)
    return out


def _role_dates(start: str, end: str) -> str:
    start, end = (start or "").strip(), (end or "").strip()
    if start and end:
        return f"{start} - {end}"
    return start or end


def resume_to_template_data(r: ResumeContent) -> dict[str, Any]:
    """Bid-bot-compatible resume payload for template.render()."""
    contact = parse_contact_line(r.contact)
    skills = [{"category": "Core Competencies", "items": " · ".join(r.skills)}] if r.skills else []
    experience = [
        {
            "company": e.company,
            "title": e.title,
            "location": e.location,
            "dates": _role_dates(e.start, e.end),
            "bullets": list(e.bullets or []),
            "project": "",
        }
        for e in r.experience
    ]
    education = []
    for e in r.education:
        degree = e.degree + (f", {e.field}" if e.field else "")
        education.append(
            {
                "school": e.school,
                "degree": degree.strip(" ,"),
                "year": e.dates,
                "location": "",
                "details": "",
            }
        )
    certs = list(r.licenses or []) + list(r.certifications or [])
    projects = [
        {"name": p.name, "description": p.description, "link": p.link}
        for p in (r.projects or [])
        if p.name or p.description
    ]
    additional = [a for a in (r.additional or []) if str(a).strip()]
    data: dict[str, Any] = {
        "name": r.name,
        "headline": r.headline,
        "profile": r.summary,
        "technicalSummary": additional,
        "skills": skills,
        "experience": experience,
        "education": education,
        "certifications": certs,
        "projects": projects,
        "location": contact.get("location", ""),
        "email": contact.get("email", ""),
        "phone": contact.get("phone", ""),
        "linkedin": contact.get("linkedin", ""),
    }
    # Teaching samples often only have a freeform contact note — keep it visible.
    if r.contact and not any(contact.get(k) for k in ("email", "phone", "linkedin")):
        if not data["location"]:
            data["location"] = r.contact.strip()
    return data
