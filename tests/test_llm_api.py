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
    monkeypatch.setattr("jt.llm.prefs.load_prefs", lambda: {"engine": "auto"})
    config.ensure_dirs()


def test_auto_prefers_openai_key(clean_keys, monkeypatch):
    monkeypatch.setattr(config, "openai_api_key", lambda: "sk-test")
    monkeypatch.setattr("jt.llm.prefs.load_prefs", lambda: {"engine": "auto"})
    assert llm_client.resolve_provider("auto") == "openai"


def test_auto_falls_back_to_anthropic_then_claude(clean_keys, monkeypatch):
    monkeypatch.setattr("jt.llm.prefs.load_prefs", lambda: {"engine": "auto"})
    assert llm_client.resolve_provider("auto") == "claude"
    monkeypatch.setattr(config, "anthropic_api_key", lambda: "ant-test")
    assert llm_client.resolve_provider("auto") == "anthropic"


def test_browser_keeps_explicit_gpt_and_claude(clean_keys, monkeypatch):
    monkeypatch.setattr("jt.llm.prefs.load_prefs", lambda: {"engine": "browser"})
    monkeypatch.setattr(config, "openai_api_key", lambda: "sk-test")
    assert llm_client.resolve_provider("gpt") == "gpt"
    assert llm_client.resolve_provider("claude") == "claude"
    assert llm_client.resolve_provider("browser") == "claude"  # fallback when task says browser


def test_sidebar_browser_session_routes_browser_tasks(clean_keys, monkeypatch):
    monkeypatch.setattr("jt.llm.prefs.load_prefs", lambda: {"engine": "browser", "browser": "claude"})
    assert llm_client.route_provider("gpt") == "claude"
    assert llm_client.route_provider("gpt", explicit=True) == "gpt"
    assert llm_client.route_provider("openai") == "openai"


def test_prefs_override_auto(clean_keys, monkeypatch):
    monkeypatch.setattr(config, "openai_api_key", lambda: "sk-test")
    monkeypatch.setattr("jt.llm.prefs.load_prefs", lambda: {"engine": "gpt"})
    assert llm_client.resolve_provider("auto") == "gpt"
    assert llm_client.resolve_provider("openai") == "openai"  # explicit wins


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
