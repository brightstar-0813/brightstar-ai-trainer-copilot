"""Full pipeline with a fake LLM (no extension, no network)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from jt import config, db
from jt.collect import store
from jt.llm import client as llm_client
from jt.llm.client import LLMError
from jt.models import Job
from jt.pipelines import analyze, match, profile, samples, tailor
from jt.schemas import (
    Gap,
    JobRequirements,
    MasterProfile,
    MatchReport,
    ResumeContent,
    ResumeRole,
    TopTierScreen,
    load_profile,
    save_profile,
)
from jt.sources.base import RawJob

JOB_REQ = {
    "summary": "Rank and write math answers for an LLM", "domain": "math",
    "task_types": ["rlhf ranking", "sft writing"], "seniority": "expert",
    "must_haves": [
        {"text": "Master's or PhD in mathematics", "keywords": ["mathematics", "msc"], "category": "education"},
        {"text": "Experience with RLHF", "keywords": ["rlhf"], "category": "experience"},
        {"text": "Admitted to the bar", "keywords": ["bar admission"], "category": "license"}],
    "nice_to_haves": [{"text": "Python", "keywords": ["python"], "category": "skill"}],
    "keywords": ["rlhf", "mathematics", "python", "latex"], "pay": "$45/hour",
    "screening_signals": ["timed assessment"], "red_flags": []}

RESUME = {
    "name": "Jane Example", "headline": "Mathematics MSc | RLHF evaluator", "contact": "City | jane@example.com",
    "summary": "MSc mathematician who ranks model answers.", "skills": ["mathematics", "python", "rlhf"],
    "experience": [{"company": "Example University", "title": "Teaching Assistant", "start": "2021-09",
                    "end": "2023-06", "bullets": ["Graded 400+ problem sets per term",
                                                   "Reviewed 9,999 model answers"]}],
    "education": [{"school": "Example University", "degree": "MSc", "field": "Mathematics", "dates": "2021-2023"}],
    "certifications": [], "projects": [], "additional": [], "unverified_claims": []}


class FakeBC:
    calls: list[str] = []
    first_job_analyze_garbage = False

    def __init__(self, *a, **k): ...
    def __enter__(self): return self
    def __exit__(self, *a): ...

    def ask(self, provider, prompt, **kw):
        FakeBC.calls.append(prompt)
        FakeBC.last = {"provider": provider, **kw}
        if "connectivity test" in prompt:
            return '```json\n{"ok": true}\n```'
        j = lambda o: "```json\n" + json.dumps(o) + "\n```"  # noqa: E731
        if prompt.startswith("Your last reply was not valid"):  # same-chat repair follow-up
            return j(JOB_REQ)
        if "recruiter-side analyst" in prompt:
            if FakeBC.first_job_analyze_garbage:
                FakeBC.first_job_analyze_garbage = False
                return "Sorry, I cannot do that"
            return j(JOB_REQ)
        if "interviewer helping" in prompt:
            return j({"questions": [{"gap": "Admitted to the bar", "question": "Are you admitted to a bar?"},
                                    {"gap": "RLHF", "question": "How many RLHF tasks did you rank?"}]})
        if "expert resume writer" in prompt:
            return j(RESUME)
        if "Edit the resume below" in prompt:
            return j({"resume": RESUME, "changes": ["varied verbs"]})
        if "LinkedIn strategist" in prompt:
            return j({"headline_options": ["h1", "h2", "h3"], "about": "About me", "featured": [],
                      "skills_order": ["math"], "experience_edits": [], "certifications_to_get": ["Cert X"],
                      "projects_to_build": [], "quick_wins": []})
        if "domain hiring benchmark writer" in prompt:
            note = lambda section: {  # noqa: E731
                "section": section,
                "necessary_information": f"Complete {section} facts",
                "best_option": f"Real {section} choice",
                "how_to_teach": f"Walk through {section}",
            }
            return j({
                "inferred_industry": "Industrial robotics",
                "inferred_domain": "controls engineering",
                "target_kind": "company_domain",
                "why_this_shape": "A licensed controls engineer who has shipped safety-rated cells.",
                "persona_name": "Someone Else",
                "teaching_notes": [note(s) for s in ("headline", "experience", "education", "licenses", "certifications", "projects")],
                "sample": {
                    "archetype": "Controls engineer",
                    "label": "TEACHING EXAMPLE - virtual candidate, model career at real organisations",
                    "headline": "Controls engineer for safety-rated automation",
                    "about": "Designs and commissions safety-rated motion systems.",
                    "experience": [
                        {"company": "Siemens", "title": "Senior Controls Engineer",
                         "start": "2019", "end": "2024", "bullets": ["Commissioned 12 robot cells"]},
                        {"company": "Fanuc", "title": "Controls Engineer",
                         "start": "2014", "end": "2019", "bullets": ["Wrote PLC standards for 4 lines"]},
                    ],
                    "education": [
                        {"school": "Georgia Institute of Technology", "degree": "BSc",
                         "field": "Electrical Engineering", "dates": "2010-2014"},
                        {"school": "a state engineering university", "degree": "coursework", "field": "Controls"},
                    ],
                    "licenses_certs": ["Professional Engineer (PE), electrical, NCEES"],
                    "projects": [{"name": "Cell safety retrofit", "description": "Documented a lockout design used on 12 cells."}],
                    "skills": ["PLC", "safety PLCs", "robot commissioning"],
                    "signals": ["PE license", "shipped safety cells", "named PLC platforms", "documented lockout design"],
                    "benchmarks": {"years": "12"},
                },
            })
        if "talent strategist" in prompt:
            return j({"archetype": "STEM PhD Expert", "headline": "Top", "about": "x",
                      "experience": [{"company": "Lab", "title": "Postdoc", "bullets": ["b"]}],
                      "education": [{"school": "Uni", "degree": "PhD"}], "signals": ["s"], "benchmarks": {"pubs": "8"}})
        if "candid career coach" in prompt:
            return j({"strengths": ["math"], "gaps": ["no publications"], "priority_actions": ["publish"]})
        if "senior recruiter and ATS screener" in prompt:
            return j({
                "is_top_tier": False,
                "tier_label": "top_10",
                "confidence": "medium",
                "verdict": "Strong math and RLHF signal, but missing bar admission for a top 0.1% screen.",
                "strengths": ["MSc mathematics", "RLHF keywords present"],
                "gaps_vs_bar": ["No bar admission evidence"],
                "ats_risks": ["bar admission keyword missing"],
                "recruiter_notes": ["Would pass an initial ATS keyword pass for math/RLHF"],
                "priority_actions": ["Add bar admission only if true"],
            })
        if "converting a candidate's existing resume" in prompt:
            return j({"profile": {"basics": {"name": "Jane"}, "domains": ["mathematics"]},
                      "missing_evidence_questions": ["How many hours?"]})
        raise AssertionError("unrecognised prompt: " + prompt[:80])


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "data" / "jobs.db")
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path / "output")
    monkeypatch.setattr(config, "PROFILE_DIR", tmp_path / "profile")
    monkeypatch.setattr(config, "PEOPLE_DIR", tmp_path / "profile" / "people")
    monkeypatch.setattr(config, "PROFILE_EXAMPLE", Path(__file__).parent.parent / "profile" / "profile.example.yaml")
    monkeypatch.setattr(config, "LEGACY_MASTER_PROFILE", tmp_path / "profile" / "master_profile.yaml")
    monkeypatch.setattr(config, "MASTER_PROFILE", tmp_path / "profile" / "master_profile.yaml")
    monkeypatch.setattr(config, "SAMPLES_DIR", tmp_path / "samples")
    monkeypatch.setattr(db, "_engine", None)
    monkeypatch.setattr(llm_client, "BridgeClient", FakeBC)
    # Force bridge path: ignore any real API keys / prefs from the developer machine.
    monkeypatch.setattr(config, "openai_api_key", lambda: "")
    monkeypatch.setattr(config, "anthropic_api_key", lambda: "")
    monkeypatch.setenv("JT_LLM_ENGINE", "auto")
    prefs = {"engine": "auto", "browser": "gpt", "resume_template": "ats-modern",
             "resume_accent": "", "active_profile": "test"}
    monkeypatch.setattr("jt.llm.prefs.load_prefs", lambda: dict(prefs))

    def _save_prefs(**kwargs):
        prefs.update({k: v for k, v in kwargs.items() if v is not None})
        if "active_profile" in kwargs and kwargs["active_profile"] is not None:
            prefs["active_profile"] = str(kwargs["active_profile"]).strip().lower()
        return dict(prefs)

    monkeypatch.setattr("jt.llm.prefs.save_prefs", _save_prefs)
    FakeBC.calls.clear()
    FakeBC.first_job_analyze_garbage = False
    st = store([RawJob(source="x", external_id="1", title="AI Tutor, Math", company="Acme", pay="$45/hour",
                       description="Rank answers for RLHF. Requires a math Master's.")])
    assert st.new == 1
    example = Path(__file__).parent.parent / "profile" / "profile.example.yaml"
    save_profile(
        MasterProfile.model_validate(yaml.safe_load(example.read_text(encoding="utf-8"))),
        slug="test",
    )
    return tmp_path


def test_analyze_scores_and_finds_gaps(env):
    a = analyze.analyze_job(1)
    assert 0 < a.fit_score < 100
    gaps = analyze.gaps_of(a)
    assert any(g.kind == "must" and "bar" in g.requirement for g in gaps)
    assert analyze.analyze_job(1).id == a.id  # cached, no second LLM call
    assert len(FakeBC.calls) == 1
    assert analyze.ranked()[0][0].id == 1


def test_invalid_json_is_repaired_in_same_chat(env):
    FakeBC.first_job_analyze_garbage = True
    a = analyze.analyze_job(1)
    assert a.fit_score > 0
    assert "not valid" in FakeBC.calls[1]  # repair follow-up was sent


def test_provider_override_uses_that_providers_url(env):
    """Regression: `jt bridge test gpt` must open ChatGPT, not the URL of the task's configured provider."""
    from jt.schemas import BridgeTest
    llm_client.ask_json("bridge_test", BridgeTest, provider="gpt")  # bridge_test is configured for claude
    assert FakeBC.last["provider"] == "gpt" and "chatgpt.com" in FakeBC.last["url"]
    llm_client.ask_json("bridge_test", BridgeTest, provider="claude")
    assert "claude.ai" in FakeBC.last["url"]
    llm_client.ask("bridge_test", provider="gpt", prompt="connectivity test")
    assert "chatgpt.com" in FakeBC.last["url"]


