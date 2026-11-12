"""Mercor expert marketplace listings (work.mercor.com) — public, no login."""
from __future__ import annotations

import json
import re
from typing import Iterable

import httpx

from .. import config
from .base import RawJob, clean_pay, posted_iso

EXPLORE_URL = "https://work.mercor.com/jobs"
_NEXT_RE = re.compile(r'id="__NEXT_DATA__"[^>]*>(\{.*?\})</script>', re.S)


def _client() -> httpx.Client:
    http = config.load_yaml("sources.yaml").get("http", {})
    return httpx.Client(
        timeout=http.get("timeout_seconds", 25),
        follow_redirects=True,
        headers={"User-Agent": http.get("user_agent", "Mozilla/5.0")},
    )


def _pay(listing: dict) -> str:
    lo, hi = listing.get("rateMin"), listing.get("rateMax")
    freq = (listing.get("payRateFrequency") or "hourly").strip()
    if lo is None and hi is None:
        return ""
    if lo is not None and hi is not None and lo != hi:
        return clean_pay(f"${lo}-${hi}/{freq}")
    val = hi if hi is not None else lo
    return clean_pay(f"${val}/{freq}")


def _location_blob(listing: dict) -> str:
    parts = [
        listing.get("location") or "",
        listing.get("workArrangement") or "",
    ]
    for key in ("eligibleLocation", "eligibleResidenceLocation"):
        vals = listing.get(key) or []
        if isinstance(vals, list):
            parts.extend(str(v) for v in vals)
        elif vals:
            parts.append(str(vals))
    return " | ".join(p for p in parts if p)


def _workplace(listing: dict) -> str:
    arr = str(listing.get("workArrangement") or "").strip().lower()
    if "remote" in arr:
        return "remote"
    if "hybrid" in arr:
        return "hybrid"
    if arr in {"onsite", "on-site", "office"}:
        return "onsite"
    loc = str(listing.get("location") or "").lower()
    return "remote" if "remote" in loc else arr


def _slug_title(title: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (title or "").lower()).strip("-")
    return s or "role"


def parse_listings(listings: list[dict]) -> list[RawJob]:
    out: list[RawJob] = []
    for item in listings:
        if not isinstance(item, dict):
            continue
        if item.get("status") and str(item.get("status")).lower() not in {"active", "open", ""}:
            continue
        if item.get("disableApplications") is True:
            continue
        lid = str(item.get("listingId") or item.get("uid") or "").strip()
        title = (item.get("title") or "").strip()
        if not lid or not title:
            continue
        desc = item.get("description") or ""
        url = f"https://work.mercor.com/jobs/{lid}/{_slug_title(title)}"
        out.append(
            RawJob(
                source="mercor",
                external_id=lid,
                title=title,
                company="Mercor",
                location=_location_blob(item),
                pay=_pay(item),
                url=url,
                description=desc,
                posted=posted_iso(item.get("createdAt")),
                workplace=_workplace(item),
            )
        )
    return out


def parse_explore_html(html: str) -> list[RawJob]:
    m = _NEXT_RE.search(html or "")
    if not m:
        return []
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError:
        return []
    queries = (((data.get("props") or {}).get("pageProps") or {}).get("dehydratedState") or {}).get("queries") or []
    for q in queries:
        state = (q.get("state") or {}).get("data") or {}
        listings = state.get("listings") if isinstance(state, dict) else None
        if isinstance(listings, list) and listings:
            return parse_listings(listings)
    return []


def collect_mercor() -> Iterable[RawJob]:
    with _client() as client:
        r = client.get(EXPLORE_URL)
        r.raise_for_status()
        yield from parse_explore_html(r.text)
