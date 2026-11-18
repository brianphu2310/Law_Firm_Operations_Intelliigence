"""Mock MYOB Business (AccountRight) API v2, serving integration/data/*.json.

    uvicorn integration.mock_api:app --port 8000

SIMULATED: not MYOB. It reproduces only what the pipeline relies on, so the extractor and the n8n workflow can be built and
tested without a MYOB developer account:
  * OAuth 2.0 client credentials with RS256 JWTs (integration/auth.py): a built-in issuer for offline runs and CI
    (POST /oauth/token, GET /.well-known/jwks.json), or Auth0 with AUTH_MODE=auth0
  * every data call needs a valid Bearer JWT with the resource's scope, x-myobapi-key equal to the token's client,
    and x-myobapi-version: v2
  * company-file scoped URLs  /accountright/{cf_uid}/{resource}
  * OData paging $top (max 1000) / $skip and the incremental filter  $filter=LastModified gt datetime'YYYY-MM-DDTHH:MM:SS'
  * response envelope {"Items": [...], "NextPageLink": ..., "Count": n}
  * POST /_simulate/activity: test helper (not MYOB) that settles some open invoices "today" to demo incremental loads
"""
from __future__ import annotations

import base64
import copy
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode

from fastapi import FastAPI, Form, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from integration import auth as A

DATA_DIR = Path(__file__).resolve().parent / "data"
CLIENT_ID, CLIENT_SECRET = "mock-client-id", "mock-client-secret"
MAX_TOP, DEFAULT_TOP = 1000, 400
_FILTER_RE = re.compile(r"LastModified\s+gt\s+datetime'([^']+)'", re.I)


def _load(name: str) -> list[dict]:
    return json.loads((DATA_DIR / f"{name}.json").read_text(encoding="utf-8"))


def create_app(auth_config: A.AuthConfig | None = None, jwks_fetch=None) -> FastAPI:
    """App factory: each instance has its own copy of the data and its own auth wiring, so tests can mutate either safely."""
    app = FastAPI(title="Mock MYOB AccountRight API v2 (simulated)")
    cfg, verifier, issuer = A.build(auth_config, jwks_fetch)
    app.state.auth_config, app.state.issuer = cfg, issuer

    @app.exception_handler(A.AuthError)
    def _auth_error(_, exc: A.AuthError):
        return JSONResponse({"error": exc.error, "error_description": exc.description}, status_code=exc.status,
                            headers={"WWW-Authenticate": exc.www_authenticate})

    company = _load("company_file")
    cf_uid = company[0]["Id"]
    datasets = {"GeneralLedger/Account": _load("accounts"), "Contact/Customer": _load("customers"),
                "Sale/Invoice/Service": _load("invoices"), "Sale/CustomerPayment": _load("customer_payments")}
    @app.post("/oauth/token")
    def token(grant_type: str = Form(...), client_id: str | None = Form(None), client_secret: str | None = Form(None),
              audience: str | None = Form(None), scope: str | None = Form(None), authorization: str | None = Header(None)):
        """client_credentials with client_secret_post (form fields) or client_secret_basic (HTTP Basic), like Auth0."""
        if issuer is None:
            raise HTTPException(404, "AUTH_MODE=auth0: request tokens from Auth0, not from this API")
        if grant_type != "client_credentials":
            raise A.AuthError(400, "unsupported_grant_type", "Only client_credentials is supported")
        if authorization and authorization.lower().startswith("basic "):
            try:
                client_id, client_secret = base64.b64decode(authorization.split(" ", 1)[1]).decode().split(":", 1)
            except Exception:
                raise A.AuthError(401, "invalid_client", "Malformed Basic credentials")
        if not client_id or not client_secret:
            raise A.AuthError(401, "invalid_client", "Client authentication required")
        return issuer.token_response(client_id, client_secret, audience, scope)

    @app.get("/.well-known/jwks.json")
    def jwks():
        if issuer is None:
            raise HTTPException(404, "AUTH_MODE=auth0: keys are published by Auth0")
        return issuer.jwks()

    def check(authorization, x_myobapi_key, x_myobapi_version, resource=""):
        claims = verifier.verify(authorization, x_myobapi_key, A.scope_for(resource))    # authenticate first: 401 before 400
        if x_myobapi_version != "v2":
            raise HTTPException(400, "x-myobapi-version must be v2")
        return claims

    @app.get("/accountright/")
    def company_files(authorization: str = Header(None), x_myobapi_key: str = Header(None), x_myobapi_version: str = Header(None)):
        check(authorization, x_myobapi_key, x_myobapi_version)
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
                      skip: int = Query(0, alias="$skip"), odata_filter: str | None = Query(None, alias="$filter"),
                      authorization: str = Header(None), x_myobapi_key: str = Header(None), x_myobapi_version: str = Header(None)):
        check(authorization, x_myobapi_key, x_myobapi_version, resource)
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
