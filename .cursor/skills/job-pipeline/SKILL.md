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
  with optional `--jd` or `--jd-file`. Writes a profile, resume, and coach notes under
  `output/suggestions/`. The name is the virtual candidate. The last company is their latest employer
  in the model; other employers must be US high-ranking peers, and universities/credentials stay real.

## Rules
- Never invent facts for the user. If an answer is unknown, leave it empty.
- On `usage_limit`, `no_api_key`, `api_auth`, or `api_rate_limit` errors, stop and tell the user; do not retry.
- If a browser-path pipeline fails with `no_editor` or `send_failed`, the site markup probably changed: edit
  `extension/selectors.json`, then `jt bridge test`.
