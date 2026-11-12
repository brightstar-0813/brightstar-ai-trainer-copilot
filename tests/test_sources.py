from datetime import date

from jt.analysis.eligibility import is_us_remote
from jt.analysis.fit import score_fit
from jt.analysis.taxonomy import is_relevant
from jt.collect import store
from jt.db import make_dedupe_key
from jt.schemas import JobRequirements, MasterProfile, Requirement
from jt.sources.ats import parse_ashby, parse_greenhouse, parse_lever
from jt.sources.base import RawJob, clean_pay, find_pay, html_to_text, posted_iso, within_max_age
from jt.sources.mercor import parse_explore_html, parse_listings


def test_us_remote_eligibility():
    assert is_us_remote("Remote", "")
    assert is_us_remote("Remote - United States", "")
    assert is_us_remote("US Remote", "Contract role")
    assert is_us_remote("", "Must be authorized to work in the US. Fully remote.", workplace="remote")
    assert is_us_remote("San Francisco, CA", "Build AI evals.", workplace="remote")
    assert not is_us_remote("San Francisco, CA", "Onsite collaboration required")
    assert not is_us_remote("Remote - India", "")
    assert not is_us_remote("EMEA Remote", "Remote across Europe")
    assert not is_us_remote("Remote", "This role is not available in the US")
    assert not is_us_remote("New York, NY", "", workplace="hybrid")
    assert is_us_remote("New York, NY", "This is a remote role open to US-based candidates.", workplace="hybrid")


def test_posted_iso_and_max_age():
    assert posted_iso("2026-01-02T00:00:00Z") == "2026-01-02"
    assert posted_iso(1700000000000) == "2023-11-14"
    assert within_max_age("2026-11-01", 30, today=date(2026, 11, 12))
    assert not within_max_age("2026-09-01", 30, today=date(2026, 11, 12))
    assert within_max_age("", 30, today=date(2026, 11, 12))  # unknown kept


def test_relevance_strict_titles():
    assert is_relevant("AI Tutor, Applied Math - Temporary", "")
    assert is_relevant("Data Annotation Specialist, Safety", "")
    assert is_relevant("Subject Matter Expert", "")
    assert is_relevant("Generative AI - Generalist", "")
    assert is_relevant("Finance Domain Expert Consultant", "")
    assert is_relevant("Enterprise Sales Expert (AE / Sales Leader)", "")
    assert is_relevant("Backend Engineer Talent Network", "")
    assert not is_relevant("Administrative Generalist", "llm rlhf prompt")
    assert not is_relevant("Global Specialized Domain Expert Recruiter (Contract)", "")
    assert not is_relevant("Systems Generalist, GPT Infrastructure", "llm")
    assert not is_relevant("Software Engineer, LLM Platform", "")
    # strong keyword overrides an exclusion word
    assert is_relevant("Sales Data Annotation Specialist", "")


def test_mercor_parse_listings_and_explore_html():
    listings = [{
        "listingId": "list_AAA_test",
        "title": "Legal Expert for AI Evaluation",
        "description": "Train models. Based in the United States.",
        "status": "active",
        "location": "Remote",
        "workArrangement": "remote",
        "createdAt": "2026-11-01T12:00:00",
        "rateMin": 80,
        "rateMax": 120,
        "payRateFrequency": "hourly",
        "eligibleLocation": ["United States"],
    }]
    [j] = parse_listings(listings)
    assert j.source == "mercor" and j.company == "Mercor"
    assert j.workplace == "remote" and "United States" in j.location
    assert j.pay.startswith("$80") and j.posted == "2026-11-01"
    assert "list_AAA_test" in j.url

    html = (
        '<script id="__NEXT_DATA__" type="application/json">'
        + __import__("json").dumps({
            "props": {"pageProps": {"dehydratedState": {
                "queries": [{"state": {"data": {"listings": listings}}}]
            }}}
        })
        + "</script>"
    )
    assert len(parse_explore_html(html)) == 1
    assert parse_explore_html("<html></html>") == []


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
    data = {"jobs": [{"id": 7, "title": "AI Tutor", "location": {"name": "San Francisco, CA"}, "absolute_url": "u",
                      "content": "&lt;p&gt;Pay: $40/hour&lt;/p&gt;&lt;ul&gt;&lt;li&gt;Python&lt;/li&gt;&lt;/ul&gt;",
                      "first_published": "2026-01-01T00:00:00Z",
                      "updated_at": "2026-01-02T00:00:00Z",
                      "metadata": [{"name": "Location Type", "value": "Remote"}]}]}
    [j] = parse_greenhouse("Acme", data)
    assert j.source == "greenhouse" and j.external_id == "7" and j.location == "San Francisco, CA"
    assert "Python" in j.description and "<" not in j.description
    assert j.pay == "$40/hour" and j.posted == "2026-01-01" and j.workplace == "remote"


def test_lever_and_ashby_parsers():
    [l] = parse_lever("Acme", [{"id": "a1", "text": "AI Trainer", "categories": {"location": "Remote"},
                                "hostedUrl": "u", "descriptionPlain": "Rate $35 per hour", "createdAt": 1700000000000}])
    assert l.title == "AI Trainer" and l.pay and l.posted == "2023-11-14"
    [a] = parse_ashby("Acme", {"jobs": [{"id": "z", "title": "AI Tutor", "location": "Remote", "jobUrl": "u",
                                        "descriptionPlain": "x", "publishedAt": "2026-10-01T12:00:00Z",
                                        "compensation": {"compensationTierSummary": "$30 • Equity"}}]})
    assert a.pay == "$30" and a.posted == "2026-10-01"
    assert parse_ashby("Acme", {"jobs": [{"id": "h", "title": "Hidden", "isListed": False}]}) == []


def test_store_drops_stale_keeps_recent(tmp_path, monkeypatch):
    from jt import config as cfg
    from jt import db as jdb

    monkeypatch.setattr(cfg, "DB_PATH", tmp_path / "jobs.db")
    monkeypatch.setattr(cfg, "DATA_DIR", tmp_path)
    monkeypatch.setattr(jdb, "_engine", None)
    cfg.ensure_dirs()
    recent = RawJob(
        source="x", external_id="1", title="AI Tutor, Math", company="Acme",
        location="Remote - United States", description="RLHF", posted=date.today().isoformat(),
    )
    old = RawJob(
        source="x", external_id="2", title="AI Tutor, Physics", company="Acme",
        location="Remote - United States", description="RLHF", posted="2020-01-01",
    )
    st = store([recent, old], max_age_days=30)
    assert st.new == 1 and st.too_old == 1


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
