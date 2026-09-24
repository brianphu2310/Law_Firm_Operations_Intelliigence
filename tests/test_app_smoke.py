"""Smoke test: every page and every platform dashboard renders without raising an exception (Streamlit's headless AppTest)."""
import os
import sys

import pytest
from streamlit.testing.v1 import AppTest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.platforms import NAMES
from core.ref import NAV_ITEMS

APP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py")


def _run(**state):
    at = AppTest.from_file(APP, default_timeout=120)
    for k, v in state.items():
        at.session_state[k] = v
    return at.run()


@pytest.mark.parametrize("page", NAV_ITEMS)
def test_page_renders(page):
    at = _run(view_kind="page", view_name=page)
    assert not at.exception, [e.value for e in at.exception]


@pytest.mark.parametrize("platform", NAMES)
def test_platform_dashboard_renders(platform):
    at = _run(view_kind="platform", view_name=platform)
    assert not at.exception, [e.value for e in at.exception]


@pytest.mark.parametrize("preset,compare", [("This month (MTD)", "Same period last year"), ("Last 12 months", "No comparison"), ("FY24 (two years ago)", "Prior period")])
def test_period_settings_do_not_break_pages(preset, compare):
    for page in ("Overview", "Finance", "Team"):
        at = _run(view_kind="page", view_name=page, period_preset=preset, compare_mode=compare)
        assert not at.exception, (page, [e.value for e in at.exception])
