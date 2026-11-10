"""Top-0.1% illustrative benchmark samples and the you-vs-benchmark comparison."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from sqlmodel import select

from .. import config, db
from ..analysis.fit import score_fit
from ..analysis.taxonomy import domains_in
from ..llm import ask_json
from ..llm.prefs import (
    normalize_seed_mode,
    preferred_resume_accent,
    preferred_resume_template,
)
from ..models import Job, JobAnalysis
from ..render.resume import render_docx, render_html
from ..schemas import (
    Basics,
    Credential,
    Education,
    Experience,
    JobRequirements,
    MasterProfile,
    ProfileComparison,
    Project,
    ResumeContent,
    ResumeEducation,
    ResumeProject,
    ResumeRole,
    SampleProfile,
    SuggestedBenchmark,
    load_profile,
)
from .profile import market_data

TEACHING_LABEL = "TEACHING EXAMPLE - virtual candidate, model career at real organisations"
DEFAULT_SUITABLE_MIN_FIT = 60.0
_GENERIC_ORG = re.compile(
    r"\b(a leading|a regional|a state|a top-?\s*10|a university known|a plant engineering|"
    r"placeholder|fictional firm|generic)\b",
    re.IGNORECASE,
)
# Map taxonomy domains to the closest teaching archetype when sample.archetype is free-text.
_DOMAIN_TO_ARCHETYPE: dict[str, str] = {
    "coding": "swe_coder",
    "math": "stem_phd",
    "physics": "stem_phd",
    "chemistry": "stem_phd",
    "biology": "stem_phd",
    "medicine": "licensed_professional",
    "law": "licensed_professional",
    "finance": "finance_sme",
    "engineering": "domain_engineer",
    "creative writing": "creative_writer",
    "languages": "bilingual",
    "humanities": "humanities_phd",
    "general": "creative_writer",
}


def archetypes() -> dict:
    return config.load_yaml("archetypes.yaml")


def sample_path(key: str) -> Path:
    return config.SAMPLES_DIR / f"{key}.json"


def load_sample(key: str) -> SampleProfile | None:
    p = sample_path(key)
    return SampleProfile.model_validate_json(p.read_text(encoding="utf-8")) if p.exists() else None


def generate_sample(key: str) -> SampleProfile:
    arch = archetypes()[key]
    md = market_data()
    sample = ask_json("samples", SampleProfile, {
        "archetype": arch, "n_jobs": md["n_jobs"], "top_keywords": md["top_keywords"],
        "top_requirements": md["top_requirements"]})
    config.SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    sample_path(key).write_text(sample.model_dump_json(indent=2), encoding="utf-8")
    sample_path(key).with_suffix(".md").write_text(sample_to_markdown(sample), encoding="utf-8")
    return sample


def compare(key: str, profile: str | None = None) -> ProfileComparison:
    sample = load_sample(key) or generate_sample(key)
    return ask_json("compare", ProfileComparison, {
        "sample": sample, "sample_json": sample.model_dump_json(indent=1),
        "profile_yaml": load_profile(profile).to_yaml()})


def sample_to_markdown(s: SampleProfile) -> str:
    out = [f"# {s.archetype}\n_{s.label}_\n", f"**{s.headline}**\n", s.about, "\n## Experience"]
    for r in s.experience:
        out.append(f"### {r.title}, {r.company} ({r.start} - {r.end})")
        out += [f"- {b}" for b in r.bullets]
    out.append("\n## Education")
    for e in s.education:
        out.append(f"- {e.degree}, {e.field} - {e.school} {e.dates}")
        out += [f"  - {d}" for d in e.details]
    out += _credential_lines(s)
    if s.projects:
        out.append("\n## Projects")
        out += [f"- **{p.name}**: {p.description}" for p in s.projects]
    if s.skill_groups:
        out.append("\n## Skills")
        out += [f"- **{g.category}:** {', '.join(g.items)}" for g in s.skill_groups]
    elif s.skills:
        out += ["\n## Skills", ", ".join(s.skills)]
    out += ["\n## Why this reads as top 0.1%"] + [f"- {x}" for x in s.signals]
    out += ["\n## Benchmarks"] + [f"- {k}: {v}" for k, v in s.benchmarks.items()]
    return "\n".join(out) + "\n"


def _credential_lines(s: SampleProfile) -> list[str]:
    """Licenses and certifications as their own sections, never folded into education."""
    lines: list[str] = []
    licenses = list(s.licenses)
    certifications = list(s.certifications)
    if licenses:
        lines += ["\n## Licenses"] + [f"- {c}" for c in licenses]
    if certifications:
        lines += ["\n## Certifications"] + [f"- {c}" for c in certifications]
    seen = {*licenses, *certifications}
    legacy = [c for c in s.licenses_certs if c not in seen]
    if legacy:
        lines += ["\n## Licenses and certifications"] + [f"- {c}" for c in legacy]
    return lines


def _norm_token(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (text or "").casefold())


def _mentions(value: str, company_key: str) -> bool:
    key = _norm_token(value)
    if not key or not company_key:
        return False
    if key == company_key:
        return True
    if len(company_key) < 4 or len(key) < 4:
        return False
    return company_key in key or key in company_key


def _slug(*parts: str) -> str:
    raw = "-".join(p.strip() for p in parts if p and p.strip())
    slug = re.sub(r"[^A-Za-z0-9]+", "-", raw).strip("-").lower()
    return (slug[:80] or "suggestion")


def generic_org_notes(s: SuggestedBenchmark) -> list[str]:
    """Names that are still placeholders rather than real organisations."""
    found: list[str] = []
    for role in s.sample.experience:
        if _GENERIC_ORG.search(role.company or ""):
            found.append(role.company)
    for school in s.sample.education:
        if _GENERIC_ORG.search(school.school or ""):
            found.append(school.school)
    return found


def guard_suggestion(s: SuggestedBenchmark, candidate_name: str, last_company: str) -> SuggestedBenchmark:
    """Use the given name as the virtual candidate and keep the last company as the latest employer."""
    s.for_candidate = candidate_name.strip()
    s.last_company = last_company.strip()
    s.persona_name = s.for_candidate
    s.sample.label = TEACHING_LABEL
    if not s.inferred_industry.strip():
        s.inferred_industry = "unspecified industry"
    if not s.inferred_domain.strip():
        s.inferred_domain = s.inferred_industry

    company_key = _norm_token(last_company)
    if company_key and s.sample.experience:
        match_at = next((i for i, role in enumerate(s.sample.experience) if _mentions(role.company, company_key)), None)
        if match_at is None:
            s.sample.experience[0].company = s.last_company
        else:
            s.sample.experience[match_at].company = s.last_company
            if match_at != 0:
                role = s.sample.experience.pop(match_at)
                s.sample.experience.insert(0, role)
    return s


def _credential_line(entry: dict) -> str:
    bits = [_clean_text(entry.get("name")), _clean_text(entry.get("issuer")), _clean_text(entry.get("year"))]
    return ", ".join(b for b in bits if b)


def _seed_dates(start: object = "", end: object = "") -> str:
    start_s, end_s = _clean_text(start), _clean_text(end)
    if start_s and end_s:
        return f"{start_s} - {end_s}"
    return start_s or end_s


def _year_tokens(*values: object) -> list[int]:
    years: list[int] = []
    for value in values:
        for match in re.finditer(r"(?:19|20)\d{2}", str(value or "")):
            years.append(int(match.group(0)))
    return years


def _timeline_years_label(seed: dict) -> str:
    """Honest coach marker from provided role dates (not a padded 20+ invent)."""
    years: list[int] = []
    for role in seed.get("experience") or []:
        years.extend(_year_tokens(role.get("start"), role.get("end")))
    for edu in seed.get("education") or []:
        years.extend(_year_tokens(edu.get("start"), edu.get("end")))
    if not years:
        return "provided timeline"
    span = max(years) - min(years)
    if span <= 0:
        return "provided timeline"
    if span >= 20:
        return f"{span}+ years" if span == 20 else f"{span} years"
    return f"{span} years"


def _match_model_role(roles: list[ResumeRole], company: str) -> ResumeRole | None:
    key = _norm_token(company)
    if not key:
        return None
    return next((role for role in roles if _mentions(role.company, key)), None)


def _seed_has_org_facts(seed: dict) -> bool:
    return bool(
        seed.get("experience")
        or seed.get("education")
        or seed.get("licenses")
        or seed.get("certifications")
    )


def apply_provided_orgs(
    s: SuggestedBenchmark,
    seed: dict | None,
    last_company: str,
) -> SuggestedBenchmark:
    """Lock employers / schools / credentials to the seed; keep model skills, bullets, projects."""
    data = normalize_profile_seed(seed)
    model_roles = list(s.sample.experience)
    seed_roles = list(data.get("experience") or [])
    company = (last_company or s.last_company or "").strip()

    # Ensure last company is represented even when the seed only named earlier employers.
    if company and not any(_mentions(r.get("company", ""), _norm_token(company)) for r in seed_roles):
        seed_roles.insert(0, {"company": company})
    elif company:
        # Move matching seed role to front and normalize the company spelling.
        match_at = next(
            (i for i, role in enumerate(seed_roles) if _mentions(role.get("company", ""), _norm_token(company))),
            None,
        )
        if match_at is not None:
            seed_roles[match_at] = {**seed_roles[match_at], "company": company}
            if match_at != 0:
                seed_roles.insert(0, seed_roles.pop(match_at))

    if not seed_roles and company:
        seed_roles = [{"company": company}]

    rebuilt: list[ResumeRole] = []
    for role in seed_roles:
        company_name = _clean_text(role.get("company")) or company
        model = _match_model_role(model_roles, company_name)
        bullets = list(model.bullets) if model and model.bullets else list(role.get("bullets") or [])
        rebuilt.append(
            ResumeRole(
                company=company_name,
                title=_clean_text(role.get("title")) or (model.title if model else "") or "Role",
                start=_clean_text(role.get("start")) or (model.start if model else ""),
                end=_clean_text(role.get("end")) or (model.end if model else ""),
                location=_clean_text(role.get("location")) or (model.location if model else ""),
                bullets=bullets or ["Contribution aligned to the target role."],
            )
        )
    if rebuilt:
        s.sample.experience = rebuilt

    edu_entries: list[ResumeEducation] = []
    for edu in data.get("education") or []:
        school = _clean_text(edu.get("school"))
        if not school:
            continue
        edu_entries.append(
            ResumeEducation(
                school=school,
                degree=_clean_text(edu.get("degree")),
                field=_clean_text(edu.get("field")),
                dates=_seed_dates(edu.get("start"), edu.get("end")),
                details=list(edu.get("details") or []),
            )
        )
    s.sample.education = edu_entries

    licenses = [_credential_line(item) for item in (data.get("licenses") or []) if _credential_line(item)]
    certifications = [
        _credential_line(item) for item in (data.get("certifications") or []) if _credential_line(item)
    ]
    s.sample.licenses = licenses
    s.sample.certifications = certifications
    s.sample.licenses_certs = []

    if not s.sample.projects:
        seed_projects = data.get("projects") or []
        s.sample.projects = [
            ResumeProject(
                name=_clean_text(p.get("name")) or "Project",
                description=_clean_text(p.get("description")) or "Illustrative project for the target domain.",
            )
            for p in seed_projects
            if _clean_text(p.get("name")) or _clean_text(p.get("description"))
        ]
    if not s.sample.projects:
        s.sample.projects = [
            ResumeProject(
                name="Domain delivery",
                description="Illustrative project proving the target work.",
            )
        ]

    if not s.sample.skills and not s.sample.skill_groups and data.get("skills"):
        s.sample.skills = list(data["skills"])

    # Honest tenure marker from the provided timeline (do not keep a padded 20+ invent).
    benches = dict(s.sample.benchmarks or {})
    benches["total_relevant_experience"] = _timeline_years_label(data if data.get("experience") else {
        "experience": [{"company": r.company, "start": r.start, "end": r.end} for r in s.sample.experience],
        "education": [
            {"start": "", "end": edu.dates} for edu in s.sample.education
        ],
    })
    s.sample.benchmarks = benches
    return s


# Enterprise one-page density: skills after this are noise for recruiters and ATS scans.
_RESUME_SKILL_CAP = 18


def sample_to_resume(s: SuggestedBenchmark) -> ResumeContent:
    """Map a teaching sample to a print resume.

    Section order matches a top-tier enterprise CV: summary, categorized skills,
    experience, projects, education, licenses, certifications. Coach-only fields
    (`signals`, `benchmarks`) stay in the markdown profile — never as resume lines.
    """
    from ..render.skills import flatten_skill_groups, normalize_skill_groups

    sample = s.sample
    groups = normalize_skill_groups(list(sample.skill_groups), flat=list(sample.skills))
    flat = flatten_skill_groups(groups)[:_RESUME_SKILL_CAP]
    # Dump nested models so Streamlit module reloads (stale class identity) still validate.
    return ResumeContent(
        name=s.persona_name,
        headline=sample.headline,
        contact=(s.contact or "").strip() or "Virtual candidate — teaching example",
        summary=sample.about,
        skills=flat,
        skill_groups=[g.model_dump() for g in groups],
        experience=[role.model_dump() for role in sample.experience],
        education=[edu.model_dump() for edu in sample.education],
        licenses=sample.licenses or ([] if sample.certifications else list(sample.licenses_certs)),
        certifications=sample.certifications,
        projects=[proj.model_dump() for proj in sample.projects],
        additional=[],
        unverified_claims=["Teaching model. The person is virtual. The organisations named are real ones to learn from."],
    )


def suggestion_to_markdown(s: SuggestedBenchmark) -> str:
    aimed = "the job description" if s.target_kind == "job_description" else "the last company's industry"
    lessons = "\n".join(
        f"### {n.section}\n- Necessary: {n.necessary_information}\n- Best option: {n.best_option}\n- Teach it: {n.how_to_teach}"
        for n in s.teaching_notes
    )
    placeholders = generic_org_notes(s)
    placeholder_block = ""
    if placeholders:
        placeholder_block = (
            "\n\n## Placeholders to replace with real organisations\n\n"
            + "\n".join(f"- {name}" for name in placeholders)
            + "\n"
        )
    banner = (
        f"# Teaching profile: {s.persona_name}\n\n"
        f"_Top 0.1% model for {s.inferred_domain} ({s.inferred_industry}), aimed at {aimed}. "
        f"Latest employer: {s.last_company}._\n\n"
        f"> {s.sample.label}. Use this to teach the structure and the caliber of organisation. "
        f"A learner then replaces each line with their own real history.\n\n"
        f"## Why this shape\n\n{s.why_this_shape}\n\n"
        f"## How to teach it\n\n{lessons}\n"
        f"{placeholder_block}\n"
        f"## Model profile\n\n"
    )
    return banner + sample_to_markdown(s.sample)


def _clean_text(value: object) -> str:
    return str(value or "").strip()


def _clean_list(items: object) -> list[str]:
    if items is None:
        return []
    if isinstance(items, str):
        parts = re.split(r"[\n,;]+", items)
        return [p.strip() for p in parts if p.strip()]
    if not isinstance(items, list):
        return []
    out: list[str] = []
    for item in items:
        text = _clean_text(item)
        if text:
            out.append(text)
    return out


def _clean_mapping_list(items: object, fields: tuple[str, ...], *, list_fields: tuple[str, ...] = ()) -> list[dict]:
    if not isinstance(items, list):
        return []
    cleaned: list[dict] = []
    for raw in items:
        if not isinstance(raw, dict):
            continue
        entry: dict = {}
        for field in fields:
            if field in list_fields:
                values = _clean_list(raw.get(field))
                if values:
                    entry[field] = values
            else:
                text = _clean_text(raw.get(field))
                if text:
                    entry[field] = text
        if entry:
            cleaned.append(entry)
    return cleaned


def contact_line_from_seed(seed: dict | None) -> str:
    """Build a resume contact line from optional seed contact fields."""
    data = seed if isinstance(seed, dict) else {}
    if data.get("contact"):
        return str(data["contact"]).strip()
    parts = [
        _clean_text(data.get("location")),
        _clean_text(data.get("email")),
        _clean_text(data.get("phone")),
        _clean_text(data.get("linkedin")),
    ]
    return " | ".join(p for p in parts if p)


def normalize_profile_seed(raw: dict | None) -> dict:
    """Optional LinkedIn-style seed facts that guide the teaching model."""
    data = raw if isinstance(raw, dict) else {}
    seed = {
        "location": _clean_text(data.get("location")),
        "headline": _clean_text(data.get("headline")),
        "about": _clean_text(data.get("about")),
        "email": _clean_text(data.get("email")),
        "phone": _clean_text(data.get("phone")),
        "linkedin": _clean_text(data.get("linkedin")),
        "contact": _clean_text(data.get("contact")),
        "experience": _clean_mapping_list(
            data.get("experience"),
            ("company", "title", "start", "end", "location", "bullets"),
            list_fields=("bullets",),
        ),
        "education": _clean_mapping_list(
            data.get("education"),
            ("school", "degree", "field", "start", "end", "details"),
            list_fields=("details",),
        ),
        "licenses": _clean_mapping_list(data.get("licenses"), ("name", "issuer", "year")),
        "certifications": _clean_mapping_list(data.get("certifications"), ("name", "issuer", "year")),
        "skills": _clean_list(data.get("skills")),
        "languages": _clean_mapping_list(data.get("languages"), ("name", "level")),
        "projects": _clean_mapping_list(
            data.get("projects"),
            ("name", "description", "skills"),
            list_fields=("skills",),
        ),
    }
    return {k: v for k, v in seed.items() if v}


_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_PHONE_RE = re.compile(
    r"(?:\+?\d{1,3}[\s\-.]*)?(?:\(?\d{2,4}\)?[\s\-.]*)?\d{3}[\s\-.]?\d{3,4}(?:[\s\-.]?\d{3,4})?"
)
_LINKEDIN_RE = re.compile(r"https?://(?:www\.)?linkedin\.com/in/[A-Za-z0-9\-_%/]+", re.IGNORECASE)
_BIRTH_RE = re.compile(r"^\d{4}([./]\d{1,2}){0,2}([./][Xx\d]{1,2})?$")
_DATE_RANGE_RE = re.compile(
    r"^((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}|\d{4})"
    r"\s*[-–—]\s*"
    r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}|\d{4}|Present|Current)$",
    re.IGNORECASE,
)
_ROLE_LINE_RE = re.compile(r"^(?P<title>.+?)\s+[-–—]\s+(?P<company>.+)$")
_SECTION_RE = re.compile(
    r"^(EDUCATION|PROFESSIONAL EXPERIENCE|EXPERIENCE|WORK EXPERIENCE|"
    r"COMPANIES['’]? KEY INFORMATION|COMPANY KEY INFORMATION|COMPANIES)\s*$",
    re.IGNORECASE,
)
_RULE_LINE_RE = re.compile(r"^[\W_]{3,}$")


def _split_profile_sections(text: str) -> dict[str, str]:
    """Split a LinkedIn-style dump into header + named sections."""
    lines = [ln.strip() for ln in (text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    sections: dict[str, list[str]] = {"header": []}
    current = "header"
    for line in lines:
        if _RULE_LINE_RE.match(line or ""):
            continue
        match = _SECTION_RE.match(line or "")
        if match:
            label = match.group(1).strip().lower()
            if label.startswith("educ"):
                current = "education"
            elif "compan" in label:
                current = "companies"
            else:
                current = "experience"
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(line)
    return {key: "\n".join(vals).strip() for key, vals in sections.items() if any(v.strip() for v in vals)}


def _parse_experience_block(block: str) -> list[dict[str, str]]:
    roles: list[dict[str, str]] = []
    lines = [ln.strip() for ln in (block or "").split("\n") if ln.strip()]
    i = 0
    while i < len(lines):
        line = lines[i]
        role_match = _ROLE_LINE_RE.match(line)
        if not role_match:
            i += 1
            continue
        role = {
            "title": role_match.group("title").strip(),
            "company": role_match.group("company").strip(),
        }
        if i + 1 < len(lines):
            date_match = _DATE_RANGE_RE.match(lines[i + 1])
            if date_match:
                role["start"] = date_match.group(1).strip()
                role["end"] = date_match.group(2).strip()
                i += 2
            else:
                i += 1
        else:
            i += 1
        roles.append(role)
    return roles


def _parse_education_block(block: str) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    lines = [ln.strip() for ln in (block or "").split("\n") if ln.strip()]
    i = 0
    while i < len(lines):
        school = lines[i]
        if _DATE_RANGE_RE.match(school) or _EMAIL_RE.search(school) or _LINKEDIN_RE.search(school):
            i += 1
            continue
        entry: dict[str, str] = {"school": school}
        i += 1
        if i < len(lines) and not _DATE_RANGE_RE.match(lines[i]):
            degree_line = lines[i]
            if "," in degree_line:
                degree, field = degree_line.split(",", 1)
                entry["degree"] = degree.strip()
                entry["field"] = field.strip()
            else:
                entry["degree"] = degree_line.strip()
            i += 1
        if i < len(lines):
            date_match = _DATE_RANGE_RE.match(lines[i])
            if date_match:
                entry["start"] = date_match.group(1).strip()
                entry["end"] = date_match.group(2).strip()
                i += 1
        entries.append(entry)
    return entries


def parse_profile_dump(text: str) -> dict[str, Any]:
    """Parse a pasted LinkedIn-style profile dump into suggest fields + profile_seed.

    Best-effort offline parse for Teaching models UX. Unknown prose (company blurbs)
    lands in ``notes``. Returns only non-empty keys.
    """
    raw = (text or "").strip()
    if not raw:
        return {}
    sections = _split_profile_sections(raw)
    header_lines = [ln.strip() for ln in (sections.get("header") or "").split("\n") if ln.strip()]

    email_match = _EMAIL_RE.search(raw)
    email = email_match.group(0) if email_match else ""
    li_match = _LINKEDIN_RE.search(raw)
    linkedin = li_match.group(0).rstrip("/") if li_match else ""
    phone = ""
    for line in header_lines:
        digits = re.sub(r"\D", "", line)
        if len(digits) >= 10 and ("+" in line or _PHONE_RE.search(line)):
            phone = line
            break

    skip = {p.lower() for p in (email, linkedin, phone) if p}
    identity: list[str] = []
    for line in header_lines:
        key = line.lower()
        if key in skip or _EMAIL_RE.search(line) or _LINKEDIN_RE.search(line):
            continue
        digits = re.sub(r"\D", "", line)
        if phone and line == phone:
            continue
        if len(digits) >= 10 and ("+" in line or "(" in line):
            continue
        if _BIRTH_RE.match(line):
            continue
        identity.append(line)

    name = identity[0] if identity else ""
    headline = ""
    location = ""
    rest = identity[1:]
    if rest:
        # Prefer an explicit location-looking line (comma or country/state cue).
        loc_idx = next(
            (
                i
                for i, line in enumerate(rest)
                if "," in line or re.search(r"\b(United States|USA|UK|Canada)\b", line, re.I)
            ),
            None,
        )
        if loc_idx is not None:
            location = rest[loc_idx]
            head_candidates = rest[:loc_idx] + rest[loc_idx + 1 :]
        else:
            head_candidates = rest
        if head_candidates:
            headline = head_candidates[0]

    experience = _parse_experience_block(sections.get("experience") or "")
    education = _parse_education_block(sections.get("education") or "")
    title = ""
    last_company = ""
    if experience:
        title = experience[0].get("title") or ""
        last_company = experience[0].get("company") or ""
    elif headline and "|" in headline:
        title = headline.split("|", 1)[0].strip()

    seed = normalize_profile_seed(
        {
            "location": location,
            "headline": headline,
            "email": email,
            "phone": phone,
            "linkedin": linkedin,
            "experience": experience,
            "education": education,
        }
    )
    notes = (sections.get("companies") or "").strip()
    out: dict[str, Any] = {}
    if name:
        out["name"] = name
    if last_company:
        out["last_company"] = last_company
    if title:
        out["title"] = title
    if notes:
        out["notes"] = notes
    if seed:
        out["profile_seed"] = seed
    return out


def merge_notes(*parts: str) -> str:
    """Join non-empty note blocks without duplicating identical text."""
    merged: list[str] = []
    seen: set[str] = set()
    for part in parts:
        text = (part or "").strip()
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        # Skip if this block is already contained in a previous block.
        if any(key in prev for prev in seen):
            continue
        seen.add(key)
        merged.append(text)
    return "\n\n".join(merged)


def merge_profile_seed(base: dict | None, incoming: dict | None) -> dict:
    """Fill empty seed fields from incoming; keep existing non-empty values."""
    current = normalize_profile_seed(base)
    extra = normalize_profile_seed(incoming)
    for key, value in extra.items():
        if key not in current or current[key] in ("", [], None):
            current[key] = value
    return current


def format_profile_seed_for_prompt(seed: dict) -> str:
    """Render seed facts as plain text for the sample_suggest prompt."""
    if not seed:
        return ""
    lines: list[str] = []
    if seed.get("location"):
        lines.append(f"Location: {seed['location']}")
    if seed.get("headline"):
        lines.append(f"Headline: {seed['headline']}")
    if seed.get("email"):
        lines.append(f"Email: {seed['email']}")
    if seed.get("phone"):
        lines.append(f"Phone: {seed['phone']}")
    if seed.get("linkedin"):
        lines.append(f"LinkedIn: {seed['linkedin']}")
    if seed.get("contact"):
        lines.append(f"Contact: {seed['contact']}")
    if seed.get("about"):
        lines.append(f"About:\n{seed['about']}")
    for role in seed.get("experience") or []:
        when = " - ".join(p for p in (role.get("start"), role.get("end")) if p)
        head = ", ".join(p for p in (role.get("title"), role.get("company")) if p) or "Role"
        loc = f" ({role['location']})" if role.get("location") else ""
        lines.append(f"Prior experience: {head}{loc}" + (f", {when}" if when else ""))
        for bullet in role.get("bullets") or []:
            lines.append(f"  - {bullet}")
    for edu in seed.get("education") or []:
        when = " - ".join(p for p in (edu.get("start"), edu.get("end")) if p)
        bits = [edu.get("degree"), edu.get("field"), edu.get("school")]
        head = ", ".join(p for p in bits if p) or "Education"
        lines.append(f"Education: {head}" + (f" ({when})" if when else ""))
        for detail in edu.get("details") or []:
            lines.append(f"  - {detail}")
    for lic in seed.get("licenses") or []:
        bits = [lic.get("name"), lic.get("issuer"), lic.get("year")]
        lines.append("License: " + ", ".join(p for p in bits if p))
    for cert in seed.get("certifications") or []:
        bits = [cert.get("name"), cert.get("issuer"), cert.get("year")]
        lines.append("Certification: " + ", ".join(p for p in bits if p))
    if seed.get("skills"):
        lines.append("Skills: " + ", ".join(seed["skills"]))
    for lang in seed.get("languages") or []:
        bits = [lang.get("name"), lang.get("level")]
        lines.append("Language: " + ", ".join(p for p in bits if p))
    for project in seed.get("projects") or []:
        head = project.get("name") or "Project"
        desc = project.get("description") or ""
        lines.append(f"Project: {head}" + (f" — {desc}" if desc else ""))
        skills = project.get("skills") or []
        if skills:
            lines.append("  skills: " + ", ".join(skills))
    return "\n".join(lines)


def suggest_sample(
    name: str,
    company: str,
    *,
    title: str = "",
    notes: str = "",
    jd: str = "",
    profile_seed: dict | None = None,
    seed_mode: str = "last_company",
) -> tuple[SuggestedBenchmark, dict[str, str]]:
    """Build a teaching profile and resume for a virtual candidate.

    The name is the virtual candidate. The last company is their latest real employer in the model.
    seed_mode=last_company invents peer employers/schools/creds (original teaching bar).
    seed_mode=provided locks employers/schools/creds to profile_seed; skills/bullets/projects may be generated.
    """
    name, company = (name or "").strip(), (company or "").strip()
    if not name or not company:
        raise ValueError("candidate name and last company are required")
    mode = normalize_seed_mode(seed_mode)
    jd = (jd or "").strip()
    seed = normalize_profile_seed(profile_seed) if mode == "provided" else {}
    if mode == "provided" and not _seed_has_org_facts(seed):
        raise ValueError(
            "seed_mode=provided requires profile_seed with experience, education, licenses, or certifications"
        )
    md = market_data()
    # Use the configured engine (browser ChatGPT/Claude by default). models.yaml sets a long timeout.
    suggestion = ask_json("sample_suggest", SuggestedBenchmark, {
        "name": name,
        "company": company,
        "title": (title or "").strip(),
        "notes": (notes or "").strip(),
        "jd": jd,
        "seed_mode": mode,
        "profile_seed": seed,
        "profile_seed_text": format_profile_seed_for_prompt(seed) if seed else "",
        "archetypes": archetypes(),
        "n_jobs": md["n_jobs"],
        "top_keywords": md["top_keywords"],
    })
    suggestion.target_kind = "job_description" if jd else "company_domain"
    suggestion = guard_suggestion(suggestion, name, company)
    if mode == "provided":
        suggestion = apply_provided_orgs(suggestion, seed, company)
    suggestion.contact = contact_line_from_seed(seed) or suggestion.contact
    return suggestion, write_suggestion_artifacts(suggestion)


def write_suggestion_artifacts(suggestion: SuggestedBenchmark) -> dict[str, str]:
    """Persist suggestion.json, profile.md, and resume files under output/suggestions/."""
    name = suggestion.persona_name or suggestion.for_candidate or "candidate"
    company = suggestion.last_company or "company"
    slug_parts = [name, company]
    if (suggestion.target_kind or "").strip() == "job_description":
        slug_parts.append("jd")
    out = config.OUTPUT_DIR / "suggestions" / _slug(*slug_parts)
    out.mkdir(parents=True, exist_ok=True)
    (out / "suggestion.json").write_text(suggestion.model_dump_json(indent=2), encoding="utf-8")
    profile_md = out / "profile.md"
    profile_md.write_text(suggestion_to_markdown(suggestion), encoding="utf-8")
    resume = sample_to_resume(suggestion)
    docx_path, html_path = out / "resume.docx", out / "resume.html"
    template_id = preferred_resume_template()
    accent_id = preferred_resume_accent() or None
    render_docx(resume, docx_path)
    html_path.write_text(
        render_html(resume, template_id=template_id, accent_id=accent_id),
        encoding="utf-8",
    )
    return {
        "dir": str(out),
        "json": str(out / "suggestion.json"),
        "profile": str(profile_md),
        "docx": str(docx_path),
        "html": str(html_path),
        "template_id": template_id,
    }


def import_suggestion_json(
    path: Path,
    *,
    name: str = "",
    company: str = "",
) -> tuple[SuggestedBenchmark, dict[str, str]]:
    """Save a ChatGPT/Claude JSON reply that the bridge timed out before harvesting."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("suggestion JSON must be an object")
    suggestion = SuggestedBenchmark.model_validate(raw)
    name = (name or suggestion.persona_name or suggestion.for_candidate or "").strip()
    company = (company or suggestion.last_company or "").strip()
    if not name or not company:
        raise ValueError("name and last_company are required (in JSON or as overrides)")
    suggestion = guard_suggestion(suggestion, name, company)
    return suggestion, write_suggestion_artifacts(suggestion)


