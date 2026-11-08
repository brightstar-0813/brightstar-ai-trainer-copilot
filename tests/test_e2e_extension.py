"""True end-to-end: real Chrome + the unpacked extension + the real bridge + the mock chat page.

Chrome 137+ ignores --load-extension unless DisableLoadExtensionCommandLineSwitch is disabled; if the extension
still cannot be loaded in this environment, the test skips.
"""
from __future__ import annotations

import asyncio
import functools
import http.server
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

playwright_sync = pytest.importorskip("playwright.sync_api")

from jt import config, db  # noqa: E402
from jt.llm import ask_json  # noqa: E402
from jt.llm.bridge import Bridge  # noqa: E402
from jt.llm.client import BridgeClient, LLMError  # noqa: E402
from jt.schemas import BridgeTest  # noqa: E402

EXT = Path(__file__).resolve().parent.parent / "extension"
TOKEN = "e2e-token"
MOCK_URL = "http://127.0.0.1:8799/mock_chat.html"


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def stack(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("e2e")
    # mock chat server
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(EXT / "test"))
    handler.log_message = lambda *a, **k: None
    try:
        httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 8799), handler)
    except OSError:
        pytest.skip("port 8799 busy")
    threading.Thread(target=httpd.serve_forever, daemon=True).start()

    # bridge in a background event loop
    port = free_port()
    bridge = Bridge("127.0.0.1", port, TOKEN, job_timeout=60)
    loop = asyncio.new_event_loop()
    holder: dict = {}

    def run_bridge():
        asyncio.set_event_loop(loop)
        holder["task"] = loop.create_task(bridge.run())
        try:
            loop.run_until_complete(holder["task"])
        except asyncio.CancelledError:
            pass

    bridge_thread = threading.Thread(target=run_bridge, daemon=True)
    bridge_thread.start()
    time.sleep(0.5)

    with playwright_sync.sync_playwright() as p:
        # Branded Chrome 137+ ignores --load-extension, so load via the DevTools protocol instead.
        ctx, ext_id = None, None
        for channel in ("chrome", "msedge", None):
            try:
                kw = {"channel": channel} if channel else {}
                ctx = p.chromium.launch_persistent_context(
                    str(tmp / f"profile_{channel}"), headless=False, **kw,
                    ignore_default_args=["--disable-extensions"],
                    args=["--enable-unsafe-extension-debugging", "--headless=new"])
                ext_id = ctx.browser.new_browser_cdp_session().send(
                    "Extensions.loadUnpacked", {"path": str(EXT)})["id"]
                break
            except Exception:  # noqa: BLE001
                if ctx:
                    ctx.close()
                ctx = None
        if ctx is None:
            pytest.skip("this environment cannot load an unpacked extension")
        # Opening the popup wakes the service worker; extension pages can write chrome.storage.
        cfg_page = ctx.new_page()
        cfg_page.goto(f"chrome-extension://{ext_id}/popup.html")
        cfg_page.evaluate("([t, u]) => chrome.storage.local.set({token: t, bridgeUrl: u})",
                          [TOKEN, f"ws://127.0.0.1:{port}"])
        deadline = time.time() + 20
        while bridge.ext is None and time.time() < deadline:
            time.sleep(0.3)
        if bridge.ext is None:
            ctx.close()
            pytest.fail("extension never connected to the bridge")
        yield {"bridge": bridge, "port": port, "ctx": ctx, "page": cfg_page}
        ctx.close()
    httpd.shutdown()
    loop.call_soon_threadsafe(holder["task"].cancel)
    bridge_thread.join(timeout=5)


def pumped(stack, fn):
    """Run a blocking call in a worker thread while keeping Playwright's event loop serviced.

    Playwright's sync API only processes browser events while the main thread calls into it; blocking on the
    bridge socket for long stalls the driver pipe and makes Chrome page loads hang.
    """
    with ThreadPoolExecutor(1) as ex:
        fut = ex.submit(fn)
        while not fut.done():
            stack["page"].wait_for_timeout(150)
        return fut.result()


def client(stack):
    return BridgeClient(f"ws://127.0.0.1:{stack['port']}", TOKEN)


def test_extension_round_trip(stack):
    def run():
        with client(stack) as bc:
            assert bc.status()["extension_connected"]
            return bc.ask("mock", 'Reply with the JSON {"ok": true}', url=MOCK_URL, timeout=60)

    assert '{"ok": true}' in pumped(stack, run)


def test_followup_in_same_chat_and_new_chat_reset(stack):
    def run():
        with client(stack) as bc:
            first = bc.ask("mock", "first message", url=MOCK_URL, timeout=60)
            second = bc.ask("mock", "second message", new_chat=False, url=MOCK_URL, timeout=60)
            fresh = bc.ask("mock", "fresh start", new_chat=True, url=MOCK_URL, timeout=60)
            return first, second, fresh

    first, second, fresh = pumped(stack, run)
    assert "msgs=1" in first
    assert "msgs=2" in second  # follow-up stayed in the same conversation
    assert "msgs=1" in fresh   # new chat started a clean conversation


def test_usage_limit_surfaces_as_error_code(stack):
    def run():
        with client(stack) as bc:
            bc.ask("mock", "usage-limit-test", url=MOCK_URL, timeout=30)

    with pytest.raises(LLMError) as e:
        pumped(stack, run)
    assert e.value.code == "usage_limit"


def test_ask_json_through_real_stack(stack, tmp_path, monkeypatch):
    monkeypatch.setenv("JT_BRIDGE_PORT", str(stack["port"]))
    monkeypatch.setenv("JT_BRIDGE_TOKEN", TOKEN)
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "e2e.db")
    monkeypatch.setattr(db, "_engine", None)
    r = pumped(stack, lambda: ask_json("bridge_test", BridgeTest, provider="mock", timeout=60))
    assert r.ok is True
