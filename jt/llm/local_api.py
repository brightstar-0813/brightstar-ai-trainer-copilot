"""Localhost HTTP API for the BrightStar AI Trainer Copilot side panel.

Served on bridge port+1 alongside /ext-config. Token-gated /api/* routes trigger
jt pipelines without Streamlit.
"""
from __future__ import annotations

import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from . import api as api_llm
from .errors import LLMError
from .prefs import (
    BROWSERS,
    DEFAULT_SUGGEST_YEARS,
    ENGINES,
    ENGINE_LABELS,
    SEED_MODES,
    load_prefs,
    normalize_seed_mode,
    normalize_suggest_years,
    save_prefs,
)

_MAX_JOBS = 50
_jobs: dict[str, dict[str, Any]] = {}
_jobs_lock = threading.Lock()
_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="jt-api")


def _trim_jobs() -> None:
    if len(_jobs) <= _MAX_JOBS:
        return
    done = sorted(
        (j for j in _jobs.values() if j.get("status") in ("done", "error")),
        key=lambda j: j.get("finished_at") or j.get("started_at") or 0,
    )
    for j in done[: max(0, len(_jobs) - _MAX_JOBS)]:
        _jobs.pop(j["id"], None)


def job_snapshot(job_id: str) -> dict[str, Any] | None:
    with _jobs_lock:
        job = _jobs.get(job_id)
        return dict(job) if job else None


def list_recent_jobs(limit: int = 10) -> list[dict[str, Any]]:
    with _jobs_lock:
        items = sorted(_jobs.values(), key=lambda j: j.get("started_at") or 0, reverse=True)
        return [dict(j) for j in items[:limit]]


def status_payload(bridge_status: dict | None = None) -> dict[str, Any]:
    prefs = load_prefs()
    openai_ok, openai_msg = api_llm.provider_ready("openai")
    anthropic_ok, anthropic_msg = api_llm.provider_ready("anthropic")
    engine = prefs.get("engine", "browser")
    return {
        "ok": True,
        "engine": engine,
        "engine_label": ENGINE_LABELS.get(engine, engine),
        "browser": prefs.get("browser", "gpt"),
        "suggest_seed_mode": prefs.get("suggest_seed_mode", "last_company"),
        "suggest_years_experience": prefs.get(
            "suggest_years_experience", DEFAULT_SUGGEST_YEARS
        ),
        "engines": list(ENGINES),
        "browsers": list(BROWSERS),
        "seed_modes": list(SEED_MODES),
        "openai": {"ok": openai_ok, "detail": openai_msg},
        "anthropic": {"ok": anthropic_ok, "detail": anthropic_msg},
        "bridge": bridge_status or {},
        "dashboard_url": "http://localhost:8501",
    }


def apply_prefs(body: dict) -> dict[str, Any]:
    engine = body.get("engine")
    browser = body.get("browser")
    seed_mode = body.get("suggest_seed_mode", body.get("seed_mode"))
    years = body.get("suggest_years_experience", body.get("years_experience"))
    data = save_prefs(
        engine=None if engine is None else str(engine),
        browser=None if browser is None else str(browser),
        suggest_seed_mode=None if seed_mode is None else str(seed_mode),
        suggest_years_experience=None if years is None else years,
    )
    return {"ok": True, **data, "engine_label": ENGINE_LABELS.get(data["engine"], data["engine"])}


def _profile_seed_from_body(body: dict) -> dict[str, Any]:
    seed = body.get("profile_seed")
    if isinstance(seed, dict):
        return seed
    return {
        key: body[key]
        for key in (
            "location",
            "headline",
            "about",
            "experience",
            "education",
            "licenses",
            "certifications",
            "skills",
            "languages",
            "projects",
        )
        if key in body
    }


def enqueue_suggest(body: dict) -> dict[str, Any]:
    name = str(body.get("name") or "").strip()
    company = str(body.get("last_company") or body.get("company") or "").strip()
    title = str(body.get("title") or "").strip()
    notes = str(body.get("notes") or "").strip()
    jd = str(body.get("jd") or "").strip()
    seed_mode = normalize_seed_mode(body.get("seed_mode") or body.get("suggest_seed_mode"))
    years_experience = normalize_suggest_years(
        body.get("years_experience", body.get("suggest_years_experience", DEFAULT_SUGGEST_YEARS))
    )
    profile_seed = _profile_seed_from_body(body) if seed_mode == "provided" else {}
    if not name or not company:
        return {"ok": False, "error": "name and last_company are required", "code": "bad_request"}

    job_id = uuid.uuid4().hex[:12]
    job = {
        "id": job_id,
        "kind": "suggest",
        "status": "queued",
        "started_at": time.time(),
        "finished_at": None,
        "error": "",
        "code": "",
        "paths": {},
        "label": "",
        "request": {
            "name": name,
            "last_company": company,
            "title": title,
            "notes": notes,
            "jd": jd,
            "seed_mode": seed_mode,
            "years_experience": years_experience,
            "profile_seed": profile_seed,
        },
    }
    with _jobs_lock:
        _jobs[job_id] = job
        _trim_jobs()
    _pool.submit(
        _run_suggest,
        job_id,
        name,
        company,
        title,
        notes,
        jd,
        profile_seed,
        seed_mode,
        years_experience,
    )
    return {"ok": True, "id": job_id, "status": "queued"}