def test_persistent_garbage_raises_invalid_json(env, monkeypatch):
    monkeypatch.setattr(FakeBC, "ask", lambda self, p, prompt, **kw: "no json at all")
    with pytest.raises(LLMError) as e:
        analyze.analyze_job(1)
    assert e.value.code == "invalid_json"


def test_tailor_flow_flags_fabricated_number_and_renders(env):
    qs = tailor.generate_questions(1)
    assert len(qs) == 2
    tailor.answer_question(qs[1].id, "I ranked about 500 RLHF tasks at Example University.")
    row = tailor.tailor_job(1)
    meta = json.loads(row.resume_json)["meta"]
    assert any("9,999" in w for w in meta["warnings"])  # fabricated figure is flagged
    assert not any("400" in w for w in meta["warnings"])  # 400+ is in the profile
    assert Path(row.docx_path).exists() and Path(row.docx_path).stat().st_size > 2000
    assert Path(row.prompt_path).read_text(encoding="utf-8").count("FULL JOB DESCRIPTION") == 1
    assert "500 RLHF tasks" in Path(row.prompt_path).read_text(encoding="utf-8")
    assert meta["ats_coverage"] > 0


def test_verify_resume_flags_unknown_employer(env):
    p = load_profile()
    r = ResumeContent.model_validate(RESUME)
    r.experience.append(ResumeRole(company="Imaginary Corp", title="CEO", bullets=["Led 50 people"]))
    warnings = tailor.verify_resume(r, p)
    assert any("Imaginary Corp" in w for w in warnings)
    assert any("'50'" in w for w in warnings)


