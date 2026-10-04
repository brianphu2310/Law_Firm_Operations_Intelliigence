"""Data-quality check suite for the warehouse. Writes docs/DATA_QUALITY.md.

    python -m warehouse.quality               # build (in memory), run all checks, rewrite docs/DATA_QUALITY.md
    python -m warehouse.quality --db warehouse.db

Check families: completeness (nulls), uniqueness (duplicates), referential integrity, validity/consistency
(business rules) and reconciliation of warehouse totals to the Streamlit app's own metric functions
(core/metrics.py), so the warehouse cannot silently drift from what the dashboards show.
"Observations" are informational findings about the simulated data that are reported but are not pass/fail.
Output is deterministic (no timestamps), so the committed report only changes when the data or the logic does.
"""
from __future__ import annotations

import argparse
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from core import metrics as X
from core.model import GST, build_model
from core.period import Period
from core.ref import AREAS, ATTORNEYS, AS_OF, START, TRUST_TARGET
from warehouse.build import ROOT, build_warehouse

REPORT_PATH = ROOT / "docs" / "DATA_QUALITY.md"
AS_OF_KEY = int(AS_OF.strftime("%Y%m%d"))

REQUIRED = {
    "dim_matter": ["matter_id", "matter_name", "client_key", "practice_area_key", "attorney_key", "branch_key", "status", "opened_date_key"],
    "dim_client": ["client_name", "primary_practice_area_key", "relationship_attorney_key", "country"],
    "fact_invoice": ["invoice_number", "client_key", "practice_area_key", "attorney_key", "branch_key", "issue_date_key", "due_date_key",
                     "amount_ex_gst", "gst_amount", "amount_total", "is_paid"],
    "fact_matter_position": ["estimated_value", "billed_to_date", "wip_balance", "progress_ratio", "days_open"],
    "fact_monthly_pnl": ["fees", "revenue", "total_costs", "operating_profit", "billable_hours"],
}
UNIQUE = {"fact_invoice": ["invoice_number"], "dim_matter": ["matter_id"], "dim_client": ["client_name"], "dim_attorney": ["attorney_short"],
          "dim_branch": ["branch_name"], "dim_date": ["full_date"]}
FOREIGN_KEYS = [
    ("dim_attorney", "home_branch_key", "dim_branch", "branch_key"), ("dim_attorney", "start_date_key", "dim_date", "date_key"),
    ("dim_client", "primary_practice_area_key", "dim_practice_area", "practice_area_key"),
    ("dim_client", "relationship_attorney_key", "dim_attorney", "attorney_key"),
    ("dim_matter", "client_key", "dim_client", "client_key"), ("dim_matter", "practice_area_key", "dim_practice_area", "practice_area_key"),
    ("dim_matter", "attorney_key", "dim_attorney", "attorney_key"), ("dim_matter", "branch_key", "dim_branch", "branch_key"),
    ("dim_matter", "opened_date_key", "dim_date", "date_key"), ("dim_matter", "closed_date_key", "dim_date", "date_key"),
    ("fact_invoice", "client_key", "dim_client", "client_key"), ("fact_invoice", "practice_area_key", "dim_practice_area", "practice_area_key"),
    ("fact_invoice", "attorney_key", "dim_attorney", "attorney_key"), ("fact_invoice", "branch_key", "dim_branch", "branch_key"),
    ("fact_invoice", "issue_date_key", "dim_date", "date_key"), ("fact_invoice", "due_date_key", "dim_date", "date_key"),
    ("fact_invoice", "paid_date_key", "dim_date", "date_key"),
    ("fact_matter_position", "matter_key", "dim_matter", "matter_key"), ("fact_matter_position", "as_of_date_key", "dim_date", "date_key"),
    ("fact_attorney_month", "attorney_key", "dim_attorney", "attorney_key"), ("fact_attorney_month", "month_start_date_key", "dim_date", "date_key"),
    ("fact_time_by_area", "attorney_key", "dim_attorney", "attorney_key"), ("fact_time_by_area", "practice_area_key", "dim_practice_area", "practice_area_key"),
    ("fact_time_by_area", "month_start_date_key", "dim_date", "date_key"),
    ("fact_monthly_pnl", "month_start_date_key", "dim_date", "date_key"), ("fact_monthly_pnl", "scenario_key", "dim_scenario", "scenario_key"),
    ("fact_monthly_snapshot", "month_start_date_key", "dim_date", "date_key"), ("fact_monthly_snapshot", "snapshot_date_key", "dim_date", "date_key"),
    ("fact_trust_balance", "client_key", "dim_client", "client_key"), ("fact_trust_balance", "month_start_date_key", "dim_date", "date_key"),
    ("fact_trust_txn", "client_key", "dim_client", "client_key"), ("fact_trust_txn", "txn_date_key", "dim_date", "date_key"),
]
MONEY_TOL = 0.05          # dollars; absolute tolerance for sums of floats
REL_TOL = 1e-9


