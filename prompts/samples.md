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
- education with honours that matter for the archetype. Degrees only; do not put a license or a certification here. If the archetype is PhD-level or the market prefers doctoral credentials, use a PhD (or equivalent) from a high-ranking research university — do not stop at a master's when the bar is higher;
- `licenses`: occupational licenses that actually exist for this archetype (government or licensing board). Leave empty when none exist;
- `certifications`: professional or vendor certifications that actually exist for this archetype. Leave empty when none exist. Leave `licenses_certs` empty;
- 2-3 projects or publications that prove the skill directly (including any AI-training, evaluation or red-teaming work);
- a skills list ordered by relevance;
- `signals`: 6-10 concrete markers that make a recruiter stop scrolling (what exactly, and why it works). Coach-facing only;
- `benchmarks`: quantified coach markers (years of experience, publications, hours of annotation, ranking). Never printed as resume lines.

Avoid clichés ("passionate", "results-driven"). Prefer specific, checkable details. Set `label` to "ILLUSTRATIVE SAMPLE - fictional person, not a real individual" and `archetype` to "{{ archetype.name }}".
