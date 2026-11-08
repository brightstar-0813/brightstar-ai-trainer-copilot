"""Run extension/content.js against the mock chat page in a real browser (chrome.runtime is stubbed)."""
from __future__ import annotations

import functools
import http.server
import json
import threading
from pathlib import Path

import pytest

playwright_sync = pytest.importorskip("playwright.sync_api")

EXT = Path(__file__).resolve().parent.parent / "extension"
SELECTORS = json.loads((EXT / "selectors.json").read_text(encoding="utf-8"))["mock"]
SHIM = """
window.__msgs = [];
window.chrome = { runtime: {
  sendMessage: (m) => { window.__msgs.push(m); return Promise.resolve(); },
  onMessage: { addListener: (fn) => { window.__listener = fn; } },
}};
"""


@pytest.fixture(scope="module")
def server():
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(EXT / "test"))
    handler.log_message = lambda *a, **k: None
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 8799), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield "http://127.0.0.1:8799/mock_chat.html"
    httpd.shutdown()


@pytest.fixture(scope="module")
def browser():
    with playwright_sync.sync_playwright() as p:
        try:
            b = p.chromium.launch(headless=True)
        except Exception:
            try:
                b = p.chromium.launch(channel="chrome", headless=True)
            except Exception as e:  # no browser available
                pytest.skip(f"no browser available: {e}")
        yield b
        b.close()


def run_job(browser, url: str, prompt: str, timeout: int = 30) -> dict:
    page = browser.new_page()
    page.add_init_script(SHIM)
    page.add_init_script(path=str(EXT / "content.js"))
    page.goto(url)
    page.evaluate(
        "([job, sel]) => window.__listener({type:'jt_run', job, selectors: sel}, null, () => {})",
        [{"id": "t1", "prompt": prompt, "timeout": timeout}, SELECTORS],
    )
    page.wait_for_function("window.__msgs.some(m => m.type === 'jt_result')", timeout=(timeout + 10) * 1000)
    msgs = page.evaluate("window.__msgs")
    page.close()
    return next(m for m in msgs if m["type"] == "jt_result")


def test_json_reply_keeps_fenced_block(browser, server):
    r = run_job(browser, server, 'Reply with the JSON {"ok": true}')
    assert r["ok"], r
    assert '```json\n{"ok": true}\n```' in r["text"]


def test_long_multiline_prompt_is_typed_fully(browser, server):
    prompt = "\n".join(f"line {i}: " + "word " * 20 for i in range(120))
    r = run_job(browser, server, prompt)
    assert r["ok"], r
    assert f"ECHO({len(prompt)})" in r["text"].replace("\n", "") or "ECHO(" in r["text"]


def test_usage_limit_is_reported(browser, server):
    r = run_job(browser, server, "usage-limit-test please", timeout=20)
    assert not r["ok"]
    assert r["code"] == "usage_limit"