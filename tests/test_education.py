"""Multi-degree ranking, resume selection, and teaching-model education checks."""
from types import SimpleNamespace

import pytest

from jt import config
from jt.analysis.education import (
    degree_rank,
    profile_for_resume,
    required_degree_rank,
    select_education,
)
from jt.llm.client import render_prompt
from jt.pipelines import samples
from jt.schemas import Education, JobRequirements, MasterProfile


def _edu(school: str, degree: str, field: str, end: str = "") -> Education:
    return Education(school=school, degree=degree, field=field, end=end)


def test_degree_rank_orders_common_credentials():
    assert degree_rank("BSc") < degree_rank("MS")
    assert degree_rank("Master's") < degree_rank("PhD")
    assert degree_rank("MBA") == degree_rank("MSc")
    assert degree_rank("JD") >= degree_rank("MS")
    assert degree_rank("postdoc") > degree_rank("PhD")
    assert required_degree_rank("PhD preferred") == degree_rank("PhD")


def test_select_keeps_ladder_drops_unrelated_bachelor():
    education = [
        _edu("State U", "BA", "English", "2008"),
        _edu("State U", "BS", "Computer Science", "2010"),
        _edu("Stanford", "MS", "Computer Science", "2012"),
        _edu("Stanford", "PhD", "Computer Science", "2016"),
        _edu("Wharton", "MBA", "Finance", "2018"),
    ]
    picked = select_education(
        education,
        education_required="PhD in computer science",
        domain="coding",
        keywords=["python", "algorithms", "phd"],
    )
    degrees = {(e.degree, e.field) for e in picked}
    assert ("PhD", "Computer Science") in degrees
    assert ("MS", "Computer Science") in degrees
    assert ("BS", "Computer Science") in degrees
    assert ("BA", "English") not in degrees
    assert ("MBA", "Finance") not in degrees


def test_select_keeps_domain_second_degree():
    education = [
        _edu("MIT", "BS", "Electrical Engineering", "2005"),
        _edu("MIT", "MS", "Electrical Engineering", "2007"),
        _edu("Harvard", "JD", "Law", "2010"),
    ]
    picked = select_education(
        education,
        education_required="JD",
        domain="law",
        keywords=["contract", "compliance", "jd"],
    )
    degrees = {e.degree for e in picked}
    assert "JD" in degrees
    # Engineering ladder is prior path; JD is terminal + domain match.
    assert "MS" in degrees or "BS" in degrees


def test_select_respects_limit_but_keeps_terminal():
    education = [
        _edu("A", "BS", "Math", "2001"),
        _edu("B", "MS", "Math", "2003"),
        _edu("C", "PhD", "Math", "2008"),
        _edu("D", "BA", "History", "2000"),
        _edu("E", "MA", "History", "2002"),
        _edu("F", "MBA", "Business", "2012"),
    ]
    picked = select_education(
        education,
        education_required="PhD",
        domain="math",
        keywords=["mathematics", "proofs"],
        limit=3,
    )
    assert len(picked) <= 3
    assert any(e.degree == "PhD" for e in picked)


def test_profile_for_resume_trims_without_mutating_master():
    profile = MasterProfile(
        education=[
            _edu("U1", "BA", "Art", "2009"),
            _edu("U2", "BS", "Physics", "2011"),
            _edu("U3", "PhD", "Physics", "2017"),
        ]
    )
    req = JobRequirements(
        summary="Physics evaluator",
        domain="physics",
        education_required="PhD in physics",
        keywords=["physics", "quantum"],
    )
    trimmed = profile_for_resume(profile, req)
    assert len(profile.education) == 3
    assert any(e.field == "Art" for e in profile.education)
    assert not any(e.field == "Art" for e in trimmed.education)
    assert any(e.degree == "PhD" for e in trimmed.education)


# --- Education timeline post-check (teaching models) -----------------------

