"""User-facing LLM engine preference (dashboard / `jt llm engine`)."""
from __future__ import annotations

from pathlib import Path

import yaml

from .. import config

ENGINES = ("browser", "auto", "openai", "anthropic", "claude", "gpt", "manual")
ENGINE_LABELS = {
    "browser": "Claude + ChatGPT browser (per task in models.yaml)",
    "auto": "Auto (API key if set, else Claude browser)",
    "openai": "OpenAI API only",
    "anthropic": "Anthropic API only",
    "claude": "Claude browser only",
    "gpt": "ChatGPT browser only",
    "manual": "Manual paste (dashboard)",
}


def prefs_path() -> Path:
    return config.DATA_DIR / "llm_prefs.yaml"


BROWSERS = ("gpt", "claude")
BROWSER_LABELS = {"gpt": "ChatGPT", "claude": "Claude"}


def _browser_name(value: str | None) -> str:
    raw = str(value or "gpt").strip().lower()
    if raw in ("chatgpt", "chat-gpt"):
        return "gpt"
    return raw if raw in BROWSERS else "gpt"


def load_prefs() -> dict:
    path = prefs_path()
    defaults = {
        "engine": "browser",
        "browser": "gpt",
        "resume_template": "ats-modern",
        "resume_accent": "",
        "active_profile": "",
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
    }


def save_prefs(
    *,
    engine: str | None = None,
    browser: str | None = None,
    resume_template: str | None = None,
    resume_accent: str | None = None,
    active_profile: str | None = None,
) -> dict:
    data = load_prefs()
    if engine is not None:
        engine = str(engine or "browser").strip().lower()
        if engine not in ENGINES:
            raise ValueError(f"Unknown engine '{engine}'. Choose one of: {', '.join(ENGINES)}")
        data["engine"] = engine
    if browser is not None:
        data["browser"] = _browser_name(browser)
    if resume_template is not None:
        data["resume_template"] = str(resume_template or "ats-modern").strip() or "ats-modern"
    if resume_accent is not None:
        data["resume_accent"] = str(resume_accent or "").strip()
    if active_profile is not None:
        data["active_profile"] = str(active_profile or "").strip().lower()
    config.ensure_dirs()
    prefs_path().write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return data


def preferred_resume_template() -> str:
    return str(load_prefs().get("resume_template") or "ats-modern")


def preferred_resume_accent() -> str:
    return str(load_prefs().get("resume_accent") or "")


def preferred_browser() -> str:
    """ChatGPT or Claude session used when a task needs the logged-in browser."""
    return _browser_name(load_prefs().get("browser"))


def preferred_engine() -> str:
    """Order: data/llm_prefs.yaml > JT_LLM_ENGINE env > browser."""
    prefs = load_prefs()
    if prefs.get("engine"):
        return prefs["engine"]
    env_engine = config.env("JT_LLM_ENGINE", "browser").strip().lower()
    if env_engine in ENGINES:
        return env_engine
    return "browser"
