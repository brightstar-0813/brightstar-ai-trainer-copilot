"""AI Trainer Job Copilot dashboard. Run: jt dashboard   (or: streamlit run dashboard/app.py)

Long LLM tasks are launched as background `jt` subprocesses so the page never blocks; their logs are shown live.
"""
from __future__ import annotations

import importlib
import json
import os
import re
import shutil
import subprocess
import sys
import uuid
from contextlib import contextmanager
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import yaml
from sqlmodel import select

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from jt import config, db  # noqa: E402
from jt.llm.browser_session import prepare_browser  # noqa: E402
from jt.llm.client import status_summary  # noqa: E402
from jt.llm.errors import LLMError  # noqa: E402
import jt.llm.prefs as _prefs  # noqa: E402
import jt.schemas as _schemas  # noqa: E402

importlib.reload(_prefs)
importlib.reload(_schemas)
from jt.llm.prefs import (  # noqa: E402
    BROWSER_LABELS,
    BROWSERS,
    ENGINE_LABELS,
    ENGINES,
    load_prefs,
    preferred_resume_accent,
    preferred_resume_template,
    save_prefs,
)
from jt.models import Application, GapQuestion, Job, JobAnalysis, LLMCall, TailoredResume, utcnow  # noqa: E402
from jt.pipelines import analyze as an  # noqa: E402
from jt.pipelines import profile as pf  # noqa: E402
from jt.pipelines import samples as sm  # noqa: E402
from jt.pipelines import tailor as tl  # noqa: E402
from jt.render.resume import render_docx, render_html  # noqa: E402
from jt.render.styles import get_style, list_accents, list_styles, resolve_accent_color  # noqa: E402
from jt.schemas import (  # noqa: E402
    MasterProfile,
    SuggestedBenchmark,
    get_active_profile,
    list_profiles,
    profile_example_path,
    profile_path,
    set_active_profile,
    validate_slug,
)

LOGS = config.DATA_DIR / "logs"
STATUSES = ["new", "shortlisted", "applied", "rejected", "ignored"]
STAGES = ["applied", "assessment", "interview", "offer", "rejected"]

st.set_page_config(
    page_title="AI Trainer Job Copilot",
    page_icon=":material/work:",
    layout="wide",
    initial_sidebar_state="expanded",
)


def inject_shell() -> None:
    """App chrome: slim sidebar + header tabs instead of sidebar menu rows."""
    st.markdown(
        """
<style>
  [data-testid="stSidebar"] {
    border-right: 1px solid color-mix(in srgb, var(--text-color) 10%, transparent);
  }
  [data-testid="stSidebar"] [data-testid="stSidebarContent"] {
    padding: 1.15rem 0.85rem 1.25rem;
  }
  .jt-brand {
    display: flex;
    gap: 0.7rem;
    align-items: center;
    padding: 0.1rem 0.35rem 0.95rem;
  }
  .jt-mark {
    width: 2rem;
    height: 2rem;
    border-radius: 7px;
    display: grid;
    place-items: center;
    font-size: 0.78rem;
    font-weight: 700;
    letter-spacing: -0.03em;
    color: #fff;
    background: var(--primary-color, #4c6fff);
  }
  .jt-name { font-weight: 650; letter-spacing: -0.02em; line-height: 1.15; font-size: 0.95rem; }
  .jt-sub { font-size: 0.72rem; opacity: 0.55; margin-top: 0.12rem; letter-spacing: 0.01em; }
  /* Sticky workspace tabs — sit below Streamlit's absolute toolbar */
  [data-testid="stMain"] .st-key-page {
    position: sticky;
    top: 3.75rem; /* clear absolute stHeader (~56px) */
    z-index: 100;
    width: 100% !important;
    margin: 0 0 1rem;
    padding: 0.35rem 0 0.4rem;
    background: var(--background-color, #0f172a);
    box-shadow: 0 8px 16px -12px color-mix(in srgb, #000 55%, transparent);
  }
  [data-testid="stMain"] .st-key-page [data-testid="stWidgetLabel"] { display: none; }
  [data-testid="stMain"] .st-key-page [data-testid="stRadioGroup"] {
    display: flex !important;
    flex-direction: row !important;
    flex-wrap: nowrap !important;
    justify-content: space-between;
    align-items: stretch;
    gap: 0;
    border-bottom: 1px solid color-mix(in srgb, var(--text-color) 12%, transparent);
    width: 100%;
    overflow: visible;
  }
  [data-testid="stMain"] .st-key-page [data-testid="stRadioGroup"] > div {
    width: auto !important;
    flex: 1 1 0;
    min-width: 0;
  }
  [data-testid="stMain"] .st-key-page [data-testid="stRadioOption"] {
    border-radius: 8px 8px 0 0;
    padding: 0.55rem 0.35rem;
    margin: 0;
    width: 100%;
    cursor: pointer;
    border: 1px solid transparent;
    border-bottom: none;
    box-shadow: inset 0 -2px 0 transparent;
    background: transparent;
    box-sizing: border-box;
  }
  [data-testid="stMain"] .st-key-page [data-testid="stRadioOption"]:hover {
    background: color-mix(in srgb, var(--text-color) 7%, transparent);
  }
  [data-testid="stMain"] .st-key-page [data-testid="stRadioOption"][data-selected="true"] {
    background: color-mix(in srgb, var(--primary-color, #4c6fff) 16%, transparent);
    box-shadow: inset 0 -2px 0 var(--primary-color, #4c6fff);
  }
  [data-testid="stMain"] .st-key-page [data-testid="stRadioOption"] > div > div:first-child,
  [data-testid="stMain"] .st-key-page [data-testid="stRadioOption"] input {
    position: absolute !important;
    width: 1px !important;
    height: 1px !important;
    margin: 0 !important;
    overflow: hidden !important;
    clip: rect(0, 0, 0, 0) !important;
    opacity: 0 !important;
    pointer-events: none !important;
  }
  [data-testid="stMain"] .st-key-page [data-testid="stRadioOption"] p {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.35rem;
    margin: 0;
    font-size: 0.95rem;
    line-height: 1.2;
    white-space: nowrap;
  }
  [data-testid="stMain"] .st-key-page [data-testid="stRadioOption"] [data-testid="stIconMaterial"] {
    font-size: 1.05rem;
    opacity: 0.72;
  }
  [data-testid="stMain"] .st-key-page [data-testid="stRadioOption"][data-selected="true"] p {
    font-weight: 650;
  }
  [data-testid="stMain"] .st-key-page [data-testid="stRadioOption"][data-selected="true"] [data-testid="stIconMaterial"] {
    opacity: 1;
  }
  /* Full-width main pane; clear Streamlit's absolute header */
  [data-testid="stMain"] .block-container {
    padding-top: 4.25rem;
    padding-left: 1.5rem;
    padding-right: 1.5rem;
    max-width: 100%;
  }
  [data-testid="stMain"] h1 {
    font-size: 1.55rem;
    font-weight: 650;
    letter-spacing: -0.03em;
    margin-bottom: 0.15rem;
  }
  [data-testid="stMain"] h2, [data-testid="stMain"] h3 {
    letter-spacing: -0.02em;
  }
  [data-testid="stMetric"] {
    border-radius: 12px;
    padding: 0.85rem 1rem 0.7rem;
  }
  [data-testid="stMetricValue"] {
    font-variant-numeric: tabular-nums;
    letter-spacing: -0.04em;
  }
  [data-testid="stAppDeployButton"] { display: none; }
  footer, [data-testid="stFooter"] { display: none; }
  /* Square icon-only clear / dismiss / delete controls */
  [class*="st-key-"][class*="clear"] button,
  [class*="st-key-"][class*="dismiss"] button,
  [class*="st-key-"][class*="delete_"] button {
    min-width: 2.5rem !important;
    width: 2.5rem !important;
    max-width: 2.5rem !important;
    height: 2.5rem !important;
    min-height: 2.5rem !important;
    padding: 0 !important;
    border-radius: 8px !important;
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
    gap: 0 !important;
    flex: 0 0 2.5rem !important;
  }
  [class*="st-key-"][class*="clear"] button p,
  [class*="st-key-"][class*="dismiss"] button p,
  [class*="st-key-"][class*="delete_"] button p,
  [class*="st-key-"][class*="clear"] button [data-testid="stMarkdownContainer"],
  [class*="st-key-"][class*="dismiss"] button [data-testid="stMarkdownContainer"],
  [class*="st-key-"][class*="delete_"] button [data-testid="stMarkdownContainer"] {
    display: none !important;
  }
  [class*="st-key-"][class*="clear"] button [data-testid="stIconMaterial"],
  [class*="st-key-"][class*="dismiss"] button [data-testid="stIconMaterial"],
  [class*="st-key-"][class*="delete_"] button [data-testid="stIconMaterial"] {
    font-size: 1.2rem !important;
    margin: 0 !important;
    opacity: 0.88;
    line-height: 1 !important;
  }
  [class*="st-key-"][class*="clear"] button:hover [data-testid="stIconMaterial"],
  [class*="st-key-"][class*="dismiss"] button:hover [data-testid="stIconMaterial"],
  [class*="st-key-"][class*="delete_"] button:hover [data-testid="stIconMaterial"] {
    opacity: 1;
  }
</style>
        """,
        unsafe_allow_html=True,
    )


# ----------------------------------------------------------------------------- helpers
def _resume_preview_html(html: str) -> str:
    """Keep resume ink readable inside Streamlit dark theme iframes."""
    inject = (
        "<style>html,body{color-scheme:light!important;background:#fff!important;}"
        "</style>"
    )
    if "</head>" in html:
        return html.replace("</head>", inject + "</head>", 1)
    return inject + html


