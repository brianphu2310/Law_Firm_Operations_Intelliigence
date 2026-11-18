"""Pipeline data-quality checks + reconciliation to the dashboard, then a snapshot for the app's Pipeline page.

    python -m integration.quality            # builds staging/marts, runs checks, writes integration/snapshot/*.csv
                                             # and docs/PIPELINE_QUALITY.md; exits 1 if any check fails

Two kinds of checks:
  * Accounting integrity inside the warehouse (GST, line totals, balances vs payments, referential integrity, de-duplication).
  * Reconciliation to the app: receivables, ageing buckets and monthly revenue from MYOB-shaped data must equal what the
    dashboard computes from core.model. Tolerance is cent rounding only (the export rounds each invoice to the cent).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from core import metrics as X
from core.model import build_model
from core.ref import AS_OF

ROOT = Path(__file__).resolve().parent
SNAP = ROOT / "snapshot"
DOC = ROOT.parent / "docs" / "PIPELINE_QUALITY.md"
BUCKETS = ["Not yet due", "1–30 days", "31–60 days", "61–90 days", "90+ days"]

CHECKS = {
    "API count = rows loaded (last batch, every resource)":
        "select count(*) from raw.load_audit where batch_id = (select batch_id from raw.load_audit order by loaded_at desc limit 1) and status <> 'OK'",
    "No duplicate invoices after de-duplication": "select count(*) - count(distinct invoice_uid) from staging.stg_invoices",
    "Invoice total = subtotal + GST (10%)":
        "select count(*) from staging.stg_invoices where abs(total_amount - subtotal - total_tax) > 0.005 or abs(total_tax - round(subtotal * 0.1, 2)) > 0.005",
    "Invoice subtotal = sum of its lines":
        """select count(*) from staging.stg_invoices i join (select invoice_uid, sum(line_amount_ex_gst) s from staging.stg_invoice_lines group by 1) l
           using (invoice_uid) where abs(i.subtotal - l.s) > 0.005""",
    "Balance due = total - payments applied":
        """select count(*) from staging.stg_invoices i left join (select invoice_uid, sum(amount_applied) p from staging.stg_payment_allocations group by 1) p
           using (invoice_uid) where abs(i.total_amount - coalesce(p.p, 0) - i.balance_due) > 0.005""",
    "Closed invoices have zero balance, open ones a positive balance":
        "select count(*) from staging.stg_invoices where (status = 'Closed') <> (balance_due = 0)",
    "Every invoice links to a known client":
        "select count(*) from staging.stg_invoices i left join staging.stg_customers c using (customer_uid) where c.customer_uid is null",
    "No payment dated before its invoice":
        "select count(*) from staging.stg_payment_allocations p join staging.stg_invoices i using (invoice_uid) where p.payment_date < i.invoice_date",
    # cross-system integrity (LEAP, InfoTrack, PEXA, MYOB)
    "LEAP invoices = MYOB invoices (number and total)": "select count(*) from marts.invoice_sync_recon where result <> 'Matched'",
    "Every LEAP invoice belongs to a LEAP matter":
        "select count(*) from staging.stg_leap_invoices i left join staging.stg_leap_matters m using (matter_number) where m.matter_number is null",
    "Every InfoTrack order references a LEAP matter":
        "select count(*) from staging.stg_infotrack_orders o left join staging.stg_leap_matters m using (matter_number) where m.matter_number is null",
    "Every PEXA workspace references a LEAP matter":
        "select count(*) from staging.stg_pexa_workspaces w left join staging.stg_leap_matters m using (matter_number) where m.matter_number is null",
}


def build_layers(con) -> None:
    for f in ("01_staging.sql", "02_marts.sql"):
        con.execute((ROOT / "sql" / "duckdb" / f).read_text())


def reconcile(con, M) -> pd.DataFrame:
    """Pipeline marts vs the dashboard's own numbers (core.metrics on core.model)."""
    n_inv = len(M["inv"])
    tol = round(0.011 * n_inv, 2)                                      # at most ~1 cent of rounding per invoice
    rows = []
    as_at = con.execute("select as_at from staging.stg_report_date").fetchone()[0]
    rows.append(("Report date (company file sync)", str(AS_OF.date()), str(as_at), 0.0, str(as_at) == str(AS_OF.date())))
    ar_app = X.ar_total(M, AS_OF)
    ar_pipe = float(con.execute("select coalesce(sum(balance_due), 0) from marts.aged_receivables").fetchone()[0])
    rows.append(("Receivables incl. GST", ar_app, ar_pipe, ar_pipe - ar_app, abs(ar_pipe - ar_app) <= tol))
    _, app_b = X.ar_ageing(M, AS_OF)
    pipe_b = dict(con.execute("select ageing_bucket, sum(balance_due) from marts.aged_receivables group by 1").fetchall())
    for b in BUCKETS:
        a, p = float(app_b[b]), float(pipe_b.get(b, 0))
        rows.append((f"Ageing: {b}", a, p, p - a, abs(p - a) <= tol))
    inv = M["inv"]
    rev_app = inv.groupby(inv["issue"].dt.to_period("M"))["ex_gst"].sum()
    rev_pipe = con.execute("select month, sum(revenue_ex_gst) from marts.revenue_monthly group by 1").df()
    rev_pipe = rev_pipe.set_index(pd.to_datetime(rev_pipe["month"]).dt.to_period("M")).iloc[:, 1].astype(float)
    worst = (rev_pipe.reindex(rev_app.index).fillna(0) - rev_app).abs().max()
    rows.append(("Revenue ex GST, all months (difference = worst single month)", float(rev_app.sum()), float(rev_pipe.sum()), float(worst), worst <= 0.011 * inv.groupby(inv["issue"].dt.to_period("M")).size().max()))
    leap_rev = float(con.execute("select sum(amount_ex_tax) from staging.stg_leap_invoices").fetchone()[0])
    rows.append(("LEAP invoices ex GST = app revenue ledger", float(inv["ex_gst"].sum()), leap_rev, leap_rev - float(inv["ex_gst"].sum()),
                 abs(leap_rev - float(inv["ex_gst"].sum())) <= tol))
    trust_app = float(M["trust"].iloc[-1].sum())
    trust_leap = float(con.execute("select sum(balance) from staging.stg_leap_trust").fetchone()[0])
    rows.append(("LEAP trust balances = app trust ledger", trust_app, trust_leap, trust_leap - trust_app, abs(trust_leap - trust_app) <= 0.01 * 7))
    act_app = float(M["matters"]["status"].isin(["Open", "On Hold"]).sum())
    act_leap = float(con.execute("select count(*) from staging.stg_leap_matters where status in ('Open', 'On Hold')").fetchone()[0])
    rows.append(("LEAP active matters = app active matters", act_app, act_leap, act_leap - act_app, act_leap == act_app))
    return pd.DataFrame(rows, columns=["check", "app", "pipeline", "difference", "passed"])