def test_suggest_sample_teaches_with_real_company_and_name(env):
    from jt.schemas import profile_path
    before = profile_path("test").read_text(encoding="utf-8")
    suggestion, paths = samples.suggest_sample(
        "Jane Example", "Fanuc", title="Controls Engineer")
    assert suggestion.target_kind == "company_domain"
    assert suggestion.persona_name == "Jane Example"
    assert "TEACHING EXAMPLE" in suggestion.sample.label
    assert suggestion.sample.experience[0].company == "Fanuc"
    assert suggestion.sample.experience[1].company == "Siemens"
    assert any("state engineering" in n for n in samples.generic_org_notes(suggestion))
    profile = Path(paths["profile"]).read_text(encoding="utf-8")
    assert "How to teach it" in profile and "Georgia Institute of Technology" in profile
    assert Path(paths["docx"]).stat().st_size > 1000
    html = Path(paths["html"]).read_text(encoding="utf-8")
    assert "Jane Example" in html or "Virtual candidate" in html
    assert "Fanuc" in html
    assert "total_relevant_experience" not in html
    assert "Additional" not in html
    resume = samples.sample_to_resume(suggestion)
    assert resume.additional == []
    assert len(resume.skills) <= 18
    assert "years: 12" not in " ".join(resume.additional)
    assert profile_path("test").read_text(encoding="utf-8") == before

    missing = suggestion.model_copy(deep=True)
    missing.sample.experience[0].company = "Siemens"
    missing.sample.experience[1].company = "ABB"
    fixed = samples.guard_suggestion(missing, "Jane Example", "Fanuc")
    assert fixed.persona_name == "Jane Example"
    assert fixed.sample.experience[0].company == "Fanuc"

    aimed, _ = samples.suggest_sample(
        "Jane Example", "Fanuc", jd="Need a PE-licensed controls engineer for robot cells.")
    assert aimed.target_kind == "job_description"
    assert "Fanuc" in FakeBC.calls[-1]
    assert "PE-licensed" in FakeBC.calls[-1]
    assert "real universities" in FakeBC.calls[-1]


