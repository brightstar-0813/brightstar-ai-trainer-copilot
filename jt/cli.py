"""`jt` command line interface."""
from __future__ import annotations

import secrets
from pathlib import Path

import typer
from rich import print as rprint
from rich.table import Table

from . import config

app = typer.Typer(help="AI Trainer Job Copilot", no_args_is_help=True)
bridge_app = typer.Typer(help="LLM bridge to your logged-in Claude/ChatGPT", no_args_is_help=True)
llm_app = typer.Typer(help="LLM engines: OpenAI/Anthropic API or Claude/ChatGPT browser", no_args_is_help=True)
app.add_typer(bridge_app, name="bridge")
app.add_typer(llm_app, name="llm")


@app.command()
def init() -> None:
    """Create folders and a .env with a fresh bridge token."""
    config.ensure_dirs()
    env_path = config.ROOT / ".env"
    if env_path.exists():
        rprint(f"[yellow].env already exists[/yellow] at {env_path}")
    else:
        text = (config.ROOT / ".env.example").read_text(encoding="utf-8")
        text = text.replace("JT_BRIDGE_TOKEN=change-me", f"JT_BRIDGE_TOKEN={secrets.token_urlsafe(24)}")
        env_path.write_text(text, encoding="utf-8")
        rprint(f"[green]Created {env_path}[/green]")
    from .db import get_engine
    get_engine()
    rprint(f"Database ready at {config.DB_PATH}")
    rprint("Easiest: put OPENAI_API_KEY in .env, then `jt llm status` and start using analyze/tailor.")
    rprint("Optional browser path: load extension/, `jt bridge serve`, `jt ext-config` for the token.")


@app.command("ext-config")
def ext_config() -> None:
    """Show the values to paste into the extension popup."""
    rprint(f"Bridge URL: ws://{config.bridge_host()}:{config.bridge_port()}")
    rprint(f"Token:      {config.bridge_token()}")
    rprint(f"Extension folder: {config.ROOT / 'extension'}")


@llm_app.command("status")
def llm_status() -> None:
    """Show preferred engine, API keys, and bridge connection."""
    from .llm.client import status_summary
    st = status_summary()
    rprint(f"Preferred engine: [bold]{st['preferred']}[/bold]  ({st['preferred_label']})")
    rprint(f"Auto resolves to: [bold]{st['resolved_auto']}[/bold]")
    o, a = st["openai"], st["anthropic"]
    rprint(f"OpenAI:    [{'green' if o['ok'] else 'yellow'}]{o['detail']}[/]")
    rprint(f"Anthropic: [{'green' if a['ok'] else 'yellow'}]{a['detail']}[/]")
    b = st["bridge"] or {}
    if b.get("error"):
        rprint(f"Bridge:    [red]{b['error']}[/red]")
    elif b.get("extension_connected"):
        rprint(f"Bridge:    [green]extension connected[/green]  busy={b.get('busy') or '-'}")
    else:
        rprint("Bridge:    [yellow]running but extension not connected[/yellow]" if "busy" in b
               else "Bridge:    [yellow]not running[/yellow]")


@llm_app.command("engine")
def llm_engine(
    name: str = typer.Argument(..., help="auto|openai|anthropic|claude|gpt|manual"),
) -> None:
    """Set the preferred engine for tasks configured as provider: auto."""
    from .llm.prefs import ENGINE_LABELS, save_prefs
    try:
        data = save_prefs(engine=name)
    except ValueError as e:
        rprint(f"[red]{e}[/red]")
        raise typer.Exit(1)
    rprint(f"[green]Engine set to {data['engine']}[/green] — {ENGINE_LABELS[data['engine']]}")
    rprint(f"Saved to {config.DATA_DIR / 'llm_prefs.yaml'}")


@llm_app.command("test")
def llm_test(
    providers: list[str] = typer.Argument(
        None, help="openai anthropic claude gpt (default: whichever auto resolves to)"),
) -> None:
    """Send a tiny JSON prompt to each provider and verify the round trip."""
    from .llm.client import LLMError, ask_json, resolve_provider
    from .schemas import BridgeTest
    providers = providers or [resolve_provider("auto")]
    table = Table("provider", "result", "detail")
    failed = False
    for p in providers:
        try:
            r = ask_json("bridge_test", BridgeTest, provider=p, timeout=120, max_repairs=1)
            table.add_row(p, "[green]OK[/green]", f"ok={r.ok} note={r.note}")
        except LLMError as e:
            failed = True
            table.add_row(p, "[red]FAIL[/red]", f"{e.code or 'error'}: {e}")
    rprint(table)
    if failed:
        raise typer.Exit(1)


