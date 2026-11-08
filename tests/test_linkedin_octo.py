import json

import httpx
import pytest

from jt.browser import octo
from jt.sources.linkedin import extract_job_ids, parse_job_page, search_url

LD = {
    "@context": "https://schema.org", "@type": "JobPosting", "title": "AI Trainer - Physics",
    "hiringOrganization": {"@type": "Organization", "name": "Acme AI"},
    "jobLocation": {"address": {"addressLocality": "Remote", "addressCountry": "US"}},
    "datePosted": "2026-11-01T08:00:00.000Z",
    "description": "<p>Rank physics answers.</p><ul><li>PhD in physics</li><li>RLHF experience</li></ul>" + "x" * 90,
    "baseSalary": {"value": {"minValue": 40, "maxValue": 60, "unitText": "HOUR"}},
}


def test_search_url_filters():
    u = search_url("AI trainer", 2, {"posted_within_seconds": 604800, "remote_only": True})
    assert "keywords=AI+trainer" in u and "start=50" in u and "f_TPR=r604800" in u and "f_WT=2" in u


def test_extract_job_ids_dedupes_and_handles_slugs():
    hrefs = ["https://www.linkedin.com/jobs/view/3912345678/?trk=x",
             "https://www.linkedin.com/jobs/view/ai-trainer-at-acme-3912345679",
             "https://www.linkedin.com/jobs/search/?currentJobId=3912345680&keywords=x",
             "https://www.linkedin.com/jobs/view/3912345678/?other"]
    assert extract_job_ids(hrefs) == ["3912345678", "3912345679", "3912345680"]


def test_parse_job_page_from_json_ld():
    html = f'<html><head><script type="application/ld+json">{json.dumps(LD)}</script></head><body>12 applicants</body></html>'
    j = parse_job_page(html, "111111")
    assert j.title == "AI Trainer - Physics" and j.company == "Acme AI"
    assert j.location == "Remote, US" and j.posted == "2026-11-01"
    assert "- PhD in physics" in j.description and j.pay.startswith("40-60")
    assert j.applicants == "12 applicants" and j.url.endswith("/111111/")


def test_parse_job_page_dom_fallback():
    body = "Rank model answers and write rubrics. " * 8
    html = f"""<html><body>
      <h1>AI Tutor, Math</h1>
      <div class="job-details-jobs-unified-top-card__company-name"><a href="/company/acme">Acme AI</a></div>
      <div class="job-details-jobs-unified-top-card__primary-description-container">Remote · 2 days ago · Over 100 applicants</div>
      <div id="job-details"><p>{body}</p><p>Pay: $45/hour</p></div></body></html>"""
    j = parse_job_page(html, "222222")
    assert j.title == "AI Tutor, Math" and j.company == "Acme AI" and j.location == "Remote"
    assert j.pay == "$45/hour" and "Over 100 applicants" in j.applicants


def test_parse_job_page_returns_none_when_unparseable():
    assert parse_job_page("<html><body>Sign in to view</body></html>", "1") is None


def test_octo_start_profile_builds_cdp_url(monkeypatch):
    seen = {}

    def fake_post(url, json=None, timeout=None):
        seen.update(url=url, body=json)
        return httpx.Response(200, json={"uuid": "u1", "state": "STARTED", "debug_port": "9333",
                                         "ws_endpoint": "ws://127.0.0.1:9333/devtools/browser/abc"})

    monkeypatch.setattr(octo.httpx, "post", fake_post)
    info = octo.start_profile("u1")
    assert seen["url"].endswith("/api/profiles/start") and seen["body"]["debug_port"] is True
    assert octo._cdp_url(info) == "ws://127.0.0.1:9333/devtools/browser/abc"
    assert octo._cdp_url({"debug_port": "9333"}) == "http://127.0.0.1:9333"


def test_octo_errors_are_actionable(monkeypatch):
    def refuse(*a, **k):
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(octo.httpx, "post", refuse)
    with pytest.raises(octo.OctoError, match="Octo Browser running"):
        octo.start_profile("u1")
    monkeypatch.setattr(octo.httpx, "post", lambda *a, **k: httpx.Response(400, json={"msg": "no such profile"}))
    with pytest.raises(octo.OctoError, match="refused to start"):
        octo.start_profile("u1")
