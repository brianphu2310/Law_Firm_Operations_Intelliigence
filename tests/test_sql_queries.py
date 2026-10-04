"""Every analytical query in sql/analysis/ must execute, return sensible rows, and agree with the warehouse totals."""
import csv
import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "sql"))

import run_queries as RQ
from core import metrics as X
from core.model import build_model
from core.period import Period
from core.ref import AREAS, AS_OF, START
from warehouse.build import build_warehouse

M = build_model()
FILES = RQ.query_files()
P = Period(START, AS_OF, "Full")


@pytest.fixture(scope="module")
def con():
    c = build_warehouse(":memory:", model=M)
    yield c
    c.close()


def result(con, stem):
    cols, rows = RQ.run_query(con, next(p for p in FILES if p.stem == stem))
    return [dict(zip(cols, r)) for r in rows]


def test_between_8_and_10_queries_exist():
    assert 8 <= len(FILES) <= 10


@pytest.mark.parametrize("path", FILES, ids=[p.stem for p in FILES])
def test_query_executes_and_returns_rows(con, path):
    cols, rows = RQ.run_query(con, path)
    assert cols and rows
    assert len(cols) == len(set(cols)), "duplicate output column names"


@pytest.mark.parametrize("path", FILES, ids=[p.stem for p in FILES])
def test_query_is_commented_and_uses_cte(path):
    sql = path.read_text()
    assert sql.lstrip().startswith("--")
    assert re.search(r"^\s*WITH\b", sql, re.I | re.M)


def test_portfolio_uses_the_required_sql_features():
    allsql = "\n".join(p.read_text() for p in FILES).upper()
    for feature in ("RANK()", "LAG(", "PERCENT_RANK()", "NTILE(", "SUM(", " OVER (", "CASE", "CROSS JOIN", "ROWS BETWEEN", "ROWS UNBOUNDED PRECEDING"):
        assert feature in allsql, feature


def test_utilisation_matches_app_att_table(con):
    rows = result(con, "01_utilisation_by_attorney")
    at = X.att_table(M, P)
    by = {}
    for r in rows:
        by.setdefault(r["attorney_name"], [0.0, 0.0])
        by[r["attorney_name"]][0] += r["billable_hours"]
        by[r["attorney_name"]][1] += r["capacity_hours"]
    for short, row in at.iterrows():
        h, cap = by[row["attorney"]]
        assert h == pytest.approx(row["hours"], abs=0.1 * 30) and cap == pytest.approx(row["capacity"], abs=0.1 * 30)   # rows are rounded to 1 dp
    first = [r for r in rows if r["month_start"] == rows[0]["month_start"]]
    assert sorted(r["rank_in_month"] for r in first) == list(range(1, len(first) + 1))


def test_wip_by_age_sums_to_open_matter_wip(con):
    rows = result(con, "02_wip_by_matter_age")
    mt = M["matters"]
    expected = mt.loc[mt["status"].isin(["Open", "On Hold"]), "wip"].sum()
    assert sum(r["wip"] for r in rows) == pytest.approx(expected, abs=len(rows))
    assert sum(r["matters"] for r in rows) == int(mt["status"].isin(["Open", "On Hold"]).sum())
    areas = {}
    for r in rows:
        areas[r["practice_area"]] = areas.get(r["practice_area"], 0) + r["pct_of_area_wip"]
    assert all(abs(v - 100) < 0.5 for v in areas.values())


def test_realisation_matches_app_ratios(con):
    rows = result(con, "03_realisation_trend")
    assert len(rows) == M["T_act"]
    f = X.fin_sum(M, P)
    ytd_last = rows[-1]["fy_ytd_realisation_pct"]
    fy = X.fin_sum(M, Period(X.fy_bounds(AS_OF)[0], AS_OF, "FYTD"))
    assert ytd_last == pytest.approx(100 * fy["fees"] / fy["value_std"], abs=0.06)
    assert rows[0]["mom_change_pct_pts"] is None
    assert f["fees"] > 0


