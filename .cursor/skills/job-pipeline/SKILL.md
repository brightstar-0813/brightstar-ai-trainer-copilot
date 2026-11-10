---
name: job-pipeline
description: Run analysis, gap questions and resume tailoring for AI-trainer jobs through the Claude/ChatGPT bridge, and report results. Use when the user asks to analyze jobs, rank them, tailor a resume, or improve their LinkedIn profile.
---

# Job pipeline

Project root: `D:\Work\JobHunting\00_AI Trainer\AI Trainer Copiot`. Use `.\.venv\Scripts\jt`.

## Preflight
- `jt llm status` must show a usable engine. Prefer API: `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` in `.env` with
  engine `auto` / `openai` / `anthropic` (no bridge needed).
- If the preferred engine is `claude` or `gpt`: `jt bridge status` must show the extension connected. If not:
  `jt bridge serve` in a background terminal, and ask the user to open the extension popup (token from
  `jt ext-config`) and click Reconnect.
- `jt profile show` must succeed (uses the active profile). If none exists, ask for a resume and a slug, run
  `jt profile import --name <slug> --resume <file>`, then have them review `profile/people/<slug>.yaml`.

## Flows
- Rank: `jt analyze --all-new --limit 10` then `jt rank`.
- One job: `jt jobs gaps <id>` to explain fit and gaps.
- Resume: `jt questions <id>`; relay each question to the user and write their truthful answers (dashboard Job detail
  page, or `jt tailor <id>` which asks interactively). Then `jt tailor <id>`. Report the ATS coverage, every
  "check:" warning (unverified numbers/employers), and the output paths.
- LinkedIn: `jt profile optimize` writes `output/linkedin_advice.md`.
- Benchmarks: `jt samples generate`, `jt samples compare <archetype>`.
- Teaching model: `jt samples suggest --name "<virtual candidate>" --company "<real last company>"`
  with optional `--jd` / `--jd-file`, optional `--profile-file` (LinkedIn-style .txt/.md dump), and
  `--seed-mode last_company|provided` (default `last_company`). Dashboard Teaching models has the same
  paste/upload + Fill form flow plus a "Use provided employers / schools / certs" toggle.
  `provided` locks employers/schools/creds to the seed (skills/bullets/projects may still be generated);
  `last_company` is the original invent-peers path. Writes under `output/suggestions/`.
  The name is the virtual candidate. The last company is their latest employer in the model;
  in last_company mode other employers must be US high-ranking peers, and universities/credentials stay real.
  JD-targeted runs write to a `*-jd` folder so the company-domain base is kept.
  When the JD needs more than a master's, the model should use PhD/postdoc/professional doctorate
  education from a real high-ranking university, listed as separate degree entries with the prior
  bachelor's/master's ladder (and a second field degree when dual expertise is needed). Licenses and
  certifications should be dense when real credentials exist for the domain (typically 1–3 licenses
  plus 2–4 specialty certs, or 3–6 vendor/professional certs) — not a single token credential.
  Resume tailor keeps every real degree in the master profile but surfaces only job-relevant ones.

## Rules
- Never invent facts for the user. If an answer is unknown, leave it empty.
- On `usage_limit`, `no_api_key`, `api_auth`, or `api_rate_limit` errors, stop and tell the user; do not retry.
- If a browser-path pipeline fails with `no_editor` or `send_failed`, the site markup probably changed: edit
  `extension/selectors.json`, then `jt bridge test`.
