"""Call the vendored Bid bot template engine (Node) from Python."""
from __future__ import annotations

import json
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Any

VENDOR = Path(__file__).resolve().parent / "vendor"
CLI = VENDOR / "render_cli.mjs"
DEFAULT_TEMPLATE_ID = "ats-modern"

# Mirror of Bid bot BUILTIN_TEMPLATES when Node is unavailable.
_FALLBACK_TEMPLATES = [
    {"id": "times-classic", "label": "1 · US Times Classic", "description": "Times serif · traditional US senior resume."},
    {"id": "ats-modern", "label": "2 · ATS Calibri", "description": "Calibri · Workday/Taleo-safe · Fortune 500 ATS."},
    {"id": "sv-senior", "label": "3 · Silicon Valley", "description": "Arial · experience-first · Big Tech."},
    {"id": "nyc-finance", "label": "4 · NYC Finance", "description": "Navy header · banks and fintech."},
    {"id": "harvard-rule", "label": "5 · Harvard Rule", "description": "Garamond · centered name · double rule."},
    {"id": "skills-first", "label": "6 · Skills-First Technical", "description": "Arial · inverted-bar headings · skills table."},
    {"id": "modern-sans", "label": "7 · Modern US Sans", "description": "Segoe · teal accent · product/SaaS."},
    {"id": "executive-navy", "label": "8 · Executive Navy", "description": "Navy sidebar · executive layout."},
    {"id": "orange-banner", "label": "9 · Orange Banner", "description": "Calibri · bronze section bars."},
    {"id": "date-rail", "label": "10 · Date Rail", "description": "Dates on the title line."},
]


def node_bin() -> str | None:
    return shutil.which("node")


def _run(args: list[str], *, stdin: str | None = None, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    node = node_bin()
    if not node:
        raise RuntimeError("Node.js is required to render Bid bot resume templates")
    if not CLI.exists():
        raise RuntimeError(f"Missing template CLI: {CLI}")
    return subprocess.run(
        [node, str(CLI), *args],
        input=stdin,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=timeout,
        cwd=str(VENDOR),
        check=False,
    )


@lru_cache(maxsize=1)
def list_templates() -> dict[str, Any]:
    """Return {default, templates:[{id,label,description}]}."""
    try:
        proc = _run(["list"])
        if proc.returncode == 0 and proc.stdout.strip():
            return json.loads(proc.stdout)
    except Exception:  # noqa: BLE001
        pass
    return {"default": DEFAULT_TEMPLATE_ID, "templates": list(_FALLBACK_TEMPLATES)}


def template_ids() -> set[str]:
    return {t["id"] for t in list_templates().get("templates", [])}


def resolve_template_id(template_id: str | None) -> str:
    tid = (template_id or "").strip() or DEFAULT_TEMPLATE_ID
    ids = template_ids()
    return tid if tid in ids else DEFAULT_TEMPLATE_ID


def render_template_html(
    data: dict[str, Any],
    *,
    template_id: str | None = None,
    accent_id: str | None = None,
) -> str:
    """Render Bid bot template HTML from a template-shaped resume dict."""
    tid = resolve_template_id(template_id)
    args = ["render", "--template", tid]
    if accent_id:
        args.extend(["--accent", str(accent_id)])
    proc = _run(args, stdin=json.dumps(data, ensure_ascii=False))
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "template render failed").strip()
        raise RuntimeError(err)
    html = proc.stdout
    if not html or "<html" not in html.lower():
        raise RuntimeError("template render returned empty HTML")
    return html
