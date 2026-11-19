"""Extract from the MYOB API and load the RAW layer of the warehouse.

    python -m integration.extract_load [--full]

    MYOB_MODE=mock (default) -> mock API at MYOB_BASE_URL (default http://127.0.0.1:8000)
    MYOB_MODE=live           -> https://api.myob.com with MYOB_CLIENT_ID / MYOB_ACCESS_TOKEN from the environment
    AUTH_MODE=auth0          -> client-credentials token from https://{AUTH0_DOMAIN}/oauth/token for AUTH_AUDIENCE
                                (MYOB_CLIENT_ID / MYOB_CLIENT_SECRET = the Auth0 M2M application; keep them in .env, never in git)
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
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEFAULT_DB = ROOT / "law_firm.duckdb"
MODE = os.getenv("MYOB_MODE", "mock")
BASE_URL = os.getenv("MYOB_BASE_URL", "http://127.0.0.1:8000" if MODE == "mock" else "https://api.myob.com")
AUTH_MODE = os.getenv("AUTH_MODE", "local").lower()
AUDIENCE = os.getenv("AUTH_AUDIENCE", "https://myob-mock.dagostino-demo")
if AUTH_MODE == "auth0":
    _default_token_url = f"https://{os.getenv('AUTH0_DOMAIN', '').removeprefix('https://').strip('/')}/oauth/token"
elif MODE == "mock":
    _default_token_url = f"{BASE_URL}/oauth/token"
else:
    _default_token_url = "https://secure.myob.com/oauth2/v1/authorize"
TOKEN_URL = os.getenv("MYOB_TOKEN_URL", _default_token_url)
CLIENT_ID = os.getenv("MYOB_CLIENT_ID", "mock-client-id")
CLIENT_SECRET = os.getenv("MYOB_CLIENT_SECRET", "mock-client-secret")
PAGE_SIZE = 400

@dataclass(frozen=True)
class Source:
    """One API resource: where it lives, how it pages, how it filters incrementally, and where it lands in RAW.
    Real vendor APIs all page differently; describing that as data keeps one loader (and one n8n Code node) for all of them."""
    resource: str                       # audit / watermark key
    table: str                          # raw.<table>
    path: str                           # may contain {cf} (MYOB company file)
    items: str                          # key holding the records
    next: str                           # dotted path to the next-page URL
    count: str                          # dotted path to the total count
    id_key: str
    updated: str                        # record field holding last-modified time
    since_param: str                    # incremental filter query parameter
    page_params: tuple = ()
    key_header: str | None = None       # API-key header tied to the OAuth client (MYOB, Smokeball)
    myob: bool = False


MYOB = dict(items="Items", next="NextPageLink", count="Count", id_key="UID", updated="LastModified", since_param="$filter",
            page_params=(("$top", PAGE_SIZE),), key_header="x-myobapi-key", myob=True)
SOURCES = [
    Source("GeneralLedger/Account", "myob_accounts", "/accountright/{cf}/GeneralLedger/Account", **MYOB),
    Source("Contact/Customer", "myob_customers", "/accountright/{cf}/Contact/Customer", **MYOB),
    Source("Sale/Invoice/Service", "myob_invoices", "/accountright/{cf}/Sale/Invoice/Service", **MYOB),
    Source("Sale/CustomerPayment", "myob_customer_payments", "/accountright/{cf}/Sale/CustomerPayment", **MYOB),
    *[Source(f"leap:{e}", f"leap_{e.replace('/', '_')}", f"/leap/v1/{e}", items="data", next="paging.nextPage",
             count="paging.totalRecords", id_key=k, updated="lastModified", since_param="updatedSince", page_params=(("pageSize", 200),))
      for e, k in (("matters", "matterId"), ("invoices", "invoiceId"), ("trust/balances", "ledgerId"), ("disbursements", "disbursementId"))],
    *[Source(f"triconvey:{e}", f"triconvey_{e.replace('/', '_')}", f"/smokeball/{e}", items="value", next="next.href", count="size",
             id_key="id", updated="lastUpdated", since_param="LastUpdated", page_params=(("Limit", 200),), key_header="x-api-key")
      for e in ("matters", "invoices", "trust/balances", "trust/reconciliation", "disbursements")],
    Source("infotrack:orders", "infotrack_orders", "/infotrack/v1/orders", items="orders", next="nextPageUrl", count="totalCount",
           id_key="orderId", updated="lastModified", since_param="modifiedSince", page_params=(("pageSize", 1000),)),
    Source("trisearch:orders", "trisearch_orders", "/trisearch/v1/orders", items="results", next="continuation", count="total",
           id_key="orderNumber", updated="updatedAt", since_param="updatedAfter", page_params=(("take", 500),)),
    Source("pexa:workspaces", "pexa_workspaces", "/pexa/v1/workspaces", items="workspaces", next="links.next", count="totalCount",
           id_key="workspaceId", updated="lastUpdated", since_param="updatedSince", page_params=(("limit", 100),)),
]
RESOURCES = {s.table: s.resource for s in SOURCES if s.myob}       # kept for backwards compatibility
BY_RESOURCE = {s.resource: s for s in SOURCES}


def _dig(d: dict, path: str):
    for part in path.split("."):
        d = d.get(part) if isinstance(d, dict) else None
    return d


_TOKEN_CACHE: dict[tuple[str, str, str], tuple[str, float]] = {}      # (token_url, client_id, audience) -> (token, expires_at)


class MyobClient:
    """Minimal MYOB API client. `session` can be a requests.Session or FastAPI's TestClient (used by the tests).

    Tokens are cached per (token URL, client, audience) until 60 s before expiry and shared across clients in the process, so
    a run asks the issuer for one token, not one per request (Auth0's free plan meters client-credentials tokens monthly).
    A 401 mid-run (token revoked or expired) triggers exactly one fresh token and retry.
    """

    def __init__(self, session=None, base_url: str = BASE_URL, token_url: str = TOKEN_URL, audience: str = AUDIENCE):
        if session is None:
            import requests
            session = requests.Session()
        self.s, self.base, self.token_url, self.audience, self.token = session, base_url.rstrip("/"), token_url, audience, None
        self.token_requests = 0

    def authenticate(self, force: bool = False) -> None:
        if MODE == "live" and os.getenv("MYOB_ACCESS_TOKEN"):        # live MYOB: authorization-code flow, token supplied via env
            self.token = os.environ["MYOB_ACCESS_TOKEN"]
            return
        key = (self.token_url, CLIENT_ID, self.audience)
        cached = _TOKEN_CACHE.get(key)
        if cached and not force and cached[1] - 60 > time.time():
            self.token = cached[0]
            return
        r = self.s.post(self.token_url, data={"grant_type": "client_credentials", "client_id": CLIENT_ID,
                                              "client_secret": CLIENT_SECRET, "audience": self.audience})
        r.raise_for_status()
        body = r.json()
        self.token_requests += 1
        self.token = body["access_token"]
        _TOKEN_CACHE[key] = (self.token, time.time() + int(body.get("expires_in", 300)))

    def _get(self, url, params=None, src: Source | None = None) -> dict:
        refreshed = False
        attempt = 0
        while True:
            headers = {"Authorization": f"Bearer {self.token}", "Accept": "application/json"}
            if src is None or src.myob:
                headers.update({"x-myobapi-key": CLIENT_ID, "x-myobapi-version": "v2"})
            elif src.key_header:
                headers[src.key_header] = CLIENT_ID
            r = self.s.get(url, headers=headers, params=params)
            if r.status_code == 401 and not refreshed:                # expired / revoked: one fresh token, then retry once
                self.authenticate(force=True)
                refreshed = True
                continue
            if r.status_code in (429, 500, 502, 503, 504) and attempt < 3:     # back off on rate limits / server errors
                time.sleep(2 ** attempt)
                attempt += 1
                continue
            break
        r.raise_for_status()
        return r.json()

    def company_file(self) -> dict:
        return self._get(f"{self.base}/accountright/")[0]

    def fetch(self, src: Source, since: str | None, cf_uid: str = "") -> tuple[list[dict], int]:
        """Follow the source's next-page links until the end; returns (records, total reported by the API)."""
        url = f"{self.base}{src.path.format(cf=cf_uid)}"
        params = dict(src.page_params)
        if since:
            params[src.since_param] = f"LastModified gt datetime'{since}'" if src.myob else since
        items, count = [], None
        while url:
            body = self._get(url, params, src)
            items += body[src.items]
            count = _dig(body, src.count) if _dig(body, src.count) is not None else count
            url, params = _dig(body, src.next), None                  # next links carry their own query string
        return items, (count if count is not None else len(items))

    def get_all(self, cf_uid: str, resource: str, since: str | None) -> tuple[list[dict], int]:
        return self.fetch(BY_RESOURCE[resource], since, cf_uid)


class DuckDBWarehouse:
    def __init__(self, path: str | Path = DEFAULT_DB):
        import duckdb
        self.con = duckdb.connect(str(path))
        self.con.execute((ROOT / "sql" / "duckdb" / "00_raw.sql").read_text())

    def watermark(self, resource):
        row = self.con.execute("select max(watermark) from raw.load_audit where resource = ? and status = 'OK'", [resource]).fetchone()
        return row[0] if row and row[0] else None

    def load(self, table, rows, batch_id, loaded_at, id_key="UID", updated="LastModified"):
        if rows:
            self.con.executemany(f"insert into raw.{table} values (?, ?, ?, ?, ?)",
                                 [(str(r[id_key]), json.dumps(r), r[updated], batch_id, loaded_at) for r in rows])

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
    for src in SOURCES:
        since = None if full_refresh else wh.watermark(src.resource)
        try:
            rows, api_count = (client.get_all(cf["Id"], src.resource, since) if src.myob else client.fetch(src, since))
            wh.load(src.table, rows, batch_id, loaded_at, src.id_key, src.updated)
            status = "OK" if api_count == len(rows) else "COUNT_MISMATCH"
            wm = max((r[src.updated] for r in rows if r[src.updated]), default=since)
        except Exception as exc:                                     # one failing resource must not hide the others
            rows, api_count, status, wm = [], -1, f"ERROR: {exc}"[:200], since
        rec = dict(batch_id=batch_id, resource=src.resource, api_count=api_count, loaded_count=len(rows), watermark=wm,
                   status=status, loaded_at=loaded_at)
        wh.audit(**rec)
        results.append(rec)
        if verbose:
            print(f"  {src.resource:<24} since={since or '-':<20} api={api_count:>5} loaded={len(rows):>5} {status}")
    return results


if __name__ == "__main__":
    res = run(full_refresh="--full" in sys.argv)
    sys.exit(1 if any(r["status"] != "OK" for r in res) else 0)