@bridge_app.command("serve")
def bridge_serve() -> None:
    """Run the bridge server (keep this running)."""
    from .llm.bridge import serve_forever
    serve_forever()


@bridge_app.command("status")
def bridge_status() -> None:
    """Show whether the extension is connected."""
    from .llm.client import BridgeClient, LLMError
    try:
        with BridgeClient() as bc:
            st = bc.status()
    except LLMError as e:
        rprint(f"[red]{e}[/red]")
        raise typer.Exit(1)
    ok = st["extension_connected"]
    rprint(f"Extension: [{'green' if ok else 'red'}]{'connected' if ok else 'NOT connected'}[/]"
           f"  busy={st['busy'] or '-'}")


@bridge_app.command("test")
def bridge_test(providers: list[str] = typer.Argument(None, help="claude gpt mock (default: claude and gpt)")) -> None:
    """Send a tiny JSON prompt through the browser bridge (claude/gpt/mock)."""
    from .llm.client import LLMError, ask_json
    from .schemas import BridgeTest
    providers = providers or ["claude", "gpt"]
    table = Table("provider", "result", "detail")
    failed = False
    for p in providers:
        try:
            r = ask_json("bridge_test", BridgeTest, provider=p, timeout=120, max_repairs=1)
            table.add_row(p, "[green]OK[/green]", f"ok={r.ok} note={r.note}")
        except LLMError as e:
            failed = True
            table.add_row(p, "[red]FAIL[/red]", f"{e.code or 'error'}: {e}")
    rprint(table)
    if failed:
        raise typer.Exit(1)


sources_app = typer.Typer(help="Job sources", no_args_is_help=True)
app.add_typer(sources_app, name="sources")


@sources_app.command("discover")
def sources_discover() -> None:
    """Find which ATS (Greenhouse/Lever/Ashby) each configured company uses."""
    from .sources.ats import discover
    table = Table("company", "ats", "slug", "open jobs")
    for row in discover():
        table.add_row(row["company"], row["ats"] or "[red]not found[/red]", row["slug"] or "-", str(row["open_jobs"]))
    rprint(table)


@app.command()
def collect(
    ats: bool = typer.Option(True, help="Collect from public ATS boards"),
    linkedin: bool = typer.Option(False, "--linkedin", help="Collect from LinkedIn via Octo Browser"),
    keep_irrelevant: bool = typer.Option(False, help="Store jobs even if they do not look like AI-trainer work"),
) -> None:
    """Collect jobs into the database."""
    from .collect import store
    if ats:
        from .sources.ats import collect_all, verified_boards
        if not verified_boards():
            rprint("[yellow]No verified boards yet; running discovery first...[/yellow]")
            from .sources.ats import discover
            discover()
        st = store(collect_all(), keep_irrelevant=keep_irrelevant)
        rprint(f"[bold]ATS boards[/bold]: seen {st.seen}, not relevant {st.irrelevant}, "
               f"duplicates {st.duplicates}, [green]new {st.new}[/green]")
    if linkedin:
        from .browser.octo import OctoError
        from .sources.linkedin import LinkedInBlocked, collect_linkedin
        try:
            st = store(collect_linkedin(log=lambda m: rprint(m)), keep_irrelevant=keep_irrelevant, strict=False)
        except (OctoError, LinkedInBlocked) as e:
            rprint(f"[red]{e}[/red]")
            raise typer.Exit(1)
        rprint(f"[bold]LinkedIn[/bold]: seen {st.seen}, not relevant {st.irrelevant}, "
               f"duplicates {st.duplicates}, [green]new {st.new}[/green]")


jobs_app = typer.Typer(help="Browse stored jobs", no_args_is_help=True)
app.add_typer(jobs_app, name="jobs")


