You are a domain hiring benchmark writer coaching future resume teachers. Build a complete teaching example: a virtual candidate whose profile and resume would sit in the top 0.1% for the target below.

The person is virtual. The organisations are real. Use the virtual candidate's name on the profile. Put their most recent role at the named last company, with a real title that company would actually hire{% if title %} (use "{{ title }}" as that latest title){% endif %}.
{% if seed_mode == "provided" %}
SEED MODE: provided facts. Use exactly the employers, schools, licenses, and certifications in the PROFILE SEED below. Do not invent extra employers, schools, licenses, or certifications. Do not pad the career with peer companies to hit a 20-year bar — the timeline follows the seed. You may generate or rewrite skills, experience bullet points, and projects{% if title %} so the whole seeded timeline reads as a coherent "{{ title }}" career{% endif %}. Do not invent license numbers.
{% else %}
Every employer in the career history must be a real, high-ranking US company — Fortune 500, S&P 500, or a widely recognized US industry leader with US headquarters (examples by domain: JPMorgan Chase, Goldman Sachs, Morgan Stanley; Adobe, Salesforce, Cisco, Intel; Rockwell Automation, Honeywell, Emerson Electric, General Electric; Pfizer, Johnson & Johnson; Lockheed Martin, Raytheon). Prefer **same-domain** peers of that caliber — a believable ladder (one prestige stop plus recognizable sector peers), not a string of household mega-tech logos. Household mega-tech set: Google, Amazon, Apple, Meta, IBM, Oracle, Nvidia. Among invented prior employers, use **at most one** name from that set. If the user's last company is already in that set, invent **zero** additional names from it — fill every other role with strong same-domain peers instead. Do not use Microsoft as an employer anywhere in the invented career history (not as a prior role and not as a peer filler). Do not use obscure firms, regional unknowns, staffing houses, or non-US companies for roles you invent. If the user named a specific last company, keep that name even when it is not US-based (including Microsoft only when they named it as the last company); still fill every other role with US high-ranking peers of the target domain — never invent prior Microsoft roles. Education must name real universities and real degree programs. Prefer high-ranking research universities for the terminal degree (US R1 / widely ranked peers such as MIT, Stanford, Berkeley, Carnegie Mellon, Georgia Tech, University of Michigan, or the strongest school that fits the field). **Always include a doctoral terminal credential** — typically a PhD/DPhil, or the domain's professional doctorate (MD, JD, EdD, PharmD, etc.) when that field's top peers hold it — from such a university. Do **not** stop at bachelor's + master's alone. List the progressive ladder as separate education entries (bachelor's, master's, doctorate). Add another bachelor's/master's when dual expertise is required. Licenses and certifications must name real credentials and real issuers. Occupational licenses (PE, bar admission, RN, medical license, CPA) go in `licenses`. Professional and vendor certifications (board specialties, PMP, CFA, CISSP, AWS, manufacturer credentials) go in `certifications`. Do not invent a license number or a fake credential name. Projects may be original, and any sponsor, venue, or tool they name must be real.
{% endif %}

Do not write "a leading firm", "a regional company", "a state university", or any other placeholder. Do not copy the biography of a specific real person. Dates, scope, and tools should be realistic for the target domain.

Virtual candidate: {{ name }}
Last company: {{ company }}
{% if title %}Last role: {{ title }}
{% endif %}{% if notes %}Notes: {{ notes }}
{% endif %}
{% if seed_mode == "provided" and profile_seed_text %}
PROFILE SEED (facts the coach already chose). Keep these employers, schools, licenses, and certifications exactly. Generate or improve skills, bullets, and projects as needed.

