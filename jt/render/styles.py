"""Resume styles: Bid bot look-and-feel with a fixed teaching-resume structure.

Templates change fonts, colors, and header chrome only. Section order and labels
stay the same for every style:
  Professional Summary → Core Competencies → Professional Experience →
  Representative projects → Education → Licenses → Certifications → Languages & Awards
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from html import escape
from typing import Any

from ..schemas import ResumeContent

DEFAULT_STYLE_ID = "ats-modern"

# Bump when header/section spacing or project heading labels change so saved
# teaching-model HTML is rewritten on open.
RESUME_LAYOUT_VERSION = 3
RESUME_LAYOUT_MARKER = f"/* jt-resume-layout:{RESUME_LAYOUT_VERSION} */"

# Shared layout for content sections (independent of Bid bot template.render).
_BASE_CSS = f"""
  {RESUME_LAYOUT_MARKER}
  * {{ box-sizing: border-box; }}
  html {{ color-scheme: light; background: #fff; }}
  html, body {{
    margin: 0; padding: 0;
    background: #fff;
    color: var(--ink, #111);
    font-family: var(--font, Calibri, Arial, Helvetica, sans-serif);
    font-size: var(--size, 10.5pt);
    line-height: 1.32;
  }}
  .resume {{ width: 100%; background: #fff; }}
  /* Keep header→summary tight: no stacked top/bottom pads between them. */
  .body {{ padding: var(--body-pad, 0 14mm 12mm); }}
  header.top, header.banner {{
    padding: var(--header-pad, 6mm 14mm 0);
  }}
  header.top {{
    margin: 0;
    border-bottom: none;
  }}
  header.banner {{
    background: var(--banner-bg, #0b1f3a);
    color: var(--banner-ink, #f4f6f8);
  }}
  h1 {{
    margin: 0;
    font-size: var(--name-size, 20pt);
    font-weight: 700;
    line-height: 1.1;
    color: var(--name-color, var(--accent, #1f4e79));
    letter-spacing: 0.2px;
  }}
  header.banner h1 {{ color: var(--banner-name, #fff); }}
  .headline {{
    margin: 2px 0 0;
    font-size: 11pt;
    font-weight: 600;
    color: var(--headline-color, #222);
  }}
  header.banner .headline {{ color: var(--banner-headline, #d4b56a); }}
  .contact {{
    margin: 2px 0 0;
    font-size: 9.5pt;
    color: var(--contact-color, #555);
  }}
  header.banner .contact {{ color: var(--banner-contact, #c5d0dc); }}
  .contact a {{ color: inherit; }}
  section {{ margin: 0 0 4px; }}
  h2 {{
    margin: 4px 0 2px;
    padding: 0 0 1px;
    font-size: var(--h2-size, 10.5pt);
    font-weight: 700;
    letter-spacing: var(--h2-track, 0.8px);
    text-transform: uppercase;
    color: var(--accent, #1f4e79);
    border-bottom: var(--h2-rule, 2px solid var(--accent, #1f4e79));
  }}
  .body > section:first-child {{ margin-top: 0; }}
  .body > section:first-child h2 {{ margin-top: 0; }}
  .body p,
  .body li,
  .skill-row,
  .project-item {{ text-align: justify; }}
  p {{ margin: 0 0 4px; }}
  .skills {{ margin: 0; }}
  .skills-stack {{ margin: 0; }}
  .skill-row {{ margin: 0 0 4px; font-size: 0.98em; }}
  .skill-cat {{
    font-weight: 700;
    color: var(--accent, #1f4e79);
    margin-right: 4px;
  }}
  .skill-items {{ color: var(--ink, #111); }}
  .row {{
    display: flex;
    justify-content: space-between;
    gap: 12px;
    align-items: baseline;
    font-weight: 700;
    margin-top: 6px;
  }}
  .row .role {{ font-weight: 700; }}
  .row .dates {{
    flex: 0 0 auto;
    white-space: nowrap;
    font-weight: 600;
    color: var(--muted, #4a5a6c);
    font-size: 9.5pt;
  }}
  .company {{
    margin: 0 0 1px;
    font-weight: 600;
    color: var(--ink, #111);
  }}
  .sub {{
    margin: 0 0 2px;
    font-style: italic;
    color: var(--muted, #4a5a6c);
    font-size: 9.5pt;
  }}
  ul {{ margin: 2px 0 0; padding-left: 16px; }}
  li {{ margin: 0 0 2px; }}
  .project-item {{ margin: 0 0 4px; }}
  @page {{ size: Letter; margin: 0.5in 0.55in; }}
"""


@dataclass(frozen=True)
class ResumeStyle:
    id: str
    label: str
    description: str
    chrome: str  # "top" | "banner"
    vars: dict[str, str]


STYLES: list[ResumeStyle] = [
    ResumeStyle(
        "times-classic",
        "1 · US Times Classic",
        "Times serif · traditional senior resume.",
        "top",
        {
            "--font": 'Times New Roman, Times, Georgia, serif',
            "--accent": "#1a1a1a",
            "--name-color": "#000",
            "--h2-rule": "1px solid #000",
            "--header-rule": "1px solid #000",
            "--size": "10.5pt",
        },
    ),
    ResumeStyle(
        "ats-modern",
        "2 · ATS Calibri",
        "Calibri · Workday/Taleo-safe · Fortune 500 ATS.",
        "top",
        {
            "--font": "Calibri, Arial, Helvetica, sans-serif",
            "--accent": "#1f4e79",
            "--name-color": "#1f4e79",
            "--header-rule": "3px solid #1f4e79",
            "--h2-rule": "2.5px solid #1f4e79",
            "--size": "11pt",
        },
    ),
    ResumeStyle(
        "sv-senior",
        "3 · Silicon Valley",
        "Arial · experience-first Big Tech look.",
        "top",
        {
            "--font": "Arial, Helvetica, sans-serif",
            "--accent": "#111827",
            "--name-color": "#111827",
            "--header-rule": "2px solid #111827",
            "--h2-rule": "1px solid #d1d5db",
            "--size": "10pt",
        },
    ),
    ResumeStyle(
        "nyc-finance",
        "4 · NYC Finance",
        "Navy header band · Calibri · banks and fintech.",
        "banner",
        {
            "--font": 'Calibri, "Segoe UI", Arial, Helvetica, sans-serif',
            "--accent": "#0b1f3a",
            "--banner-bg": "#0b1f3a",
            "--banner-headline": "#d4b56a",
            "--h2-rule": "2px solid #d4b56a",
            "--size": "10.2pt",
            "--header-pad": "8mm 14mm 0",
            "--body-pad": "3mm 14mm 12mm",
        },
    ),
    ResumeStyle(
        "harvard-rule",
        "5 · Harvard Rule",
        "Garamond · centered name · double rule.",
        "top",
        {
            "--font": "Garamond, Georgia, 'Times New Roman', serif",
            "--accent": "#1c1917",
            "--name-color": "#1c1917",
            "--name-size": "22pt",
            "--header-rule": "3px double #1c1917",
            "--h2-rule": "1px solid #1c1917",
            "--h2-track": "1.4px",
            "--size": "10.5pt",
        },
    ),
    ResumeStyle(
        "skills-first",
        "6 · Skills-First Technical",
        "Arial · inverted-bar headings · skills table.",
        "top",
        {
            "--font": "Arial, Helvetica, sans-serif",
            "--accent": "#0A2540",
            "--name-color": "#111111",
            "--header-rule": "2.5px solid #0A2540",
            "--h2-rule": "none",
            "--size": "10pt",
        },
    ),
    ResumeStyle(
        "modern-sans",
        "7 · Modern US Sans",
        "Segoe · teal accent · product/SaaS.",
        "top",
        {
            "--font": '"Segoe UI", Calibri, Arial, sans-serif',
            "--accent": "#0d7377",
            "--name-color": "#0f172a",
            "--header-rule": "none",
            "--h2-rule": "none",
            "--contact-color": "#0d7377",
            "--size": "10.2pt",
        },
    ),
    ResumeStyle(
        "executive-navy",
        "8 · Executive Navy",
        "Navy + gold accents · executive header.",
        "banner",
        {
            "--font": 'Calibri, "Segoe UI", Arial, Helvetica, sans-serif',
            "--accent": "#071e38",
            "--banner-bg": "#071e38",
            "--banner-headline": "#ffe08a",
            "--h2-rule": "2px solid #f5c542",
            "--size": "10pt",
            "--header-pad": "10mm 14mm 0",
            "--body-pad": "3mm 14mm 12mm",
        },
    ),
    ResumeStyle(
        "orange-banner",
        "9 · Orange Banner",
        "Calibri · bronze section banners.",
        "top",
        {
            "--font": "Calibri, Arial, Helvetica, sans-serif",
            "--accent": "#8A5A2B",
            "--name-color": "#7b8490",
            "--header-rule": "none",
            "--h2-rule": "none",
            "--size": "10.5pt",
        },
    ),
    ResumeStyle(
        "date-rail",
        "10 · Date Rail",
        "Clean date emphasis · full-width role text.",
        "top",
        {
            "--font": 'Calibri, "Segoe UI", Arial, sans-serif',
            "--accent": "#5b6770",
            "--name-color": "#1f2937",
            "--header-rule": "2px solid #5b6770",
            "--h2-rule": "1px solid #cbd5e1",
            "--size": "10.2pt",
        },
    ),
]

# Saved prefs from older builds still resolve.
_STYLE_ID_ALIASES = {
    "brief-grid": "skills-first",
}

_STYLES_BY_ID = {s.id: s for s in STYLES}

# Optional accent overrides (same ids as Bid bot).
_ACCENTS = {
    "blue": "#1F4E79",
    "navy": "#0A2540",
    "slate": "#5B6770",
    "teal": "#0D7377",
    "green": "#1E7A46",
    "burgundy": "#8B2332",
    "purple": "#5B2C6F",
    "bronze": "#8A5A2B",
    "olive": "#3F6212",
    "crimson": "#9F1239",
    "indigo": "#312E81",
    "charcoal": "#27272A",
}

_HEX_RE = re.compile(r"^#?[0-9A-Fa-f]{6}$")


def list_accents() -> list[dict[str, str]]:
    return [{"id": k, "hex": v} for k, v in _ACCENTS.items()]


def resolve_accent_color(accent: str | None, *, fallback: str = "") -> str:
    """Named Bid-bot accent id or raw #RRGGBB → hex, else fallback/empty."""
    raw = (accent or "").strip()
    if not raw:
        return fallback
    if _HEX_RE.fullmatch(raw):
        return raw if raw.startswith("#") else f"#{raw}"
    return _ACCENTS.get(raw.lower(), fallback)


def list_styles() -> dict[str, Any]:
    return {
        "default": DEFAULT_STYLE_ID,
        "templates": [
            {"id": s.id, "label": s.label, "description": s.description} for s in STYLES
        ],
        "accents": list_accents(),
    }


def resolve_style_id(style_id: str | None) -> str:
    tid = (style_id or "").strip() or DEFAULT_STYLE_ID
    tid = _STYLE_ID_ALIASES.get(tid, tid)
    return tid if tid in _STYLES_BY_ID else DEFAULT_STYLE_ID


def get_style(style_id: str | None) -> ResumeStyle:
    return _STYLES_BY_ID[resolve_style_id(style_id)]


def _contact_html(r: ResumeContent) -> str:
    return escape(r.contact or "")


def _skills_html(r: ResumeContent, *, as_table: bool = False) -> str:
    from .skills import normalize_skill_groups

    groups = normalize_skill_groups(list(r.skill_groups or []), flat=list(r.skills or []))
    if not groups:
        return ""
    if as_table:
        rows = []
        for g in groups:
            items = ", ".join(escape(i) for i in g.items)
            rows.append(
                "<tr>"
                f'<td class="skill-cat">{escape(g.category)}</td>'
                f'<td class="skill-items">{items}</td>'
                "</tr>"
            )
        return (
            '<table class="skills-table" role="table">'
            "<thead><tr><th scope=\"col\">Category</th>"
            "<th scope=\"col\">Technologies / Skills</th></tr></thead>"
            f"<tbody>\n{chr(10).join(rows)}\n</tbody></table>"
        )
    rows = []
    for g in groups:
        items = " · ".join(escape(i) for i in g.items)
        rows.append(
            f'<div class="skill-row"><span class="skill-cat">{escape(g.category)}:</span> '
            f'<span class="skill-items">{items}</span></div>'
        )
    return f'<div class="skills-stack">\n{chr(10).join(rows)}\n</div>'


def _h2(label: str, *, style_id: str) -> str:
    """Section title markup — orange-banner uses bar vs plain chrome."""
    if style_id == "orange-banner":
        if label in {"Professional Experience", "Education"}:
            return f'<h2 class="bar"><span>{escape(label)}</span></h2>'
        return f'<h2 class="plain">{escape(label)}</h2>'
    return f"<h2>{escape(label)}</h2>"


def _section_body(r: ResumeContent, *, style_id: str) -> str:
    parts: list[str] = []
    table_skills = style_id in {"skills-first", "orange-banner"}
    if r.summary:
        parts.append(
            f"<section>{_h2('Professional Summary', style_id=style_id)}"
            f"<p>{escape(r.summary)}</p></section>"
        )
    skill_block = _skills_html(r, as_table=table_skills)
    if skill_block:
        parts.append(f"<section>{_h2('Skills', style_id=style_id)}{skill_block}</section>")
    if r.experience:
        parts.append(f"<section>{_h2('Professional Experience', style_id=style_id)}")
        for e in r.experience:
            dates = f"{e.start} - {e.end}" if e.end else e.start
            parts.append(
                '<article class="job">'
                f'<div class="row"><span class="role">{escape(e.title)}</span>'
                f'<span class="dates">{escape(dates)}</span></div>'
                f'<div class="company">{escape(e.company)}</div>'
            )
            if e.location:
                parts.append(f'<div class="sub">{escape(e.location)}</div>')
            if e.bullets:
                parts.append("<ul>" + "".join(f"<li>{escape(b)}</li>" for b in e.bullets) + "</ul>")
            parts.append("</article>")
        parts.append("</section>")
    if r.projects:
        parts.append(f"<section>{_h2('Representative projects', style_id=style_id)}")
        for p in r.projects:
            link = f" ({escape(p.link)})" if p.link else ""
            parts.append(
                f'<p class="project-item"><b>{escape(p.name)}</b>{link}: {escape(p.description)}</p>'
            )
        parts.append("</section>")
    if r.education:
        parts.append(f"<section>{_h2('Education', style_id=style_id)}")
        for e in r.education:
            label = e.degree + (f", {e.field}" if e.field else "")
            parts.append(
                f'<div class="row"><span>{escape(label)} - {escape(e.school)}</span>'
                f'<span class="dates">{escape(e.dates)}</span></div>'
            )
            if e.details:
                parts.append("<ul>" + "".join(f"<li>{escape(d)}</li>" for d in e.details) + "</ul>")
        parts.append("</section>")
    if r.licenses:
        parts.append(
            f"<section>{_h2('Licenses', style_id=style_id)}<ul>"
            + "".join(f"<li>{escape(c)}</li>" for c in r.licenses)
            + "</ul></section>"
        )
    if r.certifications:
        parts.append(
            f"<section>{_h2('Certifications', style_id=style_id)}<ul>"
            + "".join(f"<li>{escape(c)}</li>" for c in r.certifications)
            + "</ul></section>"
        )
    if r.additional:
        parts.append(
            f"<section>{_h2('Languages & Awards', style_id=style_id)}<ul>"
            + "".join(f"<li>{escape(a)}</li>" for a in r.additional)
            + "</ul></section>"
        )
    return "\n".join(parts)


def _vars_css(style: ResumeStyle, accent_id: str | None) -> str:
    vals = dict(style.vars)
    accent = resolve_accent_color(accent_id)
    if accent:
        vals["--accent"] = accent
        if style.chrome == "banner":
            vals["--banner-bg"] = accent
        elif style.id == "skills-first":
            vals["--header-rule"] = f"2.5px solid {accent}"
        elif style.id == "modern-sans":
            vals["--contact-color"] = accent
        elif style.id == "orange-banner":
            pass  # keep gray name; accent only tints section chrome
        elif style.id != "date-rail":
            vals["--name-color"] = accent
            vals["--header-rule"] = f"3px solid {accent}"
            vals["--h2-rule"] = f"2px solid {accent}"
    lines = [f"  {k}: {v};" for k, v in vals.items()]
    return ":root {\n" + "\n".join(lines) + "\n}\n"


_STYLE_CHROME_CSS = {
    "skills-first": """
  header.top { border-bottom: var(--header-rule, 2.5px solid var(--accent)); padding-bottom: 4px; }
  h1 { text-transform: uppercase; letter-spacing: 0.4px; color: #111; }
  h2 {
    background: var(--accent);
    color: #fff;
    border-bottom: none;
    padding: 3px 8px;
    margin: 4px 0 2px;
  }
  .skills-table {
    width: 100%;
    border-collapse: collapse;
    table-layout: fixed;
    font-size: 0.95em;
  }
  .skills-table th, .skills-table td {
    border: 1px solid var(--accent);
    padding: 3px 6px;
    vertical-align: top;
    text-align: left;
  }
  .skills-table th { background: #f2f2f2; font-weight: 700; }
  .skills-table .skill-cat { width: 32%; font-weight: 700; background: #f4f4f4; color: #111; }
""",
    "modern-sans": """
  header.top { border-bottom: none; }
  h1 { color: #0f172a; letter-spacing: -0.5px; }
  .contact { color: var(--contact-color, var(--accent)); }
  .contact a { color: inherit; }
  .body section {
    padding-left: 10px;
    border-left: 3px solid var(--accent);
  }
  h2 {
    border-bottom: none;
    color: var(--accent);
    letter-spacing: 1.5px;
  }
  .skill-cat { color: var(--accent); }
""",
    "orange-banner": """
  header.top { border-bottom: none; }
  h1 {
    text-transform: uppercase;
    letter-spacing: 1.4px;
    color: var(--name-color, #7b8490);
    font-weight: 600;
  }
  h2.plain {
    margin: 4px 0 4px;
    padding: 0;
    border-bottom: none;
    color: var(--accent);
    letter-spacing: 0.6px;
  }
  h2.bar {
    display: flex;
    align-items: center;
    margin: 12px 0 8px;
    padding: 0;
    border-bottom: none;
    color: #fff;
    letter-spacing: 0.8px;
  }
  h2.bar span {
    background: var(--accent);
    padding: 3px 12px 3px 8px;
  }
  h2.bar::after {
    content: "";
    flex: 1;
    height: 2px;
    background: var(--accent);
  }
  .skills-table {
    width: 100%;
    border-collapse: collapse;
    table-layout: fixed;
    margin: 2px 0 0;
    font-size: 0.98em;
  }
  .skills-table th, .skills-table td {
    padding: 2px 8px 2px 0;
    vertical-align: top;
    text-align: left;
    border-bottom: 1px solid #e8d5c4;
  }
  .skills-table th {
    font-size: 8.5pt;
    font-weight: 700;
    letter-spacing: 0.4px;
    text-transform: uppercase;
    color: var(--accent);
    border-bottom: 1.5px solid var(--accent);
  }
  .skills-table .skill-cat { width: 28%; font-weight: 700; color: #333; }
""",
}


def render_styled_html(
    r: ResumeContent,
    *,
    style_id: str | None = None,
    accent_id: str | None = None,
) -> str:
    """Fixed teaching-resume structure + selected visual style."""
    style = get_style(style_id)
    name = escape(r.name or "Resume")
    headline = escape(r.headline or "")
    contact = _contact_html(r)
    header_cls = "banner" if style.chrome == "banner" else "top"
    header = f"""<header class="{header_cls}">
  <h1>{name}</h1>
  {f'<p class="headline">{headline}</p>' if headline else ""}
  {f'<p class="contact">{contact}</p>' if contact else ""}
</header>"""
    body = _section_body(r, style_id=style.id)
    css = _vars_css(style, accent_id) + _BASE_CSS
    # harvard centered name
    if style.id == "harvard-rule":
        css += "\n  header.top { text-align: center; }\n  header.top .contact { text-align: center; }\n"
    css += _STYLE_CHROME_CSS.get(style.id, "")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>{name} - Resume</title>
<style>
{css}
</style></head>
<body>
<main class="resume" data-style="{escape(style.id)}">
{header}
<div class="body">
{body}
</div>
</main>
</body></html>"""
