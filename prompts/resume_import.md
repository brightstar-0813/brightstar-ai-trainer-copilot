You are converting a candidate's existing resume and/or LinkedIn text into a structured master profile for a job-application tool.

{% include '_rules.md' %}

Rules for this task:
- Copy facts faithfully. Keep dates as written (e.g. "2021-03", "Mar 2021", "Present").
- Put each accomplishment as its own bullet, preserving any numbers exactly.
- Do not fix, embellish or reword claims. If a date or detail is missing, leave the field empty.
- `domains`: subject areas the candidate could credibly evaluate AI outputs in (e.g. "mathematics", "python programming", "contract law"), derived only from the text.
- `ai_training_experience`: only work that is clearly AI training, data annotation, RLHF, evaluation, red teaming or prompt writing.
- Degrees go in `education`. Occupational licenses (government or licensing board) go in `licenses` as name, issuer, and year. Professional and vendor certifications go in `certifications` as name, issuer, and year. Do not put a license or a certification inside education, and leave `licenses_certs` empty.
- `missing_evidence_questions`: up to 10 questions whose answers would materially strengthen the profile for AI-trainer roles (numbers, tools, volumes, outcomes, licenses, certifications, languages, publications). Ask only about things the text hints at but does not prove.

`profile` must use exactly this layout (omit nothing, use empty strings/lists when unknown):
{{ layout }}

{% if resume_text %}RESUME TEXT
{{ resume_text[:14000] }}
{% endif %}
{% if linkedin_text %}LINKEDIN PROFILE TEXT
{{ linkedin_text[:10000] }}
{% endif %}
