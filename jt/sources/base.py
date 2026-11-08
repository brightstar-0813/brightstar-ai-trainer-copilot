"""Shared types and helpers for job collectors."""
from __future__ import annotations

import html
import re
from dataclasses import dataclass

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
