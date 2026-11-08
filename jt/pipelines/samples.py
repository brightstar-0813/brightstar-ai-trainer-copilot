"""Top-0.1% illustrative benchmark samples and the you-vs-benchmark comparison."""
from __future__ import annotations

import json
import re
from pathlib import Path

from .. import config
from ..llm import ask_json
from ..llm.prefs import preferred_resume_accent, preferred_resume_template
from ..render.resume import render_docx, render_html
from ..schemas import (
    ProfileComparison,
    ResumeContent,
    SampleProfile,
    SuggestedBenchmark,
    load_profile,
)
from .profile import market_data

TEACHING_LABEL = "TEACHING EXAMPLE - virtual candidate, model career at real organisations"
_GENERIC_ORG = re.compile(
    r"\b(a leading|a regional|a state|a top-?\s*10|a university known|a plant engineering|"
    r"placeholder|fictional firm|generic)\b",
    re.IGNORECASE,
)


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
        contact="Virtual candidate — teaching example",
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


def normalize_profile_seed(raw: dict | None) -> dict:
    """Optional LinkedIn-style seed facts that guide the teaching model."""
    data = raw if isinstance(raw, dict) else {}
    seed = {
        "location": _clean_text(data.get("location")),
        "headline": _clean_text(data.get("headline")),
        "about": _clean_text(data.get("about")),
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


def format_profile_seed_for_prompt(seed: dict) -> str:
    """Render seed facts as plain text for the sample_suggest prompt."""
    if not seed:
        return ""
    lines: list[str] = []
    if seed.get("location"):
        lines.append(f"Location: {seed['location']}")
    if seed.get("headline"):
        lines.append(f"Headline: {seed['headline']}")
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
) -> tuple[SuggestedBenchmark, dict[str, str]]:
    """Build a teaching profile and resume for a virtual candidate.

    The name is the virtual candidate. The last company is their latest real employer in the model,
    and the rest of the career uses other real US high-ranking companies in that industry.
    Optional profile_seed facts (LinkedIn-style) steer sections the coach already knows.
    """
    name, company = (name or "").strip(), (company or "").strip()
    if not name or not company:
        raise ValueError("candidate name and last company are required")
    jd = (jd or "").strip()
    seed = normalize_profile_seed(profile_seed)
    md = market_data()
    suggestion = ask_json("sample_suggest", SuggestedBenchmark, {
        "name": name,
        "company": company,
        "title": (title or "").strip(),
        "notes": (notes or "").strip(),
        "jd": jd,
        "profile_seed": seed,
        "profile_seed_text": format_profile_seed_for_prompt(seed),
        "archetypes": archetypes(),
        "n_jobs": md["n_jobs"],
        "top_keywords": md["top_keywords"],
    })
    suggestion.target_kind = "job_description" if jd else "company_domain"
    suggestion = guard_suggestion(suggestion, name, company)
    return suggestion, write_suggestion_artifacts(suggestion)


def write_suggestion_artifacts(suggestion: SuggestedBenchmark) -> dict[str, str]:
    """Persist suggestion.json, profile.md, and resume files under output/suggestions/."""
    name = suggestion.persona_name or suggestion.for_candidate or "candidate"
    company = suggestion.last_company or "company"
    out = config.OUTPUT_DIR / "suggestions" / _slug(name, company)
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

