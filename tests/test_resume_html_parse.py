"""Round-trip styled resume HTML ↔ ResumeContent."""
from __future__ import annotations

import pytest

from jt.render.html_parse import ResumeHtmlParseError, parse_resume_html
from jt.render.styles import render_styled_html
from jt.schemas import (
    ResumeContent,
    ResumeEducation,
    ResumeProject,
    ResumeRole,
    SkillGroup,
)


def _sample() -> ResumeContent:
    return ResumeContent(
        name="Ada Example",
        headline="Senior Controls Engineer",
        contact="Austin, TX | ada@example.com | +1 555 0100",
        summary="Controls engineer with plant commissioning experience.",
        skills=["PLC", "Safety PLCs", "Robot commissioning"],
        skill_groups=[
            SkillGroup(category="Controls", items=["PLC", "Safety PLCs"]),
            SkillGroup(category="Delivery", items=["Robot commissioning"]),
        ],
        experience=[
            ResumeRole(
                company="Fanuc",
                title="Senior Controls Engineer",
                start="2019",
                end="Present",
                location="Austin, TX",
                bullets=["Commissioned 12 robot cells", "Wrote PLC standards"],
            ),
            ResumeRole(
                company="Siemens",
                title="Controls Engineer",
                start="2014",
                end="2019",
                bullets=["Supported 4 lines"],
            ),
        ],
        education=[
            ResumeEducation(
                school="Georgia Tech",
                degree="BSc",
                field="EE",
                dates="2010-2014",
                details=["Senior design: motion cell"],
            )
        ],
        licenses=["PE, NCEES"],
        certifications=["Professional Engineer (PE)"],
        projects=[
            ResumeProject(
                name="Cell retrofit",
                description="Lockout design on 12 cells.",
                link="https://example.com/cell",
            )
        ],
        additional=["English — native"],
    )


def test_round_trip_preserves_core_fields():
    original = _sample()
    html = render_styled_html(original, style_id="ats-modern")
    assert "Selected Projects" not in html
    assert "Representative projects" in html
    parsed = parse_resume_html(html)
    assert parsed.name == original.name
    assert parsed.headline == original.headline
    assert parsed.contact == original.contact
    assert parsed.summary == original.summary
    assert len(parsed.experience) == 2
    assert parsed.experience[0].company == "Fanuc"
    assert parsed.experience[0].title == "Senior Controls Engineer"
    assert parsed.experience[0].start == "2019"
    assert parsed.experience[0].end == "Present"
    assert parsed.experience[0].location == "Austin, TX"
    assert "Commissioned 12 robot cells" in parsed.experience[0].bullets
    assert parsed.projects[0].name == "Cell retrofit"
    assert "Lockout design" in parsed.projects[0].description
    assert parsed.projects[0].link == "https://example.com/cell"
    assert parsed.education[0].school == "Georgia Tech"
    assert parsed.education[0].degree == "BSc"
    assert parsed.education[0].field == "EE"
    assert parsed.licenses == ["PE, NCEES"]
    assert parsed.certifications == ["Professional Engineer (PE)"]
    assert parsed.additional == ["English — native"]
    assert {g.category for g in parsed.skill_groups} >= {"Controls", "Delivery"}
    assert "Selected Projects" not in render_styled_html(parsed)


def test_accepts_legacy_selected_projects_heading():
    html = render_styled_html(_sample())
    html = html.replace("Representative projects", "Selected Projects")
    parsed = parse_resume_html(html)
    assert parsed.projects[0].name == "Cell retrofit"


def test_missing_experience_raises():
    html = render_styled_html(_sample())
    html = html.split("<section><h2>Professional Experience</h2>")[0] + "</div></body></html>"
    with pytest.raises(ResumeHtmlParseError):
        parse_resume_html(html)


def test_empty_html_raises():
    with pytest.raises(ResumeHtmlParseError):
        parse_resume_html("  ")