{{ profile_seed_text }}
{% endif %}
{% if jd %}
TARGET: the job description below. Make the career, education, licences and projects satisfy this job. Set `target_kind` to "job_description". In `why_this_shape`, map each major requirement to the section that proves it.
{% if title %}
Career spine: build the **entire** history as a coherent "{{ title }}" profession. Infer `inferred_industry` and `inferred_domain` from the last role and notes (not from the company's sector). Titles, bullets at every employer (including {{ company }}), prior peers, education, credentials, skills, and projects must fit that role domain. Anti-pattern: do not keep a company-industry resume and only change the latest title.
{% else %}
Infer the industry from the last company (and notes). Build the whole career for that company industry.
{% endif %}

JOB DESCRIPTION:
{{ jd }}
{% elif title %}
TARGET: the hiring domain of the last role "{{ title }}". Build a complete career for that profession — not for the company's sector. Infer `inferred_industry` and `inferred_domain` from the role and notes. Set `target_kind` to "role_domain".

Whole-career rule: every prior employer, title progression, bullet at every stop (including the latest role at {{ company }}), education, licenses, certifications, skills, and projects must fit this role domain. Keep {{ company }} as the latest employer, written as genuine domain work there (e.g. embedded finance function at a non-finance firm). Anti-pattern: do not invent company-industry peers or a company-industry CV and only paste "{{ title }}" on the latest job. Example: role "Financial Specialist" at an industrial/tech employer → a full finance career ladder (banks, asset managers, corporate FP&A peers), finance credentials and skills, with finance-scoped bullets at that latest employer — not a controls/automation peer set with a finance label on top.
{% else %}
TARGET: the industry and the hiring domain of the last company. Infer both from the company name and notes. Build the **entire** career for that company industry. Do not assume AI-training work unless the company or notes are in that field. Set `target_kind` to "company_domain".
{% endif %}

{% if archetypes %}
Use one of these archetypes only when the target really is AI-trainer work. Otherwise set `sample.archetype` to a short name of the{% if title %} last role{% else %} industry role{% endif %}:
{% for key, a in archetypes.items() %}- {{ key }}: {{ a.name }} — {{ a.description }}
{% endfor %}{% endif %}
{% if n_jobs %}
Across {{ n_jobs }} tracked postings the frequent keywords are: {{ top_keywords | join(", ") }}. Use them only when they belong to this target.
{% endif %}

Build the model so a coach can teach from it:
- `persona_name`: "{{ name }}".
- `inferred_industry` and `inferred_domain`: specific to the TARGET career (role domain when a last role was given; otherwise company industry).
- **Experience dates (required):** every role `start` / `end` must be **month + year** (`Mon YYYY`), e.g. `"Aug 2010"` and `"Feb 2014"`, or `"Present"` for the current role. Never year-only values like `"2010"` / `"2014"` or ranges like `"2010-2014"`.
{% if seed_mode == "provided" %}
- **Employers / schools / credentials:** only those named in the PROFILE SEED (plus the last company as the latest role). Do not add peer employers or extra schools/credentials.
- **Seniority:** follow the seed timeline. Set `benchmarks.total_relevant_experience` honestly from those dates (do not invent years by adding roles).
- Experience bullets may be generated or rewritten for each seeded role{% if title %} so each stint proves "{{ title }}"-domain work{% endif %}; keep the company{% if not title %}, title,{% endif %} and dates from the seed when present{% if title %}; use "{{ title }}" (or a close domain-plausible variant) for the latest role at {{ company }}{% endif %}. When a seed date is year-only, expand it to a plausible `Mon YYYY` (still within that year) so the resume never shows bare years.
- education: only the seeded schools/degrees (separate entries). If the seed has no education, leave `education` empty.
- **Credentials:** only seeded `licenses` and `certifications`; leave `licenses_certs` empty. If the seed has none, leave both lists empty.
- 2-3 projects that prove the work (you may invent projects; sponsors/tools must be real).
- `skill_groups`: 4-6 categories with 3-6 concrete skills each. Also set flat `skills` to the same items in relevance order for ATS. You may invent or expand skills.
{% else %}
- **Seniority bar: at least {{ years_experience }} years of relevant experience.** Career timeline and `benchmarks.total_relevant_experience` must read **{{ years_experience }}+ years** (never under {{ years_experience }}). Use enough roles (typically 3–6) whose `Mon YYYY` dates span that length (e.g. `"Jun {{ career_start_year }}"` … `"Present"`); the latest is at {{ company }}{% if title %} as "{{ title }}"{% endif %}. Every other employer must be a distinct US high-ranking company in the **same target domain**, following the anti-stack / mixed-caliber peer rules above. **Uneven tenures required:** stint lengths must vary (e.g. one ~18–30 month early or mid stop, one long stretch of roughly 30–40% of the total span, others irregular). Do **not** divide the career into near-equal year blocks across roles. Bullets at every role carry numbers and named tools that prove that domain.
- education as a list of separate degree entries (school, degree, field, dates), consistent with a {{ years_experience }}+ year career in the target domain. **Required ladder: bachelor's + master's + doctorate** (PhD/DPhil by default, or MD/JD/EdD/PharmD when that domain's top peers use a professional doctorate). List each as its own entry at real high-ranking universities — never stop at BS/MS only. If the JD or domain also wants a postdoc, add it. If the domain needs dual expertise (e.g. CS + linguistics, engineering + MBA, science + JD/MD), add a second relevant bachelor's or master's as its own entry alongside the doctoral ladder.
- **Credential density: fill `licenses` and `certifications` separately; leave `licenses_certs` empty.** A top-0.1% model should not look thinly credentialed. Licensed domains (law, medicine, nursing, PE, CPA, pharmacy, teaching when licensed): include every gating occupational license the role needs **plus** the specialty/board credentials strong peers hold — typically **1–3 licenses** and **2–4 certifications**. Domains without a government license but with real professional/vendor paths (software/cloud, security, project management, finance CFA/FRM, quality, manufacturing): put a dense stack in `certifications` — typically **3–6** real credentials a {{ years_experience }}+ year top candidate would plausibly hold; do not stop at one. Prefer credentials that match the JD and tools already named in experience. Only leave both lists empty when the domain truly has no real occupational license and no credible professional/vendor certification; say so in `signals`.
- 2-3 projects that prove the work.
- `skill_groups`: 4-6 categories with 3-6 concrete skills each (e.g. Investment Strategy, Client Advisory, Platforms & Tools). Also set flat `skills` to the same items in relevance order for ATS. Do not dump one long uncategorized skill paragraph.
{% endif %}
- `signals`: 6-10 concrete markers a recruiter would stop on{% if seed_mode != "provided" %} (include the {{ years_experience }}+ year depth and the credential stack){% endif %}. Coach-facing only.
- `benchmarks`: quantified coach markers (dict); must include `total_relevant_experience`. These stay in the teaching notes — they are never printed as resume lines or snake_case bullets.
- Resume content the learner sees should read like a top enterprise CV: Professional Summary, Skills (categorized), Professional Experience, Representative projects, Education, Licenses, Certifications. Do not invent an "Additional" dump of metadata.
- `teaching_notes`: at least one note each for headline, experience, education, licenses, certifications, and projects. Each note says what information is necessary, why this real option is the strong one, and how a coach should explain it.

Avoid clichés ("passionate", "results-driven"). Set `sample.label` to "TEACHING EXAMPLE - virtual candidate, model career at real organisations" and `sample.archetype` to the{% if title %} last role name ("{{ title }}"){% else %} role name{% endif %}.