@dataclass
class Check:
    family: str
    name: str
    expected: str
    actual: str
    passed: bool
    informational: bool = False


def _scalar(con, sql, *args):
    return con.execute(sql, args).fetchone()[0]


def _chk(family, name, expected, actual, passed=None) -> Check:
    return Check(family, name, str(expected), str(actual), (expected == actual) if passed is None else passed)


def _money(family, name, expected, actual, tol=MONEY_TOL) -> Check:
    e, a = float(expected), float(actual)
    return Check(family, name, f"{e:,.2f}", f"{a:,.2f}", abs(e - a) <= tol + REL_TOL * abs(e))


# ------------------------------------------------------------------ families --
def completeness(con):
    for table, cols in REQUIRED.items():
        for col in cols:
            yield _chk("Completeness", f"{table}.{col} has no NULLs", 0, _scalar(con, f"SELECT COUNT(*) FROM {table} WHERE {col} IS NULL"))
    yield _chk("Completeness", "invoice paid date and days_to_pay are NULL if and only if the invoice is unpaid", 0, _scalar(
        con, "SELECT COUNT(*) FROM fact_invoice WHERE (is_paid = 0) <> (paid_date_key IS NULL) OR (is_paid = 0) <> (days_to_pay IS NULL)"))
    yield _chk("Completeness", "matter closed date is present if and only if status = Closed", 0, _scalar(
        con, "SELECT COUNT(*) FROM dim_matter WHERE (status = 'Closed') <> (closed_date_key IS NOT NULL)"))
    yield _chk("Completeness", "every matter has a position row", 0, _scalar(
        con, "SELECT COUNT(*) FROM dim_matter m LEFT JOIN fact_matter_position p USING (matter_key) WHERE p.matter_key IS NULL"))


def uniqueness(con):
    for table, cols in UNIQUE.items():
        for col in cols:
            yield _chk("Uniqueness", f"{table}.{col} has no duplicates", 0,
                       _scalar(con, f"SELECT COUNT(*) FROM (SELECT {col} FROM {table} GROUP BY {col} HAVING COUNT(*) > 1)"))
    yield _chk("Uniqueness", "no duplicate invoices on (client, area, issue date, amount)", 0, _scalar(
        con, "SELECT COUNT(*) FROM (SELECT 1 FROM fact_invoice GROUP BY client_key, practice_area_key, issue_date_key, ROUND(amount_ex_gst, 2) HAVING COUNT(*) > 1)"))
    yield _chk("Uniqueness", "one P&L row per (month, scenario)", 0, _scalar(
        con, "SELECT COUNT(*) FROM (SELECT 1 FROM fact_monthly_pnl GROUP BY month_start_date_key, scenario_key HAVING COUNT(*) > 1)"))
    yield _chk("Uniqueness", "one attorney-month row per (attorney, month)", 0, _scalar(
        con, "SELECT COUNT(*) FROM (SELECT 1 FROM fact_attorney_month GROUP BY attorney_key, month_start_date_key HAVING COUNT(*) > 1)"))