def comparison_to_markdown(c: ProfileComparison) -> str:
    def bl(items): return "\n".join(f"- {i}" for i in items) or "- (none)"
    return ("## Strengths\n" + bl(c.strengths) + "\n\n## Gaps\n" + bl(c.gaps) +
            "\n\n## Priority actions\n" + "\n".join(f"{i}. {a}" for i, a in enumerate(c.priority_actions, 1)) + "\n")


def _parse_education_dates(dates: str) -> tuple[str, str]:
    text = (dates or "").strip()
    if not text:
        return "", ""
    parts = re.split(r"\s*[-–—]\s*", text, maxsplit=1)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    return text, ""


def _credential_from_text(text: str) -> Credential:
    raw = (text or "").strip()
    if not raw:
        return Credential()
    if "," in raw:
        name, rest = raw.split(",", 1)
        return Credential(name=name.strip(), issuer=rest.strip())
    return Credential(name=raw)


def suggestion_to_master_profile(s: SuggestedBenchmark) -> MasterProfile:
    """In-memory MasterProfile for scoring — never written to profile/people/."""
    sample = s.sample
    skills = list(sample.skills)
    for group in sample.skill_groups:
        skills.extend(group.items)
    # Dedupe preserving order
    seen: set[str] = set()
    flat_skills: list[str] = []
    for item in skills:
        key = item.strip().casefold()
        if not key or key in seen:
            continue
        seen.add(key)
        flat_skills.append(item.strip())

    domains = [d for d in (s.inferred_domain, s.inferred_industry) if (d or "").strip()]
    domains.extend(domains_in(" ".join(domains + flat_skills + [sample.about or "", sample.headline or ""])))
    # Unique domains preserving order
    dom_seen: set[str] = set()
    uniq_domains: list[str] = []
    for d in domains:
        key = d.strip().casefold()
        if not key or key in dom_seen:
            continue
        dom_seen.add(key)
        uniq_domains.append(d.strip())

    licenses = [_credential_from_text(x) for x in (sample.licenses or [])]
    certifications = [_credential_from_text(x) for x in (sample.certifications or [])]
    if not licenses and not certifications:
        licenses = [_credential_from_text(x) for x in (sample.licenses_certs or [])]

    education: list[Education] = []
    for edu in sample.education:
        start, end = _parse_education_dates(edu.dates)
        education.append(Education(
            school=edu.school, degree=edu.degree, field=edu.field,
            start=start, end=end, details=list(edu.details or []),
        ))

    return MasterProfile(
        basics=Basics(
            name=s.persona_name or s.for_candidate or "",
            headline=sample.headline or "",
        ),
        summary=sample.about or "",
        target_roles=[sample.archetype] if sample.archetype else [],
        experience=[
            Experience(
                company=role.company, title=role.title, start=role.start, end=role.end,
                location=role.location, bullets=list(role.bullets or []),
            )
            for role in sample.experience
        ],
        education=education,
        licenses=[c for c in licenses if c.name],
        certifications=[c for c in certifications if c.name],
        projects=[
            Project(name=p.name, description=p.description, link=p.link or "")
            for p in sample.projects
        ],
        domains=uniq_domains,
        tools=flat_skills[:24],
        coding=[sk for sk in flat_skills if any(
            tok in sk.casefold() for tok in ("python", "java", "c++", "typescript", "javascript", "golang", "rust", "sql")
        )],
    )


