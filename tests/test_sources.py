from jt.analysis.fit import score_fit
from jt.analysis.taxonomy import is_relevant
from jt.db import make_dedupe_key
from jt.schemas import JobRequirements, MasterProfile, Requirement
from jt.sources.ats import parse_ashby, parse_greenhouse, parse_lever
from jt.sources.base import clean_pay, find_pay, html_to_text


def test_relevance_strict_titles():
    assert is_relevant("AI Tutor, Applied Math - Temporary", "")
    assert is_relevant("Data Annotation Specialist, Safety", "")
    assert is_relevant("Subject Matter Expert", "")
    assert is_relevant("Generative AI - Generalist", "")
    assert not is_relevant("Administrative Generalist", "llm rlhf prompt")
    assert not is_relevant("Global Specialized Domain Expert Recruiter (Contract)", "")
    assert not is_relevant("Systems Generalist, GPT Infrastructure", "llm")
    assert not is_relevant("Software Engineer, LLM Platform", "")
    # strong keyword overrides an exclusion word
    assert is_relevant("Sales Data Annotation Specialist", "")


def test_relevance_relaxed_uses_body():
    body = "You will do RLHF and evaluate model responses for our LLM."
    assert not is_relevant("Freelance Specialist", body, strict=True)
    assert is_relevant("Freelance Specialist", body, strict=False)


def test_pay_extraction():
    assert find_pay("Compensation: $45/hour for this role") == "$45/hour"
    assert find_pay("Pay rate $30 - $50 per hour depending on skills") == "$30 - $50 per hour"
    assert find_pay("We love llamas") == ""
    assert clean_pay("$198K – $320K • Offers Equity") == "$198K – $320K"


def test_greenhouse_parser_unescapes_html():
    data = {"jobs": [{"id": 7, "title": "AI Tutor", "location": {"name": "Remote"}, "absolute_url": "u",
                      "content": "&lt;p&gt;Pay: $40/hour&lt;/p&gt;&lt;ul&gt;&lt;li&gt;Python&lt;/li&gt;&lt;/ul&gt;",
                      "updated_at": "2026-01-02T00:00:00Z"}]}
    [j] = parse_greenhouse("Acme", data)
    assert j.source == "greenhouse" and j.external_id == "7" and j.location == "Remote"
    assert "Python" in j.description and "<" not in j.description
    assert j.pay == "$40/hour" and j.posted == "2026-01-02"


def test_lever_and_ashby_parsers():
    [l] = parse_lever("Acme", [{"id": "a1", "text": "AI Trainer", "categories": {"location": "Remote"},
                                "hostedUrl": "u", "descriptionPlain": "Rate $35 per hour", "createdAt": 1700000000000}])
    assert l.title == "AI Trainer" and l.pay
    [a] = parse_ashby("Acme", {"jobs": [{"id": "z", "title": "AI Tutor", "location": "Remote", "jobUrl": "u",
                                        "descriptionPlain": "x", "compensation": {"compensationTierSummary": "$30 • Equity"}}]})
    assert a.pay == "$30"
    assert parse_ashby("Acme", {"jobs": [{"id": "h", "title": "Hidden", "isListed": False}]}) == []


def test_dedupe_key_normalizes():
    assert make_dedupe_key("Scale AI", "AI Tutor – Math") == make_dedupe_key("scale  ai", "ai tutor math")


def test_html_to_text_lists():
    t = html_to_text("<p>Hello</p><ul><li>One</li><li>Two</li></ul>")
    assert "- One" in t and "- Two" in t


def test_fit_scoring_and_gaps():
    profile = MasterProfile.model_validate({
        "domains": ["math"], "coding": ["python"],
        "experience": [{"company": "X", "title": "Tutor", "bullets": ["Tutored calculus; ranked model answers (RLHF)"]}],
        "education": [{"school": "MIT", "degree": "MS", "field": "Mathematics"}]})
    req = JobRequirements(
        summary="s", domain="math",
        must_haves=[Requirement(text="Master's in math", keywords=["mathematics", "ms"]),
                    Requirement(text="Law degree", keywords=["juris doctor"])],
        keywords=["rlhf", "python", "kubernetes"])
    score, gaps = score_fit(req, profile)
    assert 40 < score < 90
    kinds = {(g.kind, g.requirement) for g in gaps}
    assert ("must", "Law degree") in kinds
    assert any(g.kind == "keyword" and "kubernetes" in g.keywords for g in gaps)