def referential_integrity(con):
    yield _chk("Referential integrity", "PRAGMA foreign_key_check returns no violations", 0, len(con.execute("PRAGMA foreign_key_check").fetchall()))
    for ct, cc, pt, pc in FOREIGN_KEYS:
        n = _scalar(con, f"SELECT COUNT(*) FROM {ct} c LEFT JOIN {pt} p ON c.{cc} = p.{pc} WHERE c.{cc} IS NOT NULL AND p.{pc} IS NULL")
        yield _chk("Referential integrity", f"no orphans: {ct}.{cc} -> {pt}.{pc}", 0, n)
    yield _chk("Referential integrity", "every invoiced client has at least one matter", 0, _scalar(
        con, "SELECT COUNT(*) FROM dim_client c WHERE EXISTS (SELECT 1 FROM fact_invoice i WHERE i.client_key = c.client_key) "
             "AND NOT EXISTS (SELECT 1 FROM dim_matter m WHERE m.client_key = c.client_key)"))


def validity(con):
    V = "Validity"
    yield _chk(V, "invoice total = ex-GST + GST (to the cent)", 0, _scalar(con, "SELECT COUNT(*) FROM fact_invoice WHERE ABS(amount_total - amount_ex_gst - gst_amount) > 0.005"))
    yield _chk(V, f"invoice GST = {GST:.0%} of ex-GST amount", 0, _scalar(con, f"SELECT COUNT(*) FROM fact_invoice WHERE ABS(gst_amount - {GST} * amount_ex_gst) > 0.005"))
    yield _chk(V, "invoice due date is 30 days after issue", 0, _scalar(
        con, "SELECT COUNT(*) FROM fact_invoice i JOIN dim_date a ON a.date_key = i.issue_date_key JOIN dim_date b ON b.date_key = i.due_date_key "
             "WHERE julianday(b.full_date) - julianday(a.full_date) <> 30"))
    yield _chk(V, "invoice paid date is not before issue date", 0, _scalar(con, "SELECT COUNT(*) FROM fact_invoice WHERE paid_date_key < issue_date_key"))
    yield _chk(V, "no invoice issued or paid after the as-of date", 0, _scalar(
        con, "SELECT COUNT(*) FROM fact_invoice WHERE issue_date_key > ? OR paid_date_key > ?", AS_OF_KEY, AS_OF_KEY))
    yield _chk(V, "invoices are issued on weekdays", 0, _scalar(
        con, "SELECT COUNT(*) FROM fact_invoice i JOIN dim_date d ON d.date_key = i.issue_date_key WHERE d.is_weekend = 1"))
    yield _chk(V, "matter closed date is not before opened date", 0, _scalar(con, "SELECT COUNT(*) FROM dim_matter WHERE closed_date_key < opened_date_key"))
    yield _chk(V, "closed matters carry no WIP", 0, _scalar(
        con, "SELECT COUNT(*) FROM dim_matter m JOIN fact_matter_position p USING (matter_key) WHERE m.status = 'Closed' AND p.wip_balance <> 0"))
    yield _chk(V, "matter progress within 0-1 and billed <= 115% of estimated value", 0, _scalar(
        con, "SELECT COUNT(*) FROM fact_matter_position WHERE progress_ratio NOT BETWEEN 0 AND 1 OR billed_to_date > 1.15 * estimated_value"))
    yield _chk(V, "attorney-month rows start on or after the attorney's start date", 0, _scalar(
        con, "SELECT COUNT(*) FROM fact_attorney_month a JOIN dim_attorney t USING (attorney_key) WHERE a.month_start_date_key < t.start_date_key"))
    yield _chk(V, "utilisation (billable / capacity hours) between 0 and 130% for every attorney-month", 0, _scalar(
        con, "SELECT COUNT(*) FROM fact_attorney_month WHERE billable_hours <= 0 OR billable_hours / capacity_hours > 1.3"))
    yield _chk(V, "P&L: revenue = fees + disbursements billed", 0, _scalar(
        con, "SELECT COUNT(*) FROM fact_monthly_pnl WHERE ABS(revenue - fees - disbursements_billed) > 0.01"))
    yield _chk(V, "P&L: operating profit = revenue - total costs", 0, _scalar(
        con, "SELECT COUNT(*) FROM fact_monthly_pnl WHERE ABS(operating_profit - revenue + total_costs) > 0.01"))
    yield _chk(V, "P&L: total costs = sum of the 13 cost lines", 0, _scalar(
        con, "SELECT COUNT(*) FROM fact_monthly_pnl WHERE ABS(total_costs - (payroll_fee_earners + disbursement_cost + payroll_support + rent + software + "
             "insurance + marketing + professional_fees + cards + merchant_fees + commission + bank_fees + other_costs)) > 0.01"))
    yield _chk(V, "no negative trust balances", 0, _scalar(con, "SELECT COUNT(*) FROM fact_trust_balance WHERE closing_balance < 0"))
    yield _chk(V, "trust ledger continuity: month-on-month balance change = net transactions (within 5 cents)", 0, _scalar(
        con, """WITH b AS (SELECT client_key, month_start_date_key, closing_balance,
                       closing_balance - LAG(closing_balance) OVER (PARTITION BY client_key ORDER BY month_start_date_key) AS delta
                FROM fact_trust_balance),
                t AS (SELECT client_key, CAST(txn_date_key / 100 AS INTEGER) AS ym, SUM(amount) AS net FROM fact_trust_txn GROUP BY 1, 2)
                SELECT COUNT(*) FROM b LEFT JOIN t ON t.client_key = b.client_key AND t.ym = CAST(b.month_start_date_key / 100 AS INTEGER)
                WHERE b.delta IS NOT NULL AND ABS(b.delta - COALESCE(t.net, 0)) > 0.05"""))
    yield _chk(V, "snapshot matters_active equals active matters recomputed from dim_matter at each snapshot date", 0, _scalar(
        con, """SELECT COUNT(*) FROM fact_monthly_snapshot s JOIN dim_date sd ON sd.date_key = s.snapshot_date_key
                WHERE s.matters_active <> (SELECT COUNT(*) FROM dim_matter m JOIN dim_date o ON o.date_key = m.opened_date_key
                                           LEFT JOIN dim_date c ON c.date_key = m.closed_date_key
                                           WHERE o.full_date <= sd.full_date AND (c.full_date IS NULL OR c.full_date > sd.full_date))"""))
    yield _chk(V, "client has a trust ledger if and only if flagged has_trust_account", 0, _scalar(
        con, "SELECT COUNT(*) FROM dim_client c WHERE c.has_trust_account <> EXISTS (SELECT 1 FROM fact_trust_balance b WHERE b.client_key = c.client_key)"))