def _suggestion_blob(s: SuggestedBenchmark) -> str:
    sample = s.sample
    parts = [
        s.inferred_domain, s.inferred_industry, sample.archetype, sample.headline, sample.about,
        " ".join(sample.skills),
        " ".join(item for g in sample.skill_groups for item in g.items),
        " ".join(b for role in sample.experience for b in role.bullets),
    ]
    return " ".join(p for p in parts if p)


def _resolve_archetype_keys(s: SuggestedBenchmark) -> list[str]:
    """Ordered archetype keys that best describe this teaching model."""
    arch = archetypes()
    label = (s.sample.archetype or "").strip()
    keys: list[str] = []
    if label in arch:
        keys.append(label)
    else:
        label_cf = label.casefold()
        for key, meta in arch.items():
            name = str(meta.get("name") or "").casefold()
            if not label_cf:
                break
            if label_cf == name or label_cf == key.casefold() or key.casefold().replace("_", " ") in label_cf:
                keys.append(key)
                break
            if name and (name in label_cf or label_cf in name):
                keys.append(key)
                break

    blob = _suggestion_blob(s)
    for domain in domains_in(blob):
        mapped = _DOMAIN_TO_ARCHETYPE.get(domain)
        if mapped and mapped in arch and mapped not in keys:
            keys.append(mapped)

    if not keys and "creative_writer" in arch:
        keys.append("creative_writer")
    return keys


