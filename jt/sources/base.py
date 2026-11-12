"""Shared types and helpers for job collectors."""
from __future__ import annotations

import html
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from bs4 import BeautifulSoup


@dataclass
class RawJob:
    source: str
    external_id: str
    title: str
    company: str
    location: str = ""
    pay: str = ""
    url: str = ""
    description: str = ""
    posted: str = ""
    applicants: str = ""
    # Structured workplace when the ATS provides it: remote / hybrid / onsite.
    workplace: str = ""


def html_to_text(raw: str) -> str:
    """HTML (possibly entity-escaped, as Greenhouse returns it) -> readable plain text."""
    if not raw:
        return ""
    raw = html.unescape(raw) if "&lt;" in raw else raw
    soup = BeautifulSoup(raw, "lxml")
    for br in soup.find_all("br"):
        br.replace_with("\n")
    for li in soup.find_all("li"):
        li.insert_before("\n- ")
    for block in soup.find_all(["p", "div", "h1", "h2", "h3", "h4", "ul", "ol"]):
        block.append("\n")
    text = soup.get_text()
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    return text.strip()


_CUR = r"(?:US\$|CA\$|C\$|A\$|€|£|\$)"
_NUM = r"\d[\d,]*(?:\.\d+)?\s?[kK]?"
PAY_RE = re.compile(
    rf"{_CUR}\s?{_NUM}"
    rf"(?:\s?(?:-|–|—|to)\s?{_CUR}?\s?{_NUM})?"
    r"(?:\s?(?:/|per\s|an\s|a\s)\s?(?:hr|hour|hourly|yr|year|month|mo|week)\b)?",
    re.I,
)
_PAY_CONTEXT = re.compile(r"pay|compensation|salary|rate|hour|stipend|earn", re.I)


def posted_iso(raw) -> str:
    """Normalize ATS posted/updated timestamps to YYYY-MM-DD (UTC). Empty if unknown."""
    if raw is None or raw == "":
        return ""
    if isinstance(raw, datetime):
        return raw.astimezone(timezone.utc).strftime("%Y-%m-%d") if raw.tzinfo else raw.strftime("%Y-%m-%d")
    if isinstance(raw, date) and not isinstance(raw, datetime):
        return raw.isoformat()
    if isinstance(raw, (int, float)):
        ts = float(raw)
        if ts > 1e12:  # milliseconds
            ts /= 1000.0
        elif ts > 1e10:  # microseconds (rare)
            ts /= 1e6
        try:
            return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
        except (OverflowError, OSError, ValueError):
            return ""
    s = str(raw).strip()
    if not s:
        return ""
    if s.isdigit():
        return posted_iso(int(s))
    # ISO-ish: 2026-01-02T00:00:00Z
    return s[:10] if re.match(r"^\d{4}-\d{2}-\d{2}", s) else ""


def within_max_age(posted: str, max_age_days: int, today: date | None = None) -> bool:
    """True if posted is within max_age_days, or posted is unknown (keep for recall)."""
    if max_age_days <= 0:
        return True
    iso = posted_iso(posted)
    if not iso:
        return True
    try:
        d = date.fromisoformat(iso)
    except ValueError:
        return True
    return (today or date.today()) - d <= timedelta(days=max_age_days)


def clean_pay(s: str) -> str:
    """Tidy a compensation string: drop bullet-separated extras such as '• Offers Equity'."""
    return re.split(r"[•·|]", s or "")[0].strip()


def find_pay(text: str) -> str:
    """Best-effort pay snippet from description text (prefers lines that talk about pay)."""
    text = text or ""
    for line in text.splitlines():
        if _PAY_CONTEXT.search(line):
            m = PAY_RE.search(line)
            if m and re.search(r"\d{2}", m.group(0)):
                return m.group(0).strip()
    m = PAY_RE.search(text)
    return m.group(0).strip() if m and re.search(r"\d{2}", m.group(0)) else ""
