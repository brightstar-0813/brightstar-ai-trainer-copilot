"""Pydantic schemas: candidate profile and every structured LLM output."""
from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from . import config

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,62}$")


class Lenient(BaseModel):
    model_config = ConfigDict(extra="allow")


# ----------------------------------------------------------------------------- candidate profile
class Basics(Lenient):
    name: str = ""
    headline: str = ""
    location: str = ""
    email: str = ""
    phone: str = ""
    links: dict[str, str] = Field(default_factory=dict)


class Experience(Lenient):
    company: str = ""
    title: str = ""
    start: str = ""
    end: str = ""
    location: str = ""
    bullets: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)


class Education(Lenient):
    school: str = ""
    degree: str = ""
    field: str = ""
    start: str = ""
    end: str = ""
    details: list[str] = Field(default_factory=list)


class Credential(Lenient):
    name: str = ""
    issuer: str = ""
    year: str = ""


class Project(Lenient):
    name: str = ""
    description: str = ""
    link: str = ""
    skills: list[str] = Field(default_factory=list)
    impact: str = ""


class AITrainingWork(Lenient):
    platform: str = ""
    task_type: str = ""
    domain: str = ""
    hours: str = ""
    outcome: str = ""


class MasterProfile(Lenient):
    basics: Basics = Field(default_factory=Basics)
    summary: str = ""
    target_roles: list[str] = Field(default_factory=list)
    experience: list[Experience] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    licenses: list[Credential] = Field(
        default_factory=list,
        description="Occupational licenses from a government or licensing board, such as PE, bar admission, RN, or CPA. Not a degree.",
    )
    certifications: list[Credential] = Field(
        default_factory=list,
        description="Professional or vendor certifications, such as PMP, AWS, OSHA, or a manufacturer credential. Not a degree and not a license.",
    )
    licenses_certs: list[Credential] = Field(
        default_factory=list,
        description="Legacy combined list. Prefer licenses and certifications.",
    )
    projects: list[Project] = Field(default_factory=list)
    publications: list[str] = Field(default_factory=list)
    ai_training_experience: list[AITrainingWork] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)  # subject-matter expertise
    languages: list[dict[str, str]] = Field(default_factory=list)  # {name, level}
    coding: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)

    def corpus(self) -> str:
        """Lower-cased text of the whole profile, used for keyword matching."""
        return yaml.safe_dump(self.model_dump(), allow_unicode=True).lower()

    def to_yaml(self) -> str:
        return yaml.safe_dump(self.model_dump(), allow_unicode=True, sort_keys=False)


def validate_slug(slug: str) -> str:
    s = (slug or "").strip().lower()
    if not _SLUG_RE.match(s):
        raise ValueError(
            "Profile name must be 1-63 chars: start with a-z/0-9, then a-z/0-9/_/- only "
            f"(got {slug!r})"
        )
    return s


def people_dir() -> Path:
    return config.PEOPLE_DIR


def profile_path(slug: str) -> Path:
    return people_dir() / f"{validate_slug(slug)}.yaml"


def profile_example_path() -> Path:
    if config.PROFILE_EXAMPLE.exists():
        return config.PROFILE_EXAMPLE
    legacy = config.PROFILE_DIR / "master_profile.example.yaml"
    return legacy if legacy.exists() else config.PROFILE_EXAMPLE


def migrate_legacy_master() -> None:
    """Copy profile/master_profile.yaml -> people/default.yaml once."""
    # Prefer the named constant; fall back so a stale Streamlit reload of config
    # (pre-multi-profile) does not crash the dashboard on import.
    legacy = getattr(config, "LEGACY_MASTER_PROFILE", None) or (
        config.PROFILE_DIR / "master_profile.yaml"
    )
    dest = people_dir() / "default.yaml"
    if not legacy.exists() or dest.exists():
        return
    people_dir().mkdir(parents=True, exist_ok=True)
    shutil.copy2(legacy, dest)
    from .llm.prefs import load_prefs, save_prefs
    if not (load_prefs().get("active_profile") or "").strip():
        save_prefs(active_profile="default")


def list_profiles() -> list[str]:
    migrate_legacy_master()
    d = people_dir()
    if not d.exists():
        return []
    return sorted(
        p.stem for p in d.glob("*.yaml")
        if p.is_file() and not p.name.startswith("_") and _SLUG_RE.match(p.stem)
    )