def recommend_job_types(s: SuggestedBenchmark) -> list[dict[str, Any]]:
    """Archetype / taxonomy job kinds when no collected posting scores high enough."""
    arch = archetypes()
    keys = _resolve_archetype_keys(s)
    out: list[dict[str, Any]] = []
    for key in keys:
        meta = arch.get(key) or {}
        roles = list(meta.get("roles") or [])
        out.append({
            "key": key,
            "name": meta.get("name") or key,
            "description": meta.get("description") or "",
            "roles": roles,
            "source": "archetype",
        })

    blob = _suggestion_blob(s)
    found_domains = domains_in(blob)
    if found_domains:
        out.append({
            "key": "taxonomy_domains",
            "name": "Taxonomy domains",
            "description": "Subject areas detected on this teaching model.",
            "roles": [f"AI Tutor / SME - {d}" for d in found_domains[:6]],
            "source": "taxonomy",
        })
    return out


def _title_examples(types: list[dict[str, Any]], *, limit: int = 8) -> list[str]:
    titles: list[str] = []
    seen: set[str] = set()
    for entry in types:
        for role in entry.get("roles") or []:
            text = str(role).strip()
            key = text.casefold()
            if not text or key in seen:
                continue
            seen.add(key)
            titles.append(text)
            if len(titles) >= limit:
                return titles
    return titles


