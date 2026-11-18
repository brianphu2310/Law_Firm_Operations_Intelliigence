"""Integration layer: MYOB export -> mock MYOB API -> extract/load -> staging/marts -> checks and reconciliation to the app.

Runs fully in memory (FastAPI TestClient + in-memory DuckDB), so no server or warehouse file is needed.
Needs the packages in requirements-pipeline.txt; skipped cleanly if they are not installed.
"""
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

duckdb = pytest.importorskip("duckdb")
pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient  # noqa: E402

from integration import extract_load as el  # noqa: E402
from integration import quality  # noqa: E402
from integration.mock_api import CLIENT_ID, create_app  # noqa: E402
from integration.myob_export import build_export  # noqa: E402

DATA = ROOT / "integration" / "data"
N8N = ROOT / "integration" / "n8n"


class MemoryWarehouse(el.DuckDBWarehouse):
    def __init__(self):
        self.con = duckdb.connect(":memory:")
        self.con.execute((el.ROOT / "sql" / "duckdb" / "00_raw.sql").read_text())


@pytest.fixture()
def api():
    return TestClient(create_app())


def _client(api):
    return el.MyobClient(session=api, base_url="http://testserver", token_url="http://testserver/oauth/token")


def _token(api):
    return api.post("/oauth/token", data={"grant_type": "client_credentials", "client_id": CLIENT_ID,
                                          "client_secret": "mock-client-secret"}).json()["access_token"]


# ------------------------------------------------------------------ export --
def test_committed_export_matches_the_model():
    """integration/data/*.json must be regenerated whenever core.model changes (python -m integration.myob_export)."""
    fresh = build_export()
    for name, rows in fresh.items():
        assert json.loads((DATA / f"{name}.json").read_text(encoding="utf-8")) == rows, name


def test_export_follows_bookkeeping_rules():
    from decimal import ROUND_HALF_UP, Decimal
    cents = lambda x: float(Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))    # GST rounds half-up, not banker's
    d = build_export()
    for i in d["invoices"]:
        assert cents(Decimal(str(i["Subtotal"])) * Decimal("0.1")) == i["TotalTax"], i["Number"]
        assert cents(Decimal(str(i["Subtotal"])) + Decimal(str(i["TotalTax"]))) == i["TotalAmount"]
        assert (i["Status"] == "Closed") == (i["BalanceDueAmount"] == 0)
        assert i["Lines"][0]["Total"] == i["Subtotal"]
    paid = {p["Invoices"][0]["UID"]: p["AmountReceived"] for p in d["customer_payments"]}
    closed = {i["UID"]: i["TotalAmount"] for i in d["invoices"] if i["Status"] == "Closed"}
    assert paid == closed                                                   # one full payment per closed invoice


# ---------------------------------------------------------------- mock API --
def test_mock_api_requires_myob_auth_headers(api):
    assert api.get("/accountright/").status_code == 401
    tok = _token(api)
    assert api.get("/accountright/", headers={"Authorization": f"Bearer {tok}", "x-myobapi-version": "v2"}).status_code == 403
    ok = api.get("/accountright/", headers={"Authorization": f"Bearer {tok}", "x-myobapi-key": CLIENT_ID, "x-myobapi-version": "v2"})
    assert ok.status_code == 200 and ok.json()[0]["LastSyncDate"].startswith("2025-09-17")


def test_mock_api_pages_and_filters(api):
    tok = _token(api)
    h = {"Authorization": f"Bearer {tok}", "x-myobapi-key": CLIENT_ID, "x-myobapi-version": "v2"}
    cf = api.get("/accountright/", headers=h).json()[0]["Id"]
    first = api.get(f"/accountright/{cf}/Sale/Invoice/Service", headers=h, params={"$top": 100}).json()
    assert len(first["Items"]) == 100 and first["Count"] == 472 and "%24skip=100" in first["NextPageLink"]
    recent = api.get(f"/accountright/{cf}/Sale/Invoice/Service", headers=h,
                     params={"$filter": "LastModified gt datetime'2025-09-01T00:00:00'"}).json()
    assert 0 < recent["Count"] < 472
    assert all(i["LastModified"] > "2025-09-01T00:00:00" for i in recent["Items"])


# -------------------------------------------------------------- end to end --
def test_full_load_passes_every_check_and_reconciles_to_the_app(api):
    wh = MemoryWarehouse()
    res = el.run(wh, _client(api), verbose=False)
    assert [r["status"] for r in res] == ["OK"] * 4
    assert {r["resource"]: r["loaded_count"] for r in res}["Sale/Invoice/Service"] == 472
    checks, rec = quality.run(wh.con, verbose=False, write=False)
    assert checks["passed"].all(), checks[~checks["passed"]]
    assert rec["passed"].all(), rec[~rec["passed"]]