def get_active_profile() -> str | None:
    migrate_legacy_master()
    from .llm.prefs import load_prefs
    raw = (load_prefs().get("active_profile") or "").strip().lower()
    if raw and profile_path(raw).exists():
        return raw
    profiles = list_profiles()
    if "default" in profiles:
        return "default"
    if len(profiles) == 1:
        return profiles[0]
    return None


def set_active_profile(slug: str) -> str:
    slug = validate_slug(slug)
    path = profile_path(slug)
    if not path.exists():
        raise FileNotFoundError(
            f"Profile '{slug}' not found at {path}. "
            f"Import with `jt profile import --name {slug} --resume ...`"
        )
    from .llm.prefs import save_prefs
    save_prefs(active_profile=slug)
    return slug


def resolve_profile_slug(slug: str | None = None) -> str:
    """Resolve an explicit slug or the active profile; raise if none."""
    migrate_legacy_master()
    if slug:
        return validate_slug(slug)
    active = get_active_profile()
    if active:
        return active
    raise FileNotFoundError(
        "No active profile. Run `jt profile import --name <slug> --resume ...` "
        "or `jt profile use <slug>`."
    )


def load_profile(slug: str | None = None) -> MasterProfile:
    resolved = resolve_profile_slug(slug)
    path = profile_path(resolved)
    if not path.exists():
        raise FileNotFoundError(
            f"Profile '{resolved}' not found at {path}. "
            f"Run `jt profile import --name {resolved} --resume ...` "
            f"or copy {profile_example_path().name}."
        )
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return MasterProfile.model_validate(data)


def save_profile(p: MasterProfile, slug: str | None = None, *, activate: bool = True) -> Path:
    """Write a profile YAML. `slug=None` uses the active profile. New imports should pass a slug."""
    if slug:
        resolved = validate_slug(slug)
    else:
        resolved = resolve_profile_slug(None)
    path = profile_path(resolved)
    people_dir().mkdir(parents=True, exist_ok=True)
    path.write_text(p.to_yaml(), encoding="utf-8")
    if activate:
        from .llm.prefs import save_prefs
        save_prefs(active_profile=resolved)
    return path


# ----------------------------------------------------------------------------- job analysis
class Requirement(BaseModel):
    text: str = Field(description="The requirement in plain words")
    keywords: list[str] = Field(default_factory=list, description="1-4 short lowercase terms a resume would use to show this")
    category: str = Field(default="skill", description="education | experience | skill | language | license | certification | tool | domain | other")


class JobRequirements(BaseModel):
    summary: str = Field(description="One-sentence summary of the job")
    domain: str = Field(default="", description="Primary subject domain, e.g. coding, math, physics, law, medicine, creative writing, general")
    task_types: list[str] = Field(default_factory=list, description="e.g. rlhf ranking, sft writing, red teaming, evaluation, rubric design, annotation")
    seniority: str = Field(default="", description="entry | mid | senior | expert")
    must_haves: list[Requirement] = Field(default_factory=list)
    nice_to_haves: list[Requirement] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list, description="ATS keywords from the posting, lowercase, max 25")
    education_required: str = ""
    languages_required: list[str] = Field(default_factory=list)
    pay: str = ""
    time_commitment: str = ""
    screening_signals: list[str] = Field(default_factory=list, description="assessments, tests, 'PhD preferred', portfolio asks, etc.")
    red_flags: list[str] = Field(default_factory=list)


class Gap(BaseModel):
    requirement: str
    kind: str = "must"  # must | nice | keyword
    keywords: list[str] = Field(default_factory=list)


class GapQuestionItem(BaseModel):
    gap: str = Field(description="The requirement or keyword this question relates to")
    question: str = Field(description="One concrete question for the candidate, asking for evidence and a number")


class GapQuestions(BaseModel):
    questions: list[GapQuestionItem] = Field(max_length=8)


# ----------------------------------------------------------------------------- resume
class ResumeRole(BaseModel):
    company: str
    title: str
    start: str = Field(default="", description="Month + year, e.g. Aug 2010")
    end: str = Field(
        default="",
        description="Month + year or Present, e.g. Feb 2014 / Present",
    )
    location: str = ""
    bullets: list[str]