def test_profile_seed_normalizes_and_reaches_prompt(env):
    seed = samples.normalize_profile_seed({
        "location": "  Chicago, IL ",
        "headline": "",
        "about": "Senior automation lead.",
        "experience": [
            {"company": "Siemens", "title": "Controls engineer", "bullets": "Line A\nLine B", "start": "2014"},
            {"company": "", "title": ""},
        ],
        "education": [{"school": "Georgia Institute of Technology", "degree": "BSc", "field": "EE"}],
        "licenses": [{"name": "PE", "issuer": "NCEES"}],
        "skills": "PLC, safety PLCs; robot commissioning",
        "languages": [{"name": "English", "level": "Native"}],
        "projects": [{"name": "Cell retrofit", "description": "Lockout design", "skills": "PLC, FANUC"}],
    })
    assert seed["location"] == "Chicago, IL"
    assert "headline" not in seed
    assert seed["experience"][0]["bullets"] == ["Line A", "Line B"]
    assert seed["skills"] == ["PLC", "safety PLCs", "robot commissioning"]
    assert len(seed["experience"]) == 1

    text = samples.format_profile_seed_for_prompt(seed)
    assert "Prior experience: Controls engineer, Siemens" in text
    assert "License: PE, NCEES" in text

    samples.suggest_sample(
        "Jane Example",
        "Fanuc",
        profile_seed=seed,
    )
    prompt = FakeBC.calls[-1]
    assert "OPTIONAL PROFILE SEED" in prompt
    assert "Siemens" in prompt
    assert "Georgia Institute of Technology" in prompt
    assert "safety PLCs" in prompt


