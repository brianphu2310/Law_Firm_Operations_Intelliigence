"""Extract from the MYOB API and load the RAW layer of the warehouse.

    python -m integration.extract_load [--full]

    MYOB_MODE=mock (default) -> mock API at MYOB_BASE_URL (default http://127.0.0.1:8000)
    MYOB_MODE=live           -> https://api.myob.com with MYOB_CLIENT_ID / MYOB_ACCESS_TOKEN from the environment
    WAREHOUSE=duckdb (default) -> integration/law_firm.duckdb     WAREHOUSE=snowflake -> SNOWFLAKE_* env vars

Design
  * RAW keeps the full JSON payload per record (Snowflake VARIANT / DuckDB JSON); flattening is done in SQL, so a new MYOB field
    never breaks the load and records can be re-modelled without calling the API again.
  * Incremental: each resource keeps a LastModified watermark; the next run asks only for records changed after it.
  * Every run writes raw.load_audit (API count vs rows loaded); a mismatch marks the resource failed instead of loading silently.
  * The company file's LastSyncDate is stored too: it is the "as at" date for receivables ageing.
"""
from __future__ import annotations

import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEFAULT_DB = ROOT / "law_firm.duckdb"
MODE = os.getenv("MYOB_MODE", "mock")
BASE_URL = os.getenv("MYOB_BASE_URL", "http://127.0.0.1:8000" if MODE == "mock" else "https://api.myob.com")
TOKEN_URL = os.getenv("MYOB_TOKEN_URL", f"{BASE_URL}/oauth/token" if MODE == "mock" else "https://secure.myob.com/oauth2/v1/authorize")
CLIENT_ID = os.getenv("MYOB_CLIENT_ID", "mock-client-id")
CLIENT_SECRET = os.getenv("MYOB_CLIENT_SECRET", "mock-client-secret")
PAGE_SIZE = 400

RESOURCES = {"myob_accounts": "GeneralLedger/Account", "myob_customers": "Contact/Customer",
             "myob_invoices": "Sale/Invoice/Service", "myob_customer_payments": "Sale/CustomerPayment"}