@jobs_app.command("list")
def jobs_list(limit: int = 30, status: str = typer.Option(None), source: str = typer.Option(None),
              min_fit: float = typer.Option(None, help="Only analyzed jobs with at least this fit score")) -> None:
    """List jobs (best fit first when analyzed)."""
    from sqlmodel import select
    from . import db
    from .models import Job, JobAnalysis
    with db.session() as s:
        q = select(Job)
        if status:
            q = q.where(Job.status == status)
        if source:
            q = q.where(Job.source == source)
        jobs = s.exec(q).all()
        fits = {a.job_id: a.fit_score for a in s.exec(select(JobAnalysis)).all()}
    rows = [(j, fits.get(j.id)) for j in jobs]
    if min_fit is not None:
        rows = [r for r in rows if r[1] is not None and r[1] >= min_fit]
    rows.sort(key=lambda r: (r[1] is None, -(r[1] or 0), -r[0].relevance))
    table = Table("id", "fit", "source", "company", "title", "pay", "status")
    for j, fit in rows[:limit]:
        table.add_row(str(j.id), "-" if fit is None else f"{fit:.0f}", j.source, j.company[:24], j.title[:50],
                      j.pay[:18], j.status)
    rprint(table)
    rprint(f"{len(rows)} jobs")


@jobs_app.command("show")
def jobs_show(job_id: int) -> None:
    """Show one job's details."""
    from . import db
    from .models import Job
    with db.session() as s:
        j = s.get(Job, job_id)
    if not j:
        rprint("[red]not found[/red]")
        raise typer.Exit(1)
    rprint(f"[bold]{j.title}[/bold] - {j.company} ({j.location})\n{j.url}\nPay: {j.pay or '-'}  Status: {j.status}\n")
    rprint(j.description[:4000])


@jobs_app.command("status")
def jobs_status(job_id: int, status: str = typer.Argument(..., help="new|shortlisted|applied|rejected|ignored")) -> None:
    """Set a job's status."""
    from . import db
    from .models import Job
    with db.session() as s:
        j = s.get(Job, job_id)
        if not j:
            rprint("[red]not found[/red]")
            raise typer.Exit(1)
        j.status = status
        s.add(j)
        s.commit()
    rprint(f"job {job_id} -> {status}")


def _llm_guard(fn):
    """Turn LLMError into a clean message instead of a traceback."""
    import functools

    from .llm.client import LLMError

    @functools.wraps(fn)
    def wrapper(*a, **kw):
        try:
            return fn(*a, **kw)
        except LLMError as e:
            rprint(f"[red]LLM error ({e.code or 'error'}):[/red] {e}")
            raise typer.Exit(1)
        except FileNotFoundError as e:
            rprint(f"[red]{e}[/red]")
            raise typer.Exit(1)
    return wrapper


@app.command()
@_llm_guard
def analyze(job_id: int = typer.Argument(None, help="Job id; omit with --all-new"),
            all_new: bool = typer.Option(False, "--all-new", help="Analyze every job without an analysis"),
            limit: int = typer.Option(None, help="Max jobs in batch mode"),
            pace: float = typer.Option(5.0, help="Seconds to wait between jobs in batch mode"),
            force: bool = typer.Option(False, help="Re-analyze even if an analysis exists"),
            profile: str = typer.Option(None, "--profile", help="Profile slug (default: active)")) -> None:
    """Extract requirements with the LLM and score fit against the active profile."""
    from .pipelines.analyze import analyze_job, analyze_pending
    from .schemas import resolve_profile_slug
    used = resolve_profile_slug(profile)
    if all_new:
        done, failed = analyze_pending(
            limit=limit, pace_seconds=pace, on_event=lambda m: rprint(m), profile=used)
        rprint(f"[green]{done} analyzed[/green], {failed} failed (profile: {used}). See: jt rank")
    elif job_id is not None:
        a = analyze_job(job_id, force=force, profile=used)
        rprint(f"job {job_id}: fit {a.fit_score:.0f}  (profile: {used}; see `jt jobs gaps {job_id}`)")
    else:
        rprint("[red]give a job id or --all-new[/red]")
        raise typer.Exit(1)


@app.command()
@_llm_guard
def rescore(profile: str = typer.Option(None, "--profile", help="Profile slug (default: active)")) -> None:
    """Recompute fit scores for all analyzed jobs (after editing a profile)."""
    from .pipelines.analyze import rescore_all
    from .schemas import resolve_profile_slug
    used = resolve_profile_slug(profile)
    rprint(f"rescored {rescore_all(profile=used)} jobs (profile: {used})")