def test_practice_area_fees_reconcile(con):
    rows = result(con, "04_practice_area_profitability")
    assert {r["practice_area"] for r in rows} == set(AREAS)
    total = sum(r["fees"] for r in rows)
    assert total == pytest.approx(X.fin_sum(M, P)["fees"], abs=len(rows))
    for fy in {r["fy_label"] for r in rows}:
        assert sorted(r["margin_rank_in_fy"] for r in rows if r["fy_label"] == fy) == list(range(1, 6))


def test_matter_billing_position_is_top_wip_first(con):
    rows = result(con, "05_matter_billing_position")
    assert len(rows) == 40
    wips = [r["wip"] for r in rows]
    assert wips == sorted(wips, reverse=True)
    assert {r["billing_flag"] for r in rows} <= {"Not started", "Under-billed", "Billed ahead of progress", "In line"}


def test_client_concentration_shares_and_hhi(con):
    rows = result(con, "06_client_concentration")
    assert sum(r["pct_of_fees"] for r in rows) == pytest.approx(100, abs=1.0)
    assert rows[-1]["cumulative_pct"] == pytest.approx(100, abs=0.2)
    hhi = rows[0]["firm_hhi"]
    shares = [r["pct_of_fees"] for r in rows]
    assert hhi == pytest.approx(sum(s * s for s in shares), rel=0.02)
    assert 0 < hhi < 10000


def test_receivables_ageing_matches_app_totals(con):
    rows = result(con, "07_receivables_ageing_by_client")
    assert sum(r["ar_incl_gst"] for r in rows) == pytest.approx(X.ar_total(M, AS_OF), abs=len(rows))
    _, buckets = X.ar_ageing(M, AS_OF)
    assert sum(r["days_90_plus"] for r in rows) == pytest.approx(buckets["90+ days"], abs=len(rows))
    assert sum(r["not_yet_due"] for r in rows) == pytest.approx(buckets["Not yet due"], abs=len(rows))


def test_payment_behaviour_covers_paid_invoices(con):
    rows = result(con, "08_payment_behaviour_by_client")
    inv = M["inv"]
    paid = inv[inv["paid"].notna() & (inv["issue"] >= START)]
    assert sum(r["paid_invoices"] for r in rows) == len(paid)
    assert all(r["sd_days"] >= 0 and 0 <= r["pct_paid_late"] <= 100 for r in rows)
    first_fy = min(r["fy_label"] for r in rows)
    assert all(r["change_vs_prior_fy_days"] is None for r in rows if r["fy_label"] == first_fy)


def test_pnl_actual_vs_budget_reconciles(con):
    rows = result(con, "09_pnl_actual_vs_budget")
    assert sum(r["actual_profit"] for r in rows) == pytest.approx(X.fin_sum(M, P)["op_profit"], abs=len(rows))
    assert sum(r["budget_profit"] for r in rows) == pytest.approx(X.plan_sum(M, P)["op_profit"], abs=len(rows))
    last = rows[-1]
    assert last["profit_ytd_variance"] == pytest.approx(last["actual_profit_fy_ytd"] - last["budget_profit_fy_ytd"], abs=1.5)


def test_trust_balances_last_12_months_and_total(con):
    rows = result(con, "10_trust_account_balances")
    months = sorted({r["month_start"] for r in rows})
    assert len(months) == 12 and months[-1] == "2025-09-01"
    latest = [r for r in rows if r["month_start"] == months[-1]]
    assert sum(r["closing_balance"] for r in latest) == pytest.approx(M["stock"]["trust"].iloc[M["T_act"] - 1], abs=len(latest))
    assert sum(r["pct_of_trust"] for r in latest) == pytest.approx(100, abs=0.5)


def test_committed_csv_outputs_are_current(con, tmp_path):
    RQ.run_all(con, tmp_path)
    for p in FILES:
        assert (RQ.OUT_DIR / f"{p.stem}.csv").read_text() == (tmp_path / f"{p.stem}.csv").read_text(), f"{p.stem}.csv is stale - run: python sql/run_queries.py"
    assert {f.name for f in RQ.OUT_DIR.glob("*.csv")} == {f"{p.stem}.csv" for p in FILES}


def test_csv_has_header_and_rows(tmp_path, con):
    RQ.run_all(con, tmp_path)
    with open(tmp_path / "06_client_concentration.csv", newline="") as f:
        r = list(csv.reader(f))
    assert r[0][0] == "client_rank" and len(r) == 24