def observations(con):
    """Informational findings (not pass/fail)."""
    n = _scalar(con, "SELECT COUNT(*) FROM dim_matter m JOIN dim_attorney a USING (attorney_key) WHERE m.branch_key <> a.home_branch_key")
    yield Check("Observations", "matters whose branch differs from the responsible attorney's home branch (hand-set on the named key matters in core/ref.py)", "n/a", str(n), True, True)
    n = _scalar(con, "SELECT COUNT(*) - COUNT(DISTINCT matter_name) FROM dim_matter")
    yield Check("Observations", "matter names that are not unique (matter_id is the key)", "n/a", str(n), True, True)
    n = _scalar(con, "SELECT COUNT(*) FROM fact_invoice i JOIN dim_date d ON d.date_key = i.issue_date_key WHERE d.full_date < ?", START.strftime("%Y-%m-%d"))
    yield Check("Observations", f"invoices issued before the history window start ({START:%Y-%m-%d}); they exist so opening receivables are realistic", "n/a", str(n), True, True)
    n = _scalar(con, "SELECT COUNT(*) FROM fact_monthly_pnl WHERE scenario_key = 1 AND fees > standard_value")
    yield Check("Observations", "actual months where fees billed exceed standard value of time recorded (WIP is being drawn down; not an error)", "n/a", str(n), True, True)
    n = _scalar(con, "SELECT COUNT(*) FROM fact_attorney_month WHERE fees_realised > standard_value")
    yield Check("Observations", "attorney-months where realised fees exceed standard value (driven by the generator's per-attorney realisation factor and fee allocation)", "n/a", str(n), True, True)


