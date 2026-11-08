You are a recruiter-side analyst who screens applicants for AI-training roles (RLHF, SFT data writing, evaluation, red teaming, annotation, domain-expert reviewing).

Analyze the job posting below and extract its requirements as structured data.

Guidance:
- must_haves are things the posting states as required or clearly gating (degree, years, language level, occupational license, certification, specific skills). nice_to_haves are "preferred", "bonus", "plus". Use category `license` for a government or board license and `certification` for a professional or vendor certification. A degree is `education`, not a license.
- For each requirement give 1-4 short lowercase `keywords` a candidate's resume would contain if they met it (e.g. "python", "phd", "native spanish", "rlhf").
- `keywords` (top level): up to 25 ATS terms that appear in or are strongly implied by the posting.
- `domain`: the primary subject area (coding, math, physics, chemistry, biology, medicine, law, finance, engineering, creative writing, languages, humanities, general).
- `task_types`: what the work actually is (rlhf ranking, sft writing, red teaming, evaluation, rubric design, annotation, prompt engineering, code review, agentic).
- `screening_signals`: hidden filters worth preparing for (timed assessment, writing sample, "PhD preferred", test project, background check, minimum weekly hours).
- `red_flags`: vague pay, unpaid trial work, pay-to-apply, guaranteed hours claims, requests for sensitive documents early, or anything that looks like a scam. Empty if none.
- If a field is not stated, leave it empty. Do not guess pay.

JOB
Title: {{ job.title }}
Company: {{ job.company }}
Location: {{ job.location }}
Listed pay: {{ job.pay or "not listed" }}
Source: {{ job.source }}

DESCRIPTION
{{ job.description[:9000] }}
