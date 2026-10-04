"""Tests for the dimensional warehouse (ETL, schema constraints, data-quality suite). Pure Python, no Streamlit UI."""
import hashlib
import os
import sqlite3
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.model import build_model
from core.ref import AS_OF
from warehouse import build as W
from warehouse import quality as Q

M = build_model()


@pytest.fixture(scope="module")
def con():
    c = W.build_warehouse(":memory:", model=M)
    yield c
    c.close()


def fresh():
    return W.build_warehouse(":memory:", model=M)


def count(c, table):
    return c.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def unconstrain(c, table):
    """Rebuild `table` as a plain CTAS copy (no PK/UNIQUE/NOT NULL/CHECK) so a fault can be injected for the DQ suite to catch."""
    c.execute("PRAGMA foreign_keys = OFF")
    c.execute(f"CREATE TABLE _copy AS SELECT * FROM {table}")
    c.execute(f"DROP TABLE {table}")
    c.execute(f"ALTER TABLE _copy RENAME TO {table}")


# --------------------------------------------------------------------- ETL --
def test_row_counts_match_the_simulator(con):
    assert count(con, "fact_invoice") == len(M["inv"])
    assert count(con, "dim_matter") == len(M["matters"]) == count(con, "fact_matter_position")
    assert count(con, "dim_client") == 23
    assert count(con, "fact_trust_txn") == len(M["trust_txns"])
    assert count(con, "fact_monthly_snapshot") == M["T_act"]
    assert count(con, "fact_monthly_pnl") == M["T_act"] + M["T"]          # Actual to as-of + Budget for the whole plan window


def test_audit_table_records_every_load(con):
    audit = dict(con.execute("SELECT table_name, row_count FROM etl_load_audit"))
    assert set(audit) == set(W.LOAD_ORDER)
    assert all(audit[t] == count(con, t) for t in audit)


def test_meta_labels_data_as_simulated(con):
    meta = dict(con.execute("SELECT meta_key, meta_value FROM etl_meta"))
    assert meta["data_origin"].startswith("SIMULATED")
    assert meta["as_of_date"] == AS_OF.strftime("%Y-%m-%d") and meta["currency"] == "AUD"


def test_surrogate_keys_are_dense_and_start_at_one(con):
    for table, key in [("dim_client", "client_key"), ("dim_matter", "matter_key"), ("fact_invoice", "invoice_key"),
                       ("dim_attorney", "attorney_key"), ("fact_trust_txn", "trust_txn_key")]:
        lo, hi, n = con.execute(f"SELECT MIN({key}), MAX({key}), COUNT(*) FROM {table}").fetchone()
        assert (lo, hi) == (1, n), table


def test_build_is_deterministic():
    def digest(c):
        h = hashlib.sha256()
        for t in W.LOAD_ORDER:
            for row in c.execute(f"SELECT * FROM {t} ORDER BY 1, 2"):
                h.update(repr(row).encode())
        return h.hexdigest()
    assert digest(fresh()) == digest(fresh())


def test_on_disk_build_creates_file_and_overwrites(tmp_path):
    p = tmp_path / "wh.db"
    W.build_warehouse(p, model=M).close()
    W.build_warehouse(p, model=M).close()
    assert count(sqlite3.connect(p), "fact_invoice") == len(M["inv"])


def test_current_month_is_prorated_and_full_months_are_not(con):
    rows = dict(con.execute("SELECT month_start_date_key, month_fraction_elapsed FROM fact_monthly_pnl WHERE scenario_key = 1"))
    assert rows[20250901] == pytest.approx(17 / 30)
    assert all(v == 1.0 for k, v in rows.items() if k != 20250901)
    # Budget for months after the as-of month is not pro-rated
    assert con.execute("SELECT MIN(month_fraction_elapsed) FROM fact_monthly_pnl WHERE scenario_key = 2 AND month_start_date_key > 20250901").fetchone()[0] == 1.0


def test_salary_allocation_conserves_cost(con):
    a = con.execute("SELECT SUM(salary_cost) FROM fact_attorney_month").fetchone()[0]
    b = con.execute("SELECT SUM(allocated_salary_cost) FROM fact_time_by_area").fetchone()[0]
    assert a == pytest.approx(b)


def test_transform_flags_and_nullable_dates():
    T = W.transform(M)
    inv = T["fact_invoice"]
    assert (inv["is_paid"] == inv["paid_date_key"].notna().astype(int)).all()
    assert inv.loc[inv["is_paid"] == 0, "days_to_pay"].isna().all()
    dm = T["dim_matter"]
    assert (dm["closed_date_key"].notna() == (dm["status"] == "Closed")).all()


