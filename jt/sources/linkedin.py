"""Optional Octo helper to copy *your own* LinkedIn profile text for `jt profile import`.

Job collection from LinkedIn is intentionally not supported — automated job search/viewing
risks account restrictions.
"""
from __future__ import annotations

import random
import time

from ..browser.octo import octo_page

BLOCK_MARKERS = ("checkpoint", "authwall", "/login", "/uas/", "captcha", "challenge")


class LinkedInBlocked(RuntimeError):
    pass


def _pause(delay: list[float]) -> None:
    time.sleep(random.uniform(delay[0], delay[1]))


def _check_blocked(page) -> None:
    url = page.url.lower()
    if any(m in url for m in BLOCK_MARKERS):
        raise LinkedInBlocked(
            f"LinkedIn showed a checkpoint/login page ({page.url}). Open the Octo profile, "
            "resolve it manually, then rerun later."
        )


def fetch_profile_text(url: str = "https://www.linkedin.com/in/me/") -> str:
    """Visible text of your own LinkedIn profile page, for `jt profile import --linkedin-text`."""
    with octo_page() as page:
        page.goto(url, wait_until="domcontentloaded")
        _pause([3, 5])
        _check_blocked(page)
        for _ in range(6):
            page.mouse.wheel(0, 2000)
            time.sleep(0.8)
        return page.inner_text("main")