@app.command()
def rank(limit: int = 25) -> None:
    """Show analyzed jobs ranked by fit."""
    from .pipelines.analyze import ranked, requirements_of
    table = Table("id", "fit", "company", "title", "domain", "pay", "must-gaps")
    for job, a in ranked(limit):
        must_gaps = sum(1 for g in __import__("json").loads(a.gaps_json) if g["kind"] == "must")
        table.add_row(str(job.id), f"{a.fit_score:.0f}", job.company[:18], job.title[:44],
                      requirements_of(a).domain[:14], job.pay[:16], str(must_gaps))
    rprint(table)


@app.command("match")
@_llm_guard
def match_cmd(
    jd: str = typer.Option("", "--jd", help="Pasted job description text"),
    jd_file: Path = typer.Option(None, "--jd-file", exists=True, help="JD file (.txt .md .pdf .docx)"),
    job_id: int = typer.Option(None, "--job-id", help="Use a collected job's description"),
    resume: Path = typer.Option(None, "--resume", exists=True, help="Candidate resume (.pdf .docx .md .txt)"),
    profile: str = typer.Option(None, "--profile", help="Profile slug when not uploading a resume"),
) -> None:
    """Screen a resume/profile vs a JD: fit, ATS coverage, and top 0.1% recruiter verdict."""
    from .pipelines.match import screen_match
    report = screen_match(jd=jd, jd_file=jd_file, job_id=job_id, resume=resume, profile=profile)
    screen = report.screen
    tier = screen.tier_label if screen else "?"
    top = "yes" if screen and screen.is_top_tier else "no"
    rprint(
        f"[bold]Tier {tier}[/bold] (top 0.1%: {top}) | "
        f"fit {report.fit_score:.0f} ({report.screen_band}) | ATS {report.ats_coverage:.0f}%"
    )
    if report.percentile is not None:
        rprint(f"Fit percentile vs analyzed jobs: {report.percentile:.0f}th")
    if screen:
        rprint(screen.verdict)
        if screen.gaps_vs_bar:
            rprint("[bold]Gaps vs bar[/bold]\n" + "\n".join(f"- {g}" for g in screen.gaps_vs_bar[:8]))
        if screen.priority_actions:
            rprint("[bold]Actions[/bold]\n" + "\n".join(f"- {a}" for a in screen.priority_actions[:8]))
    if report.keywords_missing:
        rprint("Missing keywords: " + ", ".join(report.keywords_missing[:12]))
    rprint(f"[green]Report:[/green] {report.report_dir}")


@jobs_app.command("gaps")
def jobs_gaps(job_id: int) -> None:
    """Show requirements and your gaps for an analyzed job."""
    from . import db
    from .pipelines.analyze import gaps_of, latest_analysis, requirements_of
    with db.session() as s:
        a = latest_analysis(s, job_id)
    if not a:
        rprint("[yellow]not analyzed yet: jt analyze " + str(job_id) + "[/yellow]")
        raise typer.Exit(1)
    req = requirements_of(a)
    rprint(f"[bold]Fit {a.fit_score:.0f}[/bold] | {req.domain} | {', '.join(req.task_types)} | {req.pay or 'pay n/a'}")
    rprint("[bold]Must-haves[/bold]\n" + "\n".join(f"- {r.text}" for r in req.must_haves))
    rprint("[bold]Screening signals[/bold]\n" + ("\n".join(f"- {x}" for x in req.screening_signals) or "-"))
    if req.red_flags:
        rprint("[red]Red flags[/red]\n" + "\n".join(f"- {x}" for x in req.red_flags))
    rprint("[bold]Your gaps[/bold]\n" + ("\n".join(f"- [{g.kind}] {g.requirement}" for g in gaps_of(a)) or "- none"))


