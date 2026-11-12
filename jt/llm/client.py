"""Synchronous client used by pipelines: ask(task, vars) -> reply text / validated model.

Providers:
  auto       — prefer OpenAI key, else Anthropic key, else Claude browser bridge
  openai     — OpenAI Chat Completions API (OPENAI_API_KEY)
  anthropic  — Anthropic Messages API (ANTHROPIC_API_KEY)
  claude/gpt — logged-in browser tabs via localhost bridge + Chrome extension
  manual     — dashboard / file paste
  mock       — test page via bridge
"""
from __future__ import annotations

import json
import time
import uuid
from typing import Callable, TypeVar

from jinja2 import Environment, FileSystemLoader
from pydantic import BaseModel, ValidationError
from websockets.sync.client import connect

from .. import config, db
from ..models import LLMCall
from . import api as api_llm
from .errors import LLMError
from .jsonutil import extract_json
from .prefs import preferred_browser, preferred_engine

T = TypeVar("T", bound=BaseModel)

MANUAL_DIR = config.OUTPUT_DIR / "manual"
BRIDGE_PROVIDERS = frozenset({"claude", "gpt", "mock"})


# --------------------------------------------------------------------------- bridge connection
class BridgeClient:
    def __init__(self, url: str | None = None, token: str | None = None):
        self.url = url or f"ws://{config.bridge_host()}:{config.bridge_port()}"
        self.token = token or config.bridge_token()
        self.ws = None
        self._cm = None

    def __enter__(self) -> "BridgeClient":
        try:
            self._cm = connect(self.url, max_size=16 * 1024 * 1024, open_timeout=5)
            self.ws = self._cm.__enter__()
        except OSError as e:
            raise LLMError(f"Cannot reach the bridge at {self.url}. Start it with `jt bridge serve`, "
                           "or set OPENAI_API_KEY / switch engine to openai.",
                           "no_bridge") from e
        self.ws.send(json.dumps({"type": "hello", "role": "client", "token": self.token}))
        try:
            reply = json.loads(self.ws.recv(timeout=10))
        except Exception as e:  # closed by server on bad token
            raise LLMError("Bridge rejected the connection (check JT_BRIDGE_TOKEN)", "bad_token") from e
        if reply.get("type") != "hello_ok":
            raise LLMError("Unexpected bridge handshake", "handshake")
        return self

    def __exit__(self, *exc) -> None:
        if self.ws:
            self._cm.__exit__(*exc)
            self.ws = None

    def status(self) -> dict:
        self.ws.send(json.dumps({"type": "status"}))
        while True:
            msg = json.loads(self.ws.recv(timeout=10))
            if msg.get("type") == "status":
                return msg

    def open_provider(self, provider: str, url: str | None = None) -> None:
        self.ws.send(json.dumps({"type": "open", "provider": provider, "url": url}))
        msg = json.loads(self.ws.recv(timeout=10))
        if msg.get("type") != "open_ok":
            raise LLMError(msg.get("error") or "could not open the browser session", msg.get("code") or "no_extension")

    def ask(self, provider: str, prompt: str, *, new_chat: bool = True, url: str | None = None,
            timeout: int = 300, on_progress: Callable[[dict], None] | None = None) -> str:
        from .browser_session import prepare_browser
        prepare_browser(provider, url=url)
        job_id = uuid.uuid4().hex[:12]
        self.ws.send(json.dumps({"type": "ask", "id": job_id, "provider": provider, "prompt": prompt,
                                 "new_chat": new_chat, "url": url, "timeout": timeout}))
        deadline = time.time() + timeout + 120  # lock wait + job
        while True:
            left = deadline - time.time()
            if left <= 0:
                raise LLMError("timed out waiting for the bridge", "timeout")
            try:
                msg = json.loads(self.ws.recv(timeout=left))
            except TimeoutError as e:
                raise LLMError("timed out waiting for the bridge", "timeout") from e
            if msg.get("id") != job_id:
                continue
            if msg["type"] == "progress":
                if on_progress:
                    on_progress(msg)
            elif msg["type"] == "result":
                if not msg.get("ok"):
                    raise LLMError(msg.get("error") or "LLM call failed", msg.get("code", ""))
                return msg.get("text", "")


# --------------------------------------------------------------------------- routing / prompts
def task_config(task: str) -> dict:
    cfg = config.load_yaml("models.yaml")
    merged = dict(cfg.get("defaults", {}))
    merged.update(cfg.get("tasks", {}).get(task, {}))
    return merged


def provider_url(provider: str) -> str | None:
    """Start URL of a provider (independent of which provider a task is configured for)."""
    return config.load_yaml("models.yaml").get("providers", {}).get(provider, {}).get("url")


