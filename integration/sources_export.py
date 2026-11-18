"""Re-shape the app's simulated model into the JSON of four more systems a law firm runs alongside MYOB.

    python -m integration.sources_export        # writes integration/data/{leap,triconvey,infotrack,pexa}/*.json

ALL DATA IS SIMULATED, built from core.model (fixed seed), so every system reconciles back to the dashboard.

| System     | Role at the fictional firm                                | Shape of the mock                                               |
|------------|-----------------------------------------------------------|-----------------------------------------------------------------|
| LEAP       | Current practice management: matters, invoices, trust     | "LEAP-style": LEAP's API reference is gated behind developer     |
|            |                                                           | registration, so field names are illustrative                   |
| triConvey  | Smokeball-based platform the firm is evaluating; this is  | Follows Smokeball's public API docs (docs.smokeball.com):        |
|            | a migration DRY RUN of active matters and trust balances  | `value`/`offset`/`limit`/`size`/`next`, numeric status codes     |
| InfoTrack  | Search provider; every order carries the matter number    | "InfoTrack-style" orders with client reference = matter number   |
| PEXA       | Electronic settlement workspaces for property matters     | "PEXA-style" workspaces with subscriber reference = matter no.  |

The migration dry run contains three deliberate, realistic defects so the reconciliation has something to find (the same kinds
of issue that come up in real practice-management migrations):
  1. one active matter fails to migrate (contact failed validation in the import),
  2. one matter is imported twice (re-run of a failed batch),
  3. one client's trust balance is short by a receipt banked after the cut-over snapshot.
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path

import numpy as np
import pandas as pd

from core.model import build_model
from core.ref import AS_OF, ATTORNEYS

OUT = Path(__file__).resolve().parent / "data"
NS = uuid.UUID("0b8e3f52-7c1d-4a8e-9f60-1d2c3b4a5e6f")
CUTOVER = AS_OF                                         # dry-run snapshot taken at the model's sync date
ATT_NAME = {a["short"]: a["name"] for a in ATTORNEYS}

# deterministic defects in the triConvey dry run (picked by position so they never depend on randomness)
DEFECT_NOT_MIGRATED_IDX, DEFECT_DUPLICATED_IDX, DEFECT_TRUST_CLIENT_IDX = 7, 23, 2


def _uid(kind: str, key: str) -> str:
    return str(uuid.uuid5(NS, f"{kind}:{key}"))


def _iso(ts) -> str | None:
    return None if pd.isna(ts) else pd.Timestamp(ts).strftime("%Y-%m-%dT%H:%M:%S")


def _cents(x) -> float:
    return round(float(x) + 1e-9, 2)


def _invoice_matters(inv: pd.DataFrame, mt: pd.DataFrame) -> list[str]:
    """Link each ledger invoice to a matter of the same client and practice area that was open when it was issued."""
    out = []
    by_key = {k: g.sort_values("opened") for k, g in mt.groupby(["client", "area"])}
    by_client = {k: g.sort_values("opened") for k, g in mt.groupby("client")}
    for r in inv.itertuples(index=False):
        g = by_key.get((r.client, r.area))
        if g is None:
            g = by_client[r.client]
        live = g[(g["opened"] <= r.issue) & (g["closed"].isna() | (g["closed"] >= r.issue - pd.Timedelta(days=60)))]
        pool = live if len(live) else g
        out.append(pool.iloc[int(r.invoice[-4:]) % len(pool)]["id"])     # spread invoices across the eligible matters
    return out


def build_sources(model: dict | None = None) -> dict[str, dict[str, list[dict]]]:
    M = model if model is not None else build_model()
    mt, inv = M["matters"].copy(), M["inv"].copy()
    inv["matter_id"] = _invoice_matters(inv, mt)

    # ------------------------------------------------------------------------------------------------ LEAP
    leap_matters = [{
        "matterId": _uid("leap-matter", r.id), "matterNumber": r.id, "matterDescription": r.name,
        "clientName": r.client, "practiceArea": r.area, "responsibleStaff": ATT_NAME.get(r.attorney, r.attorney),
        "branch": r.branch, "status": r.status, "openedDate": _iso(r.opened), "closedDate": _iso(r.closed),
        "estimatedValue": _cents(r.est_value), "lastModified": _iso(r.closed if pd.notna(r.closed) else r.opened)}
        for r in mt.itertuples(index=False)]
    leap_invoices = []
    for r in inv.itertuples(index=False):
        sub = _cents(r.ex_gst); tax = _cents(sub * 0.10); total = _cents(sub + tax)
        paid = pd.notna(r.paid) and r.paid <= AS_OF
        leap_invoices.append({
            "invoiceId": _uid("leap-invoice", r.invoice), "invoiceNumber": r.invoice, "matterNumber": r.matter_id,
            "clientName": r.client, "issueDate": _iso(r.issue), "dueDate": _iso(r.due), "amountExTax": sub, "tax": tax,
            "total": total, "status": "Paid" if paid else "Outstanding", "lastModified": _iso(r.paid if paid else r.issue)})
    trust = M["trust"].iloc[-1]                                     # balances at the latest month (the reference balances)
    leap_trust = [{"ledgerId": _uid("leap-trust", c), "clientName": c, "balance": _cents(v), "asAt": _iso(CUTOVER),
                   "lastModified": _iso(CUTOVER)} for c, v in trust.items()]

    # ------------------------------------------------------------------------------------ triConvey (Smokeball-shaped)
    active = mt[mt["status"].isin(["Open", "On Hold"])].reset_index(drop=True)
    tc_matters = []
    for i, r in active.iterrows():
        if i == DEFECT_NOT_MIGRATED_IDX:
            continue                                                # defect 1: failed validation, not migrated
        copies = 2 if i == DEFECT_DUPLICATED_IDX else 1             # defect 2: imported twice
        for k in range(copies):
            tc_matters.append({
                "id": _uid("tc-matter", f"{r.id}#{k}"), "number": r.id, "title": r.name,
                "status": 0 if r.status == "Open" else 1,          # Smokeball-style numeric status: 0 Open, 1 Pending
                "clientName": r.client, "matterType": {"category": r.area},
                "personResponsible": {"name": ATT_NAME.get(r.attorney, r.attorney)},
                "externalSystemId": _uid("leap-matter", r.id),     # lineage back to the LEAP matter
                "openedDate": _iso(r.opened), "lastUpdated": _iso(CUTOVER + pd.Timedelta(minutes=5 * k))})
    short_client = trust.index[DEFECT_TRUST_CLIENT_IDX]
    receipts = M["trust_txns"]
    late = receipts[(receipts["client"] == short_client) & (receipts["type"] == "Deposit")]
    short_by = _cents(late["amount"].iloc[0]) if len(late) else 1000.0
    tc_trust = [{"id": _uid("tc-trust", c), "contactName": c,
                 "balance": _cents(v - short_by) if c == short_client else _cents(v),   # defect 3: late receipt missing
                 "asAt": _iso(CUTOVER), "lastUpdated": _iso(CUTOVER)} for c, v in trust.items()]

    # ------------------------------------------------------------------------------------------------ InfoTrack
    it = M["infotrack"].sort_values("date", kind="stable").reset_index(drop=True)
    infotrack = [{
        "orderId": 900000 + i, "dateOrdered": _iso(r.date), "clientReference": r.matter_id, "matterDescription": r.matter,
        "serviceName": r.search_type, "totalFeeExGst": _cents(r.cost), "gst": _cents(r.cost * 0.10),
        "status": r.status, "office": r.branch, "lastModified": _iso(r.date)} for i, r in enumerate(it.itertuples(index=False))]

    # ------------------------------------------------------------------------------------------------ PEXA
    prop = mt[mt["name"].str.contains("Asset Purchase|Lease Review", regex=True) & (mt["country"] == "Australia")]
    rng = np.random.default_rng(20250917)
    pexa = []
    for r in prop.itertuples(index=False):
        settle = r.opened + pd.Timedelta(days=int(rng.integers(35, 90)))
        status = "Settled" if settle <= AS_OF and r.status == "Closed" or settle <= AS_OF - pd.Timedelta(days=14) else "In Preparation"
        amount = _cents(round(r.est_value * float(rng.uniform(6, 14)), -3))   # property value, not the legal fee
        pexa.append({
            "workspaceId": f"PEXA{int(rng.integers(10**8, 10**9))}", "subscriberReference": r.id,
            "jurisdiction": "NSW", "role": "Purchaser" if "Purchase" in r.name else "Lessee",
            "settlementDate": _iso(settle), "status": status, "settlementAmount": amount,
            "pexaFee": 126.94 if amount < 1_000_000 else 183.37,               # illustrative fee schedule
            "lastUpdated": _iso(min(settle, AS_OF) if status == "Settled" else r.opened)})

    return {"leap": {"matters": leap_matters, "invoices": leap_invoices, "trust_balances": leap_trust},
            "triconvey": {"matters": tc_matters, "trust_balances": tc_trust},
            "infotrack": {"orders": infotrack},
            "pexa": {"workspaces": pexa}}


def expected_defects(model: dict | None = None) -> dict:
    """What the migration reconciliation must find (used by tests and the docs)."""
    M = model if model is not None else build_model()
    mt = M["matters"]
    active = mt[mt["status"].isin(["Open", "On Hold"])].reset_index(drop=True)
    return {"not_migrated": active.loc[DEFECT_NOT_MIGRATED_IDX, "id"], "duplicated": active.loc[DEFECT_DUPLICATED_IDX, "id"],
            "trust_short_client": M["trust"].columns[DEFECT_TRUST_CLIENT_IDX]}


def write_sources(out: Path = OUT) -> dict[str, int]:
    counts = {}
    for vendor, files in build_sources().items():
        (out / vendor).mkdir(parents=True, exist_ok=True)
        for name, rows in files.items():
            (out / vendor / f"{name}.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
            counts[f"{vendor}/{name}"] = len(rows)
    return counts


if __name__ == "__main__":
    for k, n in write_sources().items():
        print(f"{k:<26} {n:>5}")