@app.command()
@_llm_guard
def tailor(job_id: int,
           interactive: bool = typer.Option(True, help="Ask the gap questions in the terminal"),
           no_humanize: bool = typer.Option(False, help="Skip the humanize pass"),
           profile: str = typer.Option(None, "--profile", help="Profile slug (default: active)")) -> None:
    """Gap questions -> tailored resume (DOCX/PDF) + reusable resume prompt."""
    from .pipelines.tailor import answer_question, generate_questions, tailor_job
    from .schemas import resolve_profile_slug
    used = resolve_profile_slug(profile)
    qs = generate_questions(job_id, profile=used)
    if qs and interactive:
        rprint(f"[bold]{len(qs)} questions.[/bold] Answer truthfully; press Enter to skip (counts as 'no').")
        for q in qs:
            if q.answer:
                continue
            ans = typer.prompt(f"\n[{q.gap}]\n{q.question}", default="", show_default=False)
            if ans.strip():
                answer_question(q.id, ans)
    row = tailor_job(job_id, humanize=not no_humanize, profile=used)
    meta = __import__("json").loads(row.resume_json)["meta"]
    rprint(f"[green]Done.[/green] ATS keyword coverage {meta['ats_coverage']}% (profile: {used})")
    rprint(f"DOCX: {row.docx_path}\nPDF:  {row.pdf_path or '(no browser for PDF)'}\nPrompt: {row.prompt_path}")
    for w in meta["warnings"] + meta["llm_unverified"]:
        rprint(f"[yellow]check:[/yellow] {w}")
    if meta["keywords_missing"]:
        rprint("Missing keywords (add only if true): " + ", ".join(meta["keywords_missing"][:12]))


@app.command()
@_llm_guard
def questions(job_id: int,
              regenerate: bool = typer.Option(False, help="Replace existing questions"),
              profile: str = typer.Option(None, "--profile", help="Profile slug (default: active)")) -> None:
    """Generate (and print) the gap questions for a job; answer them in the dashboard or via `jt tailor`."""
    from .pipelines.tailor import generate_questions
    from .schemas import resolve_profile_slug
    used = resolve_profile_slug(profile)
    qs = generate_questions(job_id, regenerate=regenerate, profile=used)
    rprint(f"[dim]profile: {used}[/dim]")
    for q in qs:
        rprint(f"[{q.id}] ({q.gap}) {q.question}" + (f"\n    answer: {q.answer}" if q.answer else ""))
    if not qs:
        rprint("No gaps to ask about.")


@app.command()
def dashboard(port: int = 8501) -> None:
    """Open the Streamlit dashboard."""
    import subprocess
    import sys
    subprocess.run([sys.executable, "-m", "streamlit", "run", str(config.ROOT / "dashboard" / "app.py"),
                    "--server.port", str(port), "--browser.gatherUsageStats", "false"], check=False)


profile_app = typer.Typer(help="Named candidate profiles and LinkedIn coaching", no_args_is_help=True)
app.add_typer(profile_app, name="profile")


@profile_app.command("list")
def profile_list() -> None:
    """List saved profiles; mark the active one."""
    from .schemas import get_active_profile, list_profiles, profile_path
    active = get_active_profile()
    names = list_profiles()
    if not names:
        rprint("[yellow]No profiles yet.[/yellow] Import with `jt profile import --name <slug> --resume ...`")
        return
    for name in names:
        mark = " *" if name == active else ""
        rprint(f"{name}{mark}  [dim]{profile_path(name)}[/dim]")
    if active:
        rprint(f"[dim]Active: {active}[/dim]")


@profile_app.command("use")
def profile_use(name: str = typer.Argument(..., help="Profile slug to make active")) -> None:
    """Set the active profile used by analyze / tailor / match / optimize."""
    from .schemas import set_active_profile
    try:
        used = set_active_profile(name)
    except (FileNotFoundError, ValueError) as e:
        rprint(f"[red]{e}[/red]")
        raise typer.Exit(1)
    rprint(f"[green]Active profile:[/green] {used}")


@profile_app.command("import")
@_llm_guard
def profile_import(
    name: str = typer.Option(..., "--name", help="Profile slug, e.g. jane or acme-sme"),
    resume: Path = typer.Option(None, exists=True, help="Resume file (.pdf .docx .md .txt)"),
    linkedin_text: Path = typer.Option(None, exists=True, help="Text file with LinkedIn profile text"),
    yes: bool = typer.Option(False, "--yes", help="Overwrite an existing profile without asking"),
    activate: bool = typer.Option(True, "--activate/--no-activate", help="Make this the active profile"),
) -> None:
    """Draft profile/people/<name>.yaml from a resume and/or LinkedIn text."""
    from .pipelines.profile import import_profile
    from .schemas import profile_path, save_profile, validate_slug
    try:
        slug = validate_slug(name)
    except ValueError as e:
        rprint(f"[red]{e}[/red]")
        raise typer.Exit(1)
    path = profile_path(slug)
    if path.exists() and not yes:
        if not typer.confirm(f"{path} exists. Overwrite?"):
            raise typer.Exit()
    p, questions = import_profile(resume, linkedin_text.read_text(encoding="utf-8") if linkedin_text else "")
    saved = save_profile(p, slug=slug, activate=activate)
    rprint(f"[green]Saved {saved}[/green]. Review and edit it by hand; it is the source of truth for that candidate.")
    if activate:
        rprint(f"[dim]Active profile: {slug}[/dim]")
    if questions:
        rprint("[bold]Questions that would strengthen it:[/bold]\n" + "\n".join(f"- {q}" for q in questions))


