import httpx
import pytest

from jt.browser import octo


def test_octo_start_profile_builds_cdp_url(monkeypatch):
    seen = {}

    def fake_post(url, json=None, timeout=None):
        seen.update(url=url, body=json)
        return httpx.Response(200, json={"uuid": "u1", "state": "STARTED", "debug_port": "9333",
                                         "ws_endpoint": "ws://127.0.0.1:9333/devtools/browser/abc"})

    monkeypatch.setattr(octo.httpx, "post", fake_post)
    info = octo.start_profile("u1")
    assert seen["url"].endswith("/api/profiles/start") and seen["body"]["debug_port"] is True
    assert octo._cdp_url(info) == "ws://127.0.0.1:9333/devtools/browser/abc"
    assert octo._cdp_url({"debug_port": "9333"}) == "http://127.0.0.1:9333"


def test_octo_errors_are_actionable(monkeypatch):
    def refuse(*a, **k):
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(octo.httpx, "post", refuse)
    with pytest.raises(octo.OctoError, match="Octo Browser running"):
        octo.start_profile("u1")
    monkeypatch.setattr(octo.httpx, "post", lambda *a, **k: httpx.Response(400, json={"msg": "no such profile"}))
    with pytest.raises(octo.OctoError, match="refused to start"):
        octo.start_profile("u1")