class MyobClient:
    """Minimal MYOB API client. `session` can be a requests.Session or FastAPI's TestClient (used by the tests)."""

    def __init__(self, session=None, base_url: str = BASE_URL, token_url: str = TOKEN_URL):
        if session is None:
            import requests
            session = requests.Session()
        self.s, self.base, self.token_url, self.token = session, base_url.rstrip("/"), token_url, None

    def authenticate(self) -> None:
        if MODE == "live" and os.getenv("MYOB_ACCESS_TOKEN"):        # live MYOB: authorization-code flow, token supplied via env
            self.token = os.environ["MYOB_ACCESS_TOKEN"]
            return
        r = self.s.post(self.token_url, data={"grant_type": "client_credentials", "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET})
        r.raise_for_status()
        self.token = r.json()["access_token"]

    def _get(self, url, params=None) -> dict:
        headers = {"Authorization": f"Bearer {self.token}", "x-myobapi-key": CLIENT_ID, "x-myobapi-version": "v2", "Accept": "application/json"}
        for attempt in range(4):                                     # back off on 429 / 5xx
            r = self.s.get(url, headers=headers, params=params)
            if r.status_code not in (429, 500, 502, 503, 504):
                break
            time.sleep(2 ** attempt)
        r.raise_for_status()
        return r.json()

    def company_file(self) -> dict:
        return self._get(f"{self.base}/accountright/")[0]

    def get_all(self, cf_uid: str, resource: str, since: str | None) -> tuple[list[dict], int]:
        url = f"{self.base}/accountright/{cf_uid}/{resource}"
        params = {"$top": PAGE_SIZE}
        if since:
            params["$filter"] = f"LastModified gt datetime'{since}'"
        items, count = [], None
        while url:
            body = self._get(url, params)
            items += body["Items"]
            count = body.get("Count", count)
            url, params = body.get("NextPageLink"), None              # the next link carries its own query string
        return items, (count if count is not None else len(items))


class DuckDBWarehouse:
    def __init__(self, path: str | Path = DEFAULT_DB):
        import duckdb
        self.con = duckdb.connect(str(path))
        self.con.execute((ROOT / "sql" / "duckdb" / "00_raw.sql").read_text())

    def watermark(self, resource):
        row = self.con.execute("select max(watermark) from raw.load_audit where resource = ? and status = 'OK'", [resource]).fetchone()
        return row[0] if row and row[0] else None

    def load(self, table, rows, batch_id, loaded_at):
        if rows:
            self.con.executemany(f"insert into raw.{table} values (?, ?, ?, ?, ?)",
                                 [(r["UID"], json.dumps(r), r["LastModified"], batch_id, loaded_at) for r in rows])

    def load_company(self, cf, batch_id, loaded_at):
        self.con.execute("insert into raw.myob_company_file values (?, ?, ?, ?, ?)",
                         [cf["Id"], cf["Name"], cf["LastSyncDate"], batch_id, loaded_at])

    def audit(self, **kw):
        self.con.execute("insert into raw.load_audit values (?, ?, ?, ?, ?, ?, ?)",
                         [kw["batch_id"], kw["resource"], kw["api_count"], kw["loaded_count"], kw["watermark"], kw["status"], kw["loaded_at"]])


class SnowflakeWarehouse(DuckDBWarehouse):
    """Same contract on Snowflake (pip install snowflake-connector-python). Payload goes in as VARIANT via PARSE_JSON."""

    def __init__(self):
        import snowflake.connector
        self.con = snowflake.connector.connect(
            account=os.environ["SNOWFLAKE_ACCOUNT"], user=os.environ["SNOWFLAKE_USER"], password=os.environ["SNOWFLAKE_PASSWORD"],
            warehouse=os.getenv("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH"), database=os.getenv("SNOWFLAKE_DATABASE", "LAW_FIRM"),
            role=os.getenv("SNOWFLAKE_ROLE"))

    def _x(self, sql, params=()):
        cur = self.con.cursor()
        cur.execute(sql, params)
        return cur

    def watermark(self, resource):
        row = self._x("select max(watermark) from raw.load_audit where resource = %s and status = 'OK'", (resource,)).fetchone()
        return row[0] if row and row[0] else None

    def load(self, table, rows, batch_id, loaded_at):
        for r in rows:
            self._x(f"insert into raw.{table} select %s, parse_json(%s), %s, %s, %s",
                    (r["UID"], json.dumps(r), r["LastModified"], batch_id, loaded_at))

    def load_company(self, cf, batch_id, loaded_at):
        self._x("insert into raw.myob_company_file values (%s, %s, %s, %s, %s)", (cf["Id"], cf["Name"], cf["LastSyncDate"], batch_id, loaded_at))

    def audit(self, **kw):
        self._x("insert into raw.load_audit values (%s, %s, %s, %s, %s, %s, %s)",
                (kw["batch_id"], kw["resource"], kw["api_count"], kw["loaded_count"], kw["watermark"], kw["status"], kw["loaded_at"]))


def run(warehouse=None, client: MyobClient | None = None, full_refresh: bool = False, verbose: bool = True) -> list[dict]:
    wh = warehouse or (SnowflakeWarehouse() if os.getenv("WAREHOUSE") == "snowflake" else DuckDBWarehouse())
    client = client or MyobClient()
    client.authenticate()
    batch_id = str(uuid.uuid4())
    loaded_at = datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")
    cf = client.company_file()
    wh.load_company(cf, batch_id, loaded_at)
    results = []
    for table, resource in RESOURCES.items():
        since = None if full_refresh else wh.watermark(resource)
        try:
            rows, api_count = client.get_all(cf["Id"], resource, since)
            wh.load(table, rows, batch_id, loaded_at)
            status = "OK" if api_count == len(rows) else "COUNT_MISMATCH"
            wm = max((r["LastModified"] for r in rows), default=since)
        except Exception as exc:                                     # one failing resource must not hide the others
            rows, api_count, status, wm = [], -1, f"ERROR: {exc}"[:200], since
        rec = dict(batch_id=batch_id, resource=resource, api_count=api_count, loaded_count=len(rows), watermark=wm, status=status, loaded_at=loaded_at)
        wh.audit(**rec)
        results.append(rec)
        if verbose:
            print(f"  {resource:<24} since={since or '-':<20} api={api_count:>5} loaded={len(rows):>5} {status}")
    return results


if __name__ == "__main__":
    res = run(full_refresh="--full" in sys.argv)
    sys.exit(1 if any(r["status"] != "OK" for r in res) else 0)