def normalize_provider(name: str | None) -> str:
    v = str(name or "browser").strip().lower()
    if v in ("chatgpt", "chat-gpt"):
        return "gpt"
    if v in ("openai-api",):
        return "openai"
    if v in ("claude-api", "anthropic-api"):
        return "anthropic"
    return v or "browser"


def resolve_provider(configured: str | None) -> str:
    """Turn task/config provider into a concrete backend name.

    Explicit task providers (gpt, claude, openai, ...) always win.
    `browser` / `auto` defer to the dashboard engine preference, then sensible defaults.
    """
    name = normalize_provider(configured)
    if name not in ("auto", "browser"):
        return name

    pref = normalize_provider(preferred_engine())
    # Force a single backend only when the user picks one of these.
    if pref in ("openai", "anthropic", "claude", "gpt", "manual"):
        return pref
    if pref == "auto":
        if config.openai_api_key():
            return "openai"
        if config.anthropic_api_key():
            return "anthropic"
        return "claude"
    # pref == browser (or unknown): keep per-task mapping. If the task itself
    # said browser/auto, default to Claude browser.
    return "claude"


def route_provider(configured: str | None, *, explicit: bool = False) -> str:
    """Resolve a task provider. The sidebar session picks ChatGPT or Claude.

    An explicit provider argument, such as `jt bridge test gpt`, stays as given.
    """
    prov = resolve_provider(configured)
    if explicit or prov not in ("gpt", "claude"):
        return prov
    return preferred_browser()


def render_prompt(task: str, **vars) -> str:
    env = Environment(loader=FileSystemLoader(str(config.PROMPTS_DIR)), keep_trailing_newline=True,
                      autoescape=False)
    return env.get_template(f"{task}.md").render(**vars).strip()


def schema_instructions(model: type[BaseModel]) -> str:
    schema = json.dumps(model.model_json_schema(), ensure_ascii=False)
    return (
        "\n\n---\nOUTPUT FORMAT: Reply with exactly one JSON object inside a single ```json code block, "
        "and nothing after it. It must validate against this JSON Schema:\n" + schema
    )


def _log_call(task: str, provider: str, prompt: str, reply: str, ok: bool, error: str, dur: float) -> None:
    with db.session() as s:
        s.add(LLMCall(task=task, provider=provider, prompt=prompt, reply=reply, ok=ok, error=error,
                      duration_s=round(dur, 2)))
        s.commit()


# --------------------------------------------------------------------------- manual provider
def _manual_ask(prompt: str, timeout: int = 3600) -> str:
    """File-based exchange: write prompt, wait for reply file (dashboard 'Manual' page or by hand)."""
    MANUAL_DIR.mkdir(parents=True, exist_ok=True)
    mid = f"{int(time.time())}_{uuid.uuid4().hex[:6]}"
    (MANUAL_DIR / f"{mid}.prompt.md").write_text(prompt, encoding="utf-8")
    reply_path = MANUAL_DIR / f"{mid}.reply.md"
    print(f"[manual] prompt saved to {MANUAL_DIR / (mid + '.prompt.md')}")
    print(f"[manual] paste the model reply into {reply_path} (or use the dashboard Manual page)")
    deadline = time.time() + timeout
    while time.time() < deadline:
        if reply_path.exists() and reply_path.stat().st_size > 0:
            time.sleep(0.5)
            return reply_path.read_text(encoding="utf-8")
        time.sleep(1)
    raise LLMError("manual reply timed out", "timeout")


def _dispatch(prov: str, prompt: str, *, new_chat: bool = True, url: str | None = None,
              timeout: int = 300, on_progress: Callable[[dict], None] | None = None,
              bc: BridgeClient | None = None, json_mode: bool = False,
              messages: list[dict[str, str]] | None = None) -> str:
    if prov == "manual":
        return _manual_ask(prompt, timeout=timeout)
    if api_llm.is_api_provider(prov):
        if messages is not None:
            return api_llm.chat(prov, messages, json_mode=json_mode, timeout=timeout)
        return api_llm.ask(prov, prompt, json_mode=json_mode, timeout=timeout)
    if prov not in BRIDGE_PROVIDERS:
        raise LLMError(f"Unknown provider '{prov}'. Use auto|openai|anthropic|claude|gpt|manual.",
                       "bad_provider")
    client = bc
    own = False
    if client is None:
        client = BridgeClient()
        client.__enter__()
        own = True
    try:
        return client.ask(prov, prompt, new_chat=new_chat, url=url or provider_url(prov),
                          timeout=timeout, on_progress=on_progress)
    finally:
        if own:
            client.__exit__(None, None, None)


_DEFAULT_TIMEOUT = 300


def _task_timeout(tc: dict, timeout: int | None) -> int:
    """Caller timeout wins; else models.yaml task timeout; else 300s."""
    if timeout is not None:
        return int(timeout)
    configured = tc.get("timeout")
    if configured is None or configured == "":
        return _DEFAULT_TIMEOUT
    return int(configured)


