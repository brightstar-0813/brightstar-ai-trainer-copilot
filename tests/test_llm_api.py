"""OpenAI/Anthropic API providers and auto engine resolution (offline)."""
from __future__ import annotations

import json

import httpx
import pytest

from jt import config
from jt.llm import api as api_llm
from jt.llm import client as llm_client
from jt.llm.errors import LLMError
from jt.llm.prefs import save_prefs
from jt.schemas import BridgeTest


@pytest.fixture
def clean_keys(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path / "output")
    monkeypatch.setattr(config, "openai_api_key", lambda: "")
    monkeypatch.setattr(config, "anthropic_api_key", lambda: "")
    monkeypatch.setenv("JT_LLM_ENGINE", "auto")
    config.ensure_dirs()
    save_prefs(engine="auto")


def test_auto_prefers_openai_key(clean_keys, monkeypatch):
    monkeypatch.setattr(config, "openai_api_key", lambda: "sk-test")
    save_prefs(engine="auto")
    assert llm_client.resolve_provider("auto") == "openai"


def test_auto_falls_back_to_anthropic_then_claude(clean_keys, monkeypatch):
    save_prefs(engine="auto")
    assert llm_client.resolve_provider("auto") == "claude"
    monkeypatch.setattr(config, "anthropic_api_key", lambda: "ant-test")
    assert llm_client.resolve_provider("auto") == "anthropic"


def test_browser_keeps_explicit_gpt_and_claude(clean_keys, monkeypatch):
    save_prefs(engine="browser")
    monkeypatch.setattr(config, "openai_api_key", lambda: "sk-test")
    assert llm_client.resolve_provider("gpt") == "gpt"
    assert llm_client.resolve_provider("claude") == "claude"
    assert llm_client.resolve_provider("browser") == "claude"  # fallback when task says browser


def test_sidebar_browser_session_routes_browser_tasks(clean_keys, monkeypatch):
    save_prefs(engine="browser", browser="claude")
    assert llm_client.session_routes_tasks() is True
    assert llm_client.route_provider("gpt") == "claude"
    assert llm_client.route_provider("gpt", explicit=True) == "gpt"
    assert llm_client.route_provider("openai") == "openai"


def test_api_engine_ignores_sidebar_session(clean_keys, monkeypatch):
    monkeypatch.setattr(config, "anthropic_api_key", lambda: "ant-test")
    save_prefs(engine="anthropic", browser="gpt")
    assert llm_client.session_routes_tasks() is False
    assert llm_client.route_provider("auto") == "anthropic"
    assert llm_client.route_provider("browser") == "anthropic"


def test_locked_browser_engine_not_overridden_by_session(clean_keys, monkeypatch):
    save_prefs(engine="gpt", browser="claude")
    # save_prefs keeps Session locked to the gpt/claude engine.
    assert llm_client.preferred_browser() == "gpt"
    from jt.llm import prefs as llm_prefs

    path = llm_prefs.prefs_path()
    raw = path.read_text(encoding="utf-8")
    path.write_text(raw.replace("browser: gpt", "browser: claude"), encoding="utf-8")
    assert llm_client.route_provider("auto") == "gpt"
    assert llm_client.session_routes_tasks() is True


def test_prefs_override_auto(clean_keys, monkeypatch):
    monkeypatch.setattr(config, "openai_api_key", lambda: "sk-test")
    save_prefs(engine="gpt")
    assert llm_client.resolve_provider("auto") == "gpt"
    assert llm_client.resolve_provider("openai") == "openai"  # explicit wins


def test_env_engine_used_when_prefs_file_missing(clean_keys, monkeypatch, tmp_path):
    prefs = config.DATA_DIR / "llm_prefs.yaml"
    if prefs.exists():
        prefs.unlink()
    monkeypatch.setenv("JT_LLM_ENGINE", "anthropic")
    monkeypatch.setattr(config, "anthropic_api_key", lambda: "ant-test")
    assert llm_client.preferred_engine() == "anthropic"
    assert llm_client.resolve_provider("auto") == "anthropic"


def test_anthropic_identity_verification_error(clean_keys, monkeypatch):
    monkeypatch.setattr(config, "anthropic_api_key", lambda: "ant-test")

    def fake_post(url, headers=None, json=None, timeout=None):
        return httpx.Response(
            400,
            json={"error": {"type": "invalid_request_error",
                            "message": "Identity verification is required to continue."}},
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    with pytest.raises(LLMError) as e:
        api_llm.ask("anthropic", "hi")
    assert e.value.code == "api_auth"
    assert "identity verification" in str(e.value).lower()


def test_openai_ask_json_and_repair(clean_keys, monkeypatch, tmp_path):
    monkeypatch.setattr(config, "openai_api_key", lambda: "sk-test")
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "data" / "jobs.db")
    from jt import db
    monkeypatch.setattr(db, "_engine", None)

    calls = {"n": 0}

    def fake_post(url, headers=None, **kwargs):
        calls["n"] += 1
        content = "not json" if calls["n"] == 1 else json.dumps({"ok": True, "note": "api"})
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    monkeypatch.setattr(httpx, "post", fake_post)
    out = llm_client.ask_json("bridge_test", BridgeTest, provider="openai", max_repairs=2)
    assert out.ok is True and out.note == "api"
    assert calls["n"] == 2


def test_task_timeout_from_models_yaml():
    tc = llm_client.task_config("sample_suggest")
    assert llm_client._task_timeout(tc, None) == 900
    assert llm_client._task_timeout(tc, 120) == 120
    assert llm_client._task_timeout({}, None) == 300


def test_openai_missing_key(clean_keys):
    with pytest.raises(LLMError) as e:
        api_llm.ask("openai", "hi")
    assert e.value.code == "no_api_key"


def test_openai_401(clean_keys, monkeypatch):
    monkeypatch.setattr(config, "openai_api_key", lambda: "bad")

    def fake_post(url, headers=None, json=None, timeout=None):
        return httpx.Response(401, json={"error": {"message": "invalid"}})

    monkeypatch.setattr(httpx, "post", fake_post)
    with pytest.raises(LLMError) as e:
        api_llm.ask("openai", "hi")
    assert e.value.code == "api_auth"


def test_anthropic_ask(clean_keys, monkeypatch):
    monkeypatch.setattr(config, "anthropic_api_key", lambda: "ant-test")

    def fake_post(url, headers=None, json=None, timeout=None):
        assert "anthropic.com" in url
        assert headers["x-api-key"] == "ant-test"
        return httpx.Response(200, json={"content": [{"type": "text", "text": "hello from claude"}]})

    monkeypatch.setattr(httpx, "post", fake_post)
    assert api_llm.ask("anthropic", "hi") == "hello from claude"
