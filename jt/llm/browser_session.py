"""Start the local bridge if needed and open ChatGPT or Claude in the user's Chrome.

Same idea as Brightstar: reuse a logged-in tab (or create one) through the
extension. The extension pulls the bridge URL and token from
http://127.0.0.1:<port+1>/ext-config — no popup paste.
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

from .. import config
from .client import BridgeClient
from .errors import LLMError

_BROWSER = frozenset({"claude", "gpt"})


def prepare_browser(provider: str, url: str | None = None, *, timeout: float = 45) -> str:
    """Open the provider window when a browser task needs it.

    Returns 'opened' when the extension accepted the request, or 'skipped' when
    this process should not touch the browser (tests, or JT_AUTO_OPEN=0).
    """
    if provider not in _BROWSER:
        return "skipped"
    if os.environ.get("PYTEST_CURRENT_TEST") or os.environ.get("JT_AUTO_OPEN", "1") == "0":
        return "skipped"
    if config.bridge_token() in ("", "change-me"):
        raise LLMError("Set JT_BRIDGE_TOKEN in .env first (run: jt init).", "bad_token")

    deadline = time.time() + timeout
    if not _bridge_listening():
        _spawn_bridge()
    _wait_config_http(deadline)

    while time.time() < deadline:
        status = _status()
        if status and status.get("extension_connected"):
            _open(provider, url)
            return "opened"
        time.sleep(0.5)

    raise LLMError(
        "ChatGPT/Claude did not connect. Open http://localhost:8501 in the Chrome "
        "where you are logged into ChatGPT or Claude (with BrightStar AI Trainer Copilot installed), "
        "wait a few seconds for it to attach, then try again.",
        "no_extension",
    )


def _bridge_listening() -> bool:
    try:
        with socket.create_connection((config.bridge_host(), config.bridge_port()), 0.4):
            return True
    except OSError:
        return False


def _wait_config_http(deadline: float) -> None:
    """Wait until the extension can read /ext-config (bridge HTTP on port+1)."""
    port = config.bridge_port() + 1
    url = f"http://127.0.0.1:{port}/ext-config"
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=0.6) as resp:
                if resp.status == 200:
                    return
        except (urllib.error.URLError, TimeoutError, OSError):
            pass
        time.sleep(0.3)


def _status() -> dict | None:
    try:
        with BridgeClient() as bc:
            return bc.status()
    except LLMError:
        return None


def _open(provider: str, url: str | None) -> None:
    with BridgeClient() as bc:
        bc.open_provider(provider, url)


def _spawn_bridge() -> None:
    flags = 0
    if os.name == "nt":
        flags = subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen(
        [sys.executable, "-m", "jt.cli", "bridge", "serve"],
        cwd=str(config.ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=flags,
    )
