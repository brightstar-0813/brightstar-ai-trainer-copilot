"""Multi-degree ranking, resume selection, and teaching-model education checks."""
from datetime import date
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


# --- Age and years-of-experience cap ----------------------------------------

TODAY = date(2026, 11, 18)


def test_earliest_year_for_age_45_is_1999():
    assert samples.earliest_year_for_age(45, today=TODAY) == 1999
    assert samples.candidate_birth_year(45, today=TODAY) == 1981


def test_years_experience_caps_at_27_for_age_45():
    assert samples.MAX_YEARS_EXPERIENCE == 27
    assert samples.normalize_years_experience(99) == 27
    assert samples.normalize_years_experience(3) == 5
    assert samples.normalize_years_experience("bad") == 20


# --- Anchored education timeline -------------------------------------------

CAREER = [
    ("Jun 2002", "Nov 2004"),
    ("Dec 2004", "Aug 2013"),
    ("Sep 2013", "Feb 2018"),
    ("Mar 2018", "Dec 2021"),
    ("Jan 2022", "Present"),
]
THREE_DEGREES = [
    "Bachelor of Science (BS)",
    "Master of Accounting (MAcc)",
    "Doctor of Philosophy (PhD)",
]


def test_back_to_back_degrees_with_no_job_are_flagged():
    # Degrees after the career ends, so no part-time overlap can save them.
    edu = [
        ("UIUC", "Aug 1999 - May 2003"),
        ("Michigan Ross", "Aug 2003 - Apr 2004"),
        ("Wharton", "Aug 2004 - May 2009"),
    ]
    issues = samples.education_timeline_issues(edu, [], age=45, today=TODAY)
    assert any("back to back" in i for i in issues)


def test_empty_gap_between_degrees_is_flagged():
    """An empty 15-month stretch between degrees is not a valid anchor."""
    edu = [
        ("UIUC", "Aug 1999 - May 2003"),
        ("Michigan Ross", "Aug 2004 - Apr 2005"),
    ]
    issues = samples.education_timeline_issues(edu, [], age=45, today=TODAY)
    assert any("back to back" in i or "unlisted" in i for i in issues)


def test_job_between_degrees_passes():
    edu = [
        ("UIUC", "Aug 1999 - May 2003"),
        ("Wharton", "Sep 2005 - May 2010"),
    ]
    roles = [("Jun 2003", "Aug 2005"), ("Jun 2010", "Present")]
    assert samples.education_timeline_issues(edu, roles, age=45, today=TODAY) == []


def test_part_time_overlap_passes():
    edu = [
        ("UIUC", "Aug 1999 - May 2003"),
        ("Booth Evening MBA", "Sep 2008 - Jun 2011"),
    ]
    roles = [("Jun 2003", "Present")]
    assert samples.education_timeline_issues(edu, roles, age=45, today=TODAY) == []


def test_degree_before_age_18_is_flagged():
    edu = [("UIUC", "Aug 1994 - May 1998")]
    issues = samples.education_timeline_issues(edu, [], age=45, today=TODAY)
    assert any("before age 18" in i for i in issues)


def test_unlisted_stretch_over_12_months_is_flagged():
    edu = [("UIUC", "Aug 1999 - May 2003")]
    roles = [("Jun 2005", "Present")]  # 25 months empty after BS
    issues = samples.education_timeline_issues(edu, roles, age=45, today=TODAY)
    assert any("unlisted" in i for i in issues)


def test_single_or_unparseable_degree_skips_pair_rules():
    assert samples.education_timeline_issues(
        [("A", "Aug 1999 - May 2003")], [("Jun 2003", "Present")], age=45, today=TODAY
    ) == []
    assert samples.education_timeline_issues([("A", ""), ("B", "")], [], age=45, today=TODAY) == []


# --- Degree count ----------------------------------------------------------


def test_three_degree_ladder_passes_count_check():
    assert samples.education_degree_count_issues(THREE_DEGREES) == []


def test_two_degrees_fail_count_check():
    assert samples.education_degree_count_issues(["Bachelor of Science", "Master of Science"]) != []


def test_missing_doctorate_fails_count_check():
    degrees = ["Bachelor of Arts", "Master of Business Administration", "Master of Science"]
    assert samples.education_degree_count_issues(degrees) != []


def test_blank_degree_entries_do_not_count():
    assert samples.education_degree_count_issues(["BS", "MS", ""]) != []