class ResumeEducation(BaseModel):
    school: str
    degree: str = ""
    field: str = ""
    dates: str = ""
    details: list[str] = Field(default_factory=list)


class ResumeProject(BaseModel):
    name: str
    description: str
    link: str = ""


class SkillGroup(BaseModel):
    """One scannable skills row: bold category + related items."""

    category: str = Field(description="Short label, e.g. Investment Strategy, Platforms & Tools")
    items: list[str] = Field(description="3-6 concrete skills in this category")


class ResumeContent(BaseModel):
    name: str
    headline: str
    contact: str = Field(description="One line: location | email | phone | links")
    summary: str
    skills: list[str] = Field(
        default_factory=list,
        description="Flat skills for ATS matching; keep aligned with skill_groups",
    )
    skill_groups: list[SkillGroup] = Field(
        default_factory=list,
        description="Categorized skills for the resume Skills section (preferred over a middot dump)",
    )
    experience: list[ResumeRole]
    education: list[ResumeEducation] = Field(default_factory=list)
    licenses: list[str] = Field(
        default_factory=list,
        description="Occupational licenses. Do not repeat these inside education.",
    )
    certifications: list[str] = Field(
        default_factory=list,
        description="Professional or vendor certifications. Do not repeat these inside education or licenses.",
    )
    projects: list[ResumeProject] = Field(default_factory=list)
    additional: list[str] = Field(
        default_factory=list,
        description="Languages, publications, awards. Human-readable bullets only — never snake_case keys or coach metadata.",
    )
    unverified_claims: list[str] = Field(default_factory=list,
                                         description="Anything you were unsure was backed by the profile or answers; empty if none")


class HumanizedResume(BaseModel):
    resume: ResumeContent
    changes: list[str] = Field(default_factory=list)


# ----------------------------------------------------------------------------- profile advice
class ProfileAdvice(BaseModel):
    headline_options: list[str] = Field(description="3 LinkedIn headlines, max 220 chars each")
    about: str = Field(description="LinkedIn About section, first-person, 1500-2000 chars")
    featured: list[str] = Field(default_factory=list, description="Items to pin to Featured")
    skills_order: list[str] = Field(description="Top 50 LinkedIn skills in the order to pin them")
    experience_edits: list[str] = Field(default_factory=list)
    certifications_to_get: list[str] = Field(default_factory=list)
    projects_to_build: list[str] = Field(default_factory=list)
    quick_wins: list[str] = Field(default_factory=list)


# ----------------------------------------------------------------------------- benchmark samples
class SampleProfile(BaseModel):
    archetype: str
    label: str = "ILLUSTRATIVE SAMPLE - fictional person, not a real individual"
    headline: str
    about: str
    experience: list[ResumeRole]
    education: list[ResumeEducation]
    licenses: list[str] = Field(
        default_factory=list,
        description="Real occupational licenses and their issuers. Licensed domains: typically 1–3 gating/specialty licenses. Empty only when the domain has none.",
    )
    certifications: list[str] = Field(
        default_factory=list,
        description="Real professional or vendor certifications and their issuers. Prefer a dense stack (typically 3–6 when cert paths exist; 2–4 alongside licenses). Empty only when the domain has none.",
    )
    licenses_certs: list[str] = Field(
        default_factory=list,
        description="Legacy combined list. Leave empty on new samples.",
    )
    projects: list[ResumeProject] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list, description="Flat list; prefer skill_groups for display")
    skill_groups: list[SkillGroup] = Field(
        default_factory=list,
        description="4-6 categorized skill rows for the resume. Prefer this over a long flat skills dump.",
    )
    signals: list[str] = Field(description="Why this profile reads as top 0.1%: concrete markers recruiters look for")
    benchmarks: dict[str, str] = Field(default_factory=dict, description="Quantified markers, e.g. years of experience, publications")


