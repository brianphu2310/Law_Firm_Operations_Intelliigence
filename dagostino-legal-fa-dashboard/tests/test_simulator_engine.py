"""Decision Simulator engine: goal-seek hits its target, delivery haircuts behave, presets are valid, delta() handles zero."""
import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import simulate as S
from core.model import build_model
from core.period import delta

M = build_model()
_, F = S.base_actuals(M)
BT = S.budget_targets(M)
Z = dict(S.DEFAULTS)


def test_every_preset_is_valid_and_within_slider_bounds():
    for name in S.PRESETS:
        st = S.preset_state(name)
        assert set(st) == set(S.DEFAULTS)
        for k, (lo, hi, _) in S.BOUNDS.items():
            assert lo <= st[k] <= hi, (name, k)
        S.project(F, st)                                                        # runs without error


def test_goal_seek_hits_the_operating_profit_target_exactly():
    gs = S.goal_seek(F, Z, target_op=BT["op"])
    solved = gs[gs["required"].notna() & (gs["change"].abs() > 1e-9)]
    assert len(solved) >= 3
    for _, row in solved.iterrows():
        lever = row["lever"]
        op = S.project(F, {**Z, lever: row["required"]})["op1"]
        assert abs(op - BT["op"]) < 1.0, (lever, op)


def test_goal_seek_hits_the_margin_target():
    gs = S.goal_seek(F, Z, target_margin=BT["margin"])
    row = gs[gs["lever"] == "sim_util"].iloc[0]
    m = S.margin(S.project(F, {**Z, "sim_util": row["required"]}))
    assert abs(m - BT["margin"]) < 1e-6


def test_goal_seek_apply_value_is_rounded_up_so_the_target_is_still_met():
    gs = S.goal_seek(F, Z, target_op=BT["op"])
    for _, row in gs[gs["apply_value"].notna() & (gs["difficulty"] != "Already met")].iterrows():
        assert S.project(F, {**Z, row["lever"]: row["apply_value"]})["op1"] >= BT["op"] - 1.0, row["lever"]


def test_goal_seek_reports_when_already_met():
    rich = {**Z, "sim_util": 8.0}
    gs = S.goal_seek(F, rich, target_op=S.project(F, Z)["op1"])
    assert (gs["difficulty"] == "Already met").all()


def test_goal_seek_says_unreachable_instead_of_inventing_an_answer():
    gs = S.goal_seek(F, Z, target_op=S.project(F, Z)["op1"] * 5)
    assert gs["required"].isna().all() or (gs["difficulty"] != "Comfortable").all()


def test_delivery_haircut_scales_improvements_only():
    up = {**Z, "sim_util": 4.0, "sim_rate": 4.0}
    full, half = S.project(F, up, 1.0)["op1"], S.project(F, up, 0.5)["op1"]
    base = S.project(F, Z)["op1"]
    assert base < half < full
    down = {**Z, "sim_util": -4.0}
    assert S.project(F, down, 0.5)["op1"] == S.project(F, down, 1.0)["op1"]        # a setback is never softened
    assert S.project(F, Z, 0.5)["op1"] == base


def test_delivery_haircut_applies_to_a_new_hires_productivity_but_not_their_pay():
    hire = S.preset_state("Hire an associate")
    full, half = S.project(F, hire, 1.0), S.project(F, hire, 0.5)
    assert half["op1"] < full["op1"]
    assert abs(half["hire_cost"] - full["hire_cost"]) < 1e-6
    dr = S.delivery_range(F, hire)
    assert dr["op"].is_monotonic_decreasing and dr["op"].iloc[0] > dr["op"].iloc[2]


def test_new_hire_economics():
    r = S.project(F, S.preset_state("Hire an associate"))
    assert r["hire_cost"] > 0 and r["hire_fees"] > 0
    assert abs(r["hire_net"] - (r["hire_fees"] - r["hire_cost"])) < 1e-6
    at_breakeven = S.project(F, {**S.preset_state("Hire an associate"), "sim_ramp": r["hire_breakeven_ramp"] * 100})
    assert abs(at_breakeven["hire_net"]) < 1.0                                    # exactly zero net contribution at the break-even productivity


def test_lever_directions():
    base = S.project(F, Z)["op1"]
    for lever, v in dict(sim_util=1.0, sim_rate=1.0, sim_real=1.0, sim_recov=5.0, sim_infl=-1.0).items():
        assert S.project(F, {**Z, lever: v})["op1"] > base, lever
    assert S.project(F, {**Z, "sim_infl": 3.0})["op1"] < base
    r = S.project(F, {**Z, "sim_dso": -7})
    assert r["dso_cash"] > 0 and abs(r["op1"] - S.project(F, Z)["op1"]) < 1e-6      # collecting faster releases cash but does not change profit


def test_delivery_range_is_ordered():
    dr = S.delivery_range(F, S.preset_state("Lift utilisation +3 pp"))
    assert list(dr["delivery"]) == [1.0, 0.75, 0.5]
    assert dr["op"].is_monotonic_decreasing


def test_budget_targets_match_the_plan():
    assert BT["op"] > 0 and 0.2 < BT["margin"] < 0.4


@pytest.mark.parametrize("cur,prev,expected", [(5, 0, None), (0, 0, None), (5, 10, -0.5), (3, 2.0, 0.5), (None, 3, None), (3, None, None), (float("nan"), 3, None), (np.int64(4), np.int64(0), None)])
def test_delta_never_divides_by_zero(cur, prev, expected):
    assert delta(cur, prev) == expected