def run(con=None, verbose: bool = True, write: bool = True) -> tuple[pd.DataFrame, pd.DataFrame]:
    if con is None:
        import duckdb
        con = duckdb.connect(str(ROOT / "law_firm.duckdb"))
    build_layers(con)
    checks = pd.DataFrame([(name, int(con.execute(sql).fetchone()[0])) for name, sql in CHECKS.items()], columns=["check", "failures"])
    checks["passed"] = checks["failures"] == 0
    rec = reconcile(con, build_model())
    if write:
        SNAP.mkdir(exist_ok=True)
        for name in ("revenue_monthly", "aged_receivables", "collection_performance", "invoice_sync_recon", "migration_recon",
                     "trust_migration_recon", "disbursements_by_matter", "migration_exceptions"):
            con.execute(f"select * from marts.{name} order by all").df().to_csv(SNAP / f"{name}.csv", index=False)
        con.execute("select * from raw.load_audit order by loaded_at, resource").df().to_csv(SNAP / "load_audit.csv", index=False)
        checks.to_csv(SNAP / "quality_checks.csv", index=False)
        rec.to_csv(SNAP / "reconciliation.csv", index=False)
        _write_doc(checks, rec)
    exceptions = con.execute("select * from marts.migration_exceptions order by kind, reference").df()
    if write:
        _append_findings(exceptions)
    if verbose:
        print(f"INFO  triConvey migration dry run: {len(exceptions)} finding(s) for the cut-over report")
        for r in checks.itertuples():
            print(f"{'PASS' if r.passed else 'FAIL'}  {r.check}" + ("" if r.passed else f"  ({r.failures})"))
        for r in rec.itertuples():
            print(f"{'PASS' if r.passed else 'FAIL'}  reconcile: {r.check}")
    return checks, rec


def _fmt(v):
    return f"{round(v, 2) + 0.0:,.2f}" if isinstance(v, float) else str(v)


def _write_doc(checks: pd.DataFrame, rec: pd.DataFrame) -> None:
    lines = ["# Pipeline data quality (MYOB, LEAP, triConvey, InfoTrack, PEXA -> warehouse)", "",
             "Generated by `python -m integration.quality` from the simulated MYOB export. Do not edit by hand.", "",
             "## Accounting integrity", "", "| Check | Failures | Result |", "|---|---:|---|"]
    lines += [f"| {r.check} | {r.failures} | {'PASS' if r.passed else 'FAIL'} |" for r in checks.itertuples()]
    lines += ["", "## Reconciliation to the dashboard", "",
              "Pipeline marts compared with what the app computes from `core.model` (tolerance: cent rounding per invoice).", "",
              "| Check | App | Pipeline | Difference | Result |", "|---|---:|---:|---:|---|"]
    lines += [f"| {r.check} | {_fmt(r.app)} | {_fmt(r.pipeline)} | {_fmt(r.difference)} | {'PASS' if r.passed else 'FAIL'} |" for r in rec.itertuples()]
    DOC.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _append_findings(exc: pd.DataFrame) -> None:
    lines = ["", "## Findings: triConvey migration dry run", "",
             "Not failures of the pipeline: these are what the reconciliation found in the migration rehearsal and would go on the",
             "cut-over issues log. LEAP is the source of truth; triConvey must match it before go-live.", "",
             "| Kind | Reference | Client | Finding | Amount |", "|---|---|---|---|---:|"]
    lines += [f"| {r.kind} | {r.reference} | {r.client_name} | {r.finding} | {'' if pd.isna(r.amount) else f'{float(r.amount):,.2f}'} |"
              for r in exc.itertuples()]
    with DOC.open("a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    c, r = run()
    sys.exit(0 if c["passed"].all() and r["passed"].all() else 1)
