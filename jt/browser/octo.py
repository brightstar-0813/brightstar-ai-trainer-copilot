"""Octo Browser local API -> Playwright over CDP.

Used only for optional one-shot reads of *your own* LinkedIn profile text
(`jt octo profile-text`). Job search/collection via LinkedIn is not supported.

Octo exposes a local API (default http://localhost:58888). `POST /api/profiles/start` launches a profile and
returns `ws_endpoint` / `debug_port`. We attach Playwright to that browser.

If you start the profile yourself, set OCTO_CDP_URL (e.g. http://127.0.0.1:9222) to attach without the API.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import httpx
from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright

from .. import config


class OctoError(RuntimeError):
    pass


def api_base() -> str:
    return config.env("OCTO_API", "http://localhost:58888").rstrip("/")


def start_profile(uuid: str, headless: bool = False, timeout: int = 90) -> dict:
    try:
        r = httpx.post(f"{api_base()}/api/profiles/start", timeout=timeout,
                       json={"uuid": uuid, "headless": headless, "debug_port": True, "timeout": 60,
                             "only_local": True})
    except httpx.HTTPError as e:
        raise OctoError(f"Cannot reach the Octo local API at {api_base()}: is Octo Browser running? ({e})") from e
    try:
        data = r.json()
    except ValueError:
        data = {"raw": r.text}
    if r.status_code >= 400 or not (data.get("ws_endpoint") or data.get("debug_port")):
        raise OctoError(f"Octo refused to start profile {uuid}: HTTP {r.status_code} {str(data)[:300]}")
    return data


def stop_profile(uuid: str) -> None:
    try:
        httpx.post(f"{api_base()}/api/profiles/stop", json={"uuid": uuid}, timeout=30)
    except httpx.HTTPError:
        pass


def _cdp_url(info: dict) -> str:
    if info.get("ws_endpoint"):
        return info["ws_endpoint"]
    return f"http://127.0.0.1:{info['debug_port']}"


@contextmanager
def octo_page(stop_when_done: bool = False) -> Iterator[Page]:
    """Yield a Playwright Page inside the logged-in Octo profile (or an attached Chrome via OCTO_CDP_URL)."""
    cdp = config.env("OCTO_CDP_URL")
    uuid = config.env("OCTO_PROFILE_UUID")
    started = False
    if not cdp:
        if not uuid:
            raise OctoError("Set OCTO_PROFILE_UUID (or OCTO_CDP_URL) in .env")
        cdp = _cdp_url(start_profile(uuid))
        started = True
    with sync_playwright() as p:
        browser: Browser = p.chromium.connect_over_cdp(cdp)
        context: BrowserContext = browser.contexts[0] if browser.contexts else browser.new_context()
        page = context.new_page()
        try:
            yield page
        finally:
            try:
                page.close()
            except Exception:  # noqa: BLE001
                pass
            browser.close()  # detaches from CDP; does not kill the Octo profile
            if started and stop_when_done:
                stop_profile(uuid)