def _spawn(args: list[str], log_name: str, detached: bool = False) -> subprocess.Popen:
    LOGS.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "NO_COLOR": "1", "TERM": "dumb", "COLUMNS": "140"}
    flags = 0
    if os.name == "nt":
        flags = subprocess.CREATE_NO_WINDOW
        if detached:
            flags |= subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
    return subprocess.Popen([sys.executable, "-m", "jt.cli", *args], cwd=str(ROOT), env=env,
                            stdout=open(LOGS / f"{log_name}.log", "w", encoding="utf-8"),
                            stderr=subprocess.STDOUT, creationflags=flags)


def run_bg(label: str, *args: str) -> None:
    procs = st.session_state.setdefault("procs", {})
    old = procs.get(label)
    if old and old.poll() is None:
        st.warning(f"'{label}' is already running", icon=":material/hourglass_top:")
        return
    procs[label] = _spawn(list(args), label.replace(" ", "_").replace("/", "_"))
    st.toast(f"Started: {label}")


def open_ai_session() -> bool:
    """Open ChatGPT or Claude in this Chrome before a browser LLM job, like Brightstar."""
    from jt.llm.client import resolve_provider, route_provider

    engine = load_prefs().get("engine", "browser")
    if engine in ("openai", "anthropic", "manual"):
        return True
    if engine == "auto" and resolve_provider("auto") in ("openai", "anthropic"):
        return True
    browser = route_provider("browser")
    if browser not in BROWSERS:
        browser = "gpt"
    label = BROWSER_LABELS.get(browser, browser)
    with st.spinner(f"Opening {label} in this browser…"):
        try:
            prepare_browser(browser)
        except LLMError as e:
            st.error(str(e), icon=":material/error:")
            return False
    st.toast(f"{label} session ready")
    return True


def go(page: str) -> None:
    """Switch the header tab page. Use as a button on_click so the radio key can change."""
    st.session_state["page"] = page


def page_header(title: str, lede: str, icon: str) -> None:
    st.title(title, icon=icon)
    st.caption(lede)


def icon_button(
    help: str,
    *,
    icon: str = ":material/delete:",
    key: str,
    disabled: bool = False,
    form: bool = False,
    type: str = "tertiary",
) -> bool:
    """Square icon-only clear/dismiss/delete (trash). Empty label; tooltip is the accessible name."""
    kwargs = {
        "help": help,
        "icon": icon,
        "type": type,
        "width": "content",
        "disabled": disabled,
        "key": key,
    }
    if form:
        return st.form_submit_button("", **kwargs)
    return st.button("", **kwargs)


@st.fragment(run_every=3)
def tasks_panel() -> None:
    procs = st.session_state.get("procs", {})
    if not procs:
        st.caption("No background tasks yet.")
        return
    finished = [label for label, p in procs.items() if p.poll() is not None]
    if finished and icon_button(
        "Clear finished tasks",
        icon=":material/delete_sweep:",
        key="clear_finished_tasks",
    ):
        for label in finished:
            procs.pop(label, None)
        st.rerun()
    for label, p in list(procs.items()):
        code = p.poll()
        if code is None:
            state, icon = "running", ":material/progress_activity:"
        elif code == 0:
            state, icon = "done", ":material/check_circle:"
        else:
            state, icon = f"failed (exit {code})", ":material/error:"
        log = LOGS / f"{label.replace(' ', '_').replace('/', '_')}.log"
        with st.expander(f"{label}: {state}", expanded=code is None, icon=icon):
            st.code(log.read_text(encoding="utf-8", errors="ignore")[-3000:] if log.exists() else "", language="text")
            if code is not None and icon_button(
                f"Dismiss {label}",
                key=f"dismiss_task_{label}",
            ):
                procs.pop(label, None)
                st.rerun()


@st.fragment(run_every=3)
def sidebar_activity() -> None:
    procs = st.session_state.get("procs", {})
    running = [label for label, proc in procs.items() if proc.poll() is None]
    if running:
        st.caption("Running: " + ", ".join(running))


def load_jobs_df() -> pd.DataFrame:
    with db.session() as s:
        jobs = s.exec(select(Job)).all()
        best: dict[int, JobAnalysis] = {}
        for a in s.exec(select(JobAnalysis).order_by(JobAnalysis.id)).all():
            best[a.job_id] = a
        resumes = {r.job_id for r in s.exec(select(TailoredResume)).all()}
    rows = []
    for j in jobs:
        a = best.get(j.id)
        rows.append({"id": j.id, "fit": a.fit_score if a else None, "company": j.company, "title": j.title,
                     "pay": j.pay, "source": j.source, "status": j.status, "resume": j.id in resumes,
                     "posted": j.posted, "location": j.location[:30], "relevance": j.relevance})
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(["fit", "relevance"], ascending=[False, False], na_position="last")
    return df


# ----------------------------------------------------------------------------- pages
def page_overview() -> None:
    page_header(
        "AI Trainer Job Copilot",
        "Collect roles, score fit, then open a job. Resumes use only facts you already recorded.",
        ":material/work:",
    )
    df = load_jobs_df()
    empty = df.empty
    with st.grid(4):
        st.metric("Jobs", 0 if empty else len(df), border=True, icon=":material/work:")
        st.metric("Analyzed", 0 if empty else int(df["fit"].notna().sum()), border=True, icon=":material/insights:")
        st.metric("Resumes", 0 if empty else int(df["resume"].sum()), border=True, icon=":material/description:")
        st.metric("Applied", 0 if empty else int((df["status"] == "applied").sum()), border=True, icon=":material/send:")

    st.subheader("Next actions", icon=":material/play_arrow:")
    boards, analyze = st.columns(2, border=True, gap="medium")
    with boards:
        st.markdown("**ATS boards**")
        st.caption("Pull new postings, or find company slugs you have not added yet.")
        if st.button("Collect from ATS boards", icon=":material/download:", width="stretch"):
            run_bg("collect ats", "collect")
        if st.button("Discover ATS slugs", icon=":material/search:", width="stretch"):
            run_bg("sources discover", "sources", "discover")
    with analyze:
        st.markdown("**Analyze**")
        st.caption("Score jobs that do not have a fit yet.")
        n = st.number_input("Max jobs to analyze", 1, 200, 10)
        if st.button("Analyze new jobs", type="primary", icon=":material/auto_awesome:", width="stretch"):
            run_bg("analyze batch", "analyze", "--all-new", "--limit", str(int(n)))

    st.subheader("AI engine", icon=":material/psychology:")
    llm = status_summary()
    with st.container(border=True):
        labels = [ENGINE_LABELS[e] for e in ENGINES]
        current = llm["preferred"] if llm["preferred"] in ENGINES else "auto"
        pick_col, save_col, refresh_col = st.columns([3, 1, 1], vertical_alignment="bottom")
        pick = pick_col.selectbox("Preferred engine for auto tasks", labels, index=ENGINES.index(current))
        chosen = ENGINES[labels.index(pick)]
        if save_col.button("Save engine", icon=":material/save:", width="stretch", disabled=(chosen == current)):
            save_prefs(engine=chosen)
            st.success(f"Saved: {ENGINE_LABELS[chosen]}", icon=":material/check_circle:")
            st.rerun()
        if refresh_col.button("Refresh status", icon=":material/refresh:", width="stretch"):
            st.rerun()
        st.caption(
            f"Engine **{llm['preferred']}**. With **browser**, tasks use both ChatGPT and Claude "
            f"(see config/models.yaml). Fallback probe resolves to **{llm['resolved_auto']}**. "
            "API keys are optional."
        )

    o, a, b = llm["openai"], llm["anthropic"], llm["bridge"] or {}
    s1, s2, s3 = st.columns(3)
    with s1:
        if o["ok"]:
            st.success(o["detail"], icon=":material/check_circle:")
        else:
            st.info(o["detail"], icon=":material/key:")
    with s2:
        if a["ok"]:
            st.success(a["detail"], icon=":material/check_circle:")
        else:
            st.info(a["detail"], icon=":material/key:")
    with s3:
        if b.get("extension_connected"):
            st.success(
                f"Browser session ready. Busy: {b.get('busy') or '-'}",
                icon=":material/extension:",
            )
        elif b.get("error"):
            st.warning(f"Bridge: {b['error']}", icon=":material/warning:")
            if st.button("Start bridge", icon=":material/play_arrow:"):
                _spawn(["bridge", "serve"], "bridge", detached=True)
                st.rerun()
        else:
            st.info(
                "Open this page in the Chrome where you are logged into ChatGPT or Claude. "
                "The BrightStar AI Trainer Copilot extension connects by itself.",
                icon=":material/chrome_reader_mode:",
            )
    with st.expander("Setup tips", icon=":material/help:"):
        st.markdown(
            """
**Preferred:** click the **BrightStar AI Trainer Copilot** extension → side panel → Build.
That opens ChatGPT/Claude in the same Chrome (Bid-bot style).

**API key (optional):** add `OPENAI_API_KEY=...` to `.env`, set Engine to **OpenAI** in the
extension Settings or Overview.

**Load once:** `extension/` in `chrome://extensions` (Developer mode → Load unpacked).
Keep `jt bridge serve` (or this dashboard) running.
"""
        )

    st.subheader("Background tasks", icon=":material/pending:")
    tasks_panel()