@profile_app.command("show")
def profile_show(profile: str = typer.Option(None, "--profile", help="Profile slug (default: active)")) -> None:
    """Print a candidate profile."""
    from .schemas import load_profile, resolve_profile_slug
    try:
        used = resolve_profile_slug(profile)
        rprint(f"[dim]# profile: {used}[/dim]")
        rprint(load_profile(used).to_yaml())
    except (FileNotFoundError, ValueError) as e:
        rprint(f"[red]{e}[/red]")
        raise typer.Exit(1)


@profile_app.command("optimize")
@_llm_guard
def profile_optimize(profile: str = typer.Option(None, "--profile", help="Profile slug (default: active)")) -> None:
    """LinkedIn headline/About/skills advice based on analyzed jobs."""
    from .pipelines.profile import advice_to_markdown, optimize_profile
    from .schemas import resolve_profile_slug
    used = resolve_profile_slug(profile)
    advice = optimize_profile(profile=used)
    out = config.OUTPUT_DIR / f"linkedin_advice_{used}.md"
    config.ensure_dirs()
    out.write_text(advice_to_markdown(advice), encoding="utf-8")
    rprint(f"[green]Saved {out}[/green] (profile: {used})")
    rprint("\n".join(f"- {h}" for h in advice.headline_options))


octo_app = typer.Typer(help="Octo Browser (LinkedIn)", no_args_is_help=True)
app.add_typer(octo_app, name="octo")


@octo_app.command("check")
def octo_check(open_linkedin: bool = typer.Option(True, help="Also open linkedin.com/feed and report login state")) -> None:
    """Start your Octo profile, attach Playwright, and check you are logged in to LinkedIn."""
    from .browser.octo import OctoError, octo_page
    try:
        with octo_page() as page:
            rprint("[green]Attached to the Octo profile.[/green]")
            if open_linkedin:
                page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
                page.wait_for_timeout(3000)
                logged_in = "/feed" in page.url and "login" not in page.url and "authwall" not in page.url
                rprint(f"URL: {page.url}\nLinkedIn login: " + ("[green]logged in[/green]" if logged_in else "[red]NOT logged in[/red]"))
    except OctoError as e:
        rprint(f"[red]{e}[/red]")
        raise typer.Exit(1)


@octo_app.command("profile-text")
def octo_profile_text(out: Path = typer.Option(Path("profile/linkedin_profile.txt"))) -> None:
    """Save the text of your own LinkedIn profile (feed it to `jt profile import --linkedin-text`)."""
    from .browser.octo import OctoError
    from .sources.linkedin import LinkedInBlocked, fetch_profile_text
    try:
        text = fetch_profile_text()
    except (OctoError, LinkedInBlocked) as e:
        rprint(f"[red]{e}[/red]")
        raise typer.Exit(1)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    rprint(f"[green]Saved {len(text)} chars to {out}[/green]")


samples_app = typer.Typer(help="Top 0.1% benchmark samples", no_args_is_help=True)
app.add_typer(samples_app, name="samples")


@samples_app.command("list")
def samples_list() -> None:
    from .pipelines.samples import archetypes, load_sample
    for key, a in archetypes().items():
        rprint(f"{key:22} {a['name']:42} {'[green]generated[/green]' if load_sample(key) else '-'}")


@samples_app.command("generate")
@_llm_guard
def samples_generate(key: str = typer.Argument(None, help="Archetype key; omit for all")) -> None:
    from .pipelines.samples import archetypes, generate_sample
    for k in ([key] if key else list(archetypes())):
        generate_sample(k)
        rprint(f"[green]generated[/green] {k} -> samples/archetypes/{k}.md")


