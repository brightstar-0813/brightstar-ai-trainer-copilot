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
from jt.pipelines import analyze, match, profile, resume_edit, samples, tailor
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
        if "teaching-model resume aligner" in prompt:
            # Weave JD keywords into skills so the alignment retry can raise ATS coverage.
            woven = dict(RESUME)
            woven["skills"] = list(dict.fromkeys(
                list(RESUME.get("skills") or []) + ["rlhf", "mathematics", "python", "latex"]
            ))
            woven["summary"] = (
                (RESUME.get("summary") or "")
                + " RLHF ranking, mathematics, python, and latex for model evaluation."
            )
            woven["unverified_claims"] = [
                "Teaching model. The person is virtual. The organisations named are real ones to learn from."
            ]
            return j(woven)
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
                         "start": "Mar 2019", "end": "Present", "bullets": ["Commissioned 12 robot cells"]},
                        {"company": "Fanuc", "title": "Controls Engineer",
                         "start": "Aug 2014", "end": "Feb 2019", "bullets": ["Wrote PLC standards for 4 lines"]},
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
             "resume_accent": "", "active_profile": "test", "suggest_seed_mode": "last_company"}
    monkeypatch.setattr("jt.llm.prefs.load_prefs", lambda: dict(prefs))

    def _save_prefs(**kwargs):
        prefs.update({k: v for k, v in kwargs.items() if v is not None})
        if "active_profile" in kwargs and kwargs["active_profile"] is not None:
            prefs["active_profile"] = str(kwargs["active_profile"]).strip().lower()
        if "suggest_seed_mode" in kwargs and kwargs["suggest_seed_mode"] is not None:
            from jt.llm.prefs import normalize_seed_mode
            prefs["suggest_seed_mode"] = normalize_seed_mode(kwargs["suggest_seed_mode"])
        return dict(prefs)

    monkeypatch.setattr("jt.llm.prefs.save_prefs", _save_prefs)

    def _fake_pdf(html: str, path: Path) -> bool:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_bytes(b"%PDF-1.4\nfake\n")
        return True

    monkeypatch.setattr("jt.render.resume.render_pdf", _fake_pdf)
    monkeypatch.setattr("jt.pipelines.samples.render_pdf", _fake_pdf)
    FakeBC.calls.clear()
    FakeBC.first_job_analyze_garbage = False
    st = store([RawJob(source="x", external_id="1", title="AI Tutor, Math", company="Acme",
                       location="Remote - United States", pay="$45/hour",
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


def test_format_month_year_normalizes_known_forms():
    assert samples.format_month_year("August 2010") == "Aug 2010"
    assert samples.format_month_year("2010-08") == "Aug 2010"
    assert samples.format_month_year("08/2010") == "Aug 2010"
    assert samples.format_month_year("present") == "Present"
    assert samples.format_month_year("2010") == "2010"
    from jt.schemas import SuggestedBenchmark

    note = {
        "section": "headline",
        "necessary_information": "n",
        "best_option": "b",
        "how_to_teach": "h",
    }
    raw = SuggestedBenchmark.model_validate(
        {
            "for_candidate": "A",
            "last_company": "Acme",
            "persona_name": "A",
            "inferred_industry": "x",
            "inferred_domain": "x",
            "why_this_shape": "x",
            "teaching_notes": [
                {**note, "section": s}
                for s in (
                    "headline",
                    "experience",
                    "education",
                    "licenses",
                    "certifications",
                    "projects",
                )
            ],
            "sample": {
                "archetype": "x",
                "label": "TEACHING EXAMPLE",
                "headline": "h",
                "about": "a",
                "experience": [
                    {
                        "company": "Acme",
                        "title": "Engineer",
                        "start": "2010-08",
                        "end": "2014-02",
                        "bullets": ["Built X"],
                    }
                ],
                "education": [],
                "projects": [{"name": "P", "description": "D"}],
                "skills": ["s1", "s2", "s3", "s4"],
                "signals": ["a", "b", "c", "d"],
                "benchmarks": {},
            },
        }
    )
    guarded = samples.guard_suggestion(raw, "A", "Acme")
    assert guarded.sample.experience[0].start == "Aug 2010"
    assert guarded.sample.experience[0].end == "Feb 2014"


def test_suggest_sample_teaches_with_real_company_and_name(env):
    from jt.schemas import profile_path
    before = profile_path("test").read_text(encoding="utf-8")
    company_only, company_paths = samples.suggest_sample("Jane Example", "Fanuc")
    assert company_only.target_kind == "company_domain"
    assert "hiring domain of the last company" in FakeBC.calls[-1]
    assert company_paths["dir"].endswith("jane-example-fanuc")

    suggestion, paths = samples.suggest_sample(
        "Jane Example", "Fanuc", title="Financial Specialist")
    assert suggestion.target_kind == "role_domain"
    assert suggestion.last_title == "Financial Specialist"
    assert suggestion.persona_name == "Jane Example"
    assert "TEACHING EXAMPLE" in suggestion.sample.label
    assert suggestion.sample.experience[0].company == "Fanuc"
    assert suggestion.sample.experience[0].title == "Financial Specialist"
    assert suggestion.sample.experience[1].company == "Siemens"
    role_prompt = FakeBC.calls[-1]
    assert "Last role: Financial Specialist" in role_prompt
    assert 'Set `target_kind` to "role_domain"' in role_prompt
    assert "Whole-career rule" in role_prompt
    assert "Anti-pattern" in role_prompt
    assert any("state engineering" in n for n in samples.generic_org_notes(suggestion))
    assert paths["dir"].endswith("jane-example-fanuc")
    profile = Path(paths["profile"]).read_text(encoding="utf-8")
    assert "How to teach it" in profile and "Georgia Institute of Technology" in profile
    assert "aimed at the last role (Financial Specialist)" in profile
    assert Path(paths["docx"]).stat().st_size > 1000
    assert paths["pdf"] and Path(paths["pdf"]).exists()
    html = Path(paths["html"]).read_text(encoding="utf-8")
    assert "Jane Example" in html
    assert "Virtual candidate — teaching example" not in html
    assert "Fanuc" in html
    assert "Aug 2014" in html and "Feb 2019" in html
    assert "Representative projects" in html
    assert "Selected Projects" not in html
    assert "Representative projects" in profile
    assert "Selected Projects" not in profile
    assert "total_relevant_experience" not in html
    assert "Additional" not in html
    resume = samples.sample_to_resume(suggestion)
    assert resume.contact == ""
    assert resume.additional == []
    assert len(resume.skills) <= 18
    assert "years: 12" not in " ".join(resume.additional)
    assert profile_path("test").read_text(encoding="utf-8") == before
    assert "Mon YYYY" in FakeBC.calls[-1] or "Aug 2010" in FakeBC.calls[-1]

    stale_dir = Path(paths["dir"])
    (stale_dir / "resume.html").write_text(
        html.replace("Representative projects", "Selected Projects"),
        encoding="utf-8",
    )
    assert samples.refresh_suggestion_resume_if_stale(stale_dir) is True
    refreshed = (stale_dir / "resume.html").read_text(encoding="utf-8")
    assert "Representative projects" in refreshed
    assert "Selected Projects" not in refreshed
    assert samples.refresh_suggestion_resume_if_stale(stale_dir) is False

    # Old header→summary padding must also force a re-render.
    from jt.render.styles import RESUME_LAYOUT_MARKER

    loose = refreshed.replace(
        ".body { padding: var(--body-pad, 0 14mm 12mm); }",
        ".body { padding: var(--body-pad, 10mm 14mm 14mm); }",
        1,
    ).replace(RESUME_LAYOUT_MARKER, "/* jt-resume-layout:0 */", 1)
    (stale_dir / "resume.html").write_text(loose, encoding="utf-8")
    assert samples.refresh_suggestion_resume_if_stale(stale_dir) is True
    tight = (stale_dir / "resume.html").read_text(encoding="utf-8")
    assert "var(--body-pad, 10mm 14mm 14mm)" not in tight
    assert RESUME_LAYOUT_MARKER in tight
    assert "Representative projects" in tight
    assert "Selected Projects" not in tight

    # Teaching-only contact note must be stripped from downloadable HTML.
    noted = tight.replace(
        "</header>",
        '<p class="contact">Virtual candidate — teaching example</p>\n</header>',
        1,
    )
    (stale_dir / "resume.html").write_text(noted, encoding="utf-8")
    assert samples.refresh_suggestion_resume_if_stale(stale_dir) is True
    cleaned = (stale_dir / "resume.html").read_text(encoding="utf-8")
    assert "Virtual candidate — teaching example" not in cleaned

    # Invalid suggestion.json must still refresh via resume.html parse fallback.
    broken_html = cleaned.replace(RESUME_LAYOUT_MARKER, "/* jt-resume-layout:0 */", 1).replace(
        "Representative projects", "Selected Projects", 1
    )
    (stale_dir / "resume.html").write_text(broken_html, encoding="utf-8")
    json_path = stale_dir / "suggestion.json"
    raw = json.loads(json_path.read_text(encoding="utf-8"))
    raw["teaching_notes"] = (raw.get("teaching_notes") or [])[:1]
    json_path.write_text(json.dumps(raw), encoding="utf-8")
    assert samples.refresh_suggestion_resume_if_stale(stale_dir) is True
    recovered = (stale_dir / "resume.html").read_text(encoding="utf-8")
    assert RESUME_LAYOUT_MARKER in recovered
    assert "Selected Projects" not in recovered
    assert "Representative projects" in recovered

    missing = suggestion.model_copy(deep=True)
    missing.sample.experience[0].company = "Siemens"
    missing.sample.experience[0].title = "Wrong Title"
    missing.sample.experience[1].company = "ABB"
    fixed = samples.guard_suggestion(
        missing, "Jane Example", "Fanuc", title="Financial Specialist")
    assert fixed.persona_name == "Jane Example"
    assert fixed.sample.experience[0].company == "Fanuc"
    assert fixed.sample.experience[0].title == "Financial Specialist"
    assert fixed.last_title == "Financial Specialist"

    aimed, aimed_paths = samples.suggest_sample(
        "Jane Example",
        "Fanuc",
        title="Financial Specialist",
        jd="Need a PE-licensed controls engineer for robot cells. RLHF mathematics python latex.",
    )
    assert aimed.target_kind == "job_description"
    assert aimed.last_title == "Financial Specialist"
    assert aimed_paths["dir"].endswith("jane-example-fanuc-jd")
    assert Path(aimed_paths["alignment_json"]).exists()
    assert Path(aimed_paths["alignment_report"]).exists()
    assert Path(aimed_paths["jd"]).exists()
    align = samples.load_alignment(aimed_paths["dir"])
    assert align is not None
    assert "ats_coverage" in align and "fit_score" in align
    assert align.get("ats_is_local_keyword_coverage") is True
    # Offline FakeBC keywords rarely match a controls teaching model on first pass.
    assert align.get("weave_attempted") is True
    assert any("teaching-model resume aligner" in c for c in FakeBC.calls)
    assert any("senior recruiter and ATS screener" in c for c in FakeBC.calls)
    # Sample suggest prompt is earlier than align/match calls.
    suggest_prompts = [c for c in FakeBC.calls if "domain hiring benchmark writer" in c]
    assert suggest_prompts
    jd_prompt = suggest_prompts[-1]
    assert "Fanuc" in jd_prompt
    assert "PE-licensed" in jd_prompt
    assert "real universities" in jd_prompt
    assert "Career spine" in jd_prompt
    assert "Financial Specialist" in jd_prompt


def test_align_suggestion_dir_rescores_without_weave(env):
    suggestion, paths = samples.suggest_sample("Jane Example", "Fanuc")
    folder = Path(paths["dir"])
    jd = "Need a PE-licensed controls engineer for robot cells. RLHF mathematics python latex."
    _s, align_paths = samples.align_suggestion_dir(folder, jd=jd, weave=False)
    assert Path(align_paths["alignment_json"]).exists()
    payload = samples.load_alignment(folder)
    assert payload is not None
    assert payload.get("weave_attempted") is False
    assert (folder / "jd.txt").read_text(encoding="utf-8").strip() == jd
    # Re-score from cached jd.txt
    _s2, paths2 = samples.align_suggestion_dir(folder, weave=False)
    assert Path(paths2["alignment_report"]).exists()


def test_parse_profile_dump_fills_suggest_fields(env):
    dump = """
Alan Jeong
Vice President Operations | Financial Planning and Analysis
1982.9.X
New York, United States
+1 (669) 223-1191
imalanjeong@gmail.com
https://www.linkedin.com/in/alanjeong/
________________________________________
EDUCATION
Baruch College
Master of Business Administration (MBA), Accounting and Finance
2008 — 2012
________________________________________
PROFESSIONAL EXPERIENCE

Financial Planning and Analysis - BNY
Jun 2022 - Present

Vice President Operations - EnTrust Global
May 2006 - Jun 2022
________________________________________
Companies’ Key Information
BNY is a global financial services platforms company.
EnTrust Global is an alternative investment firm.
""".strip()
    parsed = samples.parse_profile_dump(dump)
    assert parsed["name"] == "Alan Jeong"
    assert parsed["last_company"] == "BNY"
    assert parsed["title"] == "Financial Planning and Analysis"
    seed = parsed["profile_seed"]
    assert seed["location"] == "New York, United States"
    assert seed["email"] == "imalanjeong@gmail.com"
    assert "669" in seed["phone"]
    assert seed["linkedin"].endswith("alanjeong")
    assert seed["experience"][0]["company"] == "BNY"
    assert seed["experience"][1]["company"] == "EnTrust Global"
    assert seed["education"][0]["school"] == "Baruch College"
    assert "Accounting and Finance" in seed["education"][0]["field"]
    assert "BNY is a global" in parsed["notes"]
    assert samples.merge_notes("A", "A", "B") == "A\n\nB"
    merged = samples.merge_profile_seed({"location": "NYC"}, seed)
    assert merged["location"] == "NYC"
    assert merged["email"] == "imalanjeong@gmail.com"


def test_profile_seed_normalizes_and_reaches_prompt(env):
    seed = samples.normalize_profile_seed({
        "location": "  Chicago, IL ",
        "headline": "",
        "about": "Senior automation lead.",
        "email": " jane@example.com ",
        "phone": "+1 (555) 010-2048",
        "linkedin": "https://www.linkedin.com/in/jane-example/",
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
    assert seed["email"] == "jane@example.com"
    assert seed["experience"][0]["bullets"] == ["Line A", "Line B"]
    assert seed["skills"] == ["PLC", "safety PLCs", "robot commissioning"]
    assert len(seed["experience"]) == 1
    assert samples.contact_line_from_seed(seed) == (
        "Chicago, IL | jane@example.com | +1 (555) 010-2048 | "
        "https://www.linkedin.com/in/jane-example/"
    )

    text = samples.format_profile_seed_for_prompt(seed)
    assert "Prior experience: Controls engineer, Siemens" in text
    assert "License: PE, NCEES" in text
    assert "Email: jane@example.com" in text

    suggestion, _ = samples.suggest_sample(
        "Jane Example",
        "Fanuc",
        profile_seed=seed,
        seed_mode="provided",
    )
    prompt = FakeBC.calls[-1]
    assert "SEED MODE: provided facts" in prompt
    assert "PROFILE SEED" in prompt
    assert "fill missing career roles with other real US" not in prompt
    assert "Siemens" in prompt
    assert "Georgia Institute of Technology" in prompt
    assert "safety PLCs" in prompt
    assert "jane@example.com" in suggestion.contact
    assert "jane@example.com" in samples.sample_to_resume(suggestion).contact
    companies = [r.company for r in suggestion.sample.experience]
    assert companies[0] == "Fanuc"
    assert "Siemens" in companies
    assert all(c in {"Fanuc", "Siemens"} for c in companies)
    assert [e.school for e in suggestion.sample.education] == ["Georgia Institute of Technology"]
    assert suggestion.sample.licenses == ["PE, NCEES"]
    assert suggestion.sample.certifications == []
    assert suggestion.sample.projects  # model-generated projects kept
    fanuc = next(r for r in suggestion.sample.experience if r.company == "Fanuc")
    assert fanuc.bullets  # model-generated bullets kept


def test_last_company_mode_ignores_profile_seed(env):
    seed = samples.normalize_profile_seed({
        "experience": [{"company": "Siemens", "title": "Controls engineer"}],
        "education": [{"school": "MIT", "degree": "BSc"}],
    })
    suggestion, _ = samples.suggest_sample(
        "Jane Example",
        "Fanuc",
        profile_seed=seed,
        seed_mode="last_company",
    )
    prompt = FakeBC.calls[-1]
    assert "SEED MODE: provided facts" not in prompt
    assert "PROFILE SEED" not in prompt
    assert "at least 20 years" in prompt
    assert suggestion.sample.experience[0].company == "Fanuc"
    # Invented peers from the fake LLM remain (original mode).
    assert len(suggestion.sample.experience) >= 2


def test_apply_provided_orgs_strips_invented_peers(env):
    suggestion, _ = samples.suggest_sample("Jane Example", "Fanuc")
    seed = {
        "experience": [
            {"company": "Fanuc", "title": "Controls Engineer", "start": "2019", "end": "2024"},
            {"company": "Siemens", "title": "Controls engineer", "start": "2014", "end": "2019"},
        ],
        "education": [{"school": "Georgia Institute of Technology", "degree": "BSc", "field": "EE",
                       "start": "2010", "end": "2014"}],
        "licenses": [{"name": "PE", "issuer": "NCEES"}],
        "certifications": [],
    }
    # Simulate an LLM that invented an extra school + employer after the seed.
    suggestion.sample.experience.append(
        samples.ResumeRole(
            company="Honeywell",
            title="Intern",
            start="2012",
            end="2014",
            bullets=["Invented peer role"],
        )
    )
    suggestion.sample.education.append(
        samples.ResumeEducation(school="a state engineering university", degree="coursework", field="Controls")
    )
    suggestion.sample.certifications = ["Fake Cert, Nowhere"]
    suggestion.sample.benchmarks = {"total_relevant_experience": "20+ years"}
    fixed = samples.apply_provided_orgs(suggestion, seed, "Fanuc")
    assert [r.company for r in fixed.sample.experience] == ["Fanuc", "Siemens"]
    assert [e.school for e in fixed.sample.education] == ["Georgia Institute of Technology"]
    assert fixed.sample.licenses == ["PE, NCEES"]
    assert fixed.sample.certifications == []
    assert "Invented peer role" not in " ".join(b for r in fixed.sample.experience for b in r.bullets)
    assert fixed.sample.benchmarks["total_relevant_experience"] == "14 years"
    assert fixed.sample.projects  # kept from model


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


def test_save_teaching_resume_edit_rewrites_artifacts(env):
    from jt.render.resume import render_html

    suggestion, paths = samples.suggest_sample("Jane Example", "Fanuc")
    folder = Path(paths["dir"])
    resume = samples.sample_to_resume(suggestion)
    resume.summary = "Edited summary for the teaching model."
    resume.experience[0].bullets = ["Edited bullet for Fanuc role"]
    edited_html = render_html(resume)
    out = resume_edit.save_teaching_resume_edit(folder, edited_html)
    assert out["dir"] == str(folder)
    html = Path(out["html"]).read_text(encoding="utf-8")
    assert "Edited summary for the teaching model." in html
    assert "Edited bullet for Fanuc role" in html
    assert "Representative projects" in html
    assert "Selected Projects" not in html
    saved = samples.load_suggestion_dir(folder)
    assert saved.sample.about == "Edited summary for the teaching model."
    assert saved.sample.experience[0].bullets == ["Edited bullet for Fanuc role"]


def test_write_suggestion_artifacts_recovers_from_stale_styles_module(env, monkeypatch):
    """Simulate a long-lived dashboard that still holds a pre-v3 styles module."""
    import importlib

    import jt.render.resume as resume_mod
    import jt.render.styles as styles_mod

    suggestion, _paths = samples.suggest_sample("Jane Example", "Fanuc")

    def _stale_render(r, *, style_id=None, accent_id=None):
        return (
            "<!doctype html><html><head><style>"
            ".body { padding: var(--body-pad, 10mm 14mm 14mm); }"
            "header.top, header.banner { padding: var(--header-pad, 10mm 14mm 8mm); }"
            "</style></head><body>"
            f"<h1>{r.name}</h1>"
            "<section><h2>Selected Projects</h2></section>"
            "</body></html>"
        )

    monkeypatch.setattr(styles_mod, "RESUME_LAYOUT_VERSION", 0)
    monkeypatch.setattr(styles_mod, "render_styled_html", _stale_render)
    monkeypatch.setattr(resume_mod, "render_html", lambda *a, **k: _stale_render(a[0]))

    out = config.OUTPUT_DIR / "suggestions" / "stale-styles-probe"
    paths = samples.write_suggestion_artifacts(suggestion, out=out)
    html = Path(paths["html"]).read_text(encoding="utf-8")
    assert "Selected Projects" not in html
    assert "Representative projects" in html
    assert "jt-resume-layout:3" in html
    assert "var(--body-pad, 10mm 14mm 14mm)" not in html
    importlib.reload(styles_mod)
    importlib.reload(resume_mod)


def test_save_tailored_resume_edit_appends_row(env):
    from jt.render.resume import render_html

    qs = tailor.generate_questions(1)
    tailor.answer_question(qs[1].id, "I ranked about 500 RLHF tasks at Example University.")
    row = tailor.tailor_job(1)
    payload = json.loads(row.resume_json)
    resume = ResumeContent.model_validate(payload["resume"])
    resume.summary = "Manually edited tailored summary."
    if resume.experience:
        resume.experience[0].bullets = ["Manually edited tailored bullet"]
    edited_html = render_html(resume)
    new_row = resume_edit.save_tailored_resume_edit(1, edited_html)
    assert new_row.id != row.id
    assert new_row.job_id == 1
    saved = json.loads(new_row.resume_json)["resume"]
    assert saved["summary"] == "Manually edited tailored summary."
    assert saved["experience"][0]["bullets"] == ["Manually edited tailored bullet"]
    html = Path(new_row.docx_path).with_suffix(".html").read_text(encoding="utf-8")
    assert "Manually edited tailored summary." in html
    latest = tailor.latest_resume(1)
    assert latest is not None and latest.id == new_row.id
