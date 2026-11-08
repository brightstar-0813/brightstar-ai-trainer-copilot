# AI Trainer Job Copilot

Collects AI-trainer / RLHF / AI-tutor jobs, analyzes each one with **OpenAI/Anthropic API keys** or your
**logged-in Claude / ChatGPT** (Chrome extension + localhost bridge), asks targeted questions, and produces
tailored resumes, LinkedIn advice and top-0.1% benchmark samples. Everything runs locally.

```
LinkedIn (Octo) + ATS boards -> SQLite -> analyze / tailor / profile / samples
                                              |  ask(task, prompt, schema)
                     ┌── OpenAI / Anthropic API  (OPENAI_API_KEY / ANTHROPIC_API_KEY)
                     └── bridge ws://127.0.0.1:8765 <-> Chrome extension <-> claude.ai / chatgpt.com
```

## One-time setup (easiest: API key)

```powershell
cd "D:\Work\JobHunting\00_AI Trainer\AI Trainer Copiot"
.\.venv\Scripts\jt init
# Edit .env: set OPENAI_API_KEY=sk-...   (or ANTHROPIC_API_KEY=...)
.\.venv\Scripts\jt llm status            # should show OpenAI ready; auto resolves to openai
.\.venv\Scripts\jt llm test              # tiny JSON round trip
.\.venv\Scripts\jt dashboard
```

No Chrome extension needed when an API key is set and the engine is **Auto** (default) or **OpenAI** / **Anthropic**.

### Optional: Claude / ChatGPT browser (like the bid bot chat engines)

```powershell
.\.venv\Scripts\jt ext-config            # bridge URL + token
.\.venv\Scripts\jt bridge serve          # leave running
```

Load `extension/` in `chrome://extensions` (Developer mode → Load unpacked), paste the token, Save, Reconnect.
Then `jt llm engine claude` (or `gpt`), or pick it in the dashboard **AI engine** control.

Optional LinkedIn: set `OCTO_PROFILE_UUID=` in `.env`, start Octo Browser, `jt octo check`.

## Daily use

```powershell
.\.venv\Scripts\jt llm status            # API + bridge snapshot
.\.venv\Scripts\jt dashboard             # main UI (engine picker on Overview)
```

| Goal | Command |
|---|---|
| Set engine | `jt llm engine auto\|openai\|anthropic\|claude\|gpt\|manual` |
| Test current engine | `jt llm test` |
| Find which ATS each company uses | `jt sources discover` |
| Collect jobs (public boards) | `jt collect` |
| Collect from LinkedIn via Octo | `jt collect --no-ats --linkedin` |
| Build a named profile from a resume | `jt profile import --name jane --resume cv.pdf` (then edit `profile/people/jane.yaml`) |
| Switch active profile | `jt profile use jane` / `jt profile list` |
| Analyze + score jobs | `jt analyze --all-new --limit 10`, then `jt rank` |
| See requirements and your gaps | `jt jobs gaps <id>` |
| Tailored resume (asks gap questions) | `jt tailor <id>` → `output/resumes/<id>/` |
| LinkedIn headline / About / skills | `jt profile optimize` → `output/linkedin_advice.md` |
| Top-0.1% samples and comparison | `jt samples generate`, `jt samples compare stem_phd` |
| Teaching profile for a virtual candidate | `jt samples suggest --name "Mina Cho" --company "Rockwell Automation" --jd-file jd.txt` |

## Choosing models

`config/models.yaml` maps each task to `auto`, `openai`, `anthropic`, `claude`, `gpt`, or `manual`.

- **auto** (default): uses dashboard / `jt llm engine` preference if set; else `OPENAI_API_KEY`, else
  `ANTHROPIC_API_KEY`, else Claude browser bridge.
- Override models with `OPENAI_MODEL=` / `ANTHROPIC_MODEL=` in `.env`.
- For a Claude Project, set `providers.claude.url` to that project's `/new` URL (browser path only).

## Honesty guardrails

- Prompts forbid inventing facts. Generated resumes are checked against the active `profile/people/<slug>.yaml` and your answers;
  unknown employers, schools, certifications and numbers are shown as "check before sending" warnings.
- Samples are labelled as fictional illustrations.

## Risks

- Browser automation of claude.ai / chatgpt.com can hit rate limits or ToS issues; prefer API keys for batch work.
- LinkedIn automation can trigger account restrictions. Collection is capped (default 60 jobs per run) with random
  delays and stops at any checkpoint. Use only your own account.
- Site redesigns break the extension. Edit `extension/selectors.json` and re-run `jt bridge test`.

## Tests

```powershell
.\.venv\Scripts\python -m pytest tests -q
```

They are offline: fake LLM / mocked HTTP, mock chat page, no accounts touched.
