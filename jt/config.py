"""Paths, environment, and YAML config loading."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
PROMPTS_DIR = ROOT / "prompts"
PROFILE_DIR = ROOT / "profile"
PEOPLE_DIR = PROFILE_DIR / "people"
PROFILE_EXAMPLE = PROFILE_DIR / "profile.example.yaml"
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "output"
SAMPLES_DIR = ROOT / "samples" / "archetypes"
# Legacy single-file path; migrated to people/default.yaml on first load.
LEGACY_MASTER_PROFILE = PROFILE_DIR / "master_profile.yaml"
MASTER_PROFILE = LEGACY_MASTER_PROFILE  # backwards-compat alias for older callers/tests
DB_PATH = DATA_DIR / "jobs.db"
EXTENSION_MANIFEST = ROOT / "extension" / "manifest.json"

load_dotenv(ROOT / ".env")


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def bridge_host() -> str:
    return env("JT_BRIDGE_HOST", "127.0.0.1")


def bridge_port() -> int:
    return int(env("JT_BRIDGE_PORT", "8765"))


def bridge_token() -> str:
    return env("JT_BRIDGE_TOKEN", "change-me")


def openai_api_key() -> str:
    return env("OPENAI_API_KEY", "").strip()


def anthropic_api_key() -> str:
    return env("ANTHROPIC_API_KEY", "").strip()


def _provider_model(provider: str, env_name: str, default: str) -> str:
    from_env = env(env_name, "").strip()
    if from_env:
        return from_env
    try:
        cfg = load_yaml("models.yaml").get("providers", {}).get(provider, {}) or {}
        return str(cfg.get("model") or default)
    except Exception:  # noqa: BLE001
        return default


def openai_model() -> str:
    return _provider_model("openai", "OPENAI_MODEL", "gpt-4o-mini")


def anthropic_model() -> str:
    return _provider_model("anthropic", "ANTHROPIC_MODEL", "claude-sonnet-4-20250514")


def ensure_dirs() -> None:
    for d in (DATA_DIR, OUTPUT_DIR, PROFILE_DIR, PEOPLE_DIR, SAMPLES_DIR):
        d.mkdir(parents=True, exist_ok=True)


def extension_version() -> str:
    """Version from extension/manifest.json on disk (what Chrome should be running).

    Not cached — the bridge advertises this so the extension can self-reload.
    """
    import json

    try:
        data = json.loads(EXTENSION_MANIFEST.read_text(encoding="utf-8"))
        return str(data.get("version") or "")
    except Exception:  # noqa: BLE001
        return ""


@lru_cache(maxsize=None)
def load_yaml(name: str) -> dict:
    path = CONFIG_DIR / name
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def reload_config() -> None:
    load_yaml.cache_clear()
    extension_version.cache_clear()
