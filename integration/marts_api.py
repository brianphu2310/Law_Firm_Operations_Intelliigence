"""Marts JSON API: the finance marts over HTTP, for Excel Power Query (Web.Contents) or any other tool.

    uvicorn integration.marts_api:app --port 8001

  GET /marts                       -> available marts
  GET /marts/{name}?limit&offset   -> {"mart", "count", "rows": [...]}   (name is whitelisted: no SQL from the URL)
  GET /health                      -> last load batch and whether every resource loaded OK
Set MARTS_API_KEY to require an x-api-key header.
"""
from __future__ import annotations

import os
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Query

DB = Path(os.getenv("MARTS_DB", Path(__file__).resolve().parent / "law_firm.duckdb"))
MARTS = ["revenue_monthly", "aged_receivables", "collection_performance"]
app = FastAPI(title="Example Legal finance marts (simulated data)")


def _q(sql, params=None):
    import duckdb
    con = duckdb.connect(str(DB), read_only=True)
    try:
        cur = con.execute(sql, params or [])
        cols = [d[0] for d in cur.description]
        clean = lambda v: float(v) if isinstance(v, Decimal) else v.isoformat() if isinstance(v, (date, datetime)) else v
        return [{c: clean(v) for c, v in zip(cols, r)} for r in cur.fetchall()]
    finally:
        con.close()


def _auth(key):
    if os.getenv("MARTS_API_KEY") and key != os.getenv("MARTS_API_KEY"):
        raise HTTPException(401, "Invalid or missing x-api-key")


@app.get("/marts")
def list_marts(x_api_key: str | None = Header(None)):
    _auth(x_api_key)
    return {"marts": MARTS}


@app.get("/marts/{name}")
def get_mart(name: str, limit: int = Query(5000, ge=1, le=50000), offset: int = Query(0, ge=0), x_api_key: str | None = Header(None)):
    _auth(x_api_key)
    if name not in MARTS:
        raise HTTPException(404, f"Unknown mart '{name}'. Available: {MARTS}")
    total = _q(f"select count(*) as n from marts.{name}")[0]["n"]
    return {"mart": name, "count": total, "limit": limit, "offset": offset,
            "rows": _q(f"select * from marts.{name} order by all limit ? offset ?", [limit, offset])}


@app.get("/health")
def health():
    last = _q("""select batch_id, max(loaded_at) as loaded_at, count(*) filter (where status <> 'OK') as failed
                 from raw.load_audit group by 1 order by 2 desc limit 1""")
    return {"status": "ok" if last and last[0]["failed"] == 0 else "degraded", "last_load": last[0] if last else None}
