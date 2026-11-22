"""Re-shape the app's simulated invoice ledger into MYOB Business (AccountRight) API v2 JSON.

    python -m integration.myob_export          # writes integration/data/*.json

SIMULATED. The source is core.model.build_model() (fixed seed), the same ledger every dashboard page uses, so the pipeline can be
reconciled to the app to the cent. Field names follow the public MYOB AccountRight API v2 docs (Sale/Invoice/Service,
Sale/CustomerPayment, Contact/Customer, GeneralLedger/Account); the mapping is in docs/PIPELINE.md.

Mapping decisions
  * One MYOB Service invoice per ledger invoice; one line coded to the practice area's income account (the model does not split
    fees from recovered disbursements per invoice). Attorney -> Salesperson, branch -> Category (both real MYOB invoice fields).
  * Amounts are rounded to cents: Subtotal = round(ex GST), TotalTax = round(Subtotal x 10%), TotalAmount = Subtotal + TotalTax.
  * Status and balance are as at the model's sync date (core.ref.AS_OF): paid invoices are Closed with one CustomerPayment for the
    full amount; unpaid ones are Open with BalanceDueAmount = TotalAmount.
  * UIDs are deterministic (uuid5), so re-running the export gives identical files.
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path

import pandas as pd

from core.model import build_model
from core.ref import AREAS, AS_OF, CLIENTS

OUT = Path(__file__).resolve().parent / "data"
NS = uuid.UUID("6f1c2a0e-8d1b-4c55-9a7e-2b3c4d5e6f70")
COMPANY_FILE_UID = "d4a6b1e2-0c5f-4f3e-9a71-5b2c8e6f1a90"

INCOME_ACCOUNTS = {area: f"4-1{i + 1}00" for i, area in enumerate(AREAS)}       # 4-1100 Corporate ... 4-1500 Advisory
ACCOUNTS = ([("1-1110", "Business Cheque Account", "Asset", "Bank"),
             ("1-1200", "Trade Debtors", "Asset", "AccountReceivable"),
             ("2-1310", "GST Collected", "Liability", "OtherCurrentLiability")]
            + [(code, f"Professional Fees - {area}", "Income", "Income") for area, code in INCOME_ACCOUNTS.items()])


def _uid(kind: str, key: str) -> str:
    return str(uuid.uuid5(NS, f"{kind}:{key}"))


def _iso(ts) -> str:
    return pd.Timestamp(ts).strftime("%Y-%m-%dT%H:%M:%S")


def _cents(x: float) -> float:
    return round(float(x) + 1e-9, 2)


def build_export(model: dict | None = None) -> dict[str, list[dict]]:
    M = model if model is not None else build_model()
    inv = M["inv"]

    accounts = [{"UID": _uid("account", code), "DisplayID": code, "Name": name, "Classification": cls, "Type": typ,
                 "IsActive": True, "IsHeader": False, "LastModified": _iso("2023-07-01"), "RowVersion": "1"}
                for code, name, cls, typ in ACCOUNTS]
    acc = {a["DisplayID"]: a for a in accounts}

    first_issue = inv.groupby("client")["issue"].min()
    customers = []
    for i, c in enumerate(CLIENTS, 1):
        customers.append({"UID": _uid("customer", c["name"]), "DisplayID": f"CUS{i:05d}", "IsIndividual": False,
                          "CompanyName": c["name"], "FirstName": None, "LastName": None, "IsActive": True,
                          "Addresses": [{"Location": 1, "Country": c["country"]}],
                          "SellingDetails": {"Terms": {"PaymentIsDue": "InAGivenNumberOfDays", "BalanceDueDate": 30}},
                          "LastModified": _iso(first_issue.get(c["name"], pd.Timestamp("2023-07-01"))), "RowVersion": "1"})
    cust = {c["CompanyName"]: c for c in customers}

    invoices, payments = [], []
    for r in inv.itertuples(index=False):
        sub = _cents(r.ex_gst)
        tax = _cents(sub * 0.10)
        total = _cents(sub + tax)
        paid = pd.notna(r.paid) and r.paid <= AS_OF
        c = cust[r.client]
        code = INCOME_ACCOUNTS[r.area]
        inv_uid = _uid("invoice", r.invoice)
        invoices.append({
            "UID": inv_uid, "Number": r.invoice, "Date": _iso(r.issue),
            "Customer": {"UID": c["UID"], "Name": r.client, "DisplayID": c["DisplayID"]},
            "IsTaxInclusive": False, "Subtotal": sub, "TotalTax": tax, "TotalAmount": total,
            "BalanceDueAmount": 0.0 if paid else total, "Status": "Closed" if paid else "Open",
            "Terms": {"PaymentIsDue": "InAGivenNumberOfDays", "BalanceDueDate": 30, "DueDate": _iso(r.due)},
            "Salesperson": {"Name": r.attorney}, "Category": {"Name": r.branch},
            "Lines": [{"RowID": 1, "Type": "Transaction", "Description": f"Professional fees & disbursements - {r.area}",
                       "Total": sub, "Account": {"UID": acc[code]["UID"], "DisplayID": code, "Name": acc[code]["Name"]},
                       "TaxCode": {"Code": "GST"}, "Job": {"Name": r.area}}],
            "JournalMemo": f"Sale; {r.client}",
            "LastModified": _iso(r.paid if paid else r.issue), "RowVersion": "1"})
        if paid:
            payments.append({
                "UID": _uid("payment", r.invoice), "Date": _iso(r.paid),
                "Customer": {"UID": c["UID"], "Name": r.client, "DisplayID": c["DisplayID"]},
                "PayFrom": "Account", "Account": {"UID": acc["1-1110"]["UID"], "DisplayID": "1-1110", "Name": acc["1-1110"]["Name"]},
                "PaymentMethod": "EFT", "AmountReceived": total,
                "Invoices": [{"UID": inv_uid, "Number": r.invoice, "AmountApplied": total, "Type": "Invoice"}],
                "LastModified": _iso(r.paid), "RowVersion": "1"})

    company = [{"Id": COMPANY_FILE_UID, "Name": "Example Legal (Simulated)", "Country": "AU",
                "ProductVersion": "2025.9", "LastSyncDate": _iso(AS_OF)}]
    return {"accounts": accounts, "customers": customers, "invoices": invoices,
            "customer_payments": payments, "company_file": company}


def write_export(out: Path = OUT) -> dict[str, int]:
    out.mkdir(parents=True, exist_ok=True)
    data = build_export()
    for name, rows in data.items():
        (out / f"{name}.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    return {k: len(v) for k, v in data.items()}


if __name__ == "__main__":
    for k, n in write_export().items():
        print(f"{k:<18} {n:>5}")
