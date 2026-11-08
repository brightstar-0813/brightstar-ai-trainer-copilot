"""Public ATS job-board APIs: Greenhouse, Lever, Ashby (no login needed)."""
from __future__ import annotations

import json
from typing import Iterable

import httpx

from .. import config
from .base import RawJob, clean_pay, find_pay, html_to_text

VERIFIED_PATH = config.DATA_DIR / "verified_boards.json"


def _client() -> httpx.Client:
    http = config.load_yaml("sources.yaml").get("http", {})
    return httpx.Client(timeout=http.get("timeout_seconds", 25), follow_redirects=True,
                        headers={"User-Agent": http.get("user_agent", "Mozilla/5.0")})


# ---------------------------------------------------------------- parsers (pure, unit-tested)
def parse_greenhouse(company: str, data: dict) -> list[RawJob]:
    out = []
    for j in data.get("jobs", []):
        desc = html_to_text(j.get("content", ""))
        out.append(RawJob(
            source="greenhouse", external_id=str(j["id"]), title=j.get("title", ""), company=company,
            location=(j.get("location") or {}).get("name", ""), url=j.get("absolute_url", ""),
            description=desc, posted=(j.get("updated_at") or "")[:10], pay=find_pay(desc)))
    return out


def parse_lever(company: str, data: list) -> list[RawJob]:
    out = []
    for j in data:
        desc = j.get("descriptionPlain") or html_to_text(j.get("description", ""))
        for lst in j.get("lists", []) or []:
            desc += f"\n\n{lst.get('text', '')}\n" + html_to_text(lst.get("content", ""))
        desc += "\n\n" + (j.get("additionalPlain") or "")
        sal = j.get("salaryRange") or {}
        pay = f"{sal.get('min')}-{sal.get('max')} {sal.get('currency', '')} {sal.get('interval', '')}".strip() if sal else find_pay(desc)
        out.append(RawJob(
            source="lever", external_id=str(j["id"]), title=j.get("text", ""), company=company,
            location=(j.get("categories") or {}).get("location", "") or "", url=j.get("hostedUrl", ""),
            description=desc.strip(), posted=str(j.get("createdAt", ""))[:10], pay=pay))
    return out


def parse_ashby(company: str, data: dict) -> list[RawJob]:
    out = []
    for j in data.get("jobs", []):
        if j.get("isListed") is False:
            continue
        desc = j.get("descriptionPlain") or html_to_text(j.get("descriptionHtml", ""))
        comp = (j.get("compensation") or {}).get("compensationTierSummary", "")
        out.append(RawJob(
            source="ashby", external_id=str(j["id"]), title=j.get("title", ""), company=company,
            location=j.get("location", "") or "", url=j.get("jobUrl", ""), description=desc,
            posted=(j.get("publishedAt") or "")[:10], pay=clean_pay(comp) or find_pay(desc)))
    return out


# ---------------------------------------------------------------- fetchers
ENDPOINTS = {
    "greenhouse": ("https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true", parse_greenhouse),
    "lever": ("https://api.lever.co/v0/postings/{slug}?mode=json", parse_lever),
    "ashby": ("https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true", parse_ashby),
}


def fetch_board(client: httpx.Client, ats: str, slug: str, company: str) -> list[RawJob] | None:
    """Return jobs, or None if this slug does not exist on that ATS."""
    url, parser = ENDPOINTS[ats]
    try:
        r = client.get(url.format(slug=slug))
    except httpx.HTTPError:
        return None
    if r.status_code != 200:
        return None
    try:
        return parser(company, r.json())
    except (ValueError, KeyError, TypeError):
        return None


def discover() -> list[dict]:
    """Probe every company slug against each ATS; cache hits in data/verified_boards.json."""
    cfg = config.load_yaml("sources.yaml")
    found: list[dict] = []
    with _client() as client:
        for c in cfg.get("companies", []):
            hit = None
            for slug in c["slugs"]:
                for ats in ENDPOINTS:
                    jobs = fetch_board(client, ats, slug, c["name"])
                    if jobs is not None:
                        hit = {"company": c["name"], "ats": ats, "slug": slug, "open_jobs": len(jobs)}
                        break
                if hit:
                    break
            found.append(hit or {"company": c["name"], "ats": None, "slug": None, "open_jobs": 0})
    config.ensure_dirs()
    VERIFIED_PATH.write_text(json.dumps(found, indent=2), encoding="utf-8")
    return found


def verified_boards() -> list[dict]:
    if not VERIFIED_PATH.exists():
        return []
    return [b for b in json.loads(VERIFIED_PATH.read_text(encoding="utf-8")) if b.get("ats")]


def collect_all() -> Iterable[RawJob]:
    boards = verified_boards()
    with _client() as client:
        for b in boards:
            jobs = fetch_board(client, b["ats"], b["slug"], b["company"]) or []
            yield from jobs