def _latest_analyses() -> dict[int, JobAnalysis]:
    with db.session() as s:
        best: dict[int, JobAnalysis] = {}
        for a in s.exec(select(JobAnalysis).order_by(JobAnalysis.id)).all():
            best[a.job_id] = a
        return best


def jobs_for_suggestion(
    s: SuggestedBenchmark,
    *,
    min_fit: float = DEFAULT_SUITABLE_MIN_FIT,
) -> dict[str, Any]:
    """Score analyzed jobs in memory; fall back to job types when none meet min_fit.

    Never writes teaching-model fits onto JobAnalysis rows.
    """
    profile = suggestion_to_master_profile(s)
    matches: list[dict[str, Any]] = []
    analyses = _latest_analyses()
    with db.session() as sess:
        for jid, analysis in analyses.items():
            job = sess.get(Job, jid)
            if not job:
                continue
            try:
                req = JobRequirements.model_validate_json(analysis.data_json)
            except Exception:  # noqa: BLE001 — skip corrupt analysis rows
                continue
            score, _gaps = score_fit(req, profile, job.description or "")
            if score < min_fit:
                continue
            matches.append({
                "job_id": job.id,
                "company": job.company,
                "title": job.title,
                "fit": score,
                "domain": req.domain or "",
                "task_types": list(req.task_types or []),
                "pay": job.pay or "",
            })
    matches.sort(key=lambda row: (-row["fit"], row["job_id"]))
    if matches:
        return {
            "mode": "jobs",
            "min_fit": min_fit,
            "matches": matches,
            "types": [],
            "title_examples": [],
            "persona_name": s.persona_name or s.for_candidate or "",
            "inferred_domain": s.inferred_domain or "",
        }

    types = recommend_job_types(s)
    return {
        "mode": "types",
        "min_fit": min_fit,
        "matches": [],
        "types": types,
        "title_examples": _title_examples(types),
        "persona_name": s.persona_name or s.for_candidate or "",
        "inferred_domain": s.inferred_domain or "",
    }