OLD_NATALIE_EDU = [
    ("University of Illinois Urbana-Champaign", "Aug 1994 - May 1998"),
    ("University of Michigan, Ross", "Aug 1998 - May 1999"),
    ("University of Pennsylvania, Wharton", "Aug 1999 - May 2003"),
]
CAREER = [
    ("Nov 2003", "Apr 2010"),
    ("May 2010", "Dec 2018"),
    ("Jan 2019", "Jun 2023"),
    ("Jul 2023", "Present"),
]
THREE_DEGREES = ["Bachelor of Science (BS)", "Master of Accounting (MAcc)", "Doctor of Philosophy (PhD)"]


def test_back_to_back_degree_chain_is_flagged():
    issues = samples.education_timeline_issues(OLD_NATALIE_EDU, CAREER)
    assert issues and "back-to-back" in issues[0]


def test_degree_overlapping_a_role_passes():
    edu = [
        ("University of Illinois Urbana-Champaign", "Aug 1994 - May 1998"),
        ("University of Michigan, Ross", "Sep 2006 - Jun 2008"),
    ]
    assert samples.education_timeline_issues(edu, CAREER) == []


def test_gap_of_six_months_between_degrees_passes():
    edu = [("A", "Aug 1994 - May 1998"), ("B", "Dec 1998 - May 2000")]
    assert samples.education_timeline_issues(edu, []) == []


def test_three_month_gap_with_no_overlap_fails():
    edu = [("A", "Aug 1994 - May 1998"), ("B", "Aug 1998 - May 1999")]
    assert samples.education_timeline_issues(edu, []) != []


def test_single_or_unparseable_degree_is_not_checked():
    assert samples.education_timeline_issues([("A", "Aug 1994 - May 1998")], CAREER) == []
    assert samples.education_timeline_issues([("A", ""), ("B", "")], CAREER) == []


def test_year_only_dates_are_parsed():
    edu = [("A", "2010-2012"), ("B", "2016-2018")]
    assert samples.education_timeline_issues(edu, []) == []


# --- Degree count (bachelor's + master's + doctorate, 3+ entries) ----------


def test_three_degree_ladder_passes_count_check():
    assert samples.education_degree_count_issues(THREE_DEGREES) == []


def test_two_degrees_fail_count_check():
    assert samples.education_degree_count_issues(["Bachelor of Science", "Master of Science"]) != []


def test_missing_doctorate_fails_count_check():
    degrees = ["Bachelor of Arts", "Master of Business Administration", "Master of Science"]
    assert samples.education_degree_count_issues(degrees) != []


def test_blank_degree_entries_do_not_count():
    assert samples.education_degree_count_issues(["BS", "MS", ""]) != []


def _sample(degrees_dates, roles=CAREER):
    return SimpleNamespace(
        education=[SimpleNamespace(school=s, degree=d, dates=dt) for s, d, dt in degrees_dates],
        experience=[SimpleNamespace(start=a, end=b) for a, b in roles],
        benchmarks={},
    )


GOOD_LADDER = [
    ("UIUC", "Bachelor of Science (BS)", "Aug 1994 - May 1998"),
    ("Michigan Ross", "Master of Accounting (MAcc)", "Aug 2010 - Apr 2011"),
    ("Wharton", "Doctor of Philosophy (PhD)", "Aug 1998 - May 2003"),
]
FLAT_LADDER = [
    ("UIUC", "Bachelor of Science (BS)", "Aug 1994 - May 1998"),
    ("Michigan Ross", "Master of Accounting (MAcc)", "Aug 1998 - May 1999"),
    ("Wharton", "Doctor of Philosophy (PhD)", "Aug 1999 - May 2003"),
]


def test_retry_replaces_failing_sample_and_passes():
    flat = _sample(FLAT_LADDER)
    good = _sample(GOOD_LADDER)
    out = samples._apply_education_check(flat, lambda fix: good)
    assert out is good
    assert "education_check" not in out.benchmarks


def test_retry_receives_the_issue_text():
    flat = _sample(FLAT_LADDER)
    seen = []

    def retry(fix):
        seen.append(fix)
        return _sample(GOOD_LADDER)

    samples._apply_education_check(flat, retry)
    assert seen and "back-to-back" in seen[0]


