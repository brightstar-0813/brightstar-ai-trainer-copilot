---
name: job-search
description: Collect new AI-trainer jobs from public ATS boards and summarize what is new. Use when the user asks to search, refresh or find AI trainer / RLHF / AI tutor jobs.
---

# Job search

Run from the project root `D:\Work\JobHunting\00_AI Trainer\AI Trainer Copilot`. Use the venv: `.\.venv\Scripts\jt`
(or `.\.venv\Scripts\python -c "from jt.cli import app; app([...], standalone_mode=False)"` if `jt.exe` misbehaves).

1. Prefer one max-coverage fetch (matches the dashboard **Fetch AI trainer jobs** button):
   `jt collect --rediscover --broad --ats --mercor --us-remote-only --max-age-days 30`.
   That re-probes pinned + discovered ATS boards (Handshake Ashby, Surge, Scale, xAI, …),
   pulls Mercor expert listings from work.mercor.com, then keeps **US-eligible remote**
   AI-trainer / SME roles posted in the last ~30 days (unknown dates kept).
2. Lighter refresh when boards are already verified: `jt collect --broad`.
3. Do **not** collect jobs from LinkedIn (removed — account risk). Ignore any request to scrape LinkedIn jobs.
   Outlier/DataAnnotation project feeds need a logged-in account and are not scraped.
4. Summarize: `jt jobs list --limit 20` (new jobs have status `new`). Mention pay, company, posted date;
   fit scores appear only after analysis.
5. Offer the next step: `jt analyze --all-new --limit 10` (needs a usable LLM — check `jt llm status`; API key is
   enough, otherwise bridge + extension).

Do not analyze jobs yourself with the Cursor model; analysis runs through `jt` (OpenAI/Anthropic API or the
Claude/ChatGPT bridge).