def page_jobs() -> None:
    page_header(
        "Jobs",
        "Filter the list, select a row to score it and draft a resume.",
        ":material/work:",
    )
    df = load_jobs_df()
    if df.empty:
        st.info("No jobs yet. Collect some from Overview.", icon=":material/info:")
        st.button("Go to overview", icon=":material/arrow_back:", on_click=go, args=("Overview",))
        return
    with st.container(border=True):
        f1, f2, f3, f4, f5 = st.columns([2, 2, 2, 3, 0.55], vertical_alignment="bottom")
        sources = f1.multiselect("Source", sorted(df["source"].unique()), key="jobs_sources")
        statuses = f2.multiselect("Status", STATUSES, key="jobs_statuses")
        min_fit = f3.slider("Min fit", 0, 100, 0, key="jobs_min_fit")
        q = f4.text_input("Search title or company", placeholder="Company or title", key="jobs_q")
        filters_on = bool(sources or statuses or min_fit or (q or "").strip())
        with f5:
            if icon_button(
                "Clear all filters",
                disabled=not filters_on,
                key="jobs_clear_filters",
            ):
                st.session_state["jobs_sources"] = []
                st.session_state["jobs_statuses"] = []
                st.session_state["jobs_min_fit"] = 0
                st.session_state["jobs_q"] = ""
                st.rerun()
    filtered = df
    if sources:
        filtered = filtered[filtered["source"].isin(sources)]
    if statuses:
        filtered = filtered[filtered["status"].isin(statuses)]
    if min_fit:
        filtered = filtered[filtered["fit"].fillna(-1) >= min_fit]
    if q:
        filtered = filtered[
            filtered["title"].str.contains(q, case=False)
            | filtered["company"].str.contains(q, case=False)
        ]
    st.caption(f"{len(filtered)} shown")
    if filtered.empty:
        st.info("Nothing matches these filters.", icon=":material/filter_alt_off:")
        return
    ev = st.dataframe(
        filtered,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        column_order=["company", "title", "fit", "status", "pay", "source", "location", "posted", "resume", "relevance", "id"],
        column_config={
            "company": st.column_config.TextColumn("Company"),
            "title": st.column_config.TextColumn("Title"),
            "fit": st.column_config.ProgressColumn("Fit", min_value=0, max_value=100, format="%.0f"),
            "status": st.column_config.TextColumn("Status"),
            "pay": st.column_config.TextColumn("Pay"),
            "source": st.column_config.TextColumn("Source"),
            "location": st.column_config.TextColumn("Location"),
            "posted": st.column_config.TextColumn("Posted"),
            "resume": st.column_config.CheckboxColumn("Resume"),
            "relevance": st.column_config.NumberColumn("Relevance", format="%.0f"),
            "id": st.column_config.NumberColumn("ID"),
        },
        alt="Collected jobs",
        key="jobs_table",
    )
    ids = df["id"].tolist()
    if ev.selection.rows:
        picked = int(filtered.iloc[ev.selection.rows[0]]["id"])
        st.session_state["job_id"] = picked
        st.session_state["jobs_selected"] = picked
    if st.session_state.get("jobs_selected") not in ids:
        fallback = st.session_state.get("job_id", ids[0])
        st.session_state["jobs_selected"] = fallback if fallback in ids else ids[0]
    labels = {int(r.id): f"{r.company} · {r.title}" for r in df.itertuples()}
    st.divider()
    job_id = st.selectbox(
        "Selected job",
        ids,
        format_func=lambda i: labels[int(i)],
        key="jobs_selected",
    )
    st.session_state["job_id"] = int(job_id)
    _render_job_detail(int(job_id))


