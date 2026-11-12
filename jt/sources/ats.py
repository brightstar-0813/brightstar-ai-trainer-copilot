"""Public ATS job-board APIs: Greenhouse, Lever, Ashby (no login needed)."""
from __future__ import annotations

import json
from typing import Iterable

import httpx

from .. import config
from .base import RawJob, clean_pay, find_pay, html_to_text, posted_iso

VERIFIED_PATH = config.DATA_DIR / "verified_boards.json"


def _client() -> httpx.Client:
    http = config.load_yaml("sources.yaml").get("http", {})
    return httpx.Client(timeout=http.get("timeout_seconds", 25), follow_redirects=True,
                        headers={"User-Agent": http.get("user_agent", "Mozilla/5.0")})


# ---------------------------------------------------------------- parsers (pure, unit-tested)
def _workplace_from_ashby(j: dict) -> str:
    if j.get("isRemote") is True:
        return "remote"
    wt = (j.get("workplaceType") or j.get("employmentType") or "").strip().lower()
    if "remote" in wt:
        return "remote"
    if "hybrid" in wt:
        return "hybrid"
    if "onsite" in wt or "on-site" in wt or "office" in wt:
        return "onsite"
    return wt


def _workplace_from_greenhouse(j: dict, loc: str) -> str:
    for m in j.get("metadata") or []:
        if str(m.get("name", "")).lower() in {"location type", "workplace type", "workplace"}:
            val = str(m.get("value") or "").strip().lower()
            if "remote" in val:
                return "remote"
            if "hybrid" in val:
                return "hybrid"
            if "on-site" in val or "onsite" in val or "office" in val:
                return "onsite"
    return "remote" if "remote" in loc.lower() else ""


def parse_greenhouse(company: str, data: dict) -> list[RawJob]:
    out = []
    for j in data.get("jobs", []):
        desc = html_to_text(j.get("content", ""))
        loc = (j.get("location") or {}).get("name", "")
        # Prefer first_published for recency; updated_at churns on edits.
        posted = posted_iso(j.get("first_published") or j.get("updated_at") or j.get("created_at"))
        out.append(RawJob(
            source="greenhouse", external_id=str(j["id"]), title=j.get("title", ""), company=company,
            location=loc, url=j.get("absolute_url", ""),
            description=desc, posted=posted, pay=find_pay(desc),
            workplace=_workplace_from_greenhouse(j, loc)))
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
        wt = (j.get("workplaceType") or "").strip().lower()
        out.append(RawJob(
            source="lever", external_id=str(j["id"]), title=j.get("text", ""), company=company,
            location=(j.get("categories") or {}).get("location", "") or "", url=j.get("hostedUrl", ""),
            description=desc.strip(), posted=posted_iso(j.get("createdAt")), pay=pay,
            workplace=wt))
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
            posted=posted_iso(j.get("publishedAt") or j.get("updatedAt")),
            pay=clean_pay(comp) or find_pay(desc), workplace=_workplace_from_ashby(j)))
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


def _pin_boards(cfg: dict) -> list[dict]:
    """Always-on (company, ats, slug) rows from sources.yaml `boards:`."""
    out = []
    for b in cfg.get("boards") or []:
        if not b.get("ats") or not b.get("slug"):
            continue
        out.append({
            "company": b.get("company") or b["slug"],
            "ats": b["ats"],
            "slug": b["slug"],
            "open_jobs": b.get("open_jobs", 0),
            "pinned": True,
        })
    return out


def discover() -> list[dict]:
    """Probe company slugs against each ATS; keep *all* working boards (not just the first).

    Also merges pinned `boards:` from sources.yaml. Cache → data/verified_boards.json.
    """
    cfg = config.load_yaml("sources.yaml")
    found: list[dict] = []
    seen: set[tuple[str, str, str]] = set()
    with _client() as client:
        for pin in _pin_boards(cfg):
            key = (pin["company"], pin["ats"], pin["slug"])
            jobs = fetch_board(client, pin["ats"], pin["slug"], pin["company"])
            if jobs is None:
                # Keep the pin anyway so collect still tries later / reports missing.
                found.append({**pin, "open_jobs": 0})
                seen.add(key)
                continue
            found.append({**pin, "open_jobs": len(jobs)})
            seen.add(key)
        for c in cfg.get("companies", []):
            company_hits = 0
            for slug in c["slugs"]:
                for ats in ENDPOINTS:
                    key = (c["name"], ats, slug)
                    if key in seen:
                        continue
                    jobs = fetch_board(client, ats, slug, c["name"])
                    if jobs is None:
                        continue
                    found.append({
                        "company": c["name"], "ats": ats, "slug": slug,
                        "open_jobs": len(jobs), "pinned": False,
                    })
                    seen.add(key)
                    company_hits += 1
            if company_hits == 0:
                found.append({
                    "company": c["name"], "ats": None, "slug": None,
                    "open_jobs": 0, "pinned": False,
                })
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
