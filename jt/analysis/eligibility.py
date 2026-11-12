"""Filter postings to US-eligible remote roles during job collection."""
from __future__ import annotations

from .. import config
from .taxonomy import has_term


def _blob(*parts: str) -> str:
    return " ".join(p for p in parts if p)


def _hits(text: str, keywords: list[str]) -> int:
    return sum(1 for k in keywords if has_term(text, k))


def _cfg() -> dict:
    return config.load_yaml("taxonomy.yaml").get("eligibility", {}) or {}


def _is_remote(location: str, description: str, workplace: str) -> bool:
    cfg = _cfg()
    remote_kw = cfg.get("remote_keywords", [])
    work = (workplace or "").strip().lower().replace("-", "_").replace(" ", "_")
    if work in {"onsite", "on_site", "hybrid"}:
        # Structured workplace wins unless location/description still say fully remote.
        if _hits(_blob(location, description), remote_kw) == 0:
            return False
    if work in {"remote", "remotely", "work_from_home", "wfh"}:
        return True
    return _hits(_blob(location, description, workplace), remote_kw) > 0


def _blocks_us(location: str, description: str) -> bool:
    """True when the posting clearly excludes the US or is other-region-only."""
    cfg = _cfg()
    loc = location or ""
    if _hits(_blob(loc, description), cfg.get("us_exclude_keywords", [])) > 0:
        return True
    # Location like "Remote - India" / "EMEA Remote" without a US override.
    foreign = cfg.get("foreign_geo_keywords", [])
    us_pos = cfg.get("us_positive_keywords", [])
    return _hits(loc, foreign) > 0 and _hits(loc, us_pos) == 0


def _allows_us(location: str, description: str, workplace: str = "") -> bool:
    cfg = _cfg()
    us_pos = cfg.get("us_positive_keywords", [])
    remote_kw = cfg.get("remote_keywords", [])
    foreign = cfg.get("foreign_geo_keywords", [])
    text = _blob(location, description)
    if _hits(text, us_pos) > 0:
        return True
    loc = (location or "").strip()
    if _hits(loc, foreign) > 0:
        return False
    # Bare "Remote" (or location that says remote) with no foreign geo → US-open.
    if loc and _hits(loc, remote_kw) > 0:
        return True
    # Structured remote + non-foreign location (often an HQ city) → US-open unless excluded elsewhere.
    work = (workplace or "").strip().lower().replace("-", "_").replace(" ", "_")
    return work in {"remote", "remotely", "work_from_home", "wfh"} and _hits(loc, foreign) == 0


def is_us_remote(location: str = "", description: str = "", workplace: str = "") -> bool:
    """Keep only remote roles that US-based candidates can apply to / work from."""
    if not _is_remote(location, description, workplace):
        return False
    if _blocks_us(location, description):
        return False
    return _allows_us(location, description, workplace)