def _render_job_detail(job_id: int) -> None:
    with db.session() as s:
        job = s.get(Job, job_id)
        analysis = an.latest_analysis(s, job_id)
        qs = s.exec(select(GapQuestion).where(GapQuestion.job_id == job_id)).all()
    if job is None:
        st.error("That job is no longer in the database.", icon=":material/error:")
        return
    st.subheader(job.title, icon=":material/description:")
    st.caption(
        f"{job.company} · {job.location} · pay {job.pay or 'n/a'} · {job.source} · "
        f"posted {job.posted or '?'} · applicants {job.applicants or '?'}"
    )
    new_status = st.segmented_control(
        "Status",
        STATUSES,
        default=job.status if job.status in STATUSES else STATUSES[0],
        required=True,
        key=f"status_{job_id}",
        width="stretch",
        wrap=True,
    )
    if job.url:
        st.link_button("Open posting", job.url, icon=":material/open_in_new:")
    if new_status and new_status != job.status:
        with db.session() as s:
            j = s.get(Job, job_id)
            j.status = new_status
            s.add(j)
            s.commit()
        st.rerun()
    with st.expander("Job description", icon=":material/article:"):
        st.text(job.description)

    if analysis is None:
        st.info("Not analyzed yet.", icon=":material/info:")
        if st.button("Analyze this job", type="primary", icon=":material/auto_awesome:"):
            run_bg(f"analyze {job_id}", "analyze", str(job_id))
    else:
        req, gaps = an.requirements_of(analysis), an.gaps_of(analysis)
        facts, requirements = st.columns([1, 2], gap="medium")
        with facts:
            st.metric("Fit score", f"{analysis.fit_score:.0f}/100", border=True)
            st.markdown(
                f"**Domain**  \n{req.domain}  \n\n"
                f"**Tasks**  \n{', '.join(req.task_types) or 'n/a'}  \n\n"
                f"**Seniority**  \n{req.seniority}  \n\n"
                f"**Pay**  \n{req.pay or 'n/a'}  \n\n"
                f"**Time**  \n{req.time_commitment or 'n/a'}"
            )
        with requirements:
            with st.container(border=True):
                st.markdown("**Must-haves**")
                st.markdown("\n".join(f"- {r.text}" for r in req.must_haves) or "-")
                st.markdown("**Screening signals**")
                st.markdown("\n".join(f"- {x}" for x in req.screening_signals) or "-")
            if req.red_flags:
                st.error("Red flags: " + "; ".join(req.red_flags), icon=":material/flag:")
        st.subheader("Your gaps", icon=":material/rule:")
        st.dataframe(
            pd.DataFrame([g.model_dump() for g in gaps]) if gaps else pd.DataFrame({"gaps": []}),
            hide_index=True,
            alt="Gaps for this job",
        )
        if st.button("Re-analyze", icon=":material/refresh:", help="Runs a new LLM call."):
            run_bg(f"analyze {job_id}", "analyze", str(job_id), "--force")

        st.subheader("Gap questions", icon=":material/quiz:")
        if not qs:
            st.caption("Questions ask only about gaps. Leave an answer empty when you have no real evidence.")
            if st.button("Generate questions", type="primary", icon=":material/quiz:"):
                run_bg(f"questions {job_id}", "questions", str(job_id))
        else:
            with st.form(f"qa_{job_id}"):
                answers = {}
                for q in qs:
                    key = f"qa_ans_{job_id}_{q.id}"
                    if key not in st.session_state:
                        st.session_state[key] = q.answer or ""
                    answers[q.id] = st.text_area(
                        f"[{q.gap}] {q.question}",
                        height=88,
                        help="Leave empty if you have no real evidence.",
                        key=key,
                    )
                with st.container(horizontal=True, vertical_alignment="center"):
                    saved = st.form_submit_button(
                        "Save answers", type="primary", icon=":material/save:", width="stretch"
                    )
                    cleared = icon_button(
                        "Clear all answer boxes",
                        form=True,
                        key=f"qa_clear_{job_id}",
                    )
            if cleared:
                for q in qs:
                    st.session_state[f"qa_ans_{job_id}_{q.id}"] = ""
                st.rerun()
            if saved:
                for qid, ans in answers.items():
                    tl.answer_question(qid, ans)
                st.success("Saved", icon=":material/check_circle:")
            if st.button("Regenerate questions", icon=":material/refresh:"):
                run_bg(f"questions {job_id}", "questions", str(job_id), "--regenerate")

        st.subheader("Tailored resume", icon=":material/description:")
        if st.button("Generate tailored resume", type="primary", icon=":material/auto_awesome:"):
            run_bg(f"tailor {job_id}", "tailor", str(job_id), "--no-interactive")
        row = tl.latest_resume(job_id)
        if row:
            payload = json.loads(row.resume_json)
            meta = payload["meta"]
            coverage, fit_at = st.columns(2)
            coverage.metric("ATS keyword coverage", f"{meta['ats_coverage']}%", border=True)
            fit_at.metric("Fit at generation", f"{meta['fit_score']:.0f}", border=True)
            for w in meta["warnings"] + meta["llm_unverified"]:
                st.warning("Check before sending: " + w, icon=":material/warning:")
            if meta["keywords_missing"]:
                st.caption("Keywords still missing (add only if true): " + ", ".join(meta["keywords_missing"][:15]))
            with st.container(horizontal=True):
                for path, label, mime in (
                    (row.docx_path, "Download DOCX", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
                    (row.pdf_path, "Download PDF", "application/pdf"),
                    (row.prompt_path, "Download resume prompt", "text/markdown"),
                ):
                    if path and Path(path).exists():
                        st.download_button(
                            label,
                            Path(path).read_bytes(),
                            file_name=Path(path).name,
                            mime=mime,
                            icon=":material/download:",
                        )
            html_path = Path(row.docx_path).with_suffix(".html")
            if html_path.exists():
                st.caption("Preview")
                components.html(
                    _resume_preview_html(html_path.read_text(encoding="utf-8")),
                    height=720,
                    scrolling=True,
                )
    tasks_panel()


def page_profile() -> None:
    page_header(
        "Profiles",
        "Named candidate profiles. Resumes only use facts written in the active profile or in your answers.",
        ":material/person:",
    )
    names = list_profiles()
    active = get_active_profile()
    example = profile_example_path()
    example_text = example.read_text(encoding="utf-8") if example.exists() else "basics:\n  name: \"\"\n"

    picker, create = st.columns([2, 1], gap="medium")
    with picker:
        if names:
            options = names
            idx = options.index(active) if active in options else 0
            chosen = st.selectbox("Active profile", options, index=idx, key="profile_picker")
            if chosen != active:
                set_active_profile(chosen)
                st.session_state.pop("profile_yaml", None)
                st.rerun()
            slug = chosen
        else:
            st.info("No profiles yet. Create one on the right, or import a resume.", icon=":material/info:")
            slug = None
    with create:
        new_name = st.text_input("New profile slug", placeholder="jane", key="profile_new_slug")
        if st.button("Create empty profile", icon=":material/person_add:", width="stretch"):
            try:
                slug_new = validate_slug(new_name)
            except ValueError as e:
                st.error(str(e), icon=":material/error:")
            else:
                path_new = profile_path(slug_new)
                if path_new.exists():
                    st.error(f"Profile '{slug_new}' already exists.", icon=":material/error:")
                else:
                    config.ensure_dirs()
                    path_new.parent.mkdir(parents=True, exist_ok=True)
                    path_new.write_text(example_text, encoding="utf-8")
                    set_active_profile(slug_new)
                    st.session_state.pop("profile_yaml", None)
                    st.success(f"Created {slug_new}", icon=":material/check_circle:")
                    st.rerun()

    if not slug:
        tasks_panel()
        return

    path = profile_path(slug)
    text = path.read_text(encoding="utf-8") if path.exists() else example_text
    editor, side = st.columns([1.5, 1], gap="medium")
    with editor:
        with st.container(border=True):
            editor_key = f"profile_yaml_{slug}"
            if st.session_state.get("profile_editor_slug") != slug:
                st.session_state["profile_editor_slug"] = slug
                st.session_state[editor_key] = text
            edited = st.text_area(
                f"Profile YAML (`{slug}`)",
                height=520,
                help="Facts only. Resumes cannot invent employers, dates, metrics, or tools.",
                key=editor_key,
            )
            with st.container(horizontal=True, vertical_alignment="center"):
                if st.button("Save profile", type="primary", icon=":material/save:", width="stretch"):
                    try:
                        MasterProfile.model_validate(yaml.safe_load(edited) or {})
                    except Exception as e:  # noqa: BLE001
                        st.error(f"Invalid profile: {e}", icon=":material/error:")
                    else:
                        config.ensure_dirs()
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_text(edited, encoding="utf-8")
                        set_active_profile(slug)
                        st.success("Saved. Rescoring jobs...", icon=":material/check_circle:")
                        try:
                            st.caption(f"Rescored {an.rescore_all(profile=slug)} analyses")
                        except Exception as e:  # noqa: BLE001
                            st.caption(str(e))
                if icon_button(
                    "Reload the last saved profile from disk",
                    key="profile_yaml_clear",
                ):
                    st.session_state[editor_key] = (
                        path.read_text(encoding="utf-8") if path.exists() else example_text
                    )
                    st.rerun()
    with side:
        with st.container(border=True):
            st.subheader("Import", icon=":material/upload_file:")
            st.caption(f"Import overwrites `{slug}` with what the model can support from the file.")
            if "profile_resume_nonce" not in st.session_state:
                st.session_state["profile_resume_nonce"] = 0
            up = st.file_uploader(
                "Resume",
                type=["pdf", "docx", "md", "txt"],
                key=f"profile_resume_{st.session_state['profile_resume_nonce']}",
            )
            li = config.PROFILE_DIR / "linkedin_profile.txt"
            use_li = st.checkbox(
                f"Also use LinkedIn text ({li.name})",
                value=li.exists(),
                disabled=not li.exists(),
            )
            import_col, clear_up_col = st.columns([12, 1], vertical_alignment="center")
            if up and import_col.button(
                "Import with LLM", icon=":material/upload_file:", width="stretch"
            ):
                src = config.PROFILE_DIR / "resume_source"
                src.mkdir(parents=True, exist_ok=True)
                dest = src / up.name
                dest.write_bytes(up.getvalue())
                args = ["profile", "import", "--name", slug, "--resume", str(dest), "--yes"]
                if use_li:
                    args += ["--linkedin-text", str(li)]
                run_bg("profile import", *args)
            with clear_up_col:
                if icon_button(
                    "Clear the resume upload",
                    key="profile_resume_clear",
                    disabled=up is None,
                ):
                    st.session_state["profile_resume_nonce"] = int(st.session_state["profile_resume_nonce"]) + 1
                    st.rerun()
            if st.button("Fetch LinkedIn profile text", icon=":material/travel_explore:", width="stretch",
                         help="Uses your own Octo profile."):
                run_bg("linkedin profile text", "octo", "profile-text")
        with st.container(border=True):
            st.subheader("LinkedIn advice", icon=":material/lightbulb:")
            st.caption("Advice is drafted from jobs you have already analyzed.")
            if st.button("Generate advice", icon=":material/auto_awesome:", width="stretch"):
                run_bg("profile optimize", "profile", "optimize", "--profile", slug)
    adv = config.OUTPUT_DIR / f"linkedin_advice_{slug}.md"
    legacy_adv = config.OUTPUT_DIR / "linkedin_advice.md"
    show_adv = adv if adv.exists() else legacy_adv
    if show_adv.exists():
        st.subheader("Latest advice", icon=":material/article:")
        st.markdown(show_adv.read_text(encoding="utf-8"))
    tasks_panel()


def page_market() -> None:
    page_header(
        "Market and gaps",
        "What analyzed postings ask for, and which gaps show up most often.",
        ":material/insights:",
    )
    md = pf.market_data()
    if not md["n_jobs"]:
        st.info("Analyze some jobs first.", icon=":material/info:")
        st.button("Go to jobs", icon=":material/arrow_forward:", on_click=go, args=("Jobs",))
        return
    st.metric("Analyzed jobs", md["n_jobs"], border=True)
    keywords, domains = st.columns(2, gap="medium")
    with keywords:
        st.subheader("Most requested keywords", icon=":material/key:")
        st.bar_chart(
            pd.Series({k: n for k, n in md["keyword_counts"]}),
            horizontal=True,
            alt="Most requested keywords",
        )
    with domains:
        st.subheader("Domains", icon=":material/category:")
        if md["top_domains"]:
            with st.container(horizontal=True):
                for domain in md["top_domains"]:
                    st.badge(domain, color="blue")
        else:
            st.caption("No domains yet.")
    st.subheader("Your most frequent gaps", icon=":material/rule:")
    st.caption("Close these first. Add a fact only when you can point to real evidence.")
    st.dataframe(
        pd.DataFrame(md["top_gaps"], columns=["gap", "jobs"]),
        hide_index=True,
        alt="Most frequent gaps",
    )
    st.subheader("Most common must-haves", icon=":material/checklist:")
    with st.container(border=True):
        st.markdown("\n".join(f"- {r}" for r in md["top_requirements"]) or "-")


def _suggestion_dirs() -> list[Path]:
    root = config.OUTPUT_DIR / "suggestions"
    if not root.exists():
        return []
    dirs = [p for p in root.iterdir() if p.is_dir() and (p / "profile.md").exists()]
    return sorted(dirs, key=lambda p: (p / "profile.md").stat().st_mtime, reverse=True)


def _load_suggestion(folder: Path) -> SuggestedBenchmark | None:
    path = folder / "suggestion.json"
    if not path.exists():
        return None
    try:
        return SuggestedBenchmark.model_validate_json(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


def _suggestion_label(folder: Path) -> str:
    data = _load_suggestion(folder)
    if data is None:
        return folder.name
    target = "job description" if data.target_kind == "job_description" else data.inferred_industry
    return f"{data.persona_name} · {data.last_company} · {target}"


def _download(folder: Path, filename: str, label: str) -> None:
    path = folder / filename
    if path.exists():
        mime = "text/markdown" if path.suffix == ".md" else "text/html" if path.suffix == ".html" else (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        st.download_button(
            label,
            path.read_bytes(),
            file_name=path.name,
            mime=mime,
            key=f"dl-{folder.name}-{filename}",
            icon=":material/download:",
        )


@st.fragment(run_every=3)
def teaching_workspace() -> None:
    """Live result pane: progress, saved models, coach notes, and the resume."""
    procs = st.session_state.get("procs", {})
    running = [label for label, proc in procs.items() if proc.poll() is None]
    if any(label.startswith("suggest ") for label in running):
        st.info(
            "Notes and the resume will show here when it finishes.",
            icon=":material/progress_activity:",
            title="Building the teaching model",
        )
    for label, proc in procs.items():
        code = proc.poll()
        if code is None:
            state, icon = "running", ":material/progress_activity:"
        elif code == 0:
            state, icon = "done", ":material/check_circle:"
        else:
            state, icon = f"failed (exit {code})", ":material/error:"
        log = LOGS / f"{label.replace(' ', '_').replace('/', '_')}.log"
        with st.expander(f"{label}: {state}", expanded=code != 0, icon=icon):
            st.code(log.read_text(encoding="utf-8", errors="ignore")[-2000:] if log.exists() else "", language="text")

    dirs = _suggestion_dirs()
    if not dirs:
        st.caption("Nothing saved yet. A finished model includes:")
        career, education, notes, resume = st.columns(4, border=True)
        career.markdown("**Career**")
        career.caption("US high-ranking employers, with the last company as the current role.")
        education.markdown("**Education**")
        education.caption("Schools, licenses, and projects that are real.")
        notes.markdown("**Coach notes**")
        notes.caption("What to include, the best option, and how to teach it.")
        resume.markdown("**Resume**")
        resume.caption("A file you can download and a preview.")
        return

    labels = {d.name: _suggestion_label(d) for d in dirs}
    names = [d.name for d in dirs]
    pending = st.session_state.get("suggestion_pending")
    if pending in names:
        st.session_state["suggestion_folder"] = pending
        st.session_state["suggestion_pending"] = ""
    if st.session_state.get("suggestion_folder") not in names:
        st.session_state["suggestion_folder"] = names[0]
    pick_col, del_col = st.columns([20, 1], vertical_alignment="bottom")
    picked = pick_col.selectbox(
        "Open a saved model", names, format_func=lambda n: labels[n], key="suggestion_folder"
    )
    folder = next(d for d in dirs if d.name == picked)
    with del_col:
        if icon_button(
            "Delete this saved teaching model",
            icon=":material/delete:",
            key=f"delete_suggestion_{picked}",
        ):
            shutil.rmtree(folder, ignore_errors=True)
            st.session_state.pop("suggestion_folder", None)
            st.toast(f"Deleted {labels.get(picked, picked)}")
            st.rerun()
    data = _load_suggestion(folder)
    if data is not None:
        st.subheader(data.persona_name, icon=":material/person:")
        with st.container(horizontal=True):
            if data.inferred_domain:
                st.badge(data.inferred_domain, color="blue")
            if data.inferred_industry:
                st.badge(data.inferred_industry, color="violet")
            if data.last_company:
                st.badge(data.last_company, color="gray")
        st.markdown(data.why_this_shape)
    else:
        st.subheader(folder.name)

    html, md = folder / "resume.html", folder / "profile.md"
    with st.container(horizontal=True):
        _download(folder, "resume.docx", "Download resume")
        _download(folder, "resume.html", "Download HTML")
        _download(folder, "profile.md", "Download notes")
        if st.button(
            "Suitable jobs / types",
            icon=":material/work:",
            key=f"suitable_jobs_{folder.name}",
            help="Score collected jobs against this teaching model (in memory). "
                 "If none reach interview fit (≥60), recommend job types to collect.",
            disabled=data is None,
        ):
            try:
                result, _, report_path = sm.suitable_for_suggestion_dir(folder)
                st.session_state[f"suitable_result_{folder.name}"] = result
                st.session_state[f"suitable_report_{folder.name}"] = str(report_path)
                st.toast(
                    "Matched collected jobs"
                    if result.get("mode") == "jobs"
                    else "No strong job hits — showing job types"
                )
            except Exception as e:  # noqa: BLE001
                st.error(str(e))

    suitable = st.session_state.get(f"suitable_result_{folder.name}")
    if isinstance(suitable, dict):
        with st.container(border=True):
            if suitable.get("mode") == "jobs":
                st.markdown("**Collected jobs that fit this teaching model**")
                rows = [
                    {
                        "id": row["job_id"],
                        "fit": row["fit"],
                        "company": row["company"],
                        "title": row["title"],
                        "domain": row.get("domain") or "",
                    }
                    for row in suitable.get("matches") or []
                ]
                st.dataframe(rows, hide_index=True, width="stretch")
            else:
                st.markdown("**No collected jobs met fit ≥ 60 — suitable job kinds**")
                for entry in suitable.get("types") or []:
                    roles = ", ".join(entry.get("roles") or []) or "—"
                    st.markdown(
                        f"- **{entry.get('name') or entry.get('key')}** "
                        f"({entry.get('source')}): {entry.get('description') or ''}\n"
                        f"  - Titles: {roles}"
                    )
                examples = suitable.get("title_examples") or []
                if examples:
                    st.caption("Collect next: " + " · ".join(examples[:8]))
            report = st.session_state.get(f"suitable_report_{folder.name}")
            if report:
                st.caption(f"Saved `{Path(report).name}` in this model folder.")

    notes_tab, profile_tab, resume_tab = st.tabs(["Coach notes", "Full profile", "Resume"])
    with notes_tab:
        if data is not None and data.teaching_notes:
            for note in data.teaching_notes:
                with st.container(border=True):
                    st.markdown(f"**{note.section}**")
                    st.markdown(f"**Include.** {note.necessary_information}")
                    st.markdown(f"**Best option.** {note.best_option}")
                    st.caption(note.how_to_teach)
        elif md.exists():
            st.markdown(md.read_text(encoding="utf-8"))
    with profile_tab:
        if md.exists():
            st.markdown(md.read_text(encoding="utf-8"))
    with resume_tab:
        catalog = list_styles()
        templates = catalog.get("templates") or []
        ids = [t["id"] for t in templates]
        labels_map = {t["id"]: t.get("label") or t["id"] for t in templates}
        current_tid = preferred_resume_template()
        if current_tid not in ids and ids:
            current_tid = catalog.get("default") or ids[0]
        style_col, color_col, apply_col = st.columns([3.2, 1.1, 1], vertical_alignment="bottom")
        preview_tid = style_col.selectbox(
            "Visual style",
            ids,
            index=ids.index(current_tid) if current_tid in ids else 0,
            format_func=lambda i: labels_map.get(i, i),
            key=f"teaching_template_{folder.name}",
        )
        style_default_hex = resolve_accent_color(
            get_style(preview_tid).vars.get("--accent"),
            fallback="#1F4E79",
        )
        accent_default = resolve_accent_color(
            preferred_resume_accent(),
            fallback=style_default_hex,
        )
        preview_accent = color_col.color_picker(
            "Accent",
            value=accent_default if accent_default.startswith("#") else style_default_hex,
            key=f"teaching_accent_{folder.name}",
            help="Pick the resume accent color (headers, rules, name).",
        )
        suggestion = data if data is not None else _load_suggestion(folder)
        can_apply = suggestion is not None
        if apply_col.button(
            "Apply style",
            icon=":material/palette:",
            width="stretch",
            key=f"apply_template_{folder.name}",
            disabled=not can_apply,
        ):
            save_prefs(resume_template=preview_tid, resume_accent=preview_accent)
            resume = sm.sample_to_resume(suggestion)
            render_docx(resume, folder / "resume.docx")
            (folder / "resume.html").write_text(
                render_html(
                    resume,
                    template_id=preview_tid,
                    accent_id=preview_accent,
                ),
                encoding="utf-8",
            )
            st.toast(f"Saved {labels_map.get(preview_tid, preview_tid)} · {preview_accent}")
            st.rerun()
        preset_ids = [a["id"] for a in list_accents()]
        preset_hex = {a["id"]: a["hex"] for a in list_accents()}
        preset_key = f"teaching_accent_preset_{folder.name}"
        color_key = f"teaching_accent_{folder.name}"
        picked_preset = st.pills(
            "Saved colors",
            preset_ids,
            key=preset_key,
            help="Quick accent presets — click one to fill the color picker.",
        )
        if picked_preset:
            st.session_state[color_key] = preset_hex[picked_preset]
            st.session_state.pop(preset_key, None)
            st.rerun()
        st.caption(
            "Style only — section order stays Professional Summary → Skills (by category) → "
            "Experience → Projects → Education → Licenses / Certifications. "
            "Preview updates live; Apply style writes the files."
        )
        preview_pane, saved_pane = st.tabs(["Preview", "Saved file"])
        with preview_pane:
            if suggestion is not None:
                live = render_html(
                    sm.sample_to_resume(suggestion),
                    template_id=preview_tid,
                    accent_id=preview_accent,
                )
                st.badge(labels_map.get(preview_tid, preview_tid), color="blue")
                st.badge(preview_accent, color="gray")
                components.html(_resume_preview_html(live), height=720, scrolling=True)
            else:
                st.info(
                    "Build a teaching model first — then preview styles here.",
                    icon=":material/description:",
                )
        with saved_pane:
            if html.exists():
                components.html(
                    _resume_preview_html(html.read_text(encoding="utf-8")),
                    height=720,
                    scrolling=True,
                )
            else:
                st.info(
                    "No saved resume.html yet. Use Preview, then Apply style.",
                    icon=":material/info:",
                )


_SUGGEST_SECTION_KEYS = (
    "suggest_experience_ids",
    "suggest_education_ids",
    "suggest_license_ids",
    "suggest_cert_ids",
    "suggest_skill_ids",
    "suggest_language_ids",
    "suggest_project_ids",
)

_SUGGEST_TEXT_KEYS = (
    "suggest_name",
    "suggest_company",
    "suggest_title",
    "suggest_location",
    "suggest_headline",
    "suggest_about",
    "suggest_notes",
    "suggest_jd",
)


def _new_entry_id() -> str:
    return uuid.uuid4().hex[:8]


def _ensure_suggest_lists() -> None:
    for key in _SUGGEST_SECTION_KEYS:
        if key not in st.session_state:
            st.session_state[key] = []
    if "suggest_jd_file_nonce" not in st.session_state:
        st.session_state["suggest_jd_file_nonce"] = 0


def _add_suggest_entry(list_key: str) -> None:
    ids = list(st.session_state.get(list_key) or [])
    ids.append(_new_entry_id())
    st.session_state[list_key] = ids


def _remove_suggest_entry(list_key: str, entry_id: str) -> None:
    st.session_state[list_key] = [eid for eid in (st.session_state.get(list_key) or []) if eid != entry_id]


def _suggest_section_header(title: str, *, add_label: str, list_key: str) -> None:
    left, right = st.columns([1, 0.28], vertical_alignment="center")
    left.markdown(f"**{title}**")
    if right.button(
        add_label,
        key=f"add_{list_key}",
        icon=":material/add:",
        type="secondary",
        width="stretch",
    ):
        _add_suggest_entry(list_key)
        st.rerun()


@contextmanager
def _entry_shell(title: str, *, list_key: str, entry_id: str):
    with st.container(border=True):
        head, trash = st.columns([1, 0.08], vertical_alignment="center")
        head.caption(title)
        if trash.button(
            "",
            key=f"rm_{list_key}_{entry_id}",
            icon=":material/close:",
            type="tertiary",
            help="Remove this entry",
        ):
            _remove_suggest_entry(list_key, entry_id)
            st.rerun()
        yield


def _collect_profile_seed() -> dict:
    experience = []
    for eid in st.session_state.get("suggest_experience_ids") or []:
        bullets = [
            line.strip()
            for line in str(st.session_state.get(f"suggest_exp_bullets_{eid}") or "").splitlines()
            if line.strip()
        ]
        entry = {
            "company": str(st.session_state.get(f"suggest_exp_company_{eid}") or "").strip(),
            "title": str(st.session_state.get(f"suggest_exp_title_{eid}") or "").strip(),
            "start": str(st.session_state.get(f"suggest_exp_start_{eid}") or "").strip(),
            "end": str(st.session_state.get(f"suggest_exp_end_{eid}") or "").strip(),
            "location": str(st.session_state.get(f"suggest_exp_location_{eid}") or "").strip(),
            "bullets": bullets,
        }
        if any(entry.values()):
            experience.append({k: v for k, v in entry.items() if v})

    education = []
    for eid in st.session_state.get("suggest_education_ids") or []:
        details = [
            line.strip()
            for line in str(st.session_state.get(f"suggest_edu_details_{eid}") or "").splitlines()
            if line.strip()
        ]
        entry = {
            "school": str(st.session_state.get(f"suggest_edu_school_{eid}") or "").strip(),
            "degree": str(st.session_state.get(f"suggest_edu_degree_{eid}") or "").strip(),
            "field": str(st.session_state.get(f"suggest_edu_field_{eid}") or "").strip(),
            "start": str(st.session_state.get(f"suggest_edu_start_{eid}") or "").strip(),
            "end": str(st.session_state.get(f"suggest_edu_end_{eid}") or "").strip(),
            "details": details,
        }
        if any(entry.values()):
            education.append({k: v for k, v in entry.items() if v})

    licenses = []
    for eid in st.session_state.get("suggest_license_ids") or []:
        entry = {
            "name": str(st.session_state.get(f"suggest_lic_name_{eid}") or "").strip(),
            "issuer": str(st.session_state.get(f"suggest_lic_issuer_{eid}") or "").strip(),
            "year": str(st.session_state.get(f"suggest_lic_year_{eid}") or "").strip(),
        }
        if any(entry.values()):
            licenses.append({k: v for k, v in entry.items() if v})

    certifications = []
    for eid in st.session_state.get("suggest_cert_ids") or []:
        entry = {
            "name": str(st.session_state.get(f"suggest_cert_name_{eid}") or "").strip(),
            "issuer": str(st.session_state.get(f"suggest_cert_issuer_{eid}") or "").strip(),
            "year": str(st.session_state.get(f"suggest_cert_year_{eid}") or "").strip(),
        }
        if any(entry.values()):
            certifications.append({k: v for k, v in entry.items() if v})

    skills = []
    for eid in st.session_state.get("suggest_skill_ids") or []:
        skill = str(st.session_state.get(f"suggest_skill_{eid}") or "").strip()
        if skill:
            skills.append(skill)

    languages = []
    for eid in st.session_state.get("suggest_language_ids") or []:
        entry = {
            "name": str(st.session_state.get(f"suggest_lang_name_{eid}") or "").strip(),
            "level": str(st.session_state.get(f"suggest_lang_level_{eid}") or "").strip(),
        }
        if any(entry.values()):
            languages.append({k: v for k, v in entry.items() if v})

    projects = []
    for eid in st.session_state.get("suggest_project_ids") or []:
        skills_text = str(st.session_state.get(f"suggest_proj_skills_{eid}") or "").strip()
        entry = {
            "name": str(st.session_state.get(f"suggest_proj_name_{eid}") or "").strip(),
            "description": str(st.session_state.get(f"suggest_proj_desc_{eid}") or "").strip(),
            "skills": [p.strip() for p in re.split(r"[,;]+", skills_text) if p.strip()] if skills_text else [],
        }
        if any(entry.values()):
            projects.append({k: v for k, v in entry.items() if v})

    return sm.normalize_profile_seed({
        "location": str(st.session_state.get("suggest_location") or "").strip(),
        "headline": str(st.session_state.get("suggest_headline") or "").strip(),
        "about": str(st.session_state.get("suggest_about") or "").strip(),
        "experience": experience,
        "education": education,
        "licenses": licenses,
        "certifications": certifications,
        "skills": skills,
        "languages": languages,
        "projects": projects,
    })


def _clear_suggest_form() -> None:
    for key in _SUGGEST_TEXT_KEYS:
        st.session_state[key] = ""
    for list_key in _SUGGEST_SECTION_KEYS:
        for eid in list(st.session_state.get(list_key) or []):
            prefixes = (
                f"suggest_exp_company_{eid}",
                f"suggest_exp_title_{eid}",
                f"suggest_exp_start_{eid}",
                f"suggest_exp_end_{eid}",
                f"suggest_exp_location_{eid}",
                f"suggest_exp_bullets_{eid}",
                f"suggest_edu_school_{eid}",
                f"suggest_edu_degree_{eid}",
                f"suggest_edu_field_{eid}",
                f"suggest_edu_start_{eid}",
                f"suggest_edu_end_{eid}",
                f"suggest_edu_details_{eid}",
                f"suggest_lic_name_{eid}",
                f"suggest_lic_issuer_{eid}",
                f"suggest_lic_year_{eid}",
                f"suggest_cert_name_{eid}",
                f"suggest_cert_issuer_{eid}",
                f"suggest_cert_year_{eid}",
                f"suggest_skill_{eid}",
                f"suggest_lang_name_{eid}",
                f"suggest_lang_level_{eid}",
                f"suggest_proj_name_{eid}",
                f"suggest_proj_desc_{eid}",
                f"suggest_proj_skills_{eid}",
            )
            for widget_key in prefixes:
                st.session_state.pop(widget_key, None)
        st.session_state[list_key] = []
    st.session_state["suggest_jd_file_nonce"] = int(st.session_state.get("suggest_jd_file_nonce") or 0) + 1


def page_samples() -> None:
    page_header(
        "Teaching models",
        "Build a top 0.1% profile and resume for a virtual candidate, then teach from the notes.",
        ":material/school:",
    )
    _ensure_suggest_lists()
    with st.container(border=True):
        st.subheader("Who and where", icon=":material/badge:")
        name_col, company_col, title_col = st.columns(3, vertical_alignment="bottom")
        name = name_col.text_input(
            "Virtual candidate name", placeholder="Mina Cho", key="suggest_name"
        )
        company = company_col.text_input(
            "Last company", placeholder="Rockwell Automation", key="suggest_company"
        )
        title = title_col.text_input(
            "Last title", placeholder="Senior controls engineer", key="suggest_title"
        )
        loc_col, head_col = st.columns(2, vertical_alignment="bottom")
        loc_col.text_input(
            "Location (optional)", placeholder="Chicago, IL", key="suggest_location"
        )
        head_col.text_input(
            "Headline (optional)",
            placeholder="Senior controls engineer | safety-rated automation",
            key="suggest_headline",
        )
        st.text_area(
            "About (optional)",
            height=90,
            placeholder="Short LinkedIn-style summary. Leave empty to let the model write one.",
            key="suggest_about",
        )
        notes_col, jd_col = st.columns(2)
        notes = notes_col.text_area(
            "Industry notes (optional)",
            height=140,
            placeholder="Products, customers, or the kind of work this company hires for.",
            key="suggest_notes",
        )
        jd = jd_col.text_area(
            "Job description (optional)",
            height=140,
            placeholder="Paste a posting to aim at that job. Leave empty to aim at the company's industry.",
            key="suggest_jd",
        )
        jd_file = st.file_uploader(
            "Upload a job description",
            type=["txt", "md"],
            help="txt or md. Used when the box above is empty.",
            key=f"suggest_jd_file_{st.session_state['suggest_jd_file_nonce']}",
        )

        st.divider()
        st.caption("Optional profile sections — add only what you want to pin. Everything else stays optional.")

        _suggest_section_header(
            "Experience",
            add_label="Add position",
            list_key="suggest_experience_ids",
        )
        st.caption(
            "Last company above is the current role. Add earlier US high-ranking employers here."
        )
        for eid in st.session_state["suggest_experience_ids"]:
            with _entry_shell("Position", list_key="suggest_experience_ids", entry_id=eid):
                c1, c2 = st.columns(2)
                c1.text_input("Company", key=f"suggest_exp_company_{eid}", placeholder="Honeywell")
                c2.text_input("Title", key=f"suggest_exp_title_{eid}", placeholder="Controls engineer")
                c3, c4, c5 = st.columns(3)
                c3.text_input("Start", key=f"suggest_exp_start_{eid}", placeholder="2014")
                c4.text_input("End", key=f"suggest_exp_end_{eid}", placeholder="2019")
                c5.text_input("Location", key=f"suggest_exp_location_{eid}", placeholder="Detroit, MI")
                st.text_area(
                    "Highlights (one per line)",
                    key=f"suggest_exp_bullets_{eid}",
                    height=80,
                    placeholder="Commissioned 12 robot cells\nWrote PLC standards for 4 lines",
                )

        _suggest_section_header(
            "Education",
            add_label="Add education",
            list_key="suggest_education_ids",
        )
        for eid in st.session_state["suggest_education_ids"]:
            with _entry_shell("School", list_key="suggest_education_ids", entry_id=eid):
                c1, c2 = st.columns(2)
                c1.text_input("School", key=f"suggest_edu_school_{eid}", placeholder="Georgia Institute of Technology")
                c2.text_input("Degree", key=f"suggest_edu_degree_{eid}", placeholder="BSc")
                c3, c4, c5 = st.columns(3)
                c3.text_input("Field", key=f"suggest_edu_field_{eid}", placeholder="Electrical Engineering")
                c4.text_input("Start", key=f"suggest_edu_start_{eid}", placeholder="2010")
                c5.text_input("End", key=f"suggest_edu_end_{eid}", placeholder="2014")
                st.text_area(
                    "Details (one per line)",
                    key=f"suggest_edu_details_{eid}",
                    height=70,
                    placeholder="Controls concentration\nSenior design: motion cell",
                )

        _suggest_section_header(
            "Licenses",
            add_label="Add license",
            list_key="suggest_license_ids",
        )
        for eid in st.session_state["suggest_license_ids"]:
            with _entry_shell("License", list_key="suggest_license_ids", entry_id=eid):
                c1, c2, c3 = st.columns(3)
                c1.text_input("Name", key=f"suggest_lic_name_{eid}", placeholder="Professional Engineer (PE)")
                c2.text_input("Issuer", key=f"suggest_lic_issuer_{eid}", placeholder="NCEES / state board")
                c3.text_input("Year", key=f"suggest_lic_year_{eid}", placeholder="2018")

        _suggest_section_header(
            "Certifications",
            add_label="Add certification",
            list_key="suggest_cert_ids",
        )
        for eid in st.session_state["suggest_cert_ids"]:
            with _entry_shell("Certification", list_key="suggest_cert_ids", entry_id=eid):
                c1, c2, c3 = st.columns(3)
                c1.text_input("Name", key=f"suggest_cert_name_{eid}", placeholder="PMP")
                c2.text_input("Issuer", key=f"suggest_cert_issuer_{eid}", placeholder="PMI")
                c3.text_input("Year", key=f"suggest_cert_year_{eid}", placeholder="2020")

        _suggest_section_header(
            "Skills",
            add_label="Add skill",
            list_key="suggest_skill_ids",
        )
        for eid in st.session_state["suggest_skill_ids"]:
            with _entry_shell("Skill", list_key="suggest_skill_ids", entry_id=eid):
                st.text_input("Skill", key=f"suggest_skill_{eid}", placeholder="Safety PLCs", label_visibility="collapsed")

        _suggest_section_header(
            "Languages",
            add_label="Add language",
            list_key="suggest_language_ids",
        )
        for eid in st.session_state["suggest_language_ids"]:
            with _entry_shell("Language", list_key="suggest_language_ids", entry_id=eid):
                c1, c2 = st.columns(2)
                c1.text_input("Language", key=f"suggest_lang_name_{eid}", placeholder="English")
                c2.text_input("Level", key=f"suggest_lang_level_{eid}", placeholder="Native / Professional")

        _suggest_section_header(
            "Projects",
            add_label="Add project",
            list_key="suggest_project_ids",
        )
        for eid in st.session_state["suggest_project_ids"]:
            with _entry_shell("Project", list_key="suggest_project_ids", entry_id=eid):
                st.text_input("Name", key=f"suggest_proj_name_{eid}", placeholder="Cell safety retrofit")
                st.text_area(
                    "Description",
                    key=f"suggest_proj_desc_{eid}",
                    height=70,
                    placeholder="Documented a lockout design used on 12 cells.",
                )
                st.text_input(
                    "Skills (comma-separated)",
                    key=f"suggest_proj_skills_{eid}",
                    placeholder="PLC, lockout, FANUC",
                )

        with st.container(horizontal=True, vertical_alignment="center"):
            submitted = st.button(
                "Build teaching profile",
                type="primary",
                icon=":material/auto_awesome:",
                width="stretch",
                key="suggest_build",
            )
            cleared = icon_button(
                "Clear name, company, title, notes, JD, profile sections, and upload",
                key="suggest_clear",
            )
    if cleared:
        _clear_suggest_form()
        st.rerun()
    if submitted:
        jd_text = (jd or "").strip()
        if not jd_text and jd_file is not None:
            jd_text = jd_file.getvalue().decode("utf-8", errors="replace").strip()
        if not (name or "").strip() or not (company or "").strip():
            st.error("Add a name and a real last company.", icon=":material/error:")
        else:
            if not open_ai_session():
                st.stop()
            profile_seed = _collect_profile_seed()
            req = config.DATA_DIR / "suggestion_request.yaml"
            req.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "name": name.strip(),
                "last_company": company.strip(),
                "title": (title or "").strip(),
                "notes": (notes or "").strip(),
                "jd": jd_text,
            }
            if profile_seed:
                payload["profile_seed"] = profile_seed
            req.write_text(
                yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
            run_bg(f"suggest {company.strip()}", "samples", "suggest", "--request", str(req))
            st.session_state["suggestion_pending"] = sm._slug(name.strip(), company.strip())

    with st.expander("Recover from ChatGPT JSON (timeout)", icon=":material/content_paste:"):
        st.caption(
            "If Build timed out but ChatGPT already showed JSON, paste the object here to save the teaching model."
        )
        pasted = st.text_area("Paste suggestion JSON", height=160, key="suggest_paste_json")
        if st.button("Save pasted JSON", icon=":material/save:", key="suggest_paste_save"):
            try:
                raw = json.loads(pasted)
                path = config.DATA_DIR / "import_pasted_suggestion.json"
                path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
                suggestion, paths = sm.import_suggestion_json(path)
                st.session_state["suggestion_pending"] = sm._slug(
                    suggestion.persona_name, suggestion.last_company
                )
                st.success(
                    f"Saved {suggestion.persona_name} @ {suggestion.last_company} "
                    f"({suggestion.sample.benchmarks.get('total_relevant_experience', '?')})",
                    icon=":material/check_circle:",
                )
                st.caption(paths["profile"])
                st.rerun()
            except Exception as e:  # noqa: BLE001
                st.error(str(e), icon=":material/error:")

    st.subheader("Teach from the model", icon=":material/menu_book:")
    teaching_workspace()

    with st.expander("Archetype benchmarks", icon=":material/compare:"):
        arch = sm.archetypes()
        key = st.selectbox("Archetype", list(arch), format_func=lambda k: arch[k]["name"])
        st.markdown(arch[key]["description"])
        with st.container(horizontal=True):
            if st.button("Generate sample", icon=":material/auto_awesome:"):
                if open_ai_session():
                    run_bg(f"sample {key}", "samples", "generate", key)
            if st.button("Compare with active profile", icon=":material/compare:"):
                if open_ai_session():
                    active = get_active_profile()
                    args = ["samples", "compare", key]
                    if active:
                        args += ["--profile", active]
                    run_bg(f"compare {key}", *args)
        sample_md = config.SAMPLES_DIR / f"{key}.md"
        cmp_md = config.OUTPUT_DIR / f"compare_{key}.md"
        if cmp_md.exists():
            st.subheader("You vs benchmark")
            st.markdown(cmp_md.read_text(encoding="utf-8"))
        if sample_md.exists():
            st.subheader("Benchmark")
            st.markdown(sample_md.read_text(encoding="utf-8"))
        else:
            st.caption("Not generated yet.")


def page_tracker() -> None:
    page_header(
        "Application tracker",
        "Shortlist or mark a job applied on Jobs, then record the stage here.",
        ":material/checklist:",
    )
    with db.session() as s:
        apps = s.exec(select(Application)).all()
        jobs = {j.id: j for j in s.exec(select(Job).where(Job.status.in_(["shortlisted", "applied"]))).all()}
        all_apps = {a.job_id: a for a in apps}
    if jobs:
        jid = st.selectbox(
            "Job",
            list(jobs),
            format_func=lambda i: f"{jobs[i].company} · {jobs[i].title}",
        )
        cur = all_apps.get(jid)
        notes_key = f"track_notes_{jid}"
        if notes_key not in st.session_state:
            st.session_state[notes_key] = cur.notes if cur else ""
        with st.form("track"):
            stage = st.segmented_control(
                "Stage",
                STAGES,
                default=cur.stage if cur and cur.stage in STAGES else STAGES[0],
                required=True,
                width="stretch",
                wrap=True,
            )
            notes = st.text_area("Notes", height=120, key=notes_key)
            with st.container(horizontal=True, vertical_alignment="center"):
                saved = st.form_submit_button(
                    "Save", type="primary", icon=":material/save:", width="stretch"
                )
                cleared = icon_button(
                    "Clear notes",
                    key=f"track_notes_clear_{jid}",
                    form=True,
                )
        if cleared:
            st.session_state[notes_key] = ""
            st.rerun()
        if saved:
            with db.session() as s:
                row = s.exec(select(Application).where(Application.job_id == jid)).first() or Application(job_id=jid)
                row.stage, row.notes, row.updated_at = stage, notes, utcnow()
                s.add(row)
                s.commit()
            st.rerun()
        if cur and icon_button(
            "Remove this application tracker entry",
            key=f"delete_track_{jid}",
            icon=":material/delete:",
        ):
            with db.session() as s:
                row = s.exec(select(Application).where(Application.job_id == jid)).first()
                if row:
                    s.delete(row)
                    s.commit()
            st.session_state.pop(notes_key, None)
            st.toast("Tracking entry deleted")
            st.rerun()
    else:
        st.info("Mark a job shortlisted or applied on Jobs to track it here.", icon=":material/info:")
        st.button("Go to jobs", icon=":material/arrow_forward:", on_click=go, args=("Jobs",))
    if apps:
        st.subheader("History", icon=":material/history:")
        with db.session() as s:
            names = {j.id: f"{j.company} · {j.title}" for j in s.exec(select(Job)).all()}
        st.dataframe(
            pd.DataFrame([
                {"job": names.get(a.job_id, a.job_id), "stage": a.stage, "notes": a.notes, "updated": a.updated_at}
                for a in apps
            ]),
            hide_index=True,
            alt="Application history",
        )


def page_llm_log() -> None:
    page_header("LLM call log", "The last 100 model calls, newest first.", ":material/history:")
    with db.session() as s:
        calls = s.exec(select(LLMCall).order_by(LLMCall.id.desc()).limit(100)).all()
    if not calls:
        st.info("No calls yet.", icon=":material/info:")
        return
    st.dataframe(
        pd.DataFrame([
            {"id": c.id, "when": c.created_at, "task": c.task, "provider": c.provider,
             "ok": c.ok, "seconds": c.duration_s, "error": c.error[:80]}
            for c in calls
        ]),
        hide_index=True,
        alt="Recent LLM calls",
    )
    pick = st.selectbox("Inspect call", [c.id for c in calls], format_func=lambda i: f"{i}")
    c = next(x for x in calls if x.id == pick)
    prompt_col, reply_col = st.columns(2, gap="medium")
    prompt_col.text_area("Prompt", c.prompt, height=320)
    reply_col.text_area("Reply", c.reply, height=320)


def page_manual() -> None:
    page_header(
        "Manual replies",
        "For tasks set to provider: manual in config/models.yaml. Copy the prompt into any chat, then paste the reply.",
        ":material/forum:",
    )
    d = config.OUTPUT_DIR / "manual"
    d.mkdir(parents=True, exist_ok=True)
    pending = sorted(p for p in d.glob("*.prompt.md") if not p.with_name(p.name.replace(".prompt.", ".reply.")).exists())
    if not pending:
        st.info("Nothing waiting.", icon=":material/check_circle:")
        return
    st.caption(f"{len(pending)} waiting")
    for p in pending:
        with st.expander(p.name, expanded=True, icon=":material/chat:"):
            st.caption("1. Copy the prompt. 2. Paste the reply. 3. Submit.")
            st.code(p.read_text(encoding="utf-8"), language="markdown")
            reply = st.text_area("Paste the model's reply", key=p.name, height=200)
            submit_col, clear_col, dismiss_col = st.columns([16, 1, 1], vertical_alignment="center")
            if submit_col.button(
                "Submit reply", key="b" + p.name, type="primary", icon=":material/send:", width="stretch"
            ) and reply.strip():
                p.with_name(p.name.replace(".prompt.", ".reply.")).write_text(reply, encoding="utf-8")
                st.rerun()
            with clear_col:
                if icon_button(
                    "Clear the pasted reply",
                    key="clear_" + p.name,
                ):
                    st.session_state[p.name] = ""
                    st.rerun()
            with dismiss_col:
                if icon_button(
                    "Remove this pending prompt without a reply",
                    key="delete_" + p.name,
                    icon=":material/delete:",
                ):
                    p.unlink(missing_ok=True)
                    st.session_state.pop(p.name, None)
                    st.rerun()


def page_top_tier_screen() -> None:
    page_header(
        "Top 0.1% Screen",
        "Paste a JD and a resume (or use the active profile). Get fit, ATS coverage, and a recruiter verdict on whether it clears a top 0.1% bar.",
        ":material/military_tech:",
    )
    st.caption(
        "Uses the Overview AI engine (GPT or Claude browser, or API keys). "
        "Ad-hoc resume uploads are scored only; they do not overwrite a saved profile."
    )
    if "match_jd_nonce" not in st.session_state:
        st.session_state["match_jd_nonce"] = 0
    if "match_resume_nonce" not in st.session_state:
        st.session_state["match_resume_nonce"] = 0

    upload_root = config.OUTPUT_DIR / "matches" / "_uploads"
    upload_root.mkdir(parents=True, exist_ok=True)

    with st.container(border=True):
        st.subheader("Inputs", icon=":material/input:")
        jd_col, resume_col = st.columns(2)
        with jd_col:
            jd_text = st.text_area(
                "Job description",
                height=220,
                placeholder="Paste the full JD or job details here.",
                key="match_jd_text",
            )
            jd_up = st.file_uploader(
                "Or upload a JD file",
                type=["txt", "md", "pdf", "docx"],
                key=f"match_jd_file_{st.session_state['match_jd_nonce']}",
            )
            with db.session() as s:
                job_ids = [j.id for j in s.exec(select(Job).order_by(Job.id.desc())).all()[:80]]
            use_job = st.selectbox(
                "Or use a collected job",
                options=[None, *job_ids],
                format_func=lambda i: "(none)" if i is None else f"#{i}",
                key="match_job_id",
            )
        with resume_col:
            active = get_active_profile()
            use_active = st.checkbox("Use active profile", value=True, key="match_use_master")
            resume_up = st.file_uploader(
                "Or upload a candidate resume",
                type=["pdf", "docx", "md", "txt"],
                key=f"match_resume_file_{st.session_state['match_resume_nonce']}",
                disabled=use_active,
            )
            if active:
                st.caption(f"Active profile: `{active}`")
            else:
                st.warning("No active profile yet. Upload a resume or import one on Profiles.", icon=":material/warning:")

        run = st.button("Run top 0.1% screen", type="primary", icon=":material/military_tech:", width="stretch")
        if run:
            if not open_ai_session():
                st.stop()
            args: list[str] = ["match"]
            if use_job is not None:
                args += ["--job-id", str(int(use_job))]
            elif jd_up is not None:
                dest = upload_root / f"jd_{jd_up.name}"
                dest.write_bytes(jd_up.getvalue())
                args += ["--jd-file", str(dest)]
            elif jd_text.strip():
                dest = upload_root / "jd_paste.txt"
                dest.write_text(jd_text.strip(), encoding="utf-8")
                args += ["--jd-file", str(dest)]
            else:
                st.error("Provide a JD (paste, file, or collected job).", icon=":material/error:")
                st.stop()
            if not use_active:
                if resume_up is None:
                    st.error("Upload a resume, or check Use active profile.", icon=":material/error:")
                    st.stop()
                dest = upload_root / f"resume_{resume_up.name}"
                dest.write_bytes(resume_up.getvalue())
                args += ["--resume", str(dest)]
            elif not active:
                st.error("Active profile missing. Upload a resume instead.", icon=":material/error:")
                st.stop()
            else:
                args += ["--profile", active]
            run_bg("top 0.1% screen", *args)

    matches_dir = config.OUTPUT_DIR / "matches"
    latest = None
    if matches_dir.exists():
        dirs = sorted(
            [p for p in matches_dir.iterdir() if p.is_dir() and p.name != "_uploads" and (p / "report.json").exists()],
            key=lambda p: p.name,
            reverse=True,
        )
        latest = dirs[0] if dirs else None

    st.subheader("Latest report", icon=":material/assessment:")
    if not latest:
        st.info("No screens yet. Run one above.", icon=":material/info:")
        tasks_panel()
        return

    data = json.loads((latest / "report.json").read_text(encoding="utf-8"))
    screen = data.get("screen") or {}
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Tier", screen.get("tier_label") or "—", border=True)
    m2.metric("Fit", f"{data.get('fit_score', 0):.0f}/100", border=True)
    m3.metric("ATS", f"{data.get('ats_coverage', 0):.0f}%", border=True)
    m4.metric("Band", data.get("screen_band") or "—", border=True)
    if screen.get("verdict"):
        st.markdown(screen["verdict"])
    if data.get("percentile") is not None:
        st.caption(f"Fit percentile vs analyzed jobs: {data['percentile']:.0f}th")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Strengths**")
        st.write("\n".join(f"- {x}" for x in (screen.get("strengths") or [])) or "_none_")
        st.markdown("**Gaps vs top 0.1% bar**")
        st.write("\n".join(f"- {x}" for x in (screen.get("gaps_vs_bar") or [])) or "_none_")
    with c2:
        st.markdown("**ATS risks**")
        st.write("\n".join(f"- {x}" for x in (screen.get("ats_risks") or [])) or "_none_")
        st.markdown("**Priority actions**")
        st.write("\n".join(f"- {x}" for x in (screen.get("priority_actions") or [])) or "_none_")

    with st.expander("Keywords and profile gaps", icon=":material/key:"):
        st.write("Present: " + (", ".join(data.get("keywords_present") or []) or "(none)"))
        st.write("Missing: " + (", ".join(data.get("keywords_missing") or []) or "(none)"))
        gaps = data.get("gaps") or []
        if gaps:
            st.dataframe(pd.DataFrame(gaps), hide_index=True, width="stretch")

    md_path = latest / "report.md"
    if md_path.exists():
        st.download_button(
            "Download report.md",
            data=md_path.read_text(encoding="utf-8"),
            file_name=f"match_{latest.name}.md",
            mime="text/markdown",
            icon=":material/download:",
        )
    st.caption(f"Saved under `{latest}`")
    tasks_panel()


NAV_LABELS = {
    "Overview": ":material/space_dashboard: Overview",
    "Top 0.1% Screen": ":material/military_tech: Top 0.1%",
    "Samples": ":material/school: Teaching",
    "Jobs": ":material/work: Jobs",
    "Tracker": ":material/conversion_path: Tracker",
    "Profile": ":material/person: Profiles",
    "Market and gaps": ":material/query_stats: Market",
    "LLM log": ":material/history: Activity",
    "Manual replies": ":material/forum: Manual",
}
PAGES = {
    "Overview": page_overview,
    "Top 0.1% Screen": page_top_tier_screen,
    "Samples": page_samples,
    "Jobs": page_jobs,
    "Tracker": page_tracker,
    "Profile": page_profile,
    "Market and gaps": page_market,
    "LLM log": page_llm_log,
    "Manual replies": page_manual,
}
def _bridge_listening() -> bool:
    import socket
    try:
        with socket.create_connection((config.bridge_host(), config.bridge_port()), 0.4):
            return True
    except OSError:
        return False


if not os.environ.get("PYTEST_CURRENT_TEST") and not st.session_state.get("bridge_autostarted"):
    if not _bridge_listening():
        _spawn(["bridge", "serve"], "bridge", detached=True)
    st.session_state["bridge_autostarted"] = True

inject_shell()
st.sidebar.markdown(
    """
<div class="jt-brand">
  <div class="jt-mark">JT</div>
  <div>
    <div class="jt-name">Job Copilot</div>
    <div class="jt-sub">Teaching studio</div>
  </div>
</div>
""",
    unsafe_allow_html=True,
)
_browser_now = load_prefs()["browser"]
if "browser_session" not in st.session_state:
    st.session_state["browser_session"] = BROWSER_LABELS.get(_browser_now, "ChatGPT")
_browser_pick = st.sidebar.selectbox(
    "Session",
    [BROWSER_LABELS[b] for b in BROWSERS],
    key="browser_session",
    help="Opens in a tab of this browser when a build needs it.",
)
_browser_chosen = BROWSERS[[BROWSER_LABELS[b] for b in BROWSERS].index(_browser_pick)]
if _browser_chosen != _browser_now:
    save_prefs(browser=_browser_chosen)
_active_now = get_active_profile()
_profile_names = list_profiles()
if _profile_names:
    _profile_idx = _profile_names.index(_active_now) if _active_now in _profile_names else 0
    _profile_pick = st.sidebar.selectbox(
        "Profile",
        _profile_names,
        index=_profile_idx,
        key="sidebar_profile",
        help="Active candidate profile for analyze, tailor, and match.",
    )
    if _profile_pick != _active_now:
        set_active_profile(_profile_pick)
else:
    st.sidebar.caption("No profiles yet — open Profiles to import one.")
sidebar_activity()
if st.session_state.get("page") == "Job detail":
    st.session_state["page"] = "Jobs"
choice = st.radio(
    "Page",
    list(PAGES),
    format_func=lambda name: NAV_LABELS[name],
    key="page",
    label_visibility="collapsed",
    horizontal=True,
    width="stretch",
)
PAGES[choice]()
