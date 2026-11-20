You are a talent strategist who has screened thousands of applicants for AI-training, RLHF, evaluation and domain-expert contract roles at frontier AI labs and data vendors.

Create an ILLUSTRATIVE benchmark profile of a fictional person who would sit in the top 0.1% of applicants for this archetype. It is a teaching sample: every person, employer, school and publication in it is invented, plausible, and must not resemble a specific real individual. Use realistic but generic institution names (for example "a top-10 US research university") or well-known institutions only for degrees and licences that exist, never for fabricated roles at named real employers.

Archetype: {{ archetype.name }}
Description: {{ archetype.description }}
Typical roles: {{ archetype.roles | join(", ") }}

Ground it in the market. Across {{ n_jobs }} tracked postings the most frequent keywords are:
{{ top_keywords | join(", ") }}
Most common requirements: 
{% for r in top_requirements %}- {{ r }}
{% endfor %}

Build a complete profile with:
- a realistic, believable career history (3-4 roles) whose progression makes the archetype's credibility obvious, with bullets that carry numbers and named tools;
- education as separate degree entries from real high-ranking universities. A doctoral terminal credential is required (research PhD, or the profession's doctorate such as MD, JD, EdD, or PharmD). A master's is not required: include it only when it is a prerequisite, a conventional qualification, a distinct specialization, an embedded doctoral milestone, or it has a clear professional purpose. Bachelor's → direct-entry PhD is a legitimate US pathway in computer science, mathematics, engineering, and many research sciences. Undergraduate or first degree → professional doctorate is the path for medicine, law, and pharmacy. Do not add a master's only to increase the number of degrees. Add a second degree only when the profession needs another field. Give each degree month + year start and end dates. The candidate is about {{ candidate_age }} years old; nothing starts before {{ earliest_year }} (age 18). Consecutive degrees may follow one another within 12 months (including a spring bachelor's into a fall direct-entry doctorate), a listed job may sit entirely between them, or the later degree may overlap a job only when that program is part-time or executive. Never invent empty years longer than 12 months. Treat unverified programs as full-time: they must sit in a window with no listed job. Degrees only; do not put a license or a certification here;
- `licenses`: occupational licenses that actually exist for this archetype (government or licensing board). Licensed archetypes should list the full gating set strong peers hold (typically 1–3), not a single token license. Leave empty only when none exist;
- `certifications`: professional or vendor certifications that actually exist for this archetype. Prefer a dense, plausible stack (typically 3–6 when the domain has real cert paths; 2–4 specialty/board certs alongside licenses). Do not stop at one when more exist. Leave empty only when none exist. Leave `licenses_certs` empty;
- 2-3 projects or publications that prove the skill directly (including any AI-training, evaluation or red-teaming work);
- **Career chronology (checked after generation):** list `experience` newest first. Every role start and end, and every degree start and end, is `Mon YYYY` (`Present` only for the current role). Jobs never overlap: one full-time job at a time. A full-time degree never overlaps a listed job; a degree may overlap a job only when its program is part-time, evening, executive, or online (use the verified formats above). `benchmarks.total_relevant_experience` must match years counted from employment dates only. Do not count degree enrollment as experience. No role may cite a tool, product, or standard that did not exist yet when that role started. Availability: {% for name, year in tool_launch_years %}{{ name }} {{ year }}{% if not loop.last %}; {% endif %}{% endfor %}. Use older tools for older roles (for example Excel, SAP ERP, Hyperion, Oracle Financials, ACL Analytics).
- a skills list ordered by relevance;
- `signals`: 6-10 concrete markers that make a recruiter stop scrolling (what exactly, and why it works). Coach-facing only;
- `benchmarks`: quantified coach markers (years of experience, publications, hours of annotation, ranking). Never printed as resume lines.

Avoid clichés ("passionate", "results-driven"). Prefer specific, checkable details. Set `label` to "ILLUSTRATIVE SAMPLE - fictional person, not a real individual" and `archetype` to "{{ archetype.name }}".
{% if program_formats %}
Verified program formats (state a format only for these schools and programs; for any other school, state no format or length):
{% for p in program_formats %}- {{ p.school }} - {{ p.program }}: {{ p.format }}; {{ p.length }}. {{ p.notes }}
{% endfor %}{% endif %}
{% if timeline_fix %}
Retry fix (the previous answer failed the career or education check): {{ timeline_fix }} Fix only the problems named here, in the experience, education, or benchmarks. Keep a first degree and a doctoral terminal credential. Do not add a master's unless the failure says the profession requires one. Keep every fact the problems do not name.
{% endif %}
