"""Direct HTTP providers (OpenAI / Anthropic). No bridge or Chrome extension needed."""
from __future__ import annotations

import json
from typing import Any

import httpx

from .. import config
from .errors import LLMError

OPENAI_URL = "https://api.openai.com/v1/chat/completions"
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"

API_PROVIDERS = frozenset({"openai", "anthropic"})


def is_api_provider(provider: str) -> bool:
    return provider in API_PROVIDERS


def _openai_key() -> str:
    return config.openai_api_key()


def _anthropic_key() -> str:
    return config.anthropic_api_key()


def provider_ready(provider: str) -> tuple[bool, str]:
    """Return (ok, human message) for dashboard / CLI status."""
    if provider == "openai":
        if _openai_key():
            return True, f"OpenAI API ready (model {config.openai_model()})"
        return False, "Set OPENAI_API_KEY in .env"
    if provider == "anthropic":
        if _anthropic_key():
            return True, f"Anthropic API ready (model {config.anthropic_model()})"
        return False, "Set ANTHROPIC_API_KEY in .env"
    return False, f"Unknown API provider: {provider}"


def chat(provider: str, messages: list[dict[str, str]], *, json_mode: bool = False,
         temperature: float = 0.3, max_tokens: int = 8192, timeout: int = 300) -> str:
    """Send a chat-completions-style message list; return assistant text."""
    if provider == "openai":
        return _openai_chat(messages, json_mode=json_mode, temperature=temperature,
                            max_tokens=max_tokens, timeout=timeout)
    if provider == "anthropic":
        return _anthropic_chat(messages, temperature=temperature, max_tokens=max_tokens, timeout=timeout)
    raise LLMError(f"Not an API provider: {provider}", "bad_provider")


def ask(provider: str, prompt: str, *, json_mode: bool = False, timeout: int = 300) -> str:
    return chat(provider, [{"role": "user", "content": prompt}], json_mode=json_mode, timeout=timeout)


def _openai_chat(messages: list[dict[str, str]], *, json_mode: bool, temperature: float,
                 max_tokens: int, timeout: int) -> str:
    key = _openai_key()
    if not key:
        raise LLMError("OPENAI_API_KEY is missing. Add it to .env (or switch engine to Claude/ChatGPT bridge).",
                       "no_api_key")
    body: dict[str, Any] = {
        "model": config.openai_model(),
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    try:
        r = httpx.post(OPENAI_URL, headers={"Authorization": f"Bearer {key}",
                                            "Content-Type": "application/json"},
                       json=body, timeout=timeout)
    except httpx.HTTPError as e:
        raise LLMError(f"OpenAI request failed: {e}", "api_network") from e
    return _openai_parse(r)


def _openai_parse(r: httpx.Response) -> str:
    try:
        payload = r.json()
    except json.JSONDecodeError:
        payload = None
    if r.status_code == 401:
        raise LLMError("OpenAI API key is invalid or revoked (401).", "api_auth")
    if r.status_code == 429:
        msg = (payload or {}).get("error", {}).get("message") or r.text[:200]
        raise LLMError(f"OpenAI rate limit (429): {msg}", "api_rate_limit")
    if r.status_code >= 400:
        msg = (payload or {}).get("error", {}).get("message") or r.text[:200]
        raise LLMError(f"OpenAI error (HTTP {r.status_code}): {msg}", "api_error")
    content = (payload or {}).get("choices", [{}])[0].get("message", {}).get("content")
    if not isinstance(content, str) or not content.strip():
        raise LLMError("OpenAI returned an empty response.", "api_empty")
    return content.strip()


def _anthropic_chat(messages: list[dict[str, str]], *, temperature: float,
                    max_tokens: int, timeout: int) -> str:
    key = _anthropic_key()
    if not key:
        raise LLMError("ANTHROPIC_API_KEY is missing. Add it to .env (or switch engine to Claude/ChatGPT bridge).",
                       "no_api_key")
    # Anthropic wants system as a top-level field; fold any system msgs.
    system_parts, chat_msgs = [], []
    for m in messages:
        role, content = m.get("role", "user"), m.get("content", "")
        if role == "system":
            system_parts.append(content)
        elif role in ("user", "assistant"):
            chat_msgs.append({"role": role, "content": content})
        else:
            chat_msgs.append({"role": "user", "content": content})
    if not chat_msgs:
        raise LLMError("Anthropic messages are empty.", "bad_prompt")
    body: dict[str, Any] = {
        "model": config.anthropic_model(),
        "messages": chat_msgs,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if system_parts:
        body["system"] = "\n\n".join(system_parts)
    try:
        r = httpx.post(ANTHROPIC_URL,
                       headers={"x-api-key": key, "anthropic-version": ANTHROPIC_VERSION,
                                "Content-Type": "application/json"},
                       json=body, timeout=timeout)
    except httpx.HTTPError as e:
        raise LLMError(f"Anthropic request failed: {e}", "api_network") from e
    return _anthropic_parse(r)


def _anthropic_parse(r: httpx.Response) -> str:
    try:
        payload = r.json()
    except json.JSONDecodeError:
        payload = None
    if r.status_code == 401:
        raise LLMError("Anthropic API key is invalid or revoked (401).", "api_auth")
    if r.status_code == 429:
        msg = (payload or {}).get("error", {}).get("message") or r.text[:200]
        raise LLMError(f"Anthropic rate limit (429): {msg}", "api_rate_limit")
    if r.status_code >= 400:
        msg = (payload or {}).get("error", {}).get("message") or r.text[:200]
        raise LLMError(f"Anthropic error (HTTP {r.status_code}): {msg}", "api_error")
    blocks = (payload or {}).get("content") or []
    texts = [b.get("text", "") for b in blocks if isinstance(b, dict) and b.get("type") == "text"]
    content = "\n".join(t for t in texts if t).strip()
    if not content:
        raise LLMError("Anthropic returned an empty response.", "api_empty")
    return content