def test_incremental_load_only_pulls_changes_and_staging_deduplicates(api):
    wh, client = MemoryWarehouse(), _client(api)
    el.run(wh, client, verbose=False)
    nothing_new = el.run(wh, client, verbose=False)
    assert all(r["loaded_count"] == 0 and r["status"] == "OK" for r in nothing_new)
    settled = api.post("/_simulate/activity", params={"payments": 3}).json()["settled_invoices"]
    third = {r["resource"]: r["loaded_count"] for r in el.run(wh, client, verbose=False)}
    assert third["Sale/Invoice/Service"] == len(settled) == 3 and third["Sale/CustomerPayment"] == 3
    quality.build_layers(wh.con)
    assert wh.con.execute("select count(*), count(distinct invoice_uid) from staging.stg_invoices").fetchone() == (472, 472)
    closed = wh.con.execute("select count(*) from staging.stg_invoices where status = 'Closed' and invoice_number in "
                            f"({','.join(repr(s) for s in settled)})").fetchone()[0]
    assert closed == 3
    checks, _ = quality.run(wh.con, verbose=False, write=False)              # integrity still holds after the incremental load
    assert checks["passed"].all(), checks[~checks["passed"]]


def test_count_mismatch_is_recorded_not_loaded_silently(api):
    class ShortClient(el.MyobClient):
        def get_all(self, cf_uid, resource, since):
            items, count = super().get_all(cf_uid, resource, since)
            return items[:-1], count                                       # simulate a dropped record
    wh = MemoryWarehouse()
    res = el.run(wh, ShortClient(session=api, base_url="http://testserver", token_url="http://testserver/oauth/token"), verbose=False)
    assert all(r["status"] == "COUNT_MISMATCH" for r in res)
    assert el.DuckDBWarehouse.watermark(wh, "Sale/Invoice/Service") is None  # a failed load never advances the watermark


# ------------------------------------------------------ committed artefacts --
def test_committed_snapshot_is_complete_and_green():
    import pandas as pd
    snap = ROOT / "integration" / "snapshot"
    for name in ("revenue_monthly", "aged_receivables", "collection_performance", "load_audit", "quality_checks", "reconciliation"):
        assert (snap / f"{name}.csv").exists(), name
    assert pd.read_csv(snap / "quality_checks.csv")["passed"].all()
    assert pd.read_csv(snap / "reconciliation.csv")["passed"].all()


def test_n8n_workflows_are_wired_correctly():
    for f in ("myob_to_snowflake_local.json", "myob_to_snowflake_cloud.json"):
        wf = json.loads((N8N / f).read_text(encoding="utf-8"))
        names = {n["name"] for n in wf["nodes"]}
        assert {"Daily 6am", "Extract from MYOB", "Promote to RAW", "Insert Audit", "Fail If Mismatch"} <= names
        for src, out in wf["connections"].items():
            assert src in names
            for branch in out["main"]:
                assert all(c["node"] in names for c in branch)
        assert not any("mock-client-secret" in json.dumps(n.get("credentials", {})) for n in wf["nodes"])


def test_snowflake_sql_parses():
    sqlglot = pytest.importorskip("sqlglot")
    for f in sorted((ROOT / "integration" / "sql" / "snowflake").glob("*.sql")):
        for stmt in f.read_text(encoding="utf-8").split(";"):
            body = "\n".join(l for l in stmt.splitlines() if not l.strip().startswith("--")).strip()
            if body:
                sqlglot.parse_one(body, read="snowflake")


def test_excel_pack_has_power_query_tables():
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.load_workbook(ROOT / "integration" / "excel" / "Debtors_Revenue_Pack.xlsx")
    tables = {t for ws in wb.worksheets for t in ws.tables}
    assert {"tblAged", "tblRevenue", "tblCollections"} <= tables
    assert "Power Query" in wb.sheetnames
    for f in ("01_marts_from_json_api.pq", "02_myob_api_direct.pq", "03_marts_from_snowflake.pq"):
        assert (ROOT / "integration" / "powerquery" / f).exists()


def test_secrets_are_never_committed():
    gi = (ROOT / ".gitignore").read_text()
    assert ".env" in gi and "law_firm.duckdb" in gi
    assert not (ROOT / ".env").exists() or os.environ.get("CI") is None
