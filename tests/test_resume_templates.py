"""Style-only resume themes (fixed teaching structure)."""
from __future__ import annotations

from jt.render.styles import list_styles, render_styled_html, resolve_style_id
from jt.render.template_data import parse_contact_line, resume_to_template_data
from jt.schemas import ResumeContent, ResumeEducation, ResumeProject, ResumeRole


def _sample_resume() -> ResumeContent:
    return ResumeContent(
        name="Ada Example",
        headline="Senior Controls Engineer",
        contact="Austin, TX | ada@example.com | +1 555 0100",
        summary="Controls engineer with plant commissioning experience.",
        skills=["PLC", "Safety PLCs", "Robot commissioning"],
        experience=[
            ResumeRole(
                company="Fanuc",
                title="Senior Controls Engineer",
                start="2019",
                end="Present",
                location="Austin, TX",
                bullets=["Commissioned 12 robot cells"],
            )
        ],
        education=[ResumeEducation(school="Georgia Tech", degree="BSc", field="EE", dates="2010-2014")],
        certifications=["Professional Engineer (PE)"],
        projects=[ResumeProject(name="Cell retrofit", description="Lockout design on 12 cells.")],
    )


def test_parse_contact_line():
    parts = parse_contact_line("Austin, TX | ada@example.com | +1-555-0100 | https://linkedin.com/in/ada")
    assert parts["location"] == "Austin, TX"
    assert parts["email"] == "ada@example.com"
    assert "555" in parts["phone"]
    assert "linkedin.com" in parts["linkedin"]


def test_resume_to_template_data_shape():
    data = resume_to_template_data(_sample_resume())
    assert data["name"] == "Ada Example"
    assert data["profile"].startswith("Controls")
    assert data["skills"][0]["category"] == "Core Competencies"


def test_list_styles_includes_ats_modern():
    catalog = list_styles()
    ids = {t["id"] for t in catalog["templates"]}
    assert "ats-modern" in ids
    assert resolve_style_id("nope") == "ats-modern"


def test_styled_html_keeps_teaching_structure():
    html = render_styled_html(_sample_resume(), style_id="nyc-finance")
    assert "Ada Example" in html
    assert "Professional Summary" in html
    assert "<h2>Skills</h2>" in html
    assert "skill-cat" in html
    assert "Professional Experience" in html
    assert "Representative projects" in html
    assert "Education" in html
    assert "Certifications" in html
    assert ">Profile<" not in html
    assert "data-style=\"nyc-finance\"" in html
    assert "banner" in html
    assert 'class="role">Senior Controls Engineer</span>' in html
    assert 'class="company">Fanuc</div>' in html
    assert "Senior Controls Engineer, Fanuc" not in html
    assert "text-align: justify" in html
    assert "header.top" in html and "border-bottom: none" in html


def test_style_swap_does_not_change_sections():
    a = render_styled_html(_sample_resume(), style_id="ats-modern")
    b = render_styled_html(_sample_resume(), style_id="executive-navy")
    for label in (
        "Professional Summary",
        "Skills",
        "Professional Experience",
        "Representative projects",
        "Education",
        "Certifications",
    ):
        assert f"<h2>{label}</h2>" in a
        assert f"<h2>{label}</h2>" in b


def test_flat_skills_are_bucketed_into_categories():
    from jt.render.skills import group_flat_skills

    groups = group_flat_skills(
        [
            "Private Wealth Management",
            "Portfolio Construction",
            "Bloomberg Terminal",
            "Fiduciary Oversight",
            "Private Equity",
        ]
    )
    cats = {g.category for g in groups}
    assert "Client & Wealth Advisory" in cats or "Investment Strategy" in cats
    assert any("Bloomberg" in " ".join(g.items) for g in groups)
