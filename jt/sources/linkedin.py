"""LinkedIn job collector driven through your logged-in Octo Browser profile.

Low volume on purpose: random human-like delays, a per-run cap, skipping jobs already stored, and an immediate
stop on any checkpoint / captcha / login wall. Only run this against your own account.
"""
from __future__ import annotations

import json
import random
import re
import time
from typing import Iterator
from urllib.parse import quote_plus

from bs4 import BeautifulSoup
from sqlmodel import select

from .. import config, db
from ..browser.octo import octo_page
from ..models import Job
from .base import RawJob, find_pay, html_to_text

JOB_ID_RE = re.compile(r"/jobs/view/(?:[^/?#]*-)?(\d{6,})")
BLOCK_MARKERS = ("checkpoint", "authwall", "/login", "/uas/", "captcha", "challenge")


class LinkedInBlocked(RuntimeError):
    pass


# ----------------------------------------------------------------------------- pure parsing
def search_url(query: str, page: int, filters: dict) -> str:
    parts = [f"keywords={quote_plus(query)}", f"start={25 * page}"]
    if filters.get("posted_within_seconds"):
        parts.append(f"f_TPR=r{int(filters['posted_within_seconds'])}")
    if filters.get("remote_only"):
        parts.append("f_WT=2")
    return "https://www.linkedin.com/jobs/search/?" + "&".join(parts)


def extract_job_ids(hrefs: list[str]) -> list[str]:
    seen, out = set(), []
    for h in hrefs:
        m = JOB_ID_RE.search(h) or re.search(r"currentJobId=(\d{6,})", h)
        if m and m.group(1) not in seen:
            seen.add(m.group(1))
            out.append(m.group(1))
    return out


def _first_text(soup: BeautifulSoup, selectors: list[str]) -> str:
    for sel in selectors:
        el = soup.select_one(sel)
        if el and el.get_text(strip=True):
            return el.get_text(" ", strip=True)
    return ""


def parse_job_page(html: str, job_id: str) -> RawJob | None:
    """Parse a LinkedIn job page. Prefers schema.org JSON-LD, falls back to DOM selectors."""
    soup = BeautifulSoup(html, "lxml")
    title = company = location = posted = pay = ""
    desc_html = ""

    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
        except (ValueError, TypeError):
            continue
        for item in data if isinstance(data, list) else [data]:
            if isinstance(item, dict) and item.get("@type") == "JobPosting":
                title = item.get("title", "") or title
                org = item.get("hiringOrganization") or {}
                company = org.get("name", "") if isinstance(org, dict) else company
                addr = ((item.get("jobLocation") or {}).get("address") or {}) if isinstance(item.get("jobLocation"), dict) else {}
                location = ", ".join(x for x in (addr.get("addressLocality"), addr.get("addressCountry")) if isinstance(x, str) and x)
                posted = (item.get("datePosted") or "")[:10]
                desc_html = item.get("description", "") or desc_html
                sal = ((item.get("baseSalary") or {}).get("value") or {}) if isinstance(item.get("baseSalary"), dict) else {}
                if sal.get("minValue"):
                    pay = f"{sal.get('minValue')}-{sal.get('maxValue', '')} {sal.get('unitText', '')}".strip()

    if not title:
        title = _first_text(soup, ["h1", ".job-details-jobs-unified-top-card__job-title", "[class*='job-title']"])
    if not company:
        company = _first_text(soup, [
            ".job-details-jobs-unified-top-card__company-name a", ".job-details-jobs-unified-top-card__company-name",
            "a[href*='/company/']", "[class*='company-name']"])
    if not desc_html:
        for sel in ("#job-details", ".jobs-description__content", ".jobs-box__html-content",
                    ".show-more-less-html__markup", "[class*='description__text']", "[class*='jobs-description']"):
            el = soup.select_one(sel)
            if el and len(el.get_text(strip=True)) > 80:
                desc_html = str(el)
                break
    if not location:
        top = _first_text(soup, [".job-details-jobs-unified-top-card__primary-description-container",
                                 ".job-details-jobs-unified-top-card__tertiary-description-container",
                                 "[class*='top-card'] [class*='bullet']"])
        location = top.split("·")[0].strip() if top else ""

    page_text = soup.get_text(" ", strip=True)
    m = re.search(r"((?:Over\s)?\d[\d,]*\s+(?:applicants|people clicked apply))", page_text, re.I)
    applicants = m.group(1) if m else ""
    description = html_to_text(desc_html)
    if not (title and company and description):
        return None
    return RawJob(source="linkedin", external_id=job_id, title=title.strip(), company=company.strip(),
                  location=location, pay=pay or find_pay(description), posted=posted, applicants=applicants,
                  url=f"https://www.linkedin.com/jobs/view/{job_id}/", description=description)


# ----------------------------------------------------------------------------- browsing
def _pause(delay: list[float]) -> None:
    time.sleep(random.uniform(delay[0], delay[1]))


def _check_blocked(page) -> None:
    url = page.url.lower()
    if any(m in url for m in BLOCK_MARKERS):
        raise LinkedInBlocked(f"LinkedIn showed a checkpoint/login page ({page.url}). Open the Octo profile, "
                              "resolve it manually, then rerun later.")


def _known_ids() -> set[str]:
    with db.session() as s:
        return {j.external_id for j in s.exec(select(Job).where(Job.source == "linkedin")).all()}


def collect_linkedin(log=print) -> Iterator[RawJob]:
    cfg = config.load_yaml("sources.yaml")["linkedin"]
    delay = cfg.get("delay_seconds", [3, 8])
    cap = int(cfg.get("max_jobs_per_run", 60))
    pages = int(cfg.get("max_pages_per_query", 3))
    known = _known_ids()
    fetched = 0
    with octo_page() as page:
        for query in cfg["queries"]:
            for pg in range(pages):
                if fetched >= cap:
                    log(f"Reached the per-run cap of {cap} jobs.")
                    return
                page.goto(search_url(query, pg, cfg.get("filters", {})), wait_until="domcontentloaded")
                _pause(delay)
                _check_blocked(page)
                for _ in range(4):  # lazy-loaded result list
                    page.mouse.wheel(0, 1800)
                    time.sleep(random.uniform(0.6, 1.4))
                hrefs = page.eval_on_selector_all("a[href*='/jobs/view/']", "els => els.map(e => e.href)")
                ids = [i for i in extract_job_ids(hrefs) if i not in known]
                log(f"'{query}' page {pg + 1}: {len(ids)} new job ids")
                if not hrefs:
                    break
                for jid in ids:
                    if fetched >= cap:
                        break
                    page.goto(f"https://www.linkedin.com/jobs/view/{jid}/", wait_until="domcontentloaded")
                    _pause(delay)
                    _check_blocked(page)
                    known.add(jid)
                    fetched += 1
                    job = parse_job_page(page.content(), jid)
                    if job is None:
                        log(f"  could not parse job {jid} (selectors may have changed)")
                        continue
                    yield job


def fetch_profile_text(url: str = "https://www.linkedin.com/in/me/") -> str:
    """Visible text of your own LinkedIn profile page, for `jt profile import --linkedin-text`."""
    with octo_page() as page:
        page.goto(url, wait_until="domcontentloaded")
        _pause([3, 5])
        _check_blocked(page)
        for _ in range(6):
            page.mouse.wheel(0, 2000)
            time.sleep(0.8)
        return page.inner_text("main")
