"""Re-shape the app's simulated model into the JSON of the systems a law firm runs around MYOB, across ONE cut-over.

    python -m integration.sources_export        # writes integration/data/{leap,triconvey,infotrack,trisearch,pexa}/*.json

ALL DATA IS SIMULATED, built from core.model (fixed seed), so every system reconciles back to the dashboard. The story is the
transition period of a NSW law firm (dates in core/transition.py; what is sourced vs assumed in docs/TRANSITION.md):

| System     | Role at the fictional firm                                                                                       |
|------------|-------------------------------------------------------------------------------------------------------------------|
| LEAP       | Legacy practice management. FROZEN at the final data collection (Fri 29 Aug 2025): matters, invoices, trust       |
| triConvey  | Smokeball-based platform, live from Tue 2 Sep 2025: migrated matters + open invoices + hand-keyed trust opening   |
|            | balances, then native matters, invoices and disbursements. Follows Smokeball's public API docs shape              |
| InfoTrack  | Legacy search supplier, orders to 31 Aug, plus a few habit orders in September                                    |
| TriSearch  | New search supplier from go-live. Public API docs were not found: the response shape is illustrative              |
| PEXA       | Electronic settlement workspaces for property matters                                                             |

What gets planted so the reconciliations have real findings (each is a documented risk of a hard cut-over, see docs/TRANSITION.md):
  1. one active matter fails to migrate; 2. one matter is imported twice (re-run of a failed batch);
  3. every Advisory matter lands in the "General" matter type (unmapped type defaults to General);
  4. one migrated invoice loses its GST (tax-code mapping); 5. a trust receipt posted in LEAP after the Friday extract ran is
  missing from the hand-keyed opening balance (Global Trust Bank); 6. InfoTrack orders placed between final collection and go-live,
  and September stragglers, exist in neither ledger until re-keyed: two never are, one is keyed twice, one is keyed with GST in the
  ex-GST column; 7. TriSearch's "automatically create a disbursement" setting is off for two days, so those orders have no ledger line.
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path

import numpy as np
import pandas as pd

from core.model import build_model
from core.ref import AS_OF, ATTORNEYS
from core import transition as T

OUT = Path(__file__).resolve().parent / "data"
NS = uuid.UUID("0b8e3f52-7c1d-4a8e-9f60-1d2c3b4a5e6f")
ATT_NAME = {a["short"]: a["name"] for a in ATTORNEYS}

DEFECT_NOT_MIGRATED, DEFECT_DUPLICATED = "M-2024-0209", "M-2024-0277"      # matter numbers (open at the final collection)
DEFECT_UNMAPPED_TYPE = "Advisory"                                           # practice area with no matter-type mapping
DEFECT_GST_DROPPED_IDX = 3                                                  # position among the invoices open at cut-over
MANUAL_MISSING_IDX, MANUAL_DUPLICATE_IDX, MANUAL_AMOUNT_IDX = (2, 9), 5, 7  # positions among InfoTrack orders re-keyed after cut-over
REF_VARIANT_EVERY = 41                                                      # every n-th TriSearch order carries a re-typed matter reference


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


def _state(model: dict | None):
    """Everything both build_sources and expected_defects need, computed once from the model."""
    M = model if model is not None else build_model()
    mt, inv = M["matters"].copy(), M["inv"].copy()
    inv["matter_id"] = _invoice_matters(inv, mt)
    F = T.FINAL_COLLECTION
    # --- matters as LEAP knew them at the final collection
    leap_mt = mt[mt["opened"] <= F].copy()
    still_open = leap_mt["closed"].notna() & (leap_mt["closed"] > F)            # closed AFTER the freeze: LEAP still shows them open
    leap_mt.loc[still_open, "status"] = "Open"
    leap_mt["closed_at_final"] = leap_mt["closed"].where(~still_open)
    # --- trust ledgers by client, rolled back from the model's balance at AS_OF
    trust_now, txns = M["trust"].iloc[-1], M["trust_txns"]

    def trust_at(day: pd.Timestamp) -> pd.Series:
        after = txns[txns["date"] > day].groupby("client")["amount"].sum().reindex(trust_now.index).fillna(0.0)
        return (trust_now - after).round(2)
    return M, mt, inv, leap_mt, trust_at


def build_sources(model: dict | None = None) -> dict[str, dict[str, list[dict]]]:
    M, mt, inv, leap_mt, trust_at = _state(model)
    F, GO = T.FINAL_COLLECTION, T.GO_LIVE
    rng = np.random.default_rng(20250902)

    # ------------------------------------------------------------------------------------------------ LEAP (frozen)
    leap_matters = [{
        "matterId": _uid("leap-matter", r.id), "matterNumber": r.id, "matterDescription": r.name,
        "clientName": r.client, "practiceArea": r.area, "responsibleStaff": ATT_NAME.get(r.attorney, r.attorney),
        "branch": r.branch, "status": r.status, "openedDate": _iso(r.opened), "closedDate": _iso(r.closed_at_final),
        "estimatedValue": _cents(r.est_value), "lastModified": _iso(r.closed_at_final if pd.notna(r.closed_at_final) else r.opened)}
        for r in leap_mt.itertuples(index=False)]
    inv_leap = inv[inv["issue"] <= F]
    leap_invoices, open_at_cutover = [], []
    for r in inv_leap.itertuples(index=False):
        sub = _cents(r.ex_gst); tax = _cents(sub * 0.10); total = _cents(sub + tax)
        paid = pd.notna(r.paid) and r.paid <= F
        row = {"invoiceId": _uid("leap-invoice", r.invoice), "invoiceNumber": r.invoice, "matterNumber": r.matter_id,
               "clientName": r.client, "issueDate": _iso(r.issue), "dueDate": _iso(r.due), "amountExTax": sub, "tax": tax,
               "total": total, "status": "Paid" if paid else "Outstanding", "lastModified": _iso(r.paid if paid else r.issue)}
        leap_invoices.append(row)
        if not paid:
            open_at_cutover.append((row, r))
    trust_final = trust_at(F)
    leap_trust = [{"ledgerId": _uid("leap-trust", c), "clientName": c, "balance": _cents(v), "asAt": _iso(F), "lastModified": _iso(F)}
                  for c, v in trust_final.items()]

    # ------------------------------------------------------------------------------ triConvey (Smokeball-shaped), live from go-live
    status_code = {"Open": 0, "On Hold": 1, "Closed": 2}                     # Smokeball-style numeric status
    active_at_cutover = leap_mt[leap_mt["status"].isin(["Open", "On Hold"])]
    tc_matters = []
    for r in active_at_cutover.itertuples(index=False):
        if r.id == DEFECT_NOT_MIGRATED:
            continue                                                         # defect: failed validation, never migrated
        copies = 2 if r.id == DEFECT_DUPLICATED else 1                       # defect: imported twice
        for k in range(copies):
            changed = r.closed if pd.notna(r.closed) else GO
            tc_matters.append({
                "id": _uid("tc-matter", f"{r.id}#{k}"), "number": r.id, "title": r.name,
                "status": status_code[r.status] if pd.isna(r.closed) else 2, "clientName": r.client,
                "matterType": {"category": "General" if r.area == DEFECT_UNMAPPED_TYPE else r.area},   # defect: no mapping -> General
                "personResponsible": {"name": ATT_NAME.get(r.attorney, r.attorney)},
                "externalSystemId": _uid("leap-matter", r.id), "origin": "Migrated",
                "openedDate": _iso(r.opened), "lastUpdated": _iso(max(changed, GO) + pd.Timedelta(minutes=5 * k))})
    for r in mt[mt["opened"] > F].itertuples(index=False):                   # opened after the freeze: keyed fresh in triConvey
        tc_matters.append({
            "id": _uid("tc-matter", r.id), "number": r.id, "title": r.name, "status": status_code[r.status], "clientName": r.client,
            "matterType": {"category": r.area}, "personResponsible": {"name": ATT_NAME.get(r.attorney, r.attorney)},
            "externalSystemId": None, "origin": "Created in triConvey", "openedDate": _iso(r.opened),
            "lastUpdated": _iso(max(r.closed if pd.notna(r.closed) else r.opened, GO))})

    tc_invoices = []
    for i, (row, r) in enumerate(open_at_cutover):                           # open invoices migrate as one aggregate total each
        ex_tax, tax = row["amountExTax"], row["tax"]
        if i == DEFECT_GST_DROPPED_IDX:
            tax = 0.0                                                        # defect: tax code not mapped, GST dropped
        paid_now = pd.notna(r.paid) and r.paid <= AS_OF
        tc_invoices.append({"id": _uid("tc-invoice", row["invoiceNumber"]), "invoiceNumber": row["invoiceNumber"],
                            "matterNumber": row["matterNumber"], "clientName": row["clientName"], "issueDate": row["issueDate"],
                            "amountExTax": ex_tax, "tax": tax, "total": _cents(ex_tax + tax),
                            "balanceDue": 0.0 if paid_now else _cents(ex_tax + tax), "status": "Paid" if paid_now else "Outstanding",
                            "origin": "Migrated", "lastUpdated": _iso(r.paid if paid_now else GO)})
    for r in inv[inv["issue"] > F].itertuples(index=False):                  # raised in triConvey after go-live
        sub = _cents(r.ex_gst); tax = _cents(sub * 0.10); total = _cents(sub + tax)
        paid_now = pd.notna(r.paid) and r.paid <= AS_OF
        tc_invoices.append({"id": _uid("tc-invoice", r.invoice), "invoiceNumber": r.invoice, "matterNumber": r.matter_id,
                            "clientName": r.client, "issueDate": _iso(r.issue), "amountExTax": sub, "tax": tax, "total": total,
                            "balanceDue": 0.0 if paid_now else total, "status": "Paid" if paid_now else "Outstanding",
                            "origin": "Created in triConvey", "lastUpdated": _iso(r.paid if paid_now else r.issue)})

    keyed_on = GO + pd.Timedelta(days=1)                                     # opening balances keyed in the Trust Transition session
    tc_trust = [{"id": _uid("tc-trust", c), "contactName": c,
                 "balance": _cents(v - T.TRUST_OPENING_SHORT_BY) if c == T.TRUST_SHORT_CLIENT else _cents(v),   # defect: late receipt missing
                 "asAt": _iso(F), "origin": "Opening balance keyed by the firm", "lastUpdated": _iso(keyed_on)}
                for c, v in trust_final.items()]
    # August trust reconciliation (r48), prepared in triConvey from the bank statement: the books are right, the keyed ledgers are not
    month_end = T.RECON_MONTH_END
    trust_me = trust_at(month_end)
    cheque_txn = M["trust_txns"][(M["trust_txns"]["date"] > F) & (M["trust_txns"]["date"] <= month_end) & (M["trust_txns"]["amount"] < 0)]
    unpresented = _cents(-cheque_txn["amount"].sum())
    ledger_total = _cents(trust_me.sum() - T.TRUST_OPENING_SHORT_BY)
    tc_recon = [{"id": _uid("tc-recon", "2025-08"), "periodEnd": _iso(month_end), "dueDate": _iso(T.recon_due()),
                 "bankBalance": _cents(trust_me.sum() + unpresented), "depositsNotBanked": 0.0, "unpresentedCheques": unpresented,
                 "cashBookBalance": _cents(trust_me.sum()), "ledgerTotal": ledger_total, "ledgersListed": int(len(trust_me)),
                 "status": "Not yet prepared", "lastUpdated": _iso(AS_OF)}]

    # ---------------------------------------------------------------------------------------------- search suppliers and the ledgers
    it = M["infotrack"].sort_values("date", kind="stable").reset_index(drop=True)
    it["order_id"] = 900000 + it.index
    live = it["date"] >= GO
    habit = pd.Series(False, index=it.index)
    habit[live] = (np.arange(int(live.sum())) % T.INFOTRACK_STRAGGLER_EVERY) == T.INFOTRACK_STRAGGLER_EVERY - 1
    to_trisearch = live & ~habit                                              # everything from go-live except habit orders
    infotrack_rows, trisearch_rows = [], []
    for i, r in it.iterrows():
        lts = r.search_type == "Land Title Search"
        if to_trisearch[i]:
            total = _cents(r.cost * T.TRISEARCH_FEE_RATIO)
            k = len(trisearch_rows)
            ref = r.matter_id
            if k % REF_VARIANT_EVERY == REF_VARIANT_EVERY - 1:
                ref = ref.lower().replace("-", "")                           # re-typed reference: "m20240153"
            trisearch_rows.append({
                "orderNumber": f"TS-{100000 + k}", "placedAt": _iso(r.date), "reference": ref, "matterDescription": r.matter,
                "product": r.search_type, "feeExGst": total, "registryFeeExGst": T.NSW_LRS_SEARCH_EX_GST if lts else None,
                "serviceFeeExGst": _cents(total - T.NSW_LRS_SEARCH_EX_GST) if lts else total, "gst": _cents(total * 0.10),
                "state": r.status, "office": r.branch, "updatedAt": _iso(r.date), "_i": int(i)})
        else:
            total = _cents(r.cost)
            infotrack_rows.append({
                "orderId": int(r.order_id), "dateOrdered": _iso(r.date), "clientReference": r.matter_id, "matterDescription": r.matter,
                "serviceName": r.search_type, "totalFeeExGst": total, "registryFeeExGst": T.NSW_LRS_SEARCH_EX_GST if lts else None,
                "serviceFeeExGst": _cents(total - T.NSW_LRS_SEARCH_EX_GST) if lts else total, "gst": _cents(total * 0.10),
                "status": r.status, "office": r.branch, "lastModified": _iso(r.date), "_i": int(i)})

    def disb(system, matter, desc, day, ex_gst, supplier, order_ref, by):
        row = {"matterNumber": matter, "description": desc, "date": _iso(day), "amountExGst": _cents(ex_gst), "gst": _cents(ex_gst * 0.10),
               "supplier": supplier, "supplierOrderRef": order_ref, "postedBy": by}
        uid = _uid(f"{system}-disb", f"{supplier}:{order_ref}:{day}:{ex_gst}:{by}")
        # same field conventions as each system's other resources: LEAP-style disbursementId/lastModified, Smokeball-style id/lastUpdated
        return {"disbursementId": uid, **row, "lastModified": _iso(day)} if system == "leap" else {"id": uid, **row, "lastUpdated": _iso(day)}
    leap_disb, tc_disb = [], []
    for row in infotrack_rows:                                                # InfoTrack orders still inside LEAP's lifetime
        day = pd.Timestamp(row["dateOrdered"])
        if T.RECON_WINDOW_START <= day <= F and row["status"] == "Complete":    # LEAP posts when the order completes
            leap_disb.append(disb("leap", row["clientReference"], f"{row['serviceName']} (InfoTrack)", day, row["totalFeeExGst"],
                                  "InfoTrack", str(row["orderId"]), "InfoTrack integration"))
    manual = [r for r in infotrack_rows if pd.Timestamp(r["dateOrdered"]) > F and r["status"] == "Complete"]
    for n, row in enumerate(manual):                                          # LEAP is frozen: someone must re-key these in triConvey
        if n in MANUAL_MISSING_IDX:
            continue                                                          # defect: never entered, so never billed to the client
        amount = _cents(row["totalFeeExGst"] + row["gst"]) if n == MANUAL_AMOUNT_IDX else row["totalFeeExGst"]   # defect: GST in ex-GST column
        day = pd.Timestamp(row["dateOrdered"])
        line = disb("tc", row["clientReference"], f"{row['serviceName']} (InfoTrack)", day, amount, "InfoTrack", str(row["orderId"]), "Manual entry")
        tc_disb.append(line)
        if n == MANUAL_DUPLICATE_IDX:                                         # defect: keyed twice
            tc_disb.append({**line, "id": _uid("tc-disb-dup", str(row["orderId"])), "lastUpdated": _iso(day + pd.Timedelta(hours=1))})
    off_from, off_to = T.AUTO_DISBURSEMENT_OFF
    for row in trisearch_rows:                                                # TriSearch charges the matter when the order is PLACED
        day = pd.Timestamp(row["placedAt"])
        if off_from <= day <= off_to:
            continue                                                          # defect: "Automatically create a disbursement" was off
        tc_disb.append(disb("tc", it.loc[row["_i"], "matter_id"], f"{row['product']} (TriSearch)", day, row["feeExGst"], "TriSearch",
                            row["orderNumber"], "TriSearch integration"))
    for rows in (infotrack_rows, trisearch_rows):                             # drop the helper column
        for r in rows:
            r.pop("_i", None)

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

    return {"leap": {"matters": leap_matters, "invoices": leap_invoices, "trust_balances": leap_trust, "disbursements": leap_disb},
            "triconvey": {"matters": tc_matters, "invoices": tc_invoices, "trust_balances": tc_trust,
                          "trust_reconciliation": tc_recon, "disbursements": tc_disb},
            "infotrack": {"orders": infotrack_rows}, "trisearch": {"orders": trisearch_rows}, "pexa": {"workspaces": pexa}}


def expected_defects(model: dict | None = None) -> dict:
    """What the cut-over reconciliations must find (used by tests and the docs)."""
    return {"not_migrated": DEFECT_NOT_MIGRATED, "duplicated": DEFECT_DUPLICATED, "unmapped_type": DEFECT_UNMAPPED_TYPE,
            "trust_short_client": T.TRUST_SHORT_CLIENT, "trust_short_by": T.TRUST_OPENING_SHORT_BY}


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
