"""Parse our styled resume HTML back into ResumeContent."""
from __future__ import annotations

import re
from html import unescape

from bs4 import BeautifulSoup, NavigableString, Tag

from ..schemas import ResumeContent, ResumeEducation, ResumeProject, ResumeRole, SkillGroup

_SECTION_ALIASES = {
    "professional summary": "summary",
    "summary": "summary",
    "skills": "skills",
    "core competencies": "skills",
    "professional experience": "experience",
    "experience": "experience",
    "representative projects": "projects",
    "selected projects": "projects",
    "selected project": "projects",
    "projects": "projects",
    "education": "education",
    "licenses": "licenses",
    "certifications": "certifications",
    "languages & awards": "additional",
    "languages and awards": "additional",
    "additional": "additional",
}


class ResumeHtmlParseError(ValueError):
    """Edited HTML no longer matches the fixed resume section structure."""


def _norm_heading(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip()).casefold()


def _text(node: Tag | NavigableString | None) -> str:
    if node is None:
        return ""
    if isinstance(node, NavigableString):
        return unescape(str(node)).strip()
    return unescape(node.get_text(" ", strip=True))


def _section_key(h2: Tag) -> str | None:
    return _SECTION_ALIASES.get(_norm_heading(_text(h2)))


def _split_dates(raw: str) -> tuple[str, str]:
    text = (raw or "").strip()
    if not text:
        return "", ""
    if " - " in text:
        start, end = text.split(" - ", 1)
        return start.strip(), end.strip()
    if " – " in text:
        start, end = text.split(" – ", 1)
        return start.strip(), end.strip()
    return text, ""


def _parse_skills(section: Tag) -> tuple[list[str], list[SkillGroup]]:
    groups: list[SkillGroup] = []
    for row in section.select(".skill-row"):
        cat_el = row.select_one(".skill-cat")
        items_el = row.select_one(".skill-items")
        category = _text(cat_el).rstrip(":").strip()
        items_raw = _text(items_el)
        items = [p.strip() for p in re.split(r"\s*·\s*|\s*[•|]\s*", items_raw) if p.strip()]
        if category and items:
            groups.append(SkillGroup(category=category, items=items))
    flat: list[str] = []
    for g in groups:
        flat.extend(g.items)
    if not groups:
        # Fallback: plain paragraph / middot dump under Skills
        blob = _text(section)
        blob = re.sub(r"(?i)^skills\s*", "", blob).strip()
        flat = [p.strip() for p in re.split(r"\s*·\s*|,\s*", blob) if p.strip()]
    return flat, groups


def _parse_experience(section: Tag) -> list[ResumeRole]:
    roles: list[ResumeRole] = []
    jobs = section.select("article.job")
    if not jobs:
        raise ResumeHtmlParseError("Professional Experience is missing job blocks.")
    for job in jobs:
        title = _text(job.select_one(".role"))
        dates = _text(job.select_one(".dates"))
        company = _text(job.select_one(".company"))
        location = _text(job.select_one(".sub"))
        start, end = _split_dates(dates)
        bullets = [_text(li) for li in job.select("ul li") if _text(li)]
        if not title and not company:
            raise ResumeHtmlParseError("A job block is missing title and company.")
        roles.append(
            ResumeRole(
                company=company or "Unknown",
                title=title or "Role",
                start=start,
                end=end,
                location=location,
                bullets=bullets,
            )
        )
    return roles


def _parse_projects(section: Tag) -> list[ResumeProject]:
    projects: list[ResumeProject] = []
    for item in section.select("p.project-item"):
        name_el = item.find("b")
        name = _text(name_el) if name_el else ""
        raw = _text(item)
        link = ""
        description = ""
        if name and raw.startswith(name):
            rest = raw[len(name) :].strip()
        else:
            rest = raw
        m = re.match(r"^\(([^)]+)\)\s*:\s*(.*)$", rest)
        if m:
            link, description = m.group(1).strip(), m.group(2).strip()
        elif rest.startswith(":"):
            description = rest[1:].strip()
        else:
            description = rest
        if not name:
            # "Name: desc" without <b>
            if ":" in raw:
                name, description = raw.split(":", 1)
                name, description = name.strip(), description.strip()
            else:
                name, description = raw, ""
        if name:
            projects.append(ResumeProject(name=name, description=description, link=link))
    return projects


