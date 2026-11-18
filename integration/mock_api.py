"""Mock MYOB Business (AccountRight) API v2, serving integration/data/*.json.

    uvicorn integration.mock_api:app --port 8000

SIMULATED: not MYOB. It reproduces only what the pipeline relies on, so the extractor and the n8n workflow can be built and
tested without a MYOB developer account:
  * POST /oauth/token (form: grant_type, client_id, client_secret) -> bearer token, 20-minute life like MYOB
  * every data call needs Authorization: Bearer, x-myobapi-key and x-myobapi-version: v2
  * company-file scoped URLs  /accountright/{cf_uid}/{resource}
  * OData paging $top (max 1000) / $skip and the incremental filter  $filter=LastModified gt datetime'YYYY-MM-DDTHH:MM:SS'
  * response envelope {"Items": [...], "NextPageLink": ..., "Count": n}
  * POST /_simulate/activity: test helper (not MYOB) that settles some open invoices "today" to demo incremental loads
"""
from __future__ import annotations

import copy
import json
import re
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode

from fastapi import Depends, FastAPI, Form, Header, HTTPException, Query, Request

DATA_DIR = Path(__file__).resolve().parent / "data"
CLIENT_ID, CLIENT_SECRET = "mock-client-id", "mock-client-secret"
MAX_TOP, DEFAULT_TOP = 1000, 400
_FILTER_RE = re.compile(r"LastModified\s+gt\s+datetime'([^']+)'", re.I)


def _load(name: str) -> list[dict]:
    return json.loads((DATA_DIR / f"{name}.json").read_text(encoding="utf-8"))


def create_app() -> FastAPI:
    """App factory: each instance has its own copy of the data, so tests can mutate it safely."""
    app = FastAPI(title="Mock MYOB AccountRight API v2 (simulated)")
    company = _load("company_file")
    cf_uid = company[0]["Id"]
    datasets = {"GeneralLedger/Account": _load("accounts"), "Contact/Customer": _load("customers"),
                "Sale/Invoice/Service": _load("invoices"), "Sale/CustomerPayment": _load("customer_payments")}
    tokens: dict[str, datetime] = {}

    @app.post("/oauth/token")
    def token(grant_type: str = Form(...), client_id: str = Form(...), client_secret: str = Form(...)):
        if client_id != CLIENT_ID or client_secret != CLIENT_SECRET:
            raise HTTPException(401, "invalid_client")
        if grant_type not in {"client_credentials", "refresh_token", "authorization_code"}:
            raise HTTPException(400, "unsupported_grant_type")
        tok = secrets.token_urlsafe(24)
        tokens[tok] = datetime.utcnow() + timedelta(minutes=20)
        return {"access_token": tok, "token_type": "bearer", "expires_in": 1200, "refresh_token": secrets.token_urlsafe(24)}

    def auth(authorization: str = Header(None), x_myobapi_key: str = Header(None), x_myobapi_version: str = Header(None)):
        if not authorization or not authorization.lower().startswith("bearer "):
            raise HTTPException(401, "Missing bearer token")
        exp = tokens.get(authorization.split(" ", 1)[1])
        if exp is None or exp < datetime.utcnow():
            raise HTTPException(401, "Token invalid or expired")
        if x_myobapi_key != CLIENT_ID:
            raise HTTPException(403, "Invalid x-myobapi-key")
        if x_myobapi_version != "v2":
            raise HTTPException(400, "x-myobapi-version must be v2")

    @app.get("/accountright/")
    def company_files(_=Depends(auth)):
        return company

    @app.post("/_simulate/activity")
    def simulate(payments: int = 5):
        invoices, pays = datasets["Sale/Invoice/Service"], datasets["Sale/CustomerPayment"]
        sync = datetime.fromisoformat(company[0]["LastSyncDate"]) + timedelta(days=1)
        company[0]["LastSyncDate"] = sync.isoformat()
        bank = next(a for a in datasets["GeneralLedger/Account"] if a["DisplayID"] == "1-1110")
        settled = []
        for inv in [i for i in invoices if i["Status"] == "Open"][:payments]:
            amt = inv["BalanceDueAmount"]
            inv.update(BalanceDueAmount=0.0, Status="Closed", LastModified=sync.isoformat(), RowVersion=str(int(inv["RowVersion"]) + 1))
            pays.append({"UID": f"sim-{inv['UID']}", "Date": sync.isoformat(), "Customer": copy.deepcopy(inv["Customer"]),
                         "PayFrom": "Account", "Account": {"UID": bank["UID"], "DisplayID": "1-1110", "Name": bank["Name"]},
                         "PaymentMethod": "EFT", "AmountReceived": amt,
                         "Invoices": [{"UID": inv["UID"], "Number": inv["Number"], "AmountApplied": amt, "Type": "Invoice"}],
                         "LastModified": sync.isoformat(), "RowVersion": "1"})
            settled.append(inv["Number"])
        return {"settled_invoices": settled, "sync_date": sync.isoformat()}

    @app.get("/accountright/{cf}/{resource:path}")
    def list_resource(cf: str, resource: str, request: Request, top: int = Query(DEFAULT_TOP, alias="$top"),
                      skip: int = Query(0, alias="$skip"), odata_filter: str | None = Query(None, alias="$filter"), _=Depends(auth)):
        if cf != cf_uid:
            raise HTTPException(404, "Company file not found")
        rows = datasets.get(resource.strip("/"))
        if rows is None:
            raise HTTPException(404, f"Unknown resource {resource}")
        if not 1 <= top <= MAX_TOP:
            raise HTTPException(400, f"$top must be between 1 and {MAX_TOP}")
        if odata_filter:
            m = _FILTER_RE.search(odata_filter)
            if not m:
                raise HTTPException(400, "Only LastModified gt datetime'...' is supported by the mock")
            since = datetime.fromisoformat(m.group(1))
            rows = [r for r in rows if datetime.fromisoformat(r["LastModified"]) > since]
        page = rows[skip: skip + top]
        nxt = None
        if skip + top < len(rows):
            params = {**dict(request.query_params), "$skip": str(skip + top), "$top": str(top)}
            nxt = f"{str(request.base_url).rstrip('/')}{request.url.path}?{urlencode(params)}"
        return {"Items": page, "NextPageLink": nxt, "Count": len(rows)}

    return app


app = create_app()