def suitable_report_markdown(result: dict[str, Any]) -> str:
    """Human-readable report for CLI / dashboard / suitable_jobs.md."""
    name = result.get("persona_name") or "virtual candidate"
    domain = result.get("inferred_domain") or "their domain"
    min_fit = result.get("min_fit", DEFAULT_SUITABLE_MIN_FIT)
    lines = [
        f"# Suitable jobs for {name}",
        "",
        f"_Teaching model domain: {domain}. Interview threshold: fit >= {min_fit:.0f}._",
        "",
    ]
    if result.get("mode") == "jobs":
        lines += ["## Collected jobs that fit", ""]
        for row in result.get("matches") or []:
            pay = f" | {row['pay']}" if row.get("pay") else ""
            tasks = ", ".join(row.get("task_types") or []) or "—"
            lines.append(
                f"- **#{row['job_id']}** fit {row['fit']:.0f} — {row['company']}: {row['title']} "
                f"({row.get('domain') or 'domain n/a'}; {tasks}){pay}"
            )
        lines.append("")
        return "\n".join(lines)

    lines += [
        "## No collected jobs met the fit bar",
        "",
        "Use these **job kinds** when collecting or coaching next:",
        "",
    ]
    for entry in result.get("types") or []:
        roles = ", ".join(entry.get("roles") or []) or "—"
        lines += [
            f"### {entry.get('name') or entry.get('key')}",
            f"- Source: {entry.get('source')}",
            f"- {entry.get('description') or ''}".rstrip(),
            f"- Example titles: {roles}",
            "",
        ]
    examples = result.get("title_examples") or []
    if examples:
        lines += ["## Title examples to collect", ""]
        lines += [f"- {t}" for t in examples]
        lines.append("")
    return "\n".join(lines)


