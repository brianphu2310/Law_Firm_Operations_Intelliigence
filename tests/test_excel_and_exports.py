"""The CSV export (read by Snowflake and Power Query) and the Excel decision pack are deterministic and committed up to date."""
import sys
from pathlib import Path

import pytest
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from excel import build_pack
from warehouse import export as E
from warehouse.build import LOAD_ORDER, build_warehouse


@pytest.fixture(scope="module")
def con():
    c = build_warehouse(":memory:")
    yield c
    c.close()


def test_export_writes_every_table_and_matches_the_committed_copy(con, tmp_path):
    paths = E.export(con, tmp_path)
    assert [p.stem for p in paths] == LOAD_ORDER
    for p in paths:
        committed = E.OUT_DIR / p.name
        assert committed.exists(), p.name
        assert p.read_text() == committed.read_text(), f"{p.name} is stale - run: python -m warehouse.export"


def test_export_row_counts_match_the_warehouse(con):
    for t in LOAD_ORDER:
        lines = (E.OUT_DIR / f"{t}.csv").read_text().count("\n") - 1
        assert lines == con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0], t


def test_staffing_export_sums_to_branch_support(con):
    import csv
    rows = list(csv.DictReader((E.OUT_DIR / "fact_staffing.csv").open()))
    by_branch = {}
    for r in rows:
        by_branch[r["branch_key"]] = by_branch.get(r["branch_key"], 0) + int(r["headcount"])
    expected = dict(con.execute("SELECT CAST(branch_key AS TEXT), support_headcount FROM dim_branch").fetchall())
    assert by_branch == expected


def test_decision_pack_has_tables_and_formula_summary(tmp_path):
    out = build_pack.build(tmp_path / "pack.xlsx")
    wb = load_workbook(out)
    assert wb.sheetnames == ["Summary", "PnL", "Where_to_hire", "Staffing", "Marketing", "Receivables", "Power Query"]
    tables = {t for ws in wb.worksheets for t in ws.tables}
    assert tables == {"tblPnL", "tblHire", "tblStaffing", "tblMarketing", "tblAgeing"}
    formulas = [c.value for row in wb["Summary"].iter_rows() for c in row if isinstance(c.value, str) and c.value.startswith("=")]
    assert len(formulas) >= 12
    for f in formulas:
        assert any(s in f for s in ("SUMIFS", "INDEX", "MIN(", "COUNTIF", "SUM(", "B7-B8")), f


def test_committed_pack_exists():
    assert build_pack.OUT.exists()


def test_power_query_scripts_read_this_repository():
    pq = ROOT / "excel" / "powerquery"
    files = sorted(pq.glob("*.pq"))
    assert len(files) == 7
    base = (pq / "00_fnQueryResult.pq").read_text()
    assert "raw.githubusercontent.com/brianphu2310/law-firm-decision-support/main/" in base
    for f in files[1:]:
        text = f.read_text()
        assert "fnQueryResult(" in text
        for name in __import__("re").findall(r'fnQueryResult\("([^"]+)", "([^"]+)"\)', text):
            folder, stem = name
            assert (ROOT / folder / f"{stem}.csv").exists(), f"{f.name} reads a missing file {folder}/{stem}.csv"
