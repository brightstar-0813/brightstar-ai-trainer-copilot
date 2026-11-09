"""Multi-degree ranking and resume selection."""
from jt.analysis.education import (
    degree_rank,
    profile_for_resume,
    required_degree_rank,
    select_education,
)
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