def _sample(degrees_dates, roles=None):
    role_list = CAREER if roles is None else roles
    return SimpleNamespace(
        education=[
            SimpleNamespace(school=s, degree=d, field="", dates=dt, details=[])
            for s, d, dt in degrees_dates
        ],
        experience=[
            SimpleNamespace(title=f"Role {i}", company="Co", start=a, end=b, bullets=[])
            for i, (a, b) in enumerate(role_list, start=1)
        ],
        benchmarks={},
    )


GOOD_LADDER = [
    ("UIUC", "Bachelor of Science (BS)", "Aug 1999 - May 2003"),
    ("Wharton", "Doctor of Philosophy (PhD)", "Sep 2005 - May 2010"),
    ("Booth", "Master of Business Administration (MBA), part-time evening", "Sep 2012 - Jun 2015"),
]
GOOD_ROLES = [
    ("Jun 2010", "Present"),
    ("Jun 2003", "Aug 2005"),
]


def test_retry_replaces_failing_sample_and_passes():
    flat = _sample(
        [
            ("UIUC", "Bachelor of Science (BS)", "Aug 1999 - May 2003"),
            ("Ross", "Master of Accounting (MAcc)", "Aug 2003 - Apr 2004"),
            ("Wharton", "Doctor of Philosophy (PhD)", "Aug 2004 - May 2009"),
        ],
        roles=GOOD_ROLES,
    )
    good = _sample(GOOD_LADDER, roles=GOOD_ROLES)
    # Force the age-aware check by patching _sample_education_issues via the real path.
    out = samples._apply_education_check(flat, lambda fix: good)
    assert out is good
    assert "education_check" not in out.benchmarks


def test_retry_that_still_fails_is_noted_for_coach():
    # Consecutive degrees with no roles at all — fails both back-to-back and unlisted rules.
    flat = _sample(
        [
            ("UIUC", "Bachelor of Science (BS)", "Aug 1999 - May 2003"),
            ("Ross", "Master of Accounting (MAcc)", "Aug 2003 - Apr 2004"),
            ("Wharton", "Doctor of Philosophy (PhD)", "Aug 2004 - May 2009"),
        ],
        roles=[],
    )
    out = samples._apply_education_check(flat, lambda fix: flat)
    assert "education_check" in out.benchmarks
    assert "back to back" in out.benchmarks["education_check"]


def test_missing_degree_is_noted_even_when_timeline_passes():
    two = _sample(
        [
            ("UIUC", "Bachelor of Science (BS)", "Aug 1999 - May 2003"),
            ("Wharton", "Doctor of Philosophy (PhD)", "Sep 2005 - May 2010"),
        ],
        roles=GOOD_ROLES,
    )
    assert samples.education_timeline_issues(
        [(e.school, e.dates) for e in two.education],
        GOOD_ROLES,
        age=45,
        today=TODAY,
    ) == []
    out = samples._apply_education_check(two, lambda fix: two)
    assert "at least three degrees" in out.benchmarks["education_check"]
    assert "back to back" not in out.benchmarks["education_check"]


def test_timeline_fix_block_renders_into_samples_prompt():
    prompt = render_prompt(
        "samples",
        archetype={"name": "Finance SME", "description": "d", "roles": []},
        n_jobs=0,
        top_keywords=[],
        top_requirements=[],
        candidate_age=45,
        earliest_year=1999,
        timeline_fix="FIX THE DATES",
    )
    assert "Retry fix" in prompt and "FIX THE DATES" in prompt
    assert "about 45 years old" in prompt or "45" in prompt
    plain = render_prompt(
        "samples",
        archetype={"name": "Finance SME", "description": "d", "roles": []},
        n_jobs=0,
        top_keywords=[],
        top_requirements=[],
        candidate_age=45,
        earliest_year=1999,
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
        candidate_age=45,
        earliest_year=1999,
        program_formats=samples.program_formats(),
    )
    assert "Verified program formats" in prompt
    assert "Master of Accounting (MAcc)" in prompt
    assert "eight months" in prompt


def test_ross_macc_and_wharton_phd_are_recorded_as_full_time():
    by_program = {p["program"]: p for p in samples.program_formats()}
    assert "full-time" in by_program["Master of Accounting (MAcc)"]["format"]
    assert "full-time" in by_program["PhD in Accounting"]["format"]


# --- Saved teaching models -------------------------------------------------


def test_all_saved_teaching_models_report_via_audit_helper():
    """Smoke: the audit helper returns a dict keyed by folder name."""
    report = samples.audit_teaching_model_education()
    assert isinstance(report, dict)


# --- Career chronology and factual tool dates ------------------------------