def suggestion_dirs() -> list[Path]:
    root = config.OUTPUT_DIR / "suggestions"
    if not root.exists():
        return []
    return sorted(
        [p for p in root.iterdir() if p.is_dir() and (p / "suggestion.json").exists()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )


def load_suggestion_dir(folder: Path | str) -> SuggestedBenchmark:
    path = Path(folder)
    if path.is_file() and path.name == "suggestion.json":
        path = path.parent
    json_path = path / "suggestion.json"
    if not json_path.exists():
        raise FileNotFoundError(f"No suggestion.json in {path}")
    return SuggestedBenchmark.model_validate_json(json_path.read_text(encoding="utf-8"))


def suitable_for_suggestion_dir(
    folder: Path | str | None = None,
    *,
    min_fit: float = DEFAULT_SUITABLE_MIN_FIT,
) -> tuple[dict[str, Any], Path, Path]:
    """Resolve a suggestion folder, score/types, and write suitable_jobs.md."""
    if folder is None:
        dirs = suggestion_dirs()
        if not dirs:
            raise FileNotFoundError("No teaching models under output/suggestions/")
        folder = dirs[0]
    folder_path = Path(folder)
    suggestion = load_suggestion_dir(folder_path)
    result = jobs_for_suggestion(suggestion, min_fit=min_fit)
    md = suitable_report_markdown(result)
    out = folder_path / "suitable_jobs.md"
    out.write_text(md, encoding="utf-8")
    return result, folder_path, out