def _run_suggest(
    job_id: str,
    name: str,
    company: str,
    title: str,
    notes: str,
    jd: str,
    profile_seed: dict | None = None,
    seed_mode: str = "last_company",
    years_experience: int = DEFAULT_SUGGEST_YEARS,
) -> None:
    with _jobs_lock:
        job = _jobs.get(job_id)
        if not job:
            return
        job["status"] = "running"
    try:
        from ..pipelines.samples import suggest_sample

        suggestion, paths = suggest_sample(
            name,
            company,
            title=title,
            notes=notes,
            jd=jd,
            profile_seed=profile_seed,
            seed_mode=seed_mode,
            years_experience=years_experience,
        )
        with _jobs_lock:
            job = _jobs[job_id]
            job["status"] = "done"
            job["finished_at"] = time.time()
            job["paths"] = paths
            job["label"] = suggestion.sample.label
            job["persona_name"] = suggestion.persona_name
            job["why"] = suggestion.why_this_shape
    except LLMError as e:
        with _jobs_lock:
            job = _jobs[job_id]
            job["status"] = "error"
            job["finished_at"] = time.time()
            job["error"] = str(e)
            job["code"] = e.code or "llm_error"
    except Exception as e:  # noqa: BLE001
        with _jobs_lock:
            job = _jobs[job_id]
            job["status"] = "error"
            job["finished_at"] = time.time()
            job["error"] = str(e)
            job["code"] = "suggest_failed"


def authorized(token: str, headers: dict[str, str], query: dict[str, str]) -> bool:
    if not token:
        return False
    auth = headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        supplied = auth[7:].strip()
    else:
        supplied = headers.get("x-jt-token", "") or query.get("token", "")
    if not supplied:
        return False
    import hmac

    return hmac.compare_digest(supplied, token)


def parse_query(path: str) -> tuple[str, dict[str, str]]:
    if "?" not in path:
        return path, {}
    base, qs = path.split("?", 1)
    out: dict[str, str] = {}
    for part in qs.split("&"):
        if not part:
            continue
        if "=" in part:
            k, v = part.split("=", 1)
        else:
            k, v = part, ""
        from urllib.parse import unquote

        out[unquote(k)] = unquote(v)
    return base, out


def dispatch(
    *,
    method: str,
    path: str,
    headers: dict[str, str],
    body: bytes,
    token: str,
    bridge_status: dict | None,
) -> tuple[int, dict[str, Any]]:
    """Return (http_status, json_body) for /api/* routes."""
    path, query = parse_query(path)
    method = method.upper()

    if method == "OPTIONS":
        return 204, {}

    if path == "/api/status" and method == "GET":
        # Status is useful before the panel has a token from /ext-config; still
        # require token once stored. Allow unauthenticated minimal probe.
        if not authorized(token, headers, query):
            return 200, {
                "ok": True,
                "auth_required": True,
                "bridge": bridge_status or {},
                "dashboard_url": "http://localhost:8501",
            }
        return 200, status_payload(bridge_status)

    if not authorized(token, headers, query):
        return 401, {"ok": False, "error": "bad or missing token", "code": "unauthorized"}

    if path == "/api/prefs" and method == "POST":
        try:
            data = _json_body(body)
            return 200, apply_prefs(data)
        except ValueError as e:
            return 400, {"ok": False, "error": str(e), "code": "bad_request"}

    if path == "/api/suggest" and method == "POST":
        data = _json_body(body)
        result = enqueue_suggest(data)
        return (200 if result.get("ok") else 400), result

    if path.startswith("/api/jobs/") and method == "GET":
        job_id = path[len("/api/jobs/") :].strip("/")
        if not job_id:
            return 400, {"ok": False, "error": "job id required", "code": "bad_request"}
        job = job_snapshot(job_id)
        if not job:
            return 404, {"ok": False, "error": "job not found", "code": "not_found"}
        return 200, {"ok": True, "job": job}

    if path == "/api/jobs" and method == "GET":
        return 200, {"ok": True, "jobs": list_recent_jobs()}

    return 404, {"ok": False, "error": "not found", "code": "not_found"}


def _json_body(body: bytes) -> dict:
    if not body:
        return {}
    import json

    try:
        data = json.loads(body.decode("utf-8"))
    except Exception as e:  # noqa: BLE001
        raise ValueError(f"invalid JSON body: {e}") from e
    if not isinstance(data, dict):
        raise ValueError("JSON body must be an object")
    return data
