"""Localhost /api routes for the BrightStar side panel (no browser)."""
from __future__ import annotations

import asyncio
import json
import socket
from unittest.mock import patch

import pytest

from jt.llm.bridge import Bridge
from jt.llm import local_api
from jt.llm.prefs import save_prefs

TOKEN = "api-test-token"


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
async def api_bridge(tmp_path, monkeypatch):
    monkeypatch.setenv("JT_BRIDGE_TOKEN", TOKEN)
    from jt import config

    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    port = free_port()
    b = Bridge("127.0.0.1", port, TOKEN, job_timeout=5)
    task = asyncio.create_task(b.run())
    await asyncio.sleep(0.35)
    yield b, port
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)


async def http_json(port: int, method: str, path: str, body: dict | None = None, token: str | None = TOKEN):
    reader, writer = await asyncio.open_connection("127.0.0.1", port + 1)
    payload = b""
    if body is not None:
        payload = json.dumps(body).encode()
    headers = [
        f"{method} {path} HTTP/1.1",
        "Host: 127.0.0.1",
        "Connection: close",
    ]
    if token:
        headers.append(f"Authorization: Bearer {token}")
    if payload:
        headers.append("Content-Type: application/json")
        headers.append(f"Content-Length: {len(payload)}")
    writer.write(("\r\n".join(headers) + "\r\n\r\n").encode() + payload)
    await writer.drain()
    raw = b""
    while True:
        chunk = await reader.read(4096)
        if not chunk:
            break
        raw += chunk
    writer.close()
    head, _, rest = raw.partition(b"\r\n\r\n")
    status = int(head.split(b" ")[1])
    data = json.loads(rest.decode() or "{}") if rest else {}
    return status, data


async def test_ext_config_includes_api_base(api_bridge):
    _, port = api_bridge
    status, data = await http_json(port, "GET", "/ext-config", token=None)
    assert status == 200
    assert data["token"] == TOKEN
    assert data["apiBase"] == f"http://127.0.0.1:{port + 1}"


async def test_status_requires_token_for_full_payload(api_bridge):
    _, port = api_bridge
    status, data = await http_json(port, "GET", "/api/status", token=None)
    assert status == 200
    assert data.get("auth_required") is True

    status, data = await http_json(port, "GET", "/api/status")
    assert status == 200
    assert data["ok"] is True
    assert "engine" in data
    assert "browser" in data


async def test_prefs_round_trip(api_bridge):
    _, port = api_bridge
    status, data = await http_json(
        port, "POST", "/api/prefs", {"engine": "openai", "browser": "claude"}
    )
    assert status == 200
    assert data["engine"] == "openai"
    assert data["browser"] == "claude"

    status, data = await http_json(port, "GET", "/api/status")
    assert data["engine"] == "openai"
    assert data["browser"] == "claude"


async def test_prefs_unauthorized(api_bridge):
    _, port = api_bridge
    status, data = await http_json(
        port, "POST", "/api/prefs", {"engine": "openai"}, token="wrong"
    )
    assert status == 401
    assert data["code"] == "unauthorized"


async def test_suggest_enqueue_and_poll(api_bridge):
    _, port = api_bridge

    fake_paths = {"profile": "p.md", "docx": "r.docx", "json": "s.json"}

    class FakeSuggestion:
        class sample:
            label = "illustrative"

        persona_name = "AA"
        why_this_shape = "because"

    def fake_suggest(
        name,
        company,
        title="",
        notes="",
        jd="",
        profile_seed=None,
        seed_mode="last_company",
        years_experience=20,
    ):
        fake_suggest.seen_seed = profile_seed
        fake_suggest.seen_mode = seed_mode
        fake_suggest.seen_years = years_experience
        return FakeSuggestion(), fake_paths

    with patch("jt.pipelines.samples.suggest_sample", fake_suggest):
        status, data = await http_json(
            port,
            "POST",
            "/api/suggest",
            {
                "name": "AA",
                "last_company": "Morgan Stanley",
                "title": "Engineer",
                "seed_mode": "provided",
                "profile_seed": {
                    "skills": ["PLC"],
                    "education": [{"school": "MIT", "degree": "BSc"}],
                },
            },
        )
        assert status == 200
        assert data["ok"] is True
        job_id = data["id"]

        for _ in range(40):
            status, data = await http_json(port, "GET", f"/api/jobs/{job_id}")
            assert status == 200
            if data["job"]["status"] in ("done", "error"):
                break
            await asyncio.sleep(0.05)

    assert data["job"]["status"] == "done"
    assert data["job"]["paths"]["docx"] == "r.docx"
    assert fake_suggest.seen_mode == "provided"
    assert fake_suggest.seen_years == 20
    assert fake_suggest.seen_seed == {
        "skills": ["PLC"],
        "education": [{"school": "MIT", "degree": "BSc"}],
    }


async def test_suggest_requires_name_company(api_bridge):
    _, port = api_bridge
    status, data = await http_json(port, "POST", "/api/suggest", {"name": "Only"})
    assert status == 400
    assert data["code"] == "bad_request"


def test_dispatch_unit_status_and_missing_job(tmp_path, monkeypatch):
    from jt import config

    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    save_prefs(engine="browser", browser="gpt")
    status, body = local_api.dispatch(
        method="GET",
        path="/api/status",
        headers={"authorization": f"Bearer {TOKEN}"},
        body=b"",
        token=TOKEN,
        bridge_status={"extension_connected": True},
    )
    assert status == 200
    assert body["bridge"]["extension_connected"] is True

    status, body = local_api.dispatch(
        method="GET",
        path="/api/jobs/missing",
        headers={"authorization": f"Bearer {TOKEN}"},
        body=b"",
        token=TOKEN,
        bridge_status={},
    )
    assert status == 404
    assert body["code"] == "not_found"
