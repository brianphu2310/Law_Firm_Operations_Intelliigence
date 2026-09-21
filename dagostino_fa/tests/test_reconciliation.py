"""Reconciliation tests: the numbers on different pages must agree with each other.

Run from the project folder:  python -m pytest -q     (or)     python tests/test_reconciliation.py
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import metrics as X
from core import platforms as P
from core.model import build_model
from core.period import Period, presets, flow, _shift
from core.ref import AS_OF, OFFICE_CASH_AT_AS_OF, TRUST_TARGET

M = build_model()
T = M["T_act"]
FIN, PLAN, STK, INV = M["fin"], M["plan"], M["stock"], M["inv"]


def close(a, b, tol=1.0):
    assert abs(a - b) <= tol, f"{a} != {b} (tol {tol})"


# ------------------------------------------------------------------ model ----
def test_balances_at_as_of_date():
    close(STK["cash"].iloc[T - 1], OFFICE_CASH_AT_AS_OF)
    close(STK["trust"].iloc[T - 1], sum(TRUST_TARGET.values()))
    assert int(STK["matters_active"].iloc[T - 1]) == 142


def test_profit_arithmetic():
    a = FIN.iloc[:T]
    assert np.allclose(a["revenue"] - a["total_costs"], a["op_profit"])
    assert np.allclose(a["fees"] + a["disb_billed"], a["revenue"])


def test_invoice_ledger_equals_revenue():
    """Every dollar of monthly revenue is an invoice on the ledger (full financial year FY25)."""
    fy25 = FIN.loc["2024-07-01":"2025-06-01", "revenue"].sum()
    issued = INV[(INV["issue"] >= "2024-07-01") & (INV["issue"] <= "2025-06-30")]["ex_gst"].sum()
    close(fy25, issued, 1.0)


def test_cash_never_below_operating_floor():
    assert STK["cash"].iloc[:T].min() >= 60_000 - 1


def test_trust_ledgers_never_negative_and_match_transactions():
    assert (M["trust"] >= 0).all().all()
    close(M["trust"].iloc[-1].sum(), sum(TRUST_TARGET.values()))


def test_matter_wip_reconciles_to_firm_wip():
    live = M["matters"][M["matters"]["status"].isin(["Open", "On Hold"])]
    close(live["wip"].sum(), STK["wip"].iloc[T - 1], tol=live.shape[0])          # per-matter rounding to whole dollars


def test_detail_tables_tie_to_monthly_totals():
    m0 = AS_OF.replace(day=1)
    close(M["infotrack"][M["infotrack"]["date"] >= m0]["cost"].sum(), FIN["searches"].iloc[T - 1] * 38 * M["frac"][T - 1], tol=T)
    close(M["cards"][M["cards"]["date"] >= m0]["amount"].sum(), FIN["cards"].iloc[T - 1] * M["frac"][T - 1], tol=T)


# ----------------------------------------------------------------- periods ----
def test_period_presets():
    pre = presets()
    qtd, _ = pre["This quarter (QTD)"]
    assert (qtd.start, qtd.end) == (pd.Timestamp("2025-07-01"), AS_OF)
    fy25, _ = pre["FY25 (last financial year)"]
    assert (fy25.start, fy25.end) == (pd.Timestamp("2024-07-01"), pd.Timestamp("2025-06-30"))


def test_mtd_revenue_equals_invoices_issued():
    mtd, _ = presets()["This month (MTD)"]
    f = X.fin_sum(M, mtd)
    issued = INV[(INV["issue"] >= mtd.start) & (INV["issue"] <= mtd.end)]["ex_gst"].sum()
    close(f["revenue"], issued, 1.0)


def test_quarters_add_up_to_year():
    q = [Period(pd.Timestamp(a), pd.Timestamp(b), "q") for a, b in [("2024-07-01", "2024-09-30"), ("2024-10-01", "2024-12-31"), ("2025-01-01", "2025-03-31"), ("2025-04-01", "2025-06-30")]]
    fy = Period(pd.Timestamp("2024-07-01"), pd.Timestamp("2025-06-30"), "fy")
    close(sum(X.fin_sum(M, p)["revenue"] for p in q), X.fin_sum(M, fy)["revenue"], 1.0)


# ------------------------------------------------------------------ metrics ----
def test_attorney_table_sums_to_firm():
    cur, _ = presets()["This quarter (QTD)"]
    at, f = X.att_table(M, cur), X.fin_sum(M, cur)
    close(at["hours"].sum(), f["hours"], 0.5)
    close(at["fees"].sum(), f["fees"], 1.0)
    close(at["cost"].sum(), f["payroll_fee"], 1.0)


def test_branch_table_sums_to_firm():
    cur, _ = presets()["This quarter (QTD)"]
    bt, f = X.branch_table(M, cur), X.fin_sum(M, cur)
    close(bt["revenue"].sum(), f["revenue"], 1.0)
    close(bt["op_profit"].sum(), f["op_profit"], 5.0)
    assert int(bt["active_matters"].sum()) == 142


def test_receivables_ageing_sums_to_total():
    _, buckets = X.ar_ageing(M, AS_OF)
    close(buckets.sum(), X.ar_total(M, AS_OF), 0.01)
    close(X.ar_total(M, AS_OF), STK["ar"].iloc[T - 1], 0.01)


def test_client_table_sums_to_firm():
    cur, cmp = presets()["This quarter (QTD)"][0], None
    ct = X.client_table(M, cur, cmp)
    close(ct["revenue"].sum(), X.fin_sum(M, cur)["revenue"], 1.0)


def test_cash_forecast_is_self_consistent():
    wk = X.cash_forecast(M)
    assert len(wk) == 13
    close(wk["opening"].iloc[0], OFFICE_CASH_AT_AS_OF, 0.01)
    assert np.allclose(wk["closing"], wk["opening"] + wk["net"])
    assert np.allclose(wk["opening"].iloc[1:].values, wk["closing"].iloc[:-1].values)


def test_fy_outlook_budget_matches_plan():
    o = X.fy_outlook(M)
    close(o["budget_rev"], PLAN.loc["2025-07-01":"2026-06-01", "revenue"].sum(), 1.0)
    close(o["fc_op"], o["fc_rev"] - o["fc_cost"], 1.0)


# --------------------------------------------------------------- platforms ----
def test_platforms():
    inp = P.base_inputs(M)
    ev, _ = P.evaluate(P.BASELINE, inp)
    assert abs(ev["npv"]) < 1e-6 and len(P.NAMES) == 7
    assert set(P.ranking(inp)["rank"]) <= set(range(1, 8))
    bad = P.evaluate("PracticeEvolve + PEXA", inp)[0]
    assert bad["npv"] < P.evaluate("Smokeball + GlobalX", inp)[0]["npv"]


def test_simulator_zero_levers_equals_base():
    from views import simulator as S
    _, f = S._base(M)
    r = S.project(f, dict(S.DEFAULTS))
    close(r["rev1"], r["rev0"], 0.01); close(r["op1"], r["op0"], 0.01)
    up = S.project(f, {**S.DEFAULTS, "sim_util": 1.0})
    assert up["op1"] > r["op1"]


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    for n, f in tests:
        f(); print("PASS", n)
    print(f"{len(tests)} tests passed")
