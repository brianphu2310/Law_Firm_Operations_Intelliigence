"""Clicks and edits in the running app (Streamlit AppTest): the things a plain 'does it render' test misses."""
import datetime as dt
import os
import sys

import pytest
from streamlit.testing.v1 import AppTest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import simulate as S
from core.model import build_model
from core.ref import NAV_ITEMS

APP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py")


def new(**state):
    at = AppTest.from_file(APP, default_timeout=120)
    for k, v in state.items():
        at.session_state[k] = v
    return at.run()


def button(at, key):
    return next(b for b in at.button if b.key == key)


def sim():
    return new(view_kind="page", view_name="Simulator")


def ok(at):
    assert not at.exception, [e.value for e in at.exception]


def test_reset_levers_button_works():
    at = sim()
    at.slider(key="sim_util").set_value(3.0).run()
    assert at.session_state["sim_util"] == 3.0
    button(at, "act_reset").click().run()
    ok(at)
    assert at.session_state["sim_util"] == 0.0


def test_preset_buttons_load_their_levers():
    at = sim()
    names = list(S.PRESETS)
    for i, name in enumerate(names):
        button(at, f"act_preset_{i}").click().run()
        ok(at)
        for k, v in S.preset_state(name).items():
            assert at.session_state[k] == v, (name, k)


def test_levers_survive_leaving_and_returning_to_the_page():
    at = sim()
    at.slider(key="sim_util").set_value(3.5).run()
    at.session_state["view_name"] = "Finance"; at.run(); ok(at)
    at.session_state["view_name"] = "Simulator"; at.run(); ok(at)
    assert at.slider(key="sim_util").value == 3.5


def test_goal_seek_apply_closes_the_gap():
    at = sim()
    M = build_model()
    bt = S.budget_targets(M)
    button(at, "act_apply_sim_util").click().run()
    ok(at)
    _, f = S.base_actuals(M)
    assert S.project(f, {k: at.session_state[k] for k in S.DEFAULTS})["op1"] >= bt["op"] - 1.0


def test_apply_is_disabled_when_a_lever_cannot_reach_the_goal_alone():
    at = sim()
    assert button(at, "act_apply_sim_recov").disabled
    assert not button(at, "act_apply_sim_util").disabled


def test_save_scenario_and_clear():
    at = sim()
    button(at, "act_preset_1").click().run()
    button(at, "act_save").click().run(); ok(at)
    assert len(at.session_state["saved_scen"]) == 1 and at.session_state["sim_name"] == "Scenario 2"
    button(at, "act_save").click().run()
    assert len(at.session_state["saved_scen"]) == 2
    button(at, "act_clear").click().run(); ok(at)
    assert at.session_state["saved_scen"] == []


def test_new_hire_shows_role_and_productivity_controls():
    at = sim()
    at.slider(key="sim_hires").set_value(2).run(); ok(at)
    assert at.selectbox(key="sim_role").value == "Associate"
    at.selectbox(key="sim_role").set_value("Partner").run(); ok(at)


def test_finance_call_to_action_opens_the_simulator_with_the_budget_goal():
    at = new(view_kind="page", view_name="Finance")
    button(at, "act_cta_pl").click().run(); ok(at)
    assert (at.session_state["view_kind"], at.session_state["view_name"]) == ("page", "Simulator")
    assert at.session_state["sim_target_kind"].startswith("Match the FY26 budget")


def test_billing_call_to_action_loads_the_collections_preset():
    at = new(view_kind="page", view_name="Finance")
    button(at, "act_cta_bill").click().run(); ok(at)
    assert at.session_state["view_name"] == "Simulator" and at.session_state["sim_dso"] == -7


def test_team_call_to_action_loads_the_utilisation_preset():
    at = new(view_kind="page", view_name="Team")
    button(at, "act_cta_team").click().run(); ok(at)
    assert at.session_state["view_name"] == "Simulator" and at.session_state["sim_util"] == 3.0


def test_platform_score_uses_the_weights_just_chosen():
    """Regression: the score used to lag one click behind the weight sliders."""
    import re
    name = "Smokeball + GlobalX"
    at = new(view_kind="platform", view_name=name)

    def score(a):
        html = next(m.value for m in a.markdown if 'kpi-label">Weighted score' in m.value)
        return float(re.search(r'kpi-value[^>]*>([\d.]+)<', html).group(1))
    before = score(at)
    at.slider(key="w_Cost").set_value(50).run()
    after_change = score(at)
    at.run()
    assert after_change == score(at) != before


def test_platform_weights_are_shared_across_platforms():
    at = new(view_kind="platform", view_name="Smokeball + GlobalX")
    at.slider(key="w_Speed").set_value(40).run()
    at.session_state["view_name"] = "Clio + GlobalX"; at.run(); ok(at)
    assert at.slider(key="w_Speed").value == 40


def test_calendar_workload_legend_never_exceeds_four_categories():
    """Regression: the per-attorney workload chart used to group by raw deadline `type` text (up to 14 distinct
    values in the model), which overflowed the Plotly legend and covered the chart title/bars at normal card
    heights. It must now use the same 4-category bucketing as the rest of the Calendar page."""
    from core.model import build_model
    from views.calendar_view import KIND_ORDER, KIND_COLOR, _kind
    M = build_model()
    dl = M["deadlines"]
    raw_types = dl["type"].nunique()
    buckets = set(_kind(t, ty) for t, ty in zip(dl["title"], dl["type"]))
    assert raw_types > 4, "fixture no longer exercises the bug (not enough distinct raw types to matter)"
    assert buckets <= set(KIND_ORDER) and len(KIND_ORDER) == 4
    assert set(KIND_COLOR) == set(KIND_ORDER)                                       # month-view legend and chart never drift apart
    at = new(view_kind="page", view_name="Calendar")                                # st.tabs renders every tab's content in one run
    ok(at)


EDGE_RANGES = [("single day", dt.date(2025, 9, 17), dt.date(2025, 9, 17)), ("weekend", dt.date(2025, 9, 13), dt.date(2025, 9, 14)),
               ("reversed", dt.date(2025, 9, 17), dt.date(2025, 9, 1)), ("first day of data", dt.date(2023, 7, 1), dt.date(2023, 7, 1))]


@pytest.mark.parametrize("label,start,end", EDGE_RANGES)
@pytest.mark.parametrize("compare", ["Prior period", "Same period last year"])
def test_pages_survive_periods_with_no_activity(label, start, end, compare):
    """Regression: a period with zero matters opened / zero invoices used to crash Matters and Clients (division by zero)."""
    for page in NAV_ITEMS:
        at = new(view_kind="page", view_name=page, period_preset="Custom range", custom_start=start, custom_end=end, compare_mode=compare)
        ok(at)
