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
    assert [r["status"] for r in res] == ["OK"] * len(el.SOURCES)
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
    myob = [r for r in res if ":" not in r["resource"]]                    # ShortClient only shortens the MYOB resources
    assert len(myob) == 4 and all(r["status"] == "COUNT_MISMATCH" for r in myob)
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
        assert {"Daily 6am", "Extract from Sources", "Promote to RAW", "Insert Audit", "Fail If Mismatch"} <= names
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


# ------------------------------------------------------------- other systems --
def test_committed_vendor_exports_match_the_model():
    """integration/data/{leap,triconvey,infotrack,pexa} must be regenerated when core.model changes (python -m integration.sources_export)."""
    from integration.sources_export import build_sources
    for vendor, files in build_sources().items():
        for name, rows in files.items():
            assert json.loads((DATA / vendor / f"{name}.json").read_text(encoding="utf-8")) == rows, f"{vendor}/{name}"


@pytest.mark.parametrize("path,params,items,next_path", [
    ("/leap/v1/invoices", {"pageSize": 100}, "data", ("paging", "nextPage")),
    ("/smokeball/matters", {"Limit": 50}, "value", ("next", "href")),
    ("/infotrack/v1/orders", {"pageSize": 1000}, "orders", ("nextPageUrl",)),
    ("/trisearch/v1/orders", {"take": 50}, "results", ("continuation",)),
    ("/pexa/v1/workspaces", {"limit": 10}, "workspaces", ("links", "next")),
])
def test_each_vendor_api_pages_in_its_own_style(api, path, params, items, next_path):
    h = {"Authorization": f"Bearer {_token(api)}", "x-api-key": CLIENT_ID}
    body = api.get(path, headers=h, params=params).json()
    nxt = body
    for k in next_path:
        nxt = nxt[k]
    assert len(body[items]) > 0 and nxt and nxt.startswith("http://testserver/")


def test_loader_reads_every_source_and_api_counts_match(api):
    wh = MemoryWarehouse()
    res = {r["resource"]: r for r in el.run(wh, _client(api), verbose=False)}
    expected = {"leap:matters": 430, "leap:invoices": 457, "leap:disbursements": 215, "triconvey:matters": 149, "triconvey:invoices": 36,
                "triconvey:trust/balances": 7, "triconvey:trust/reconciliation": 1, "triconvey:disbursements": 126,
                "infotrack:orders": 5413, "trisearch:orders": 115, "pexa:workspaces": 24}
    for resource, n in expected.items():
        assert res[resource]["status"] == "OK" and res[resource]["loaded_count"] == n, resource


def _loaded(api):
    wh = MemoryWarehouse()
    el.run(wh, _client(api), verbose=False)
    quality.build_layers(wh.con)
    return lambda sql: wh.con.execute(sql).fetchall()


def test_cross_system_reconciliations_find_exactly_the_planted_cutover_defects(api):
    from integration.sources_export import expected_defects
    q, exp = _loaded(api), expected_defects()
    assert q("select result, count(*) from marts.invoice_sync_recon group by 1") == [("Matched", 472)]       # LEAP 457 + triConvey 15
    assert dict(q("select outcome, count(*) from marts.migration_recon group by 1")) == {"Migrated": 132, "Not migrated": 1, "Duplicated": 1}
    found = {(k, ref) for k, ref, *_ in q("select kind, reference from marts.migration_exceptions where kind <> 'Disbursement'")}
    assert found == {("Matter", exp["not_migrated"]), ("Matter", exp["duplicated"]), ("Matter type", exp["unmapped_type"]),
                     ("Invoice", "INV-1021"), ("Trust balance", exp["trust_short_client"]), ("Trust reconciliation", "r48 Aug 2025")}
    assert q("select fell_to_general from marts.matter_type_mapping_recon where practice_area = 'Advisory'") == [(12,)]
    assert [round(float(d), 2) for (d,) in q("select difference from marts.trust_migration_recon where result <> 'Matched'")] == [-exp["trust_short_by"]]


def test_august_trust_reconciliation_straddles_both_systems_and_has_a_deadline(api):
    q = _loaded(api)
    (due, as_at, s1, s2, d2), = q("select due_date, as_at, statement_1_bank, statement_2_ledgers, ledgers_vs_cash_book from marts.trust_r48_status")
    assert str(due) == "2025-09-19" and str(as_at) == "2025-09-17"       # 15 working days after 31 Aug; two working days left
    assert (s1, s2) == ("Balances", "Does not balance") and round(float(d2), 2) == -5799.21     # the bank agrees with the books; the keyed ledgers do not


def test_supplier_switch_findings_are_classified_by_cause(api):
    q = _loaded(api)
    got = {(r, c, s): n for r, c, s, n in q("""select result, coalesce(likely_cause, ''), supplier, count(*) from marts.supplier_disbursement_recon
                                               where result <> 'Matched' group by all""")}
    assert got == {("On supplier feed, not in ledger", "TriSearch charges at order: check the auto-disbursement setting", "TriSearch"): 18,
                   ("On supplier feed, not in ledger", "Ordered after LEAP froze: needs re-keying", "InfoTrack"): 2,
                   ("Duplicate in ledger", "Manual entry", "InfoTrack"): 1, ("Amount differs", "Manual entry", "InfoTrack"): 1}
    # a re-typed reference still matches the right matter, and the cut-over month shows both suppliers
    assert q("select count(*) from marts.supplier_disbursement_recon where likely_cause = 'Supplier reference typed differently' and result = 'Matched'")[0][0] == 2
    assert dict(q("select supplier, count(*) from marts.supplier_switch_summary where month = date '2025-09-01' group by 1")) == {"InfoTrack": 1, "TriSearch": 1}
    assert q("select go_live, final_collection from staging.stg_cutover") == [(__import__("datetime").date(2025, 9, 2), __import__("datetime").date(2025, 8, 29))]


def test_nothing_is_dated_across_the_freeze_in_the_wrong_system(api):
    q = _loaded(api)
    assert q("select count(*) from staging.stg_leap_matters where opened_date > date '2025-08-29'")[0][0] == 0
    assert q("select count(*) from staging.stg_trisearch_orders where ordered_date < date '2025-09-02'")[0][0] == 0
    assert q("select count(*) from staging.stg_leap_disbursements where disb_date > date '2025-08-29'")[0][0] == 0


def test_power_query_scripts_read_the_committed_github_files():
    pq = ROOT / "integration" / "powerquery" / "github"
    scripts = sorted(pq.glob("*.pq"))
    assert len(scripts) == 4
    for f in scripts:
        text = f.read_text(encoding="utf-8")
        assert "raw.githubusercontent.com/brianphu2310/Law_Firm_Operations_Intelliigence/main/integration/data/" in text
        for rel in __import__("re").findall(r'Get\("([\w/]+\.json)"\)', text):
            assert (DATA / rel).exists(), (f.name, rel)
        assert text.count("let") >= 1 and text.rstrip().split()[-1] in ("Typed", "Sorted")
