"""ETL: simulated model (core.model.build_model, fixed seed) -> SQLite star schema.

    python -m warehouse.build                 # writes ./warehouse.db (gitignored)
    python -m warehouse.build --db other.db

Pipeline stages (each a pure function so it can be unit-tested):
    extract()   -> raw pandas frames / arrays straight from the simulator (no cleaning)
    transform() -> conformed dimensions + facts with surrogate keys, flags and derived measures
    load()      -> DDL from schema.sql, then bulk insert in FK order with foreign keys enforced

All data is SIMULATED. Nothing is fetched from any external source.

Pro-rating: core.model stores monthly flows as "full-month equivalents" (the month containing AS_OF is scaled up by days
elapsed). The app re-weights by days when it aggregates. The warehouse stores the *observed-to-date* amount (full-month
equivalent x month_fraction_elapsed), so plain SUMs match the app for any period ending at the as-of date.
"""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

from core.model import COST_LINES, SEED, build_model
from core.ref import AREAS, AS_OF, ATTORNEYS, BRANCHES, CLIENTS, PLAN_END, START, TRUST_TARGET

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"
DEFAULT_DB = ROOT / "warehouse.db"

LOAD_ORDER = ["dim_date", "dim_branch", "dim_practice_area", "dim_scenario", "dim_attorney", "dim_client", "dim_matter",
              "fact_invoice", "fact_matter_position", "fact_attorney_month", "fact_time_by_area", "fact_monthly_pnl",
              "fact_monthly_snapshot", "fact_trust_balance", "fact_trust_txn"]
COST_COLUMN = {"payroll_fee": "payroll_fee_earners", "disb_cost": "disbursement_cost", "payroll_support": "payroll_support",
               "rent": "rent", "software": "software", "insurance": "insurance", "marketing": "marketing",
               "prof_fees": "professional_fees", "cards": "cards", "merchant": "merchant_fees", "commission": "commission",
               "bank_fees": "bank_fees", "other": "other_costs"}


# ------------------------------------------------------------------ helpers --
def date_key(s: pd.Series) -> pd.Series:
    """Timestamp -> yyyymmdd integer; NaT -> <NA> (nullable Int64)."""
    return (s.dt.year * 10000 + s.dt.month * 100 + s.dt.day).astype("Int64")


