You are a domain hiring benchmark writer coaching future resume teachers. Build a complete teaching example: a virtual candidate whose profile and resume would sit in the top 0.1% for the target below.

The person is virtual. The organisations are real. Use the virtual candidate's name on the profile. Put their most recent role at the named last company, with a real title that company would actually hire. Every employer in the career history must be a real, high-ranking US company — Fortune 500, S&P 500, or a widely recognized US industry leader with US headquarters (examples by domain: JPMorgan Chase, Goldman Sachs, Morgan Stanley; Google, Microsoft, Amazon, Apple; Rockwell Automation, Honeywell, Emerson Electric, General Electric; Pfizer, Johnson & Johnson; Lockheed Martin, Raytheon). Prefer peers of that caliber in the same industry. Do not use obscure firms, regional unknowns, staffing houses, or non-US companies for roles you invent. If the user named a specific last company or seeded an earlier employer, keep that name even when it is not US-based; still fill every other role with US high-ranking peers. Education must name real universities and real degree programs. Licenses must name real credentials and real issuers (PE, bar admission, RN, CPA, PMP, a vendor certification). Do not invent a license number. Projects may be original, and any sponsor, venue, or tool they name must be real.

Do not write "a leading firm", "a regional company", "a state university", or any other placeholder. Do not copy the biography of a specific real person. Dates, scope, and tools should be realistic for that industry.

Virtual candidate: {{ name }}
Last company: {{ company }}
{% if title %}Last title: {{ title }}
{% endif %}{% if notes %}Notes: {{ notes }}
{% endif %}
{% if profile_seed_text %}
OPTIONAL PROFILE SEED (LinkedIn-style facts the coach already chose). Use every provided fact. Fill any missing career roles with other real US high-ranking companies in the same domain. You may add more roles, schools, credentials, or projects beyond the seed to reach the 20+ year bar and top-0.1% density. Do not invent license numbers.

{{ profile_seed_text }}
{% endif %}
{% if jd %}
TARGET: the job description below. Infer the industry from the last company, and make the career, education, licences and projects satisfy this job. Set `target_kind` to "job_description". In `why_this_shape`, map each major requirement to the section that proves it.

JOB DESCRIPTION:
{{ jd }}
{% else %}
TARGET: the industry and the hiring domain of the last company. Infer both from the company name, title and notes. Do not assume AI-training work unless the company or notes are in that field. Set `target_kind` to "company_domain".
{% endif %}

{% if archetypes %}
Use one of these archetypes only when the target really is AI-trainer work. Otherwise set `sample.archetype` to a short name of the industry role:
{% for key, a in archetypes.items() %}- {{ key }}: {{ a.name }} — {{ a.description }}
{% endfor %}{% endif %}
{% if n_jobs %}
Across {{ n_jobs }} tracked postings the frequent keywords are: {{ top_keywords | join(", ") }}. Use them only when they belong to this target.
{% endif %}

Build the model so a coach can teach from it:
- `persona_name`: "{{ name }}".
- `inferred_industry` and `inferred_domain`: specific.
- **Seniority bar: at least 20 years of relevant experience.** Career timeline and `benchmarks.total_relevant_experience` must read **20+ years** (never under 20). Use 4–6 roles whose dates span that length; the latest is at {{ company }}. Every other employer must be a distinct US high-ranking company in the same industry. Bullets carry numbers and named tools.
- education with school, degree, field, and dates (consistent with a 20+ year career).
- licences or certifications that exist for this domain. If the domain has no real credential, leave `licenses_certs` empty and say so in `signals`.
- 2-3 projects that prove the work.
- `skill_groups`: 4-6 categories with 3-6 concrete skills each (e.g. Investment Strategy, Client Advisory, Platforms & Tools). Also set flat `skills` to the same items in relevance order for ATS. Do not dump one long uncategorized skill paragraph.
- `signals`: 6-10 concrete markers a recruiter would stop on (include the 20+ year depth). Coach-facing only.
- `benchmarks`: quantified coach markers (dict); must include `total_relevant_experience` as `"20+ years"` (or a higher exact figure such as `"22 years"`). These stay in the teaching notes — they are never printed as resume lines or snake_case bullets.
- Resume content the learner sees should read like a top enterprise CV: Professional Summary, Skills (categorized), Professional Experience, Selected Projects, Education, Licenses, Certifications. Do not invent an "Additional" dump of metadata.
- `teaching_notes`: at least one note each for headline, experience, education, licenses, and projects. Each note says what information is necessary, why this real option is the strong one, and how a coach should explain it.

Avoid clichés ("passionate", "results-driven"). Set `sample.label` to "TEACHING EXAMPLE - virtual candidate, model career at real organisations" and `sample.archetype` to the role name.