def test_roles_must_be_listed_newest_first():
    roles = [("Old role", "Jun 2003", "Jul 2006", []), ("New role", "Aug 2006", "Jul 2008", [])]
    issues = samples.career_timeline_issues(roles, [], today=TODAY)
    assert any("newest first" in i for i in issues)


def test_overlapping_full_time_jobs_are_flagged():
    roles = [("Job A", "Jan 2015", "Dec 2019", []), ("Job B", "Jun 2017", "Present", [])]
    issues = samples.career_timeline_issues(roles, [], today=TODAY)
    assert any("overlap" in i for i in issues)


def test_full_time_degree_overlapping_job_is_flagged():
    roles = [("Analyst at Acme", "Jan 2012", "Dec 2016", [])]
    edu = [("Wharton", "Aug 2010 – May 2015", "PhD in Accounting, full-time residential")]
    issues = samples.career_timeline_issues(roles, edu, today=TODAY)
    assert any("full-time but overlaps" in i for i in issues)


def test_part_time_degree_overlapping_job_passes():
    roles = [("Audit Manager at Deloitte", "Aug 2006", "Jul 2008", [])]
    edu = [("Booth", "Sep 2005 – Jun 2008", "MBA, Evening part-time format")]
    issues = samples.career_timeline_issues(roles, edu, today=TODAY)
    assert not any("full-time" in i for i in issues)


def test_role_citing_standard_before_it_existed_is_flagged():
    roles = [(
        "Audit Manager at Deloitte", "Aug 2006", "Jul 2008",
        ["Applied ASC 606 and ASC 842 to client revenue and leases", "Built Power BI dashboards"],
    )]
    issues = samples.career_timeline_issues(roles, [], today=TODAY)
    assert any("ASC 606" in i and "2014" in i for i in issues)
    assert any("ASC 842" in i for i in issues)
    assert any("Power BI" in i for i in issues)


def test_asc_codification_before_2009_is_flagged():
    roles = [("Senior Associate at Deloitte", "Jun 2003", "Jul 2006", ["Tested ASC 360 fixed-asset balances"])]
    issues = samples.career_timeline_issues(roles, [], today=TODAY)
    assert any("ASC 360" in i and "2009" in i for i in issues)


def test_tool_inside_its_launch_year_passes():
    roles = [("Director at GE", "Jun 2015", "Oct 2023", ["Ran scenario models in Anaplan and Power BI"])]
    assert samples.career_timeline_issues(roles, [], today=TODAY) == []


def test_pasted_career_history_flags_order_and_anachronisms():
    roles = [
        ("Director of Finance & Accounting at The Wall Street Journal", "Nov 2023", "Present",
         ["Led ASC 606 revenue recognition across subscription and advertising",
          "Automated reporting in Power BI and Workday Adaptive Planning"]),
        ("Audit Manager at Deloitte", "Aug 2006", "Jul 2008",
         ["Led technical reviews covering ASC 606 revenue recognition and ASC 842 lease accounting"]),
        ("Senior Audit Associate at Deloitte", "Jun 2003", "Jul 2006",
         ["Tested cash and accounts receivable balances"]),
        ("Finance Manager at JPMorgan Chase", "Aug 2008", "Jul 2010",
         ["Supported planning in Hyperion Planning and Essbase"]),
        ("Finance Director at General Electric", "Jun 2015", "Oct 2023",
         ["Ran scenario models in Anaplan and Power BI"]),
    ]
    education = [
        ("University of Illinois Urbana-Champaign", "Aug 1999 – May 2003",
         "Bachelor of Science, Accountancy, full-time on campus"),
        ("University of Chicago Booth School of Business", "Sep 2005 – Jun 2008",
         "MBA, Evening part-time format"),
        ("University of Pennsylvania, The Wharton School", "Aug 2010 – May 2015",
         "PhD Accounting, full-time residential"),
    ]
    text_out = " | ".join(samples.career_timeline_issues(roles, education, today=TODAY))
    assert "newest first" in text_out
    assert "ASC 606" in text_out and "ASC 842" in text_out
    assert "Booth" not in text_out
    assert "Wharton" not in text_out


def test_chronology_rule_and_tool_years_render_into_samples_prompt():
    prompt = render_prompt(
        "samples",
        archetype={"name": "Finance SME", "description": "d", "roles": []},
        n_jobs=0,
        top_keywords=[],
        top_requirements=[],
        candidate_age=45,
        earliest_year=1999,
        tool_launch_years=samples.TOOL_LAUNCH_YEARS,
    )
    assert "newest first" in prompt
    assert "Power BI 2015" in prompt and "ASC 842 2016" in prompt
