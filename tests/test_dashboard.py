"""Render every dashboard page headlessly and fail on any exception."""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parent.parent / "dashboard" / "app.py")
PAGES = ["Overview", "Jobs", "Profile", "Market and gaps", "Samples", "Tracker", "LLM log",
         "Manual replies"]


@pytest.mark.parametrize("page", PAGES)
def test_page_renders(page):
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception, at.exception
    at.radio(key="page").set_value(page).run()
    assert not at.exception, [e.value for e in at.exception]
