"""Bridge protocol tests using a fake extension (no browser needed)."""
from __future__ import annotations

import asyncio
import json
import socket

import pytest
from pydantic import BaseModel
from websockets.asyncio.client import connect

from jt.llm.bridge import Bridge
from jt.llm.client import BridgeClient, LLMError
from jt.llm.jsonutil import extract_json

TOKEN = "test-token"


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
async def bridge():
    port = free_port()
    b = Bridge("127.0.0.1", port, TOKEN, job_timeout=5)
    task = asyncio.create_task(b.run())
    await asyncio.sleep(0.3)
    yield b, port
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)


async def fake_extension(port, handler):
    ws = await connect(f"ws://127.0.0.1:{port}")
    await ws.send(json.dumps({"type": "hello", "role": "extension", "token": TOKEN, "version": "t"}))
    assert json.loads(await ws.recv())["type"] == "hello_ok"

    async def loop():
        async for raw in ws:
            msg = json.loads(raw)
            if msg["type"] == "job":
                reply = await handler(msg)
                await ws.send(json.dumps({"type": "result", "id": msg["id"], **reply}))

    return ws, asyncio.create_task(loop())


async def test_round_trip(bridge):
    b, port = bridge

    async def handler(job):
        return {"ok": True, "text": "```json\n{\"ok\": true}\n```"}

    ws, t = await fake_extension(port, handler)

    def run():
        with BridgeClient(f"ws://127.0.0.1:{port}", TOKEN) as bc:
            return bc.ask("claude", "hi")

    text = await asyncio.to_thread(run)
    assert extract_json(text) == {"ok": True}
    t.cancel()
    await ws.close()


async def test_bad_token_rejected(bridge):
    _, port = bridge

    def run():
        with BridgeClient(f"ws://127.0.0.1:{port}", "wrong"):
            pass

    with pytest.raises(LLMError) as e:
        await asyncio.to_thread(run)
    assert e.value.code == "bad_token"


async def test_foreign_origin_rejected(bridge):
    _, port = bridge
    ws = await connect(f"ws://127.0.0.1:{port}", origin="https://evil.example")
    with pytest.raises(Exception):
        await ws.send(json.dumps({"type": "hello", "role": "client", "token": TOKEN}))
        await asyncio.wait_for(ws.recv(), 3)


async def test_no_extension(bridge):
    _, port = bridge

    def run():
        with BridgeClient(f"ws://127.0.0.1:{port}", TOKEN) as bc:
            bc.ask("claude", "hi")

    with pytest.raises(LLMError) as e:
        await asyncio.to_thread(run)
    assert e.value.code == "no_extension"


async def test_provider_serialized_and_followup_holds_lock(bridge):
    b, port = bridge
    active, peak = 0, 0

    async def handler(job):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.3)
        active -= 1
        return {"ok": True, "text": job["prompt"]}

    ws, t = await fake_extension(port, handler)

    def run(tag):
        with BridgeClient(f"ws://127.0.0.1:{port}", TOKEN) as bc:
            a = bc.ask("claude", f"{tag}-1")
            c = bc.ask("claude", f"{tag}-2", new_chat=False)
            return a, c

    r = await asyncio.gather(asyncio.to_thread(run, "A"), asyncio.to_thread(run, "B"))
    assert peak == 1  # never two jobs at once on one provider
    assert r[0] == ("A-1", "A-2") and r[1] == ("B-1", "B-2")
    t.cancel()
    await ws.close()


async def test_timeout_sends_cancel(bridge):
    b, port = bridge
    cancelled = asyncio.Event()

    ws = await connect(f"ws://127.0.0.1:{port}")
    await ws.send(json.dumps({"type": "hello", "role": "extension", "token": TOKEN, "version": "t"}))
    await ws.recv()

    async def silent():
        async for raw in ws:
            if json.loads(raw)["type"] == "cancel":
                cancelled.set()

    t = asyncio.create_task(silent())

    def run():
        with BridgeClient(f"ws://127.0.0.1:{port}", TOKEN) as bc:
            bc.ask("gpt", "hi", timeout=1)

    b.grace = 1
    with pytest.raises(LLMError) as e:
        await asyncio.wait_for(asyncio.to_thread(run), 15)
    assert e.value.code == "timeout"
    assert cancelled.is_set()
    t.cancel()
    await ws.close()


def test_extract_json_variants():
    assert extract_json('text ```json\n{"a": 1}\n``` tail') == {"a": 1}
    assert extract_json('blah {"a": {"b": [1, 2]}} blah') == {"a": {"b": [1, 2]}}
    assert extract_json('```json\n{bad}\n``` then {"ok": 1}') == {"ok": 1}
    with pytest.raises(ValueError):
        extract_json("no json here")


class Dummy(BaseModel):
    ok: bool