# ---------------------------------------------------------------- dim_date --
def test_dim_date_is_contiguous_and_has_australian_fy(con):
    n, span = con.execute("SELECT COUNT(*), julianday(MAX(full_date)) - julianday(MIN(full_date)) + 1 FROM dim_date").fetchone()
    assert n == span
    assert con.execute("SELECT fy_label, fy_quarter, day_name FROM dim_date WHERE full_date = '2025-07-01'").fetchone() == ("FY26", 1, "Tuesday")
    assert con.execute("SELECT fy_label, fy_quarter FROM dim_date WHERE full_date = '2026-06-30'").fetchone() == ("FY26", 4)
    assert con.execute("SELECT is_weekend FROM dim_date WHERE full_date = '2025-09-13'").fetchone()[0] == 1


def test_no_foreign_key_violations(con):
    assert con.execute("PRAGMA foreign_key_check").fetchall() == []


# --------------------------------------------------------- schema constraints --
def test_foreign_keys_are_enforced(con):
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("INSERT INTO fact_trust_txn VALUES (99999, 9999, 20250101, 'Deposit', 10)")
    con.rollback()


def test_check_constraints_reject_bad_values(con):
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("UPDATE fact_invoice SET is_paid = 2 WHERE invoice_key = 1")
    con.rollback()
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("UPDATE fact_trust_txn SET amount = 5 WHERE txn_type = 'Disbursement' AND trust_txn_key = (SELECT MIN(trust_txn_key) FROM fact_trust_txn WHERE txn_type = 'Disbursement')")
    con.rollback()


def test_unique_business_keys(con):
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("INSERT INTO dim_scenario VALUES (9, 'Actual')")
    con.rollback()


def test_indexes_exist_and_are_used(con):
    idx = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type = 'index'")}
    assert {"ix_invoice_client", "ix_invoice_issue", "ix_matter_status"} <= idx
    plan = " ".join(str(r) for r in con.execute("EXPLAIN QUERY PLAN SELECT * FROM fact_invoice WHERE client_key = 5"))
    assert "ix_invoice_client" in plan


# ------------------------------------------------------------ quality suite --
def test_dq_suite_passes_on_clean_warehouse(con):
    checks = Q.run_checks(con, M)
    failed = [c for c in checks if not c.passed]
    assert not failed, failed
    gated = [c for c in checks if not c.informational]
    assert {c.family for c in gated} == {"Completeness", "Uniqueness", "Referential integrity", "Validity", "Reconciliation"}
    assert len(gated) > 100
    assert any(c.informational for c in checks)


def _failures(c):
    return [x.name for x in Q.run_checks(c, M) if not x.passed]


def test_dq_detects_orphan_foreign_key():
    c = fresh()
    c.execute("PRAGMA foreign_keys = OFF")
    c.execute("UPDATE fact_invoice SET client_key = 9999 WHERE invoice_key = 1")
    assert any("orphans" in n or "foreign_key_check" in n for n in _failures(c))


def test_dq_detects_duplicate_business_key():
    c = fresh()
    unconstrain(c, "fact_invoice")
    c.execute("INSERT INTO fact_invoice SELECT * FROM fact_invoice WHERE invoice_key = 1")
    names = [x.name for x in Q.uniqueness(c) if not x.passed]
    assert any("invoice_number" in n for n in names) and any("duplicate invoices" in n for n in names)


def test_dq_detects_null_in_required_column():
    c = fresh()
    unconstrain(c, "dim_matter")
    c.execute("UPDATE dim_matter SET matter_name = NULL WHERE matter_key = 3")
    assert any("dim_matter.matter_name" in x.name for x in Q.completeness(c) if not x.passed)


def test_dq_detects_reconciliation_drift():
    c = fresh()
    c.execute("UPDATE fact_monthly_pnl SET fees = fees + 1000, revenue = revenue + 1000, operating_profit = operating_profit + 1000 "
              "WHERE scenario_key = 1 AND month_start_date_key = 20240701")
    assert any("Actual fees" in n for n in _failures(c))
    c = fresh()
    c.execute("UPDATE fact_invoice SET paid_date_key = NULL, is_paid = 0, days_to_pay = NULL WHERE invoice_key = (SELECT MIN(invoice_key) FROM fact_invoice WHERE is_paid = 1)")
    assert any("receivables" in n or "AR ageing" in n for n in _failures(c))


def test_dq_detects_business_rule_violation():
    c = fresh()
    c.execute("UPDATE fact_invoice SET gst_amount = gst_amount + 5, amount_total = amount_total + 5 WHERE invoice_key = 1")
    assert any("GST" in n for n in _failures(c))
    c = fresh()
    c.execute("UPDATE fact_trust_balance SET closing_balance = closing_balance + 500 WHERE rowid = 40")
    assert any("trust ledger continuity" in n for n in _failures(c))


def test_report_is_deterministic_and_committed_copy_is_current(con):
    md = Q.render_markdown(Q.run_checks(con, M))
    assert md == Q.render_markdown(Q.run_checks(con, M))
    assert "checks passed" in md and "FAIL" not in md and "Observations" in md
    committed = Q.REPORT_PATH.read_text().rstrip("\n")
    assert committed == md.rstrip("\n"), "docs/DATA_QUALITY.md is stale - run: python -m warehouse.quality"
