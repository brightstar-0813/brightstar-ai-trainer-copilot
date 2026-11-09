"""Teaching model → suitable collected jobs, or job-type fallback (offline)."""
from __future__ import annotations

import pytest
from sqlmodel import select

from jt import config, db
from jt.models import Job, JobAnalysis
from jt.pipelines import samples
from jt.schemas import (
    JobRequirements,
    Requirement,
    ResumeEducation,
    ResumeProject,
    ResumeRole,
    SkillGroup,
    SuggestedBenchmark,
    TeachingNote,
    TargetedSample,
)


def _notes() -> list[TeachingNote]:
    return [
        TeachingNote(
            section=sec,
            necessary_information="facts",
            best_option="real orgs",
            how_to_teach="explain caliber",
        )
        for sec in ("headline", "experience", "education", "licenses", "certifications", "projects")
    ]


def _suggestion(
    *,
    archetype: str = "swe_coder",
    domain: str = "coding",
    industry: str = "software",
    skills: list[str] | None = None,
    about: str = "Senior engineer writing and ranking code for RLHF and agent evals.",
) -> SuggestedBenchmark:
    skills = skills or ["python", "code review", "rlhf", "algorithms", "unit tests"]
    sample = TargetedSample(
        archetype=archetype,
        label=samples.TEACHING_LABEL,
        headline="Staff Software Engineer | Coding trainer",
        about=about,
        experience=[
            ResumeRole(
                company="Google",
                title="Staff Software Engineer",
                start="2018",
                end="Present",
                bullets=["Led Python platform reviews", "Built RLHF coding eval harnesses"],
            ),
            ResumeRole(
                company="Microsoft",
                title="Senior Software Engineer",
                start="2012",
                end="2018",
                bullets=["Owned backend services in Python and C++"],
            ),
        ],
        education=[
            ResumeEducation(
                school="Stanford University",
                degree="MS",
                field="Computer Science",
                dates="2010-2012",
            )
        ],
        projects=[
            ResumeProject(name="Agent traj eval", description="Graded tool-use trajectories"),
        ],
        skills=skills,
        skill_groups=[SkillGroup(category="Coding", items=skills[:4])],
        signals=["20+ years", "FAANG depth", "RLHF coding", "rubrics", "agent evals"],
        benchmarks={"total_relevant_experience": "20+ years"},
        licenses=[],
        certifications=[],
    )
    return SuggestedBenchmark(
        for_candidate="Marcus Chen",
        last_company="Google",
        inferred_industry=industry,
        inferred_domain=domain,
        target_kind="job_description",
        why_this_shape="Matches coding trainer bar.",
        persona_name="Marcus Chen",
        teaching_notes=_notes(),
        sample=sample,
    )


@pytest.fixture
def iso_env(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "data" / "jobs.db")
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path / "output")
    monkeypatch.setattr(config, "SAMPLES_DIR", tmp_path / "samples")
    monkeypatch.setattr(db, "_engine", None)
    config.ensure_dirs()
    db.get_engine()
    return tmp_path


def test_suggestion_to_master_profile_maps_fields():
    s = _suggestion()
    profile = samples.suggestion_to_master_profile(s)
    assert profile.basics.name == "Marcus Chen"
    assert profile.experience[0].company == "Google"
    assert profile.education[0].school == "Stanford University"
    assert profile.education[0].start == "2010"
    assert "python" in profile.tools
    assert any("coding" in d.lower() or "software" in d.lower() for d in profile.domains)


def test_jobs_for_suggestion_falls_back_to_types(iso_env):
    s = _suggestion(archetype="Senior Software Engineer (Coding Trainer)")
    result = samples.jobs_for_suggestion(s, min_fit=60)
    assert result["mode"] == "types"
    assert result["matches"] == []
    keys = {t["key"] for t in result["types"]}
    assert "swe_coder" in keys
    assert result["title_examples"]
    assert any("Coding" in t or "SWE" in t or "Python" in t for t in result["title_examples"])


def test_jobs_for_suggestion_returns_matching_jobs(iso_env):
    with db.session() as s:
        job = Job(
            source="greenhouse",
            external_id="swe-1",
            dedupe_key="acme|swe fellow",
            title="SWE Fellow - Coding Trainer",
            company="Acme AI",
            description="Python code review RLHF ranking algorithms unit tests",
            pay="$50/hour",
            relevance=1.0,
        )
        s.add(job)
        s.commit()
        s.refresh(job)
        job_id = job.id
        req = JobRequirements(
            summary="Coding trainer",
            domain="coding",
            task_types=["code review", "rlhf ranking"],
            must_haves=[
                Requirement(text="Python experience", keywords=["python"], category="skill"),
                Requirement(text="Code review", keywords=["code review"], category="skill"),
            ],
            nice_to_haves=[],
            keywords=["python", "rlhf", "algorithms", "unit tests"],
        )
        s.add(JobAnalysis(
            job_id=job_id,
            data_json=req.model_dump_json(),
            fit_score=12.0,  # real-candidate score must stay unchanged
            gaps_json="[]",
            provider="test",
        ))
        s.commit()

    suggestion = _suggestion()
    result = samples.jobs_for_suggestion(suggestion, min_fit=60)
    assert result["mode"] == "jobs"
    assert len(result["matches"]) == 1
    assert result["matches"][0]["job_id"] == job_id
    assert result["matches"][0]["fit"] >= 60
    assert result["matches"][0]["company"] == "Acme AI"

    with db.session() as s:
        stored = s.exec(select(JobAnalysis).where(JobAnalysis.job_id == job_id)).first()
        assert stored is not None
        assert stored.fit_score == 12.0  # not overwritten by teaching-model scoring


def test_suitable_for_suggestion_dir_writes_report(iso_env):
    suggestion = _suggestion(archetype="stem_phd", domain="math", industry="research",
                             skills=["mathematics", "proofs", "rlhf", "latex"],
                             about="PhD mathematician grading frontier model proofs.")
    folder = config.OUTPUT_DIR / "suggestions" / "priya-natarajan-intel"
    folder.mkdir(parents=True)
    (folder / "suggestion.json").write_text(suggestion.model_dump_json(indent=2), encoding="utf-8")

    result, used, report = samples.suitable_for_suggestion_dir(folder, min_fit=60)
    assert used == folder
    assert report.exists()
    text = report.read_text(encoding="utf-8")
    assert result["mode"] == "types"
    assert "No collected jobs met the fit bar" in text or "job kinds" in text.lower()
    assert "stem" in text.lower() or "Math" in text or "Tutor" in text


def test_suitable_report_markdown_jobs_mode():
    md = samples.suitable_report_markdown({
        "mode": "jobs",
        "min_fit": 60,
        "persona_name": "Marcus Chen",
        "inferred_domain": "coding",
        "matches": [{
            "job_id": 14, "fit": 88.0, "company": "Scale AI", "title": "SWE Fellow",
            "domain": "coding", "task_types": ["code review"], "pay": "$50/hour",
        }],
        "types": [],
        "title_examples": [],
    })
    assert "#14" in md or "# 14" in md or "**#14**" in md
    assert "Scale AI" in md
    assert "88" in md