def build_dim_date(start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    """Calendar dimension covering whole years from `start` to `end` (Australian financial-year attributes)."""
    days = pd.date_range(pd.Timestamp(start.year, 1, 1), pd.Timestamp(end.year, 12, 31), freq="D")
    d = pd.DataFrame({"full_ts": days})
    d["date_key"] = date_key(d["full_ts"]).astype(int)
    d["full_date"] = d["full_ts"].dt.strftime("%Y-%m-%d")
    d["year"] = d["full_ts"].dt.year
    d["quarter"] = d["full_ts"].dt.quarter
    d["month"] = d["full_ts"].dt.month
    d["month_name"] = d["full_ts"].dt.strftime("%B")
    d["month_start_date"] = d["full_ts"].dt.strftime("%Y-%m-01")
    d["day_of_month"] = d["full_ts"].dt.day
    d["day_of_week"] = d["full_ts"].dt.dayofweek + 1
    d["day_name"] = d["full_ts"].dt.strftime("%A")
    d["is_weekend"] = (d["day_of_week"] >= 6).astype(int)
    d["is_month_end"] = d["full_ts"].dt.is_month_end.astype(int)
    d["fy_start_year"] = np.where(d["month"] >= 7, d["year"], d["year"] - 1)
    d["fy_label"] = "FY" + ((d["fy_start_year"] + 1) % 100).astype(str).str.zfill(2)
    d["fy_quarter"] = ((d["month"] - 7) % 12) // 3 + 1
    return d.drop(columns="full_ts")


def _days(a: pd.Series, b: pd.Series) -> pd.Series:
    return (b - a).dt.days.astype("Int64")


# ------------------------------------------------------------------ extract --
def extract(model: dict | None = None) -> dict:
    """Raw objects from the simulator. Uses the app's own fixed-seed generator, unchanged."""
    M = model if model is not None else build_model()
    return M


# ---------------------------------------------------------------- transform --
def transform(M: dict) -> dict[str, pd.DataFrame]:
    months, T_act, frac, wi = M["months"], M["T_act"], M["frac"], M["wi"]
    inv, mt, stock = M["inv"], M["matters"], M["stock"]
    T: dict[str, pd.DataFrame] = {}

    # --- dim_date spans every date in the data (matters opened 2022, invoices from 2023-04, plan to PLAN_END)
    trust_txn = M["trust_txns"]
    all_dates = pd.concat([inv["issue"], inv["due"], inv["paid"], mt["opened"], mt["closed"], trust_txn["date"], stock["date"],
                           pd.Series([pd.Timestamp(a["start"]) for a in ATTORNEYS]), pd.Series([START, AS_OF, PLAN_END]),
                           pd.Series(months)]).dropna()
    T["dim_date"] = build_dim_date(all_dates.min(), all_dates.max())

    # --- small dimensions
    T["dim_branch"] = pd.DataFrame([dict(branch_key=i + 1, branch_name=b["name"], council_area=b["council"], latitude=b["lat"],
                                         longitude=b["lon"], support_headcount=b["support"], base_monthly_rent=float(b["rent"]))
                                    for i, b in enumerate(BRANCHES)])
    branch_key = dict(zip(T["dim_branch"]["branch_name"], T["dim_branch"]["branch_key"]))
    T["dim_practice_area"] = pd.DataFrame({"practice_area_key": range(1, len(AREAS) + 1), "practice_area": AREAS})
    area_key = dict(zip(AREAS, T["dim_practice_area"]["practice_area_key"]))
    T["dim_scenario"] = pd.DataFrame({"scenario_key": [1, 2], "scenario_name": ["Actual", "Budget"]})
    scen_key = {"Actual": 1, "Budget": 2}

    T["dim_attorney"] = pd.DataFrame([
        dict(attorney_key=i + 1, attorney_short=a["short"], attorney_name=a["name"], role=a["role"], home_branch_key=branch_key[a["branch"]],
             start_date_key=int(pd.Timestamp(a["start"]).strftime("%Y%m%d")), target_hours_per_month=float(a["target"]),
             bill_rate=float(a["bill_rate"]), pay_rate=float(a["pay_rate"]), realisation_factor=float(a["real_factor"]))
        for i, a in enumerate(ATTORNEYS)])
    att_key = dict(zip(T["dim_attorney"]["attorney_short"], T["dim_attorney"]["attorney_key"]))

    cl = sorted(CLIENTS, key=lambda c: c["name"])
    T["dim_client"] = pd.DataFrame([
        dict(client_key=i + 1, client_name=c["name"], primary_practice_area_key=area_key[c["practice"]],
             relationship_attorney_key=att_key[c["attorney"]], client_since_year=int(c["since"]), country=c["country"],
             has_trust_account=int(c["name"] in TRUST_TARGET))
        for i, c in enumerate(cl)])
    client_key = dict(zip(T["dim_client"]["client_name"], T["dim_client"]["client_key"]))

    # --- dim_matter / fact_matter_position
    m = mt.sort_values("id", kind="stable").reset_index(drop=True)
    T["dim_matter"] = pd.DataFrame({
        "matter_key": np.arange(1, len(m) + 1), "matter_id": m["id"], "matter_name": m["name"],
        "client_key": m["client"].map(client_key), "practice_area_key": m["area"].map(area_key),
        "attorney_key": m["attorney"].map(att_key), "branch_key": m["branch"].map(branch_key), "country": m["country"],
        "status": m["status"], "opened_date_key": date_key(m["opened"]), "closed_date_key": date_key(m["closed"]),
        "is_named_matter": m["named"].astype(int)})
    T["fact_matter_position"] = pd.DataFrame({
        "matter_key": T["dim_matter"]["matter_key"], "as_of_date_key": int(AS_OF.strftime("%Y%m%d")),
        "estimated_value": m["est_value"], "billed_to_date": m["billed"], "wip_balance": m["wip"],
        "progress_ratio": m["progress"].astype(float), "days_open": m["days_open"]})

    # --- fact_invoice
    i = inv.sort_values("invoice", kind="stable").reset_index(drop=True)
    T["fact_invoice"] = pd.DataFrame({
        "invoice_key": np.arange(1, len(i) + 1), "invoice_number": i["invoice"], "client_key": i["client"].map(client_key),
        "practice_area_key": i["area"].map(area_key), "attorney_key": i["attorney"].map(att_key), "branch_key": i["branch"].map(branch_key),
        "issue_date_key": date_key(i["issue"]), "due_date_key": date_key(i["due"]), "paid_date_key": date_key(i["paid"]),
        "amount_ex_gst": i["ex_gst"], "gst_amount": i["gst"], "amount_total": i["total"],
        "days_to_pay": _days(i["issue"], i["paid"]), "is_paid": i["paid"].notna().astype(int)})

    # --- attorney-month and attorney-area-month facts (actual months only, pro-rated)
    f = np.where(np.arange(len(months)) == T_act - 1, frac, 1.0)
    H, V, F, act = M["H"], M["V_ak"], M["fees_ak"], M["active"]
    am, tba = [], []
    for ai, a in enumerate(ATTORNEYS):
        for t in range(T_act):
            if act[ai, t] == 0:
                continue
            mk = int(months[t].strftime("%Y%m%d"))
            hrs = H[ai, :, t]
            salary = a["target"] * a["pay_rate"] * wi[t] * f[t]
            am.append(dict(attorney_key=att_key[a["short"]], month_start_date_key=mk, month_fraction_elapsed=float(f[t]),
                           capacity_hours=float(a["target"] * f[t]), billable_hours=float(hrs.sum() * f[t]),
                           standard_value=float(V[ai, :, t].sum() * f[t]), fees_realised=float(F[ai, :, t].sum() * f[t]),
                           salary_cost=float(salary)))
            share = hrs / hrs.sum() if hrs.sum() > 0 else np.zeros(len(AREAS))
            for ki, k in enumerate(AREAS):
                tba.append(dict(attorney_key=att_key[a["short"]], practice_area_key=area_key[k], month_start_date_key=mk,
                                billable_hours=float(hrs[ki] * f[t]), standard_value=float(V[ai, ki, t] * f[t]),
                                fees_realised=float(F[ai, ki, t] * f[t]), allocated_salary_cost=float(salary * share[ki])))
    T["fact_attorney_month"] = pd.DataFrame(am)
    T["fact_time_by_area"] = pd.DataFrame(tba)

    # --- fact_monthly_pnl: Actual (to as-of) and Budget (whole plan window)
    rows = []
    for scen, frame, n in (("Actual", M["fin"], T_act), ("Budget", M["plan"], len(months))):
        for t in range(n):
            r = frame.iloc[t]
            d = dict(month_start_date_key=int(months[t].strftime("%Y%m%d")), scenario_key=scen_key[scen],
                     month_fraction_elapsed=float(f[t]), billable_hours=r["hours"] * f[t], capacity_hours=r["capacity"] * f[t],
                     standard_value=r["value_std"] * f[t], writeoff=r["writeoff"] * f[t], fees=r["fees"] * f[t],
                     disbursements_billed=r["disb_billed"] * f[t], revenue=r["revenue"] * f[t],
                     total_costs=r["total_costs"] * f[t], operating_profit=r["op_profit"] * f[t])
            for src, dst in COST_COLUMN.items():
                d[dst] = r[src] * f[t]
            rows.append(d)
    T["fact_monthly_pnl"] = pd.DataFrame(rows)

    # --- fact_monthly_snapshot (stock)
    st = stock.iloc[:T_act].reset_index().rename(columns={"index": "month_start"})
    T["fact_monthly_snapshot"] = pd.DataFrame({
        "month_start_date_key": date_key(st["month_start"]), "snapshot_date_key": date_key(st["date"]),
        "wip_balance": st["wip"], "cash_balance": st["cash"], "receivables_incl_gst": st["ar"], "trust_balance": st["trust"],
        "matters_active": st["matters_active"].astype(int)})

    # --- trust
    tb = M["trust"].stack().reset_index()
    tb.columns = ["month_start", "client", "closing_balance"]
    tb = tb.sort_values(["client", "month_start"], kind="stable")
    T["fact_trust_balance"] = pd.DataFrame({"client_key": tb["client"].map(client_key), "month_start_date_key": date_key(tb["month_start"]),
                                            "closing_balance": tb["closing_balance"]})
    tx = trust_txn.sort_values(["date", "client", "amount"], kind="stable").reset_index(drop=True)
    T["fact_trust_txn"] = pd.DataFrame({"trust_txn_key": np.arange(1, len(tx) + 1), "client_key": tx["client"].map(client_key),
                                        "txn_date_key": date_key(tx["date"]), "txn_type": tx["type"], "amount": tx["amount"]})
    return T


# --------------------------------------------------------------------- load --
def _py(v):
    if v is None or v is pd.NA or v is pd.NaT:
        return None
    if isinstance(v, float) and np.isnan(v):
        return None
    if isinstance(v, np.generic):
        return v.item()
    return v


def load(tables: dict[str, pd.DataFrame], db_path: str | Path = DEFAULT_DB, meta: dict | None = None) -> sqlite3.Connection:
    """Create a fresh database from schema.sql and bulk-load the tables. Returns an open connection."""
    db_path = str(db_path)
    if db_path != ":memory:":
        Path(db_path).unlink(missing_ok=True)
    con = sqlite3.connect(db_path)
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(SCHEMA_PATH.read_text())
    with con:
        for name in LOAD_ORDER:
            df = tables[name]
            cols = list(df.columns)
            rows = [tuple(_py(v) for v in r) for r in df.itertuples(index=False, name=None)]
            con.executemany(f"INSERT INTO {name} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})", rows)
            con.execute("INSERT INTO etl_load_audit VALUES (?, ?)", (name, len(rows)))
        meta = {"data_origin": "SIMULATED (core/model.py, fixed seed) - fictional firm, clients, matters and invoices",
                "seed": str(SEED), "as_of_date": AS_OF.strftime("%Y-%m-%d"), "history_start": START.strftime("%Y-%m-%d"),
                "plan_end": PLAN_END.strftime("%Y-%m-%d"), "currency": "AUD", **(meta or {})}
        con.executemany("INSERT INTO etl_meta VALUES (?, ?)", list(meta.items()))
    fk = con.execute("PRAGMA foreign_key_check").fetchall()
    if fk:
        raise RuntimeError(f"foreign key violations after load: {fk[:5]}")
    return con


def build_warehouse(db_path: str | Path = DEFAULT_DB, model: dict | None = None) -> sqlite3.Connection:
    return load(transform(extract(model)), db_path)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", default=str(DEFAULT_DB), help="output SQLite path (default: ./warehouse.db)")
    args = ap.parse_args(argv)
    con = build_warehouse(args.db)
    for name, n in con.execute("SELECT table_name, row_count FROM etl_load_audit"):
        print(f"{name:26s}{n:>8d}")
    con.close()
    print(f"warehouse written to {args.db}")


if __name__ == "__main__":
    main()