@samples_app.command("compare")
@_llm_guard
def samples_compare(
    key: str,
    profile: str = typer.Option(None, "--profile", help="Profile slug (default: active)"),
) -> None:
    """Compare a candidate profile with a benchmark archetype."""
    from .pipelines.samples import compare, comparison_to_markdown
    from .schemas import resolve_profile_slug
    used = resolve_profile_slug(profile)
    md = comparison_to_markdown(compare(key, profile=used))
    config.ensure_dirs()
    (config.OUTPUT_DIR / f"compare_{key}.md").write_text(md, encoding="utf-8")
    rprint(f"[dim]profile: {used}[/dim]")
    rprint(md)


@samples_app.command("suggest")
@_llm_guard
def samples_suggest(
    name: str = typer.Option(None, "--name", help="Virtual candidate name"),
    company: str = typer.Option(
        None,
        "--company",
        help="Real last company (prefer a US high-ranking employer); latest role and industry anchor",
    ),
    title: str = typer.Option("", "--title", help="Last title, if you know it"),
    notes: str = typer.Option("", "--notes", help="Extra company or industry context"),
    jd: str = typer.Option("", "--jd", help="Job description. When set, the sample targets this job"),
    jd_file: Path = typer.Option(None, "--jd-file", help="Read the job description from a text file"),
    request: Path = typer.Option(
        None,
        "--request",
        help="YAML with name, last_company, title, notes, jd, and optional LinkedIn-style profile_seed",
    ),
) -> None:
    """Build a teaching profile and resume for a virtual candidate.

    Uses the name on the model resume and the real last company as the latest role.
    Other employers should be US high-ranking peers; universities and credentials are real.
    """
    import yaml

    from .pipelines.samples import suggest_sample

    data: dict = {}
    if request:
        loaded = yaml.safe_load(request.read_text(encoding="utf-8")) or {}
        if not isinstance(loaded, dict):
            rprint("[red]request file must be a YAML mapping[/red]")
            raise typer.Exit(1)
        data = loaded
    name = (name or data.get("name") or "").strip()
    company = (company or data.get("last_company") or data.get("company") or "").strip()
    title = title or str(data.get("title") or "")
    notes = notes or str(data.get("notes") or "")
    jd_text = (jd or "").strip()
    if not jd_text and jd_file:
        jd_text = jd_file.read_text(encoding="utf-8").strip()
    if not jd_text:
        jd_text = str(data.get("jd") or "").strip()
    profile_seed = data.get("profile_seed")
    if profile_seed is None:
        profile_seed = {
            key: data[key]
            for key in (
                "location",
                "headline",
                "about",
                "experience",
                "education",
                "licenses",
                "certifications",
                "skills",
                "languages",
                "projects",
            )
            if key in data
        }
    if not name or not company:
        rprint("[red]candidate name and last company are required[/red]")
        raise typer.Exit(1)
    suggestion, paths = suggest_sample(
        name, company, title=title, notes=notes, jd=jd_text, profile_seed=profile_seed
    )
    rprint(f"[yellow]{suggestion.sample.label}[/yellow]")
    rprint(f"Virtual candidate: [bold]{suggestion.persona_name}[/bold]")
    rprint(f"Target: {suggestion.inferred_domain} / {suggestion.inferred_industry} ({suggestion.target_kind})")
    rprint(suggestion.why_this_shape)
    rprint(f"[green]profile[/green] {paths['profile']}")
    rprint(f"[green]resume[/green]  {paths['docx']}")


@samples_app.command("import-json")
def samples_import_json(
    path: Path = typer.Argument(..., exists=True, readable=True, help="ChatGPT/Claude JSON reply file"),
    name: str = typer.Option("", "--name", help="Override virtual candidate name"),
    company: str = typer.Option("", "--company", help="Override last company"),
) -> None:
    """Save a pasted browser JSON reply as a teaching model (bridge timeout recovery)."""
    from .pipelines.samples import import_suggestion_json

    try:
        suggestion, paths = import_suggestion_json(path, name=name, company=company)
    except Exception as e:  # noqa: BLE001
        rprint(f"[red]{e}[/red]")
        raise typer.Exit(1)
    rprint(f"[yellow]{suggestion.sample.label}[/yellow]")
    rprint(f"Virtual candidate: [bold]{suggestion.persona_name}[/bold]")
    rprint(f"Experience: {suggestion.sample.benchmarks.get('total_relevant_experience', '?')}")
    rprint(f"[green]profile[/green] {paths['profile']}")
    rprint(f"[green]resume[/green]  {paths['docx']}")


if __name__ == "__main__":
    app()
