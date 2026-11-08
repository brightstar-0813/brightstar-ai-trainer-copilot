"""Categorize resume skills for scannable enterprise layouts."""
from __future__ import annotations

from ..schemas import SkillGroup

# (category, keyword fragments). First match wins; order = display priority.
_BUCKETS: list[tuple[str, tuple[str, ...]]] = [
    (
        "Client & Wealth Advisory",
        (
            "wealth",
            "uhnw",
            "hnw",
            "client advisory",
            "client relationship",
            "family office",
            "private banking",
            "financial planning",
            "estate",
            "retirement",
        ),
    ),
    (
        "Investment Strategy",
        (
            "portfolio",
            "asset allocation",
            "investment strategy",
            "investment management",
            "equities",
            "equity",
            "fixed income",
            "municipal",
            "multi-asset",
            "security selection",
            "valuation",
            "macroeconomic",
            "capital markets",
        ),
    ),
    (
        "Alternatives & Private Markets",
        (
            "private equity",
            "private credit",
            "private markets",
            "hedge fund",
            "alternative",
            "real asset",
            "real estate",
            "infrastructure",
        ),
    ),
    (
        "Risk, Governance & Compliance",
        (
            "risk",
            "fiduciary",
            "governance",
            "compliance",
            "regulatory",
            "suitability",
            "finra",
            "sec ",
            "stress test",
            "liquidity",
            "concentration",
        ),
    ),
    (
        "Platforms & Analytics",
        (
            "bloomberg",
            "factset",
            "morningstar",
            "aladdin",
            "excel",
            "financial modeling",
            "python",
            "sql",
            "tableau",
            "power bi",
            "salesforce",
            "aws",
            "azure",
            "gcp",
            "kubernetes",
            "docker",
            "git",
            "jira",
        ),
    ),
    (
        "AI Training & Evaluation",
        (
            "rlhf",
            "preference",
            "annotation",
            "labeling",
            "evaluation",
            "red team",
            "llm",
            "prompt",
            "sft",
            "reward model",
            "ranking",
        ),
    ),
    (
        "Engineering & Delivery",
        (
            "plc",
            "robot",
            "commission",
            "controls",
            "automation",
            "ci/cd",
            "devops",
            "architecture",
            "integration",
            "api",
            "microserv",
        ),
    ),
    (
        "Leadership & Stakeholder Management",
        (
            "leadership",
            "stakeholder",
            "committee",
            "cross-functional",
            "mentoring",
            "people management",
            "program management",
        ),
    ),
]

_MAX_GROUPS = 6
_MAX_ITEMS_PER_GROUP = 6
_MAX_FLAT = 18


def flatten_skill_groups(groups: list[SkillGroup]) -> list[str]:
    out: list[str] = []
    for g in groups:
        for item in g.items:
            text = str(item).strip()
            if text and text not in out:
                out.append(text)
    return out


def normalize_skill_groups(
    groups: list[SkillGroup] | None,
    *,
    flat: list[str] | None = None,
    max_groups: int = _MAX_GROUPS,
    max_per_group: int = _MAX_ITEMS_PER_GROUP,
) -> list[SkillGroup]:
    """Prefer explicit groups; otherwise bucket a flat skills list."""
    cleaned: list[SkillGroup] = []
    for g in groups or []:
        cat = str(g.category or "").strip()
        items = [str(i).strip() for i in (g.items or []) if str(i).strip()]
        if cat and items:
            cleaned.append(SkillGroup(category=cat, items=items[:max_per_group]))
    if cleaned:
        return cleaned[:max_groups]
    return group_flat_skills(flat or [], max_groups=max_groups, max_per_group=max_per_group)


def group_flat_skills(
    skills: list[str],
    *,
    max_groups: int = _MAX_GROUPS,
    max_per_group: int = _MAX_ITEMS_PER_GROUP,
) -> list[SkillGroup]:
    """Keyword-bucket a flat list so legacy teaching models still render cleanly."""
    items = [str(s).strip() for s in skills if str(s).strip()]
    if not items:
        return []
    buckets: dict[str, list[str]] = {name: [] for name, _ in _BUCKETS}
    other: list[str] = []
    for skill in items:
        key = skill.lower()
        placed = False
        for name, needles in _BUCKETS:
            if any(n in key for n in needles):
                if len(buckets[name]) < max_per_group:
                    buckets[name].append(skill)
                placed = True
                break
        if not placed:
            other.append(skill)
    groups = [SkillGroup(category=name, items=vals) for name, vals in buckets.items() if vals]
    if other:
        groups.append(SkillGroup(category="Additional Skills", items=other[:max_per_group]))
    # Prefer filled domain buckets over a long "Additional" tail.
    return groups[:max_groups]