class TargetedSample(SampleProfile):
    """A complete illustrative benchmark: career, education, credentials, and projects."""

    # min_length=1 on experience so provided-seed mode can keep a single last-company role.
    experience: list[ResumeRole] = Field(min_length=1)
    education: list[ResumeEducation] = Field(default_factory=list)
    projects: list[ResumeProject] = Field(min_length=1)
    skills: list[str] = Field(default_factory=list)
    skill_groups: list[SkillGroup] = Field(default_factory=list)
    signals: list[str] = Field(min_length=4, description="Why this profile reads as top 0.1%")

    @model_validator(mode="after")
    def _require_skills(self) -> TargetedSample:
        flat = [s for s in self.skills if str(s).strip()]
        groups = [g for g in self.skill_groups if g.category and g.items]
        if not flat and not groups:
            raise ValueError("Provide skills or skill_groups")
        return self


class TeachingNote(BaseModel):
    """One lesson a coach can use while walking through the model profile."""

    section: str = Field(description="headline, experience, education, licenses, certifications, projects, or skills")
    necessary_information: str = Field(description="Facts a complete entry in this section must contain")
    best_option: str = Field(description="Why these real organisations, credentials, or projects are the strong choice")
    how_to_teach: str = Field(description="One or two sentences a coach can say to a learner")


class SuggestedBenchmark(BaseModel):
    """Teaching profile and resume for a virtual candidate in a real industry.

    The name is the virtual candidate. Employers, schools, and credentials are real organisations.
    """

    for_candidate: str = ""
    last_company: str = ""
    last_title: str = Field(
        default="",
        description="Last role/title when the coach set one; empty means company-domain framing.",
    )
    inferred_industry: str = Field(
        description="Industry of the target career (role domain when last role is set, else company industry), "
        "e.g. corporate finance, industrial robotics, hospital systems"
    )
    inferred_domain: str = Field(description="Specific function the model is built for, e.g. financial specialist, controls engineering")
    target_kind: str = Field(
        default="company_domain",
        description="company_domain, role_domain, or job_description",
    )
    why_this_shape: str = Field(
        description="Why this career, education, licenses, certifications and projects would rank in the top 0.1% for the target. "
        "When a job description was given, map its main requirements onto sections of the sample.")
    persona_name: str = Field(description="Virtual candidate name. Use the name that was provided.")
    contact: str = Field(
        default="",
        description="Optional resume contact line from the seed (location | email | phone | links).",
    )
    teaching_notes: list[TeachingNote] = Field(
        min_length=6,
        description="At least one note each for headline, experience, education, licenses, certifications, and projects.",
    )
    sample: TargetedSample


class ProfileComparison(BaseModel):
    strengths: list[str]
    gaps: list[str]
    priority_actions: list[str] = Field(description="Ordered, most impactful first")


class ImportedProfile(BaseModel):
    profile: dict = Field(description="Object matching the master profile layout")
    missing_evidence_questions: list[str] = Field(default_factory=list)


class TopTierScreen(BaseModel):
    """Recruiter + ATS verdict: does this profile/resume clear a top 0.1% bar for the JD?"""

    is_top_tier: bool = Field(description="True only when the evidence supports a top 0.1% read for this JD")
    tier_label: str = Field(
        description="One of: top_0_1 | top_1 | top_10 | average | below",
    )
    confidence: str = Field(default="medium", description="low | medium | high")
    verdict: str = Field(description="2-4 sentence recruiter screening verdict")
    strengths: list[str] = Field(default_factory=list, description="Evidence that supports a strong screen")
    gaps_vs_bar: list[str] = Field(
        default_factory=list,
        description="Concrete gaps vs a top 0.1% bar for this posting",
    )
    ats_risks: list[str] = Field(default_factory=list, description="ATS keyword or format risks")
    recruiter_notes: list[str] = Field(default_factory=list, description="How a recruiter would read this resume")
    priority_actions: list[str] = Field(
        default_factory=list,
        description="Ordered, truthful upgrades only — no invented experience",
    )


class MatchReport(BaseModel):
    """Full one-off JD + resume/profile screen result."""

    fit_score: float
    ats_coverage: float
    screen_band: str
    percentile: Optional[float] = None
    keywords_present: list[str] = Field(default_factory=list)
    keywords_missing: list[str] = Field(default_factory=list)
    gaps: list[Gap] = Field(default_factory=list)
    requirements: Optional[JobRequirements] = None
    screen: Optional[TopTierScreen] = None
    jd_title: str = ""
    jd_company: str = ""
    candidate_source: str = ""
    report_dir: str = ""


class BridgeTest(BaseModel):
    ok: bool
    note: Optional[str] = None
