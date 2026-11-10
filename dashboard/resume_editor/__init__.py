"""Word-like in-dashboard resume editor (Streamlit custom component, no build step)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit.components.v1 as components

_FRONTEND = Path(__file__).resolve().parent / "frontend"
_resume_doc_editor = components.declare_component("resume_doc_editor", path=str(_FRONTEND))


def resume_doc_editor(
    *,
    html: str,
    edit_id: str,
    height: int = 780,
    key: str | None = None,
) -> dict[str, Any] | None:
    """Show a contenteditable resume page with a light Word-style toolbar.

    Returns ``{"action": "save"|"cancel", "edit_id": str, "html": str}`` when the
    user clicks Save/Cancel; otherwise ``None``.
    """
    return _resume_doc_editor(
        html=html or "",
        edit_id=edit_id or "",
        height=height,
        key=key,
        default=None,
    )
