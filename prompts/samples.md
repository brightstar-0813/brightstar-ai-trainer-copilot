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
- education as multiple degree entries: bachelor's + master's + PhD (or domain professional doctorate) from high-ranking research universities — do not stop at a master's. Dual fields get a second relevant bachelor's or master's as its own entry. Give each degree month + year start and end dates. The candidate is about {{ candidate_age }} years old; nothing starts before {{ earliest_year }} (age 18). Anchor every degree to working life: either the later degree overlaps a listed role (part-time or executive study only where that school really offers it) or a listed job sits entirely between two consecutive degrees. Never invent empty years between degrees or before the first job. Full-time programs (most PhDs, full-time master's) must sit in a window with no listed job. Degrees only; do not put a license or a certification here;
- `licenses`: occupational licenses that actually exist for this archetype (government or licensing board). Licensed archetypes should list the full gating set strong peers hold (typically 1–3), not a single token license. Leave empty only when none exist;
- `certifications`: professional or vendor certifications that actually exist for this archetype. Prefer a dense, plausible stack (typically 3–6 when the domain has real cert paths; 2–4 specialty/board certs alongside licenses). Do not stop at one when more exist. Leave empty only when none exist. Leave `licenses_certs` empty;
- 2-3 projects or publications that prove the skill directly (including any AI-training, evaluation or red-teaming work);
- **Career chronology (checked after generation):** list `experience` newest first. Jobs never overlap: one full-time job at a time. A full-time degree never overlaps a listed job; a degree may overlap a job only when its program is part-time, evening, executive, or online (use the verified formats above). No role may cite a tool, product, or standard that did not exist yet when that role started. Availability: {% for name, year in tool_launch_years %}{{ name }} {{ year }}{% if not loop.last %}; {% endif %}{% endfor %}. Use older tools for older roles (for example Excel, SAP ERP, Hyperion, Oracle Financials, ACL Analytics).
- a skills list ordered by relevance;
- `signals`: 6-10 concrete markers that make a recruiter stop scrolling (what exactly, and why it works). Coach-facing only;
- `benchmarks`: quantified coach markers (years of experience, publications, hours of annotation, ranking). Never printed as resume lines.

Avoid clichés ("passionate", "results-driven"). Prefer specific, checkable details. Set `label` to "ILLUSTRATIVE SAMPLE - fictional person, not a real individual" and `archetype` to "{{ archetype.name }}".
{% if program_formats %}
Verified program formats (state a format only for these schools and programs; for any other school, state no format or length):
{% for p in program_formats %}- {{ p.school }} - {{ p.program }}: {{ p.format }}; {{ p.length }}. {{ p.notes }}
{% endfor %}{% endif %}
{% if timeline_fix %}
Retry fix (the previous answer failed the career or education check): {{ timeline_fix }} Fix only the problems named here, in the experience or education section. Keep at least three degree entries (bachelor's, master's, doctorate). Keep every fact the problems do not name.
{% endif %}
