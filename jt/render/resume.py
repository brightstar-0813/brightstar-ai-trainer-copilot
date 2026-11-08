"""Render a ResumeContent to DOCX, HTML and PDF.

HTML uses Bid bot *styles* (fonts/colors/header chrome) on a fixed teaching-resume
structure — templates do not rewrite section order or labels.
"""
from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt, RGBColor

from ..schemas import ResumeContent
from .styles import DEFAULT_STYLE_ID, render_styled_html, resolve_style_id


def render_html(
    r: ResumeContent,
    *,
    template_id: str | None = None,
    accent_id: str | None = None,
) -> str:
    """Style-only HTML: fixed sections + selected visual theme."""
    return render_styled_html(r, style_id=template_id, accent_id=accent_id)


def _heading(doc: Document, text: str) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after = Pt(2)
    run = p.add_run(text.upper())
    run.bold = True
    run.font.size = Pt(10.5)
    run.font.color.rgb = RGBColor(0x22, 0x22, 0x22)
    pPr = p._p.get_or_add_pPr()
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    border = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    for k, v in (("w:val", "single"), ("w:sz", "6"), ("w:space", "1"), ("w:color", "999999")):
        bottom.set(qn(k), v)
    border.append(bottom)
    pPr.append(border)


def _bullets(doc: Document, items: list[str]) -> None:
    for b in items:
        p = doc.add_paragraph(style="List Bullet")
        p.paragraph_format.space_after = Pt(0)
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        p.add_run(b).font.size = Pt(10)


def render_docx(r: ResumeContent, path: Path) -> None:
    doc = Document()
    sec = doc.sections[0]
    sec.left_margin = sec.right_margin = Inches(0.65)
    sec.top_margin = sec.bottom_margin = Inches(0.55)
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(10)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    run = p.add_run(r.name)
    run.bold = True
    run.font.size = Pt(20)
    p.paragraph_format.space_after = Pt(0)
    doc.add_paragraph(r.headline).paragraph_format.space_after = Pt(0)
    c = doc.add_paragraph(r.contact)
    if c.runs:
        c.runs[0].font.size = Pt(9)

    if r.summary:
        _heading(doc, "Professional Summary")
        sp = doc.add_paragraph(r.summary)
        sp.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    from .skills import normalize_skill_groups

    groups = normalize_skill_groups(list(r.skill_groups or []), flat=list(r.skills or []))
    if groups:
        _heading(doc, "Skills")
        for g in groups:
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(2)
            p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            run = p.add_run(f"{g.category}: ")
            run.bold = True
            p.add_run(" · ".join(g.items))
    elif r.skills:
        _heading(doc, "Skills")
        sp = doc.add_paragraph(" · ".join(r.skills))
        sp.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    if r.experience:
        _heading(doc, "Professional Experience")
        for e in r.experience:
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.space_before = Pt(4)
            p.add_run(e.title).bold = True
            dates = f"{e.start} - {e.end}" if e.end else e.start
            if dates.strip():
                p.add_run(f"    {dates}")
            if e.company:
                co = doc.add_paragraph(e.company)
                if co.runs:
                    co.runs[0].bold = True
                co.paragraph_format.space_after = Pt(0)
                co.paragraph_format.space_before = Pt(0)
            if e.location:
                loc = doc.add_paragraph(e.location)
                if loc.runs:
                    loc.runs[0].italic = True
                loc.paragraph_format.space_after = Pt(0)
            _bullets(doc, e.bullets)
    if r.projects:
        _heading(doc, "Selected Projects")
        for pr in r.projects:
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(1)
            p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            p.add_run(pr.name).bold = True
            p.add_run((f" ({pr.link})" if pr.link else "") + f": {pr.description}")
    if r.education:
        _heading(doc, "Education")
        for e in r.education:
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(0)
            label = e.degree + (f", {e.field}" if e.field else "")
            p.add_run(f"{label} - {e.school}".strip(" -")).bold = True
            if e.dates:
                p.add_run(f"    {e.dates}")
            _bullets(doc, e.details)
    if r.licenses:
        _heading(doc, "Licenses")
        _bullets(doc, r.licenses)
    if r.certifications:
        _heading(doc, "Certifications")
        _bullets(doc, r.certifications)
    if r.additional:
        _heading(doc, "Languages & Awards")
        _bullets(doc, r.additional)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(path))


def render_pdf(html: str, path: Path) -> bool:
    """Print HTML to PDF with headless Chromium/Chrome. Returns False if no browser is available."""
    from playwright.sync_api import sync_playwright

    path.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = None
        for kwargs in ({}, {"channel": "chrome"}, {"channel": "msedge"}):
            try:
                browser = p.chromium.launch(headless=True, **kwargs)
                break
            except Exception:  # noqa: BLE001
                continue
        if browser is None:
            return False
        page = browser.new_page()
        page.set_content(html, wait_until="load")
        page.pdf(path=str(path), format="Letter", print_background=True, prefer_css_page_size=True)
        browser.close()
    return True


def render_all(
    r: ResumeContent,
    outdir: Path,
    stem: str = "resume",
    *,
    template_id: str | None = None,
    accent_id: str | None = None,
) -> dict[str, str]:
    outdir.mkdir(parents=True, exist_ok=True)
    docx_path, pdf_path, html_path = outdir / f"{stem}.docx", outdir / f"{stem}.pdf", outdir / f"{stem}.html"
    render_docx(r, docx_path)
    html = render_html(r, template_id=template_id, accent_id=accent_id)
    html_path.write_text(html, encoding="utf-8")
    ok = render_pdf(html, pdf_path)
    return {
        "docx": str(docx_path),
        "html": str(html_path),
        "pdf": str(pdf_path) if ok else "",
        "template_id": resolve_style_id(template_id) if template_id else DEFAULT_STYLE_ID,
    }