# --------------------------------------------------------------------------- public API
def ask(task: str, prompt_vars: dict | None = None, *, prompt: str | None = None, provider: str | None = None,
        timeout: int | None = None, on_progress: Callable[[dict], None] | None = None) -> str:
    """Render prompts/<task>.md (or use `prompt`) and send it to the provider configured for `task`."""
    tc = task_config(task)
    configured = provider if provider is not None else tc.get("provider", "auto")
    prov = route_provider(configured, explicit=provider is not None)
    job_timeout = _task_timeout(tc, timeout)
    text = prompt if prompt is not None else render_prompt(task, **(prompt_vars or {}))
    start = time.time()
    try:
        reply = _dispatch(prov, text, new_chat=bool(tc.get("new_chat", True)),
                          url=provider_url(prov), timeout=job_timeout, on_progress=on_progress)
        _log_call(task, prov, text, reply, True, "", time.time() - start)
        return reply
    except LLMError as e:
        _log_call(task, prov, text, "", False, str(e), time.time() - start)
        raise


def ask_json(task: str, schema: type[T], prompt_vars: dict | None = None, *, provider: str | None = None,
             max_repairs: int = 2, timeout: int | None = None,
             on_progress: Callable[[dict], None] | None = None) -> T:
    """Ask and validate against a pydantic model; on invalid output, repair in the same chat."""
    tc = task_config(task)
    configured = provider if provider is not None else tc.get("provider", "auto")
    prov = route_provider(configured, explicit=provider is not None)
    job_timeout = _task_timeout(tc, timeout)
    prompt = render_prompt(task, **(prompt_vars or {})) + schema_instructions(schema)
    url = provider_url(prov)
    start = time.time()
    reply = ""
    last_err = ""
    use_api = api_llm.is_api_provider(prov)
    messages: list[dict[str, str]] | None = (
        [{"role": "user", "content": prompt}] if use_api else None
    )

    bc_ctx = BridgeClient() if (prov in BRIDGE_PROVIDERS) else None
    try:
        if bc_ctx:
            bc_ctx.__enter__()
        msg = prompt
        for i in range(max_repairs + 1):
            if use_api:
                reply = _dispatch(prov, msg, timeout=job_timeout, json_mode=True, messages=messages)
            else:
                reply = _dispatch(prov, msg, new_chat=(i == 0) and bool(tc.get("new_chat", True)),
                                  url=url, timeout=job_timeout, on_progress=on_progress, bc=bc_ctx)
            try:
                data = extract_json(reply)
                obj = schema.model_validate(data)
                _log_call(task, prov, prompt, reply, True, "", time.time() - start)
                return obj
            except (ValueError, ValidationError) as e:
                last_err = str(e)[:1500]
                repair = (f"Your last reply was not valid. Problem: {last_err}\n"
                          "Reply again with ONLY the corrected JSON in a single ```json block.")
                if use_api and messages is not None:
                    messages.append({"role": "assistant", "content": reply})
                    messages.append({"role": "user", "content": repair})
                    msg = repair
                elif prov == "manual":
                    msg = prompt + "\n\n" + repair
                else:
                    msg = repair
    except LLMError as e:
        _log_call(task, prov, prompt, reply, False, str(e), time.time() - start)
        raise
    finally:
        if bc_ctx:
            bc_ctx.__exit__(None, None, None)
    _log_call(task, prov, prompt, reply, False, f"invalid JSON after repairs: {last_err}", time.time() - start)
    raise LLMError(f"{prov} did not return valid JSON for '{task}': {last_err}", "invalid_json")


def status_summary() -> dict:
    """Snapshot of engines for dashboard / `jt llm status`."""
    from .prefs import ENGINE_LABELS

    preferred = preferred_engine()
    resolved = resolve_provider("auto")
    openai_ok, openai_msg = api_llm.provider_ready("openai")
    anthropic_ok, anthropic_msg = api_llm.provider_ready("anthropic")
    bridge = None
    try:
        with BridgeClient() as bc:
            bridge = bc.status()
    except LLMError as e:
        bridge = {"error": str(e), "code": e.code, "extension_connected": False}
    except Exception as e:  # noqa: BLE001
        bridge = {"error": str(e), "extension_connected": False}
    return {
        "preferred": preferred,
        "preferred_label": ENGINE_LABELS.get(preferred, preferred),
        "resolved_auto": resolved,
        "active": resolve_provider(preferred if preferred != "browser" else "auto"),
        "openai": {"ok": openai_ok, "detail": openai_msg, "model": config.openai_model()},
        "anthropic": {"ok": anthropic_ok, "detail": anthropic_msg, "model": config.anthropic_model()},
        "bridge": bridge,
    }
