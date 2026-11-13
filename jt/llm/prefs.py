"""User-facing LLM engine preference (dashboard / `jt llm engine`)."""
from __future__ import annotations

from pathlib import Path

import yaml

from .. import config

ENGINES = ("browser", "auto", "openai", "anthropic", "claude", "gpt", "manual")
ENGINE_LABELS = {
    "browser": "Claude + ChatGPT browser (per task in models.yaml)",
    "auto": "Auto (OpenAI key, else Anthropic key, else Claude browser)",
    "openai": "OpenAI API only",
    "anthropic": "Anthropic / Claude API only",
    "claude": "Claude browser only",
    "gpt": "ChatGPT browser only",
    "manual": "Manual paste (dashboard)",
}


def prefs_path() -> Path:
    return config.DATA_DIR / "llm_prefs.yaml"


BROWSERS = ("gpt", "claude")
BROWSER_LABELS = {"gpt": "ChatGPT", "claude": "Claude"}

SEED_MODES = ("last_company", "provided")
SEED_MODE_LABELS = {
    "last_company": "Last company only (invent peers)",
    "provided": "Use provided employers / schools / certs",
}
DEFAULT_SUGGEST_YEARS = 20
MIN_SUGGEST_YEARS = 5
MAX_SUGGEST_YEARS = 40


def _browser_name(value: str | None) -> str:
    raw = str(value or "gpt").strip().lower()
    if raw in ("chatgpt", "chat-gpt"):
        return "gpt"
    return raw if raw in BROWSERS else "gpt"


def normalize_seed_mode(value: str | None) -> str:
    """Teaching-model seed policy: last_company (default) or provided."""
    raw = str(value or "last_company").strip().lower().replace("-", "_")
    if raw in ("provided", "seed", "full", "on", "true", "1"):
        return "provided"
    return "last_company"


def normalize_suggest_years(value) -> int:
    """Clamp invent-mode years-of-experience preference."""
    try:
        years = int(round(float(value)))
    except (TypeError, ValueError):
        years = DEFAULT_SUGGEST_YEARS
    return max(MIN_SUGGEST_YEARS, min(MAX_SUGGEST_YEARS, years))


def load_prefs() -> dict:
    path = prefs_path()
    defaults = {
        "engine": "browser",
        "browser": "gpt",
        "resume_template": "ats-modern",
        "resume_accent": "",
        "active_profile": "",
        "suggest_seed_mode": "last_company",
        "suggest_years_experience": DEFAULT_SUGGEST_YEARS,
    }
    if not path.exists():
        return dict(defaults)
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:  # noqa: BLE001
        return dict(defaults)
    engine = str(data.get("engine") or "browser").strip().lower()
    if engine not in ENGINES:
        engine = "browser"
    return {
        "engine": engine,
        "browser": _browser_name(data.get("browser")),
        "resume_template": str(data.get("resume_template") or "ats-modern").strip() or "ats-modern",
        "resume_accent": str(data.get("resume_accent") or "").strip(),
        "active_profile": str(data.get("active_profile") or "").strip().lower(),
        "suggest_seed_mode": normalize_seed_mode(data.get("suggest_seed_mode")),
        "suggest_years_experience": normalize_suggest_years(
            data.get("suggest_years_experience", DEFAULT_SUGGEST_YEARS)
        ),
    }


def save_prefs(
    *,
    engine: str | None = None,
    browser: str | None = None,
    resume_template: str | None = None,
    resume_accent: str | None = None,
    active_profile: str | None = None,
    suggest_seed_mode: str | None = None,
    suggest_years_experience=None,
) -> dict:
    data = load_prefs()
    if engine is not None:
        engine = str(engine or "browser").strip().lower()
        if engine not in ENGINES:
            raise ValueError(f"Unknown engine '{engine}'. Choose one of: {', '.join(ENGINES)}")
        data["engine"] = engine
    if browser is not None:
        data["browser"] = _browser_name(browser)
    # Locked ChatGPT/Claude engines always match Session (no divergent prefs).
    if data["engine"] in BROWSERS:
        data["browser"] = data["engine"]
    if resume_template is not None:
        data["resume_template"] = str(resume_template or "ats-modern").strip() or "ats-modern"
    if resume_accent is not None:
        data["resume_accent"] = str(resume_accent or "").strip()
    if active_profile is not None:
        data["active_profile"] = str(active_profile or "").strip().lower()
    if suggest_seed_mode is not None:
        data["suggest_seed_mode"] = normalize_seed_mode(suggest_seed_mode)
    if suggest_years_experience is not None:
        data["suggest_years_experience"] = normalize_suggest_years(suggest_years_experience)
    config.ensure_dirs()
    prefs_path().write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return data


def preferred_resume_template() -> str:
    return str(load_prefs().get("resume_template") or "ats-modern")


def preferred_resume_accent() -> str:
    return str(load_prefs().get("resume_accent") or "")


def preferred_suggest_seed_mode() -> str:
    return normalize_seed_mode(load_prefs().get("suggest_seed_mode"))


def preferred_suggest_years() -> int:
    return normalize_suggest_years(load_prefs().get("suggest_years_experience"))


def preferred_browser() -> str:
    """ChatGPT or Claude session used when a task needs the logged-in browser."""
    return _browser_name(load_prefs().get("browser"))


def preferred_engine() -> str:
    """Order: explicit engine in llm_prefs.yaml > JT_LLM_ENGINE env > browser.

    Defaults from load_prefs() alone must not hide JT_LLM_ENGINE.
    """
    path = prefs_path()
    if path.exists():
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception:  # noqa: BLE001
            raw = {}
        if "engine" in raw:
            engine = str(raw.get("engine") or "").strip().lower()
            if engine in ENGINES:
                return engine
    env_engine = config.env("JT_LLM_ENGINE", "browser").strip().lower()
    if env_engine in ENGINES:
        return env_engine
    return "browser"
