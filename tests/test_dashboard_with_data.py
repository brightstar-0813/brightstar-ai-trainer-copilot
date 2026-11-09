"""Dashboard pages that only show content once a job is analyzed, questioned and tailored."""
from pathlib import Path

from streamlit.testing.v1 import AppTest

from jt.pipelines import analyze, samples, tailor
from tests.test_pipeline_offline import env  # noqa: F401  (pytest fixture)

APP = str(Path(__file__).resolve().parent.parent / "dashboard" / "app.py")


def test_data_pages_render(env):  # noqa: F811
    analyze.analyze_job(1)
    qs = tailor.generate_questions(1)
    tailor.answer_question(qs[1].id, "I ranked about 500 RLHF tasks at Example University.")
    tailor.tailor_job(1)
    samples.generate_sample("stem_phd")
    samples.compare("stem_phd")

    at = AppTest.from_file(APP, default_timeout=60)
    at.session_state["job_id"] = 1
    at.run()
    for page in ("Jobs", "Market and gaps", "Samples", "Profile", "Overview"):
        at.radio(key="page").set_value(page).run()
        assert not at.exception, (page, [e.value for e in at.exception])
    at.radio(key="page").set_value("Jobs").run()
    metrics = {m.label: m.value for m in at.metric}
    assert "Fit score" in metrics and "ATS keyword coverage" in metrics
    warnings = " ".join(w.value for w in at.warning)
    assert "9,999" in warnings  # the fabricated figure is surfaced to the user
    answer_boxes = [t for t in at.text_area if "How many RLHF tasks" in t.label]
    assert answer_boxes and "500 RLHF tasks" in answer_boxes[0].value  # saved answer is shown back