def test_retry_that_still_fails_is_noted_for_coach():
    flat = _sample(FLAT_LADDER)
    out = samples._apply_education_check(flat, lambda fix: _sample(FLAT_LADDER))
    assert "back-to-back" in out.benchmarks["education_check"]


def test_missing_degree_is_noted_even_when_timeline_passes():
    # 6+ month gap between the two degrees, so only the degree count should fail.
    two = _sample(
        [
            ("UIUC", "Bachelor of Science (BS)", "Aug 1994 - May 1998"),
            ("Wharton", "Doctor of Philosophy (PhD)", "Aug 2005 - May 2010"),
        ],
        roles=[],
    )
    assert samples.education_timeline_issues(
        [(e.school, e.dates) for e in two.education], []
    ) == []
    out = samples._apply_education_check(two, lambda fix: two)
    assert "at least three degrees" in out.benchmarks["education_check"]
    assert "back-to-back" not in out.benchmarks["education_check"]


def test_timeline_fix_block_renders_into_samples_prompt():
    prompt = render_prompt(
        "samples",
        archetype={"name": "Finance SME", "description": "d", "roles": []},
        n_jobs=0,
        top_keywords=[],
        top_requirements=[],
        timeline_fix="FIX THE DATES",
    )
    assert "Retry fix" in prompt and "FIX THE DATES" in prompt
    plain = render_prompt(
        "samples",
        archetype={"name": "Finance SME", "description": "d", "roles": []},
        n_jobs=0,
        top_keywords=[],
        top_requirements=[],
    )
    assert "Retry fix" not in plain


# --- Verified program formats ---------------------------------------------


def test_program_formats_config_has_sources_and_formats():
    programs = samples.program_formats()
    assert len(programs) >= 8
    for p in programs:
        assert p["school"] and p["program"] and p["format"] and p["length"]
        assert p["source"].startswith("https://")


def test_program_formats_render_into_prompt():
    prompt = render_prompt(
        "samples",
        archetype={"name": "Finance SME", "description": "d", "roles": []},
        n_jobs=0,
        top_keywords=[],
        top_requirements=[],
        program_formats=samples.program_formats(),
    )
    assert "Verified program formats" in prompt
    assert "Master of Accounting (MAcc)" in prompt
    assert "eight months" in prompt


def test_ross_macc_and_wharton_phd_are_recorded_as_full_time():
    by_program = {p["program"]: p for p in samples.program_formats()}
    assert "full-time" in by_program["Master of Accounting (MAcc)"]["format"]
    assert "full-time" in by_program["PhD in Accounting"]["format"]
    assert "part-time" not in by_program["PhD in Accounting"]["format"].replace("no part-time", "")


# --- Rewritten Natalie teaching model -------------------------------------


def _natalie_suggestion():
    path = config.OUTPUT_DIR / "suggestions" / "natalie-sanders-the-wall-street-journal" / "suggestion.json"
    if not path.exists():
        pytest.skip("local teaching model output not present")
    return samples.load_suggestion_dir(path.parent)


def test_rewritten_natalie_teaching_model_passes_both_checks():
    suggestion = _natalie_suggestion()
    assert samples._sample_education_issues(suggestion.sample) == []


def test_natalie_program_durations_match_verified_formats():
    """Michigan Ross MAcc: eight-month full-time. Wharton PhD: about 4-6 years full-time."""
    suggestion = _natalie_suggestion()
    spans = {}
    for edu in suggestion.sample.education:
        start_s, end_s = samples._parse_education_dates(edu.dates)
        spans[edu.degree] = (
            samples._month_index(start_s, is_end=False),
            samples._month_index(end_s, is_end=True),
        )
    macc_start, macc_end = next(v for k, v in spans.items() if "Accounting (MAcc)" in k)
    phd_start, phd_end = next(v for k, v in spans.items() if "Philosophy" in k)
    assert macc_end - macc_start == 8
    assert 48 <= phd_end - phd_start <= 72