def _parse_education(section: Tag) -> list[ResumeEducation]:
    education: list[ResumeEducation] = []
    rows = section.select("div.row")
    for row in rows:
        spans = row.find_all("span", recursive=False)
        label = _text(spans[0]) if spans else _text(row)
        dates = ""
        for sp in spans[1:]:
            if "dates" in (sp.get("class") or []):
                dates = _text(sp)
        degree, field, school = "", "", label
        if " - " in label:
            left, school = label.rsplit(" - ", 1)
            school = school.strip()
            if ", " in left:
                degree, field = left.split(", ", 1)
            else:
                degree = left.strip()
        details: list[str] = []
        # Details list immediately after this row
        nxt = row.find_next_sibling()
        if nxt and nxt.name == "ul":
            details = [_text(li) for li in nxt.select("li") if _text(li)]
        education.append(
            ResumeEducation(
                school=school.strip() or "School",
                degree=degree.strip(),
                field=field.strip(),
                dates=dates.strip(),
                details=details,
            )
        )
    return education


def _parse_list_section(section: Tag) -> list[str]:
    return [_text(li) for li in section.select("ul li") if _text(li)]


def parse_resume_html(html: str) -> ResumeContent:
    """Convert styled resume HTML (from render_styled_html) into ResumeContent.

    Raises ResumeHtmlParseError when required structure is missing or broken.
    """
    if not (html or "").strip():
        raise ResumeHtmlParseError("Resume HTML is empty.")
    soup = BeautifulSoup(html, "html.parser")
    header = soup.find("header")
    if header is None:
        raise ResumeHtmlParseError("Resume header is missing.")
    name = _text(header.find("h1"))
    if not name:
        raise ResumeHtmlParseError("Candidate name is missing.")
    headline = _text(header.select_one(".headline"))
    contact = _text(header.select_one(".contact"))

    summary = ""
    skills: list[str] = []
    skill_groups: list[SkillGroup] = []
    experience: list[ResumeRole] = []
    projects: list[ResumeProject] = []
    education: list[ResumeEducation] = []
    licenses: list[str] = []
    certifications: list[str] = []
    additional: list[str] = []

    for h2 in soup.find_all("h2"):
        key = _section_key(h2)
        if not key:
            continue
        section = h2.parent if h2.parent and h2.parent.name == "section" else h2.find_parent("section")
        if section is None:
            # Treat following siblings until next h2 as the section body.
            section = soup.new_tag("section")
            for sib in list(h2.next_siblings):
                if isinstance(sib, Tag) and sib.name == "h2":
                    break
                section.append(sib.extract() if hasattr(sib, "extract") else sib)
            section.insert(0, h2)
        if key == "summary":
            p = section.find("p")
            summary = _text(p) if p else _text(section).replace(_text(h2), "", 1).strip()
        elif key == "skills":
            skills, skill_groups = _parse_skills(section)
        elif key == "experience":
            experience = _parse_experience(section)
        elif key == "projects":
            projects = _parse_projects(section)
        elif key == "education":
            education = _parse_education(section)
        elif key == "licenses":
            licenses = _parse_list_section(section)
        elif key == "certifications":
            certifications = _parse_list_section(section)
        elif key == "additional":
            additional = _parse_list_section(section)

    if not experience:
        raise ResumeHtmlParseError("Professional Experience section is required.")

    return ResumeContent(
        name=name,
        headline=headline,
        contact=contact,
        summary=summary,
        skills=skills,
        skill_groups=skill_groups,
        experience=experience,
        education=education,
        licenses=licenses,
        certifications=certifications,
        projects=projects,
        additional=additional,
        unverified_claims=[],
    )