def reconciliation(con, M):
    """Warehouse totals vs the app's own metric functions over the full actual window (START to AS_OF)."""
    R = "Reconciliation"
    p = Period(START, AS_OF, "Full history")
    out = []
    fin = X.fin_sum(M, p)
    act = dict(zip(("fees", "revenue", "total_costs", "operating_profit", "billable_hours", "standard_value", "writeoff", "disbursements_billed", "capacity_hours"),
                   con.execute("SELECT SUM(fees), SUM(revenue), SUM(total_costs), SUM(operating_profit), SUM(billable_hours), SUM(standard_value), SUM(writeoff), "
                               "SUM(disbursements_billed), SUM(capacity_hours) FROM fact_monthly_pnl WHERE scenario_key = 1").fetchone()))
    for col, src in [("fees", "fees"), ("revenue", "revenue"), ("total_costs", "total_costs"), ("operating_profit", "op_profit"),
                     ("billable_hours", "hours"), ("standard_value", "value_std"), ("writeoff", "writeoff"),
                     ("disbursements_billed", "disb_billed"), ("capacity_hours", "capacity")]:
        out.append(_money(R, f"Actual {col}: warehouse SUM = app fin_sum()['{src}']", fin[src], act[col]))
    plan = X.plan_sum(M, p)
    bud = dict(zip(("fees", "revenue", "op"), con.execute(
        "SELECT SUM(fees), SUM(revenue), SUM(operating_profit) FROM fact_monthly_pnl WHERE scenario_key = 2 AND month_start_date_key <= ?", (AS_OF_KEY,)).fetchone()))
    out.append(_money(R, "Budget fees to as-of date = app plan_sum()['fees']", plan["fees"], bud["fees"]))
    out.append(_money(R, "Budget revenue to as-of date = app plan_sum()['revenue']", plan["revenue"], bud["revenue"]))
    out.append(_money(R, "Budget operating profit to as-of date = app plan_sum()['op_profit']", plan["op_profit"], bud["op"]))

    at = X.att_table(M, p)
    wh = {r[0]: r[1:] for r in con.execute(
        """SELECT a.attorney_short, SUM(m.billable_hours), SUM(m.standard_value), SUM(m.fees_realised), SUM(m.salary_cost), SUM(m.capacity_hours)
           FROM fact_attorney_month m JOIN dim_attorney a USING (attorney_key) GROUP BY 1""")}
    for short, row in at.iterrows():
        h, v, f, c, cap = wh[short]
        out.append(Check(R, f"attorney '{short}': hours / value / fees / salary cost / capacity = app att_table()",
                         str((round(row["hours"], 2), round(row["value"], 2), round(row["fees"], 2), round(row["cost"], 2), round(row["capacity"], 2))),
                         str((round(h, 2), round(v, 2), round(f, 2), round(c, 2), round(cap, 2))),
                         all(abs(x - y) <= 0.05 for x, y in zip((row["hours"], row["value"], row["fees"], row["cost"], row["capacity"]), (h, v, f, c, cap)))))
    ar = X.area_table(M, p)
    whA = {r[0]: r[1:] for r in con.execute(
        "SELECT pa.practice_area, SUM(t.billable_hours), SUM(t.fees_realised) FROM fact_time_by_area t JOIN dim_practice_area pa USING (practice_area_key) GROUP BY 1")}
    for k in AREAS:
        out.append(Check(R, f"practice area '{k}': hours / fees = app area_table()", str((round(ar.loc[k, "hours"], 2), round(ar.loc[k, "fees"], 2))),
                         str((round(whA[k][0], 2), round(whA[k][1], 2))), abs(ar.loc[k, "hours"] - whA[k][0]) <= 0.05 and abs(ar.loc[k, "fees"] - whA[k][1]) <= 0.05))
    out.append(_money(R, "sum of allocated salary by area = sum of attorney salary cost", con.execute("SELECT SUM(salary_cost) FROM fact_attorney_month").fetchone()[0],
                      con.execute("SELECT SUM(allocated_salary_cost) FROM fact_time_by_area").fetchone()[0]))

    # receivables
    inv_total = _scalar(con, "SELECT SUM(amount_total) FROM fact_invoice WHERE issue_date_key <= ? AND (paid_date_key IS NULL OR paid_date_key > ?)", AS_OF_KEY, AS_OF_KEY)
    out.append(_money(R, "open receivables at as-of date = app ar_total()", X.ar_total(M, AS_OF), inv_total))
    _, buckets = X.ar_ageing(M, AS_OF)
    sql_b = dict(con.execute(
        """WITH o AS (SELECT i.amount_total, CAST(julianday(?) - julianday(d.full_date) AS INTEGER) AS past_due
                      FROM fact_invoice i JOIN dim_date d ON d.date_key = i.due_date_key
                      WHERE i.issue_date_key <= ? AND (i.paid_date_key IS NULL OR i.paid_date_key > ?))
           SELECT CASE WHEN past_due <= 0 THEN 'Not yet due' WHEN past_due <= 30 THEN '1–30 days' WHEN past_due <= 60 THEN '31–60 days'
                       WHEN past_due <= 90 THEN '61–90 days' ELSE '90+ days' END, SUM(amount_total) FROM o GROUP BY 1""",
        (AS_OF.strftime("%Y-%m-%d"), AS_OF_KEY, AS_OF_KEY)).fetchall())
    for label, v in buckets.items():
        out.append(_money(R, f"AR ageing bucket '{label}' = app ar_ageing()", v, sql_b.get(label, 0.0)))
    ct = X.client_table(M, p).set_index("client")
    whC = dict(con.execute("SELECT c.client_name, SUM(i.amount_ex_gst) FROM fact_invoice i JOIN dim_client c USING (client_key) "
                           "WHERE i.issue_date_key BETWEEN ? AND ? GROUP BY 1", (int(START.strftime("%Y%m%d")), AS_OF_KEY)).fetchall())
    bad = [c for c in ct.index if abs(ct.loc[c, "revenue"] - whC.get(c, 0.0)) > 0.05]
    out.append(_chk(R, "per-client invoiced revenue (START-AS_OF) = app client_table() for all clients", [], bad))
    out.append(_chk(R, "invoice count = model invoice ledger rows", len(M["inv"]), _scalar(con, "SELECT COUNT(*) FROM fact_invoice")))
    out.append(_money(R, "invoice total = model invoice ledger total", M["inv"]["total"].sum(), _scalar(con, "SELECT SUM(amount_total) FROM fact_invoice")))

    # stock balances
    last = con.execute("SELECT wip_balance, cash_balance, receivables_incl_gst, trust_balance, matters_active FROM fact_monthly_snapshot "
                       "ORDER BY month_start_date_key DESC LIMIT 1").fetchone()
    out.append(_money(R, "latest snapshot WIP = model stock WIP", M["stock"]["wip"].iloc[M["T_act"] - 1], last[0]))
    out.append(_money(R, "latest snapshot receivables = app ar_total()", X.ar_total(M, AS_OF), last[2]))
    out.append(_money(R, "latest snapshot trust balance = sum of TRUST_TARGET", sum(TRUST_TARGET.values()), last[3]))
    out.append(_money(R, "sum of client trust closing balances (latest month) = latest snapshot trust balance", last[3],
                      _scalar(con, "SELECT SUM(closing_balance) FROM fact_trust_balance WHERE month_start_date_key = (SELECT MAX(month_start_date_key) FROM fact_trust_balance)")))
    out.append(_chk(R, "latest snapshot active matters = 142 (the app's headline matter count)", 142, last[4]))
    out.append(_money(R, "sum of matter-level WIP = firm WIP balance (matter WIP is rounded to whole dollars; tolerance $5)", last[0],
                      _scalar(con, "SELECT SUM(wip_balance) FROM fact_matter_position"), tol=5.0))
    out.append(_chk(R, "dim_matter rows = model matter ledger rows", len(M["matters"]), _scalar(con, "SELECT COUNT(*) FROM dim_matter")))
    return out