def test_profile_optimize_samples_and_compare(env):
    analyze.analyze_job(1)
    md = profile.market_data()
    assert md["n_jobs"] == 1 and "rlhf" in md["top_keywords"]
    advice = profile.optimize_profile()
    assert advice.certifications_to_get == ["Cert X"]
    assert "About me" in profile.advice_to_markdown(advice)
    s = samples.generate_sample("stem_phd")
    assert "ILLUSTRATIVE" in s.label
    assert (config.SAMPLES_DIR / "stem_phd.md").exists()
    c = samples.compare("stem_phd")
    assert c.priority_actions == ["publish"]


def test_import_profile_from_text_file(env, tmp_path):
    f = tmp_path / "cv.txt"
    f.write_text("Jane Example, mathematician", encoding="utf-8")
    p, qs = profile.import_profile(f)
    assert p.basics.name == "Jane" and qs == ["How many hours?"]


def test_screen_band_thresholds():
    assert match.screen_band(95) == "Strong"
    assert match.screen_band(80) == "Strong"
    assert match.screen_band(60) == "Interview"
    assert match.screen_band(40) == "Stretch"
    assert match.screen_band(10) == "Reject"


def test_report_to_markdown_includes_tier():
    report = MatchReport(
        fit_score=72.0,
        ats_coverage=55.0,
        screen_band="Interview",
        percentile=40.0,
        keywords_present=["rlhf"],
        keywords_missing=["bar admission"],
        gaps=[Gap(requirement="Admitted to the bar", kind="must")],
        requirements=JobRequirements(summary="x", domain="math"),
        screen=TopTierScreen(
            is_top_tier=False,
            tier_label="top_10",
            confidence="medium",
            verdict="Not quite top 0.1%.",
            strengths=["math"],
            gaps_vs_bar=["bar"],
            ats_risks=["missing keyword"],
            recruiter_notes=["solid ATS pass for domain"],
            priority_actions=["add license if true"],
        ),
        jd_title="AI Tutor",
        jd_company="Acme",
        candidate_source="profile:test",
    )
    md = match.report_to_markdown(report)
    assert "top_10" in md and "Not quite top 0.1%" in md
    assert "72" in md and "ATS coverage" in md


def test_screen_match_pasted_jd_uses_active_profile(env):
    analyze.analyze_job(1)  # seed percentile comparison
    report = match.screen_match(jd="AI Tutor math RLHF. Requires Master's and bar admission.")
    assert report.fit_score > 0
    assert report.candidate_source == "profile:test"
    assert report.screen_band in {"Strong", "Interview", "Stretch", "Reject"}
    assert report.screen is not None
    assert report.screen.tier_label == "top_10"
    assert report.screen.is_top_tier is False
    assert Path(report.report_dir).joinpath("report.json").exists()
    assert Path(report.report_dir).joinpath("report.md").exists()
    assert report.percentile is not None
    assert any("senior recruiter and ATS screener" in c for c in FakeBC.calls)


def test_multi_profile_list_use_and_import_slug(env):
    from jt.schemas import get_active_profile, list_profiles, profile_path, set_active_profile

    assert "test" in list_profiles()
    assert get_active_profile() == "test"
    save_profile(MasterProfile(basics={"name": "Other"}), slug="other")
    assert set_active_profile("other") == "other"
    assert get_active_profile() == "other"
    assert load_profile().basics.name == "Other"
    assert profile_path("test").exists() and profile_path("other").exists()


def test_legacy_master_profile_migrates_to_default(env, monkeypatch):
    from jt.schemas import get_active_profile, list_profiles, load_profile, people_dir

    legacy = config.LEGACY_MASTER_PROFILE
    legacy.parent.mkdir(parents=True, exist_ok=True)
    legacy.write_text("basics:\n  name: Legacy Person\n", encoding="utf-8")
    # Drop people/ so migrate has to copy legacy.
    for p in people_dir().glob("*.yaml"):
        p.unlink()
    monkeypatch.setattr("jt.llm.prefs.load_prefs", lambda: {
        "engine": "auto", "browser": "gpt", "resume_template": "ats-modern",
        "resume_accent": "", "active_profile": "",
    })
    assert "default" in list_profiles()
    assert get_active_profile() == "default"
    assert load_profile().basics.name == "Legacy Person"
