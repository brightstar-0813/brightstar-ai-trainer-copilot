"""Pull a JSON value out of a chat reply."""
from __future__ import annotations

import json
import re

_FENCE = re.compile(r"```(?:json|JSON)?\s*\n(.*?)```", re.S)


def _balanced_candidates(text: str):
    """Yield every top-level balanced {...} or [...] substring, last first."""
    found = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch in "{[":
            close = "}" if ch == "{" else "]"
            depth, j, in_str, esc = 0, i, False, False
            while j < n:
                c = text[j]
                if in_str:
                    if esc:
                        esc = False
                    elif c == "\\":
                        esc = True
                    elif c == '"':
                        in_str = False
                elif c == '"':
                    in_str = True
                elif c == ch:
                    depth += 1
                elif c == close:
                    depth -= 1
                    if depth == 0:
                        found.append(text[i:j + 1])
                        i = j
                        break
                j += 1
        i += 1
    return reversed(found)


def extract_json(text: str):
    """Return the last parseable JSON value in `text` (fenced block preferred)."""
    for block in reversed(_FENCE.findall(text)):
        try:
            return json.loads(block.strip())
        except json.JSONDecodeError:
            continue
    for cand in _balanced_candidates(text):
        try:
            return json.loads(cand)
        except json.JSONDecodeError:
            continue
    raise ValueError("no valid JSON found in reply")