def run_checks(con: sqlite3.Connection, model: dict | None = None) -> list[Check]:
    M = model if model is not None else build_model()
    checks: list[Check] = []
    for fam in (completeness, uniqueness, referential_integrity, validity):
        checks.extend(fam(con))
    checks.extend(reconciliation(con, M))
    checks.extend(observations(con))
    return checks


# ------------------------------------------------------------------- report --
def render_markdown(checks: list[Check]) -> str:
    gated = [c for c in checks if not c.informational]
    info = [c for c in checks if c.informational]
    fams = list(dict.fromkeys(c.family for c in gated))
    passed = sum(c.passed for c in gated)
    lines = ["# Data quality report", "",
             "Generated by `python -m warehouse.quality` against `warehouse.db`, which is built from the **simulated**",
             "dataset (`core/model.py`, fixed seed). The report is deterministic, so it only changes if the data or the checks change.",
             "", f"**Result: {passed} of {len(gated)} checks passed.** ({len(info)} informational observations are listed separately.)", "",
             "| Family | Checks | Passed | Failed |", "|---|---:|---:|---:|"]
    for f in fams:
        cs = [c for c in gated if c.family == f]
        lines.append(f"| {f} | {len(cs)} | {sum(c.passed for c in cs)} | {sum(not c.passed for c in cs)} |")
    lines += ["", "Reconciliation checks compare warehouse SQL totals with the Streamlit app's own functions in `core/metrics.py` over the actual window",
              f"({START:%Y-%m-%d} to {AS_OF:%Y-%m-%d}). Flow amounts for the as-of month are pro-rated to days elapsed, exactly as the app does. Tolerance: 5 cents unless stated.", ""]
    for f in fams:
        lines += [f"## {f}", "", "| Status | Check | Expected | Actual |", "|---|---|---|---|"]
        for c in (c for c in gated if c.family == f):
            lines.append(f"| {'PASS' if c.passed else '**FAIL**'} | {c.name} | `{c.expected}` | `{c.actual}` |")
        lines.append("")
    if info:
        lines += ["## Observations (informational, not pass/fail)", "", "| Observation | Count |", "|---|---:|"]
        lines += [f"| {c.name} | {c.actual} |" for c in info]
        lines.append("")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", default=":memory:", help="existing warehouse.db, or ':memory:' to build one on the fly")
    ap.add_argument("--report", default=str(REPORT_PATH))
    args = ap.parse_args(argv)
    if args.db == ":memory:":
        con = build_warehouse(":memory:")
    else:
        con = sqlite3.connect(args.db)
        con.execute("PRAGMA foreign_keys = ON")
    checks = run_checks(con)
    Path(args.report).write_text(render_markdown(checks) + "\n")
    failed = [c for c in checks if not c.passed]
    gated = [c for c in checks if not c.informational]
    print(f"{len(gated) - len(failed)}/{len(gated)} checks passed -> {args.report}")
    for c in failed:
        print(f"  FAIL [{c.family}] {c.name}: expected {c.expected}, got {c.actual}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
