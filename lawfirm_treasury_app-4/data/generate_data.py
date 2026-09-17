"""
Synthetic data generator for the Law Firm Treasury & Credit Strategy project.

Generates realistic (but fake) CSVs modelling how money moves through an
Australian law firm: office account, trust account, credit cards (Amex/Visa),
InfoTrack disbursements, RapidPay collections, CommBiz reconciliation and
commission (referral + merchant-fee).

Run: python generate_data.py
Writes all CSVs into the same /data folder.
"""

import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta

rng = np.random.default_rng(42)
OUT = Path(__file__).parent
START = datetime(2024, 1, 1)
END = datetime(2025, 12, 31)
DAYS = (END - START).days

# ---------------------------------------------------------------- locations
# Modelled on D'Agostino Solicitors Pty Ltd's two NSW offices
locations = pd.DataFrame([
    {"location_id": "LOC01", "location_name": "Liverpool", "state": "NSW", "city": "Liverpool",
     "latitude": -33.9200, "longitude": 150.9236,
     "address": "Suite 101, Level 1, 203-209 Northumberland Street, Liverpool NSW 2170"},
    {"location_id": "LOC02", "location_name": "Camden", "state": "NSW", "city": "Camden",
     "latitude": -34.0532, "longitude": 150.6961,
     "address": "Shop 6, Camden Arcade, 166 Argyle Street, Camden NSW 2570"},
])
locations.to_csv(OUT / "locations.csv", index=False)

# ---------------------------------------------------------------- counsel
counsel_names = ["J. Whitfield SC", "R. Nguyen", "A. Kowalski", "M. Okafor SC", "S. Patel",
                  "L. Marsh", "D. Chen", "K. O'Brien", "T. Vella", "H. Singh"]
counsel = pd.DataFrame({
    "counsel_id": [f"CSL{str(i+1).zfill(2)}" for i in range(len(counsel_names))],
    "counsel_name": counsel_names,
    "chambers": rng.choice(["Wentworth Chambers", "Selborne Chambers", "State Chambers",
                             "Denman Chambers", "Macquarie Street Chambers"], len(counsel_names)),
    "specialty": rng.choice(["General Litigation", "Family Law", "Property Law", "Wills, Probate & Estates"], len(counsel_names)),
})
counsel.to_csv(OUT / "counsel.csv", index=False)

# ---------------------------------------------------------------- clients
n_clients = 220
first = ["James", "Olivia", "Liam", "Ava", "Noah", "Mia", "Ethan", "Grace", "Lucas", "Chloe",
         "Henry", "Isla", "Jack", "Zoe", "William", "Ruby", "Alex", "Sophie", "Sam", "Priya"]
last = ["Smith", "Nguyen", "Chen", "Patel", "Wilson", "Kelly", "Brown", "Taylor", "Anderson",
        "Ryan", "Murphy", "Costa", "Kowalski", "Novak", "Singh", "Wong", "Hughes", "Reid"]
corp_words = ["Harbour", "Summit", "Bridgeview", "Ironbark", "Coastal", "Meridian", "Sterling",
              "Union", "Redgum", "Silverline"]
corp_suffix = ["Pty Ltd", "Group", "Holdings", "Developments", "Industries"]

client_rows = []
for i in range(n_clients):
    is_corp = rng.random() < 0.4
    if is_corp:
        name = f"{rng.choice(corp_words)} {rng.choice(corp_suffix)}"
        ctype = "Corporate"
    else:
        name = f"{rng.choice(first)} {rng.choice(last)}"
        ctype = "Individual"
    client_rows.append({
        "client_id": f"CLI{str(i+1).zfill(4)}",
        "client_name": name,
        "client_type": ctype,
        # Liverpool is the larger/original office, Camden the newer satellite office
        "location_id": rng.choice(locations.location_id, p=[0.65, 0.35]),
    })
clients = pd.DataFrame(client_rows)
clients.to_csv(OUT / "clients.csv", index=False)

# ---------------------------------------------------------------- matters
# Matches D'Agostino Solicitors' four actual practice areas
matter_types = ["Family Law", "Wills, Probate & Estates", "Property Law", "General Litigation"]
matter_type_p = [0.35, 0.25, 0.25, 0.15]
n_matters = 650

matter_rows = []
for i in range(n_matters):
    cli = clients.sample(1).iloc[0]
    mtype = rng.choice(matter_types, p=matter_type_p)
    open_offset = int(rng.integers(0, DAYS - 30))
    open_date = START + timedelta(days=open_offset)
    duration = int(rng.integers(10, 400))
    close_date = open_date + timedelta(days=duration)
    if close_date > END:
        status = "Open"
        close_date = pd.NaT
    else:
        status = rng.choice(["Closed", "Written off"], p=[0.94, 0.06])
    uses_counsel = mtype in ("General Litigation", "Family Law") and rng.random() < 0.45
    counsel_id = rng.choice(counsel.counsel_id) if uses_counsel else None
    referred = rng.random() < 0.3
    matter_rows.append({
        "matter_id": f"MAT{str(i+1).zfill(5)}",
        "client_id": cli.client_id,
        "location_id": cli.location_id,
        "matter_type": mtype,
        "status": status,
        "open_date": open_date.date(),
        "close_date": close_date.date() if pd.notna(close_date) else None,
        "counsel_id": counsel_id,
        "responsible_lawyer": f"Lawyer-{rng.integers(1, 26):02d}",
        "fee_estimate": round(float(rng.lognormal(mean=8.6, sigma=0.9)), 2),
        "referred_matter": referred,
        "referral_source": (rng.choice(["Mortgage Broker Co", "Accountant Partners", "Real Estate Alliance",
                                         "Existing Client Referral", "Financial Planner Network"])
                             if referred else None),
    })
matters = pd.DataFrame(matter_rows)
matters.to_csv(OUT / "matters.csv", index=False)


def rand_date_in_matter(row):
    end = row.close_date if pd.notna(row.close_date) else END.date()
    start = row.open_date
    span = (pd.Timestamp(end) - pd.Timestamp(start)).days
    span = max(span, 1)
    return pd.Timestamp(start) + timedelta(days=int(rng.integers(0, span + 1)))

# ---------------------------------------------------------------- trust transactions
trust_rows = []
txn_id = 1
for _, m in matters.iterrows():
    n_txn = rng.integers(1, 6) if m.matter_type == "Property Law" else rng.integers(0, 4)
    running_balance = 0.0
    for _ in range(n_txn):
        date = rand_date_in_matter(m)
        ttype = rng.choice(["Deposit", "Disbursement payment", "Transfer to office (billing)"],
                            p=[0.45, 0.35, 0.20])
        if ttype == "Deposit":
            amount = round(float(rng.lognormal(9.0, 0.7)), 2)
        elif ttype == "Disbursement payment":
            amount = -round(float(rng.lognormal(6.5, 0.8)), 2)
        else:
            amount = -round(float(rng.lognormal(7.8, 0.6)), 2)
        running_balance += amount
        trust_rows.append({
            "txn_id": f"TR{str(txn_id).zfill(6)}",
            "matter_id": m.matter_id,
            "location_id": m.location_id,
            "date": date.date(),
            "type": ttype,
            "amount": amount,
            "source_system": rng.choice(["CommBiz", "RapidPay", "InfoTrack", "Manual/LEAP"],
                                         p=[0.4, 0.2, 0.2, 0.2]),
            "balance_after": round(running_balance, 2),
        })
        txn_id += 1
trust_txns = pd.DataFrame(trust_rows)
trust_txns.to_csv(OUT / "trust_transactions.csv", index=False)

# ---------------------------------------------------------------- office transactions (fees + expenses)
office_rows = []
txn_id = 1
expense_categories = ["Software subscriptions", "Travel", "Office supplies", "Marketing",
                       "Professional development", "IT equipment", "Client entertainment"]
for _, m in matters.iterrows():
    if m.status == "Closed":
        date = rand_date_in_matter(m)
        fee = round(m.fee_estimate * float(rng.uniform(0.8, 1.15)), 2)
        office_rows.append({
            "txn_id": f"OF{str(txn_id).zfill(6)}", "matter_id": m.matter_id,
            "location_id": m.location_id, "date": date.date(), "type": "Fee income",
            "category": m.matter_type, "amount": fee, "card_used": None,
            "description": f"Invoice - {m.matter_type} matter",
        })
        txn_id += 1

n_expenses = 900
for _ in range(n_expenses):
    loc = rng.choice(locations.location_id)
    date = START + timedelta(days=int(rng.integers(0, DAYS)))
    card = rng.choice(["Amex", "Visa", None], p=[0.35, 0.35, 0.30])
    office_rows.append({
        "txn_id": f"OF{str(txn_id).zfill(6)}", "matter_id": None,
        "location_id": loc, "date": date.date(), "type": "Expense",
        "category": rng.choice(expense_categories),
        "amount": -round(float(rng.lognormal(5.5, 1.0)), 2),
        "card_used": card,
        "description": "Operating expense",
    })
    txn_id += 1
office_txns = pd.DataFrame(office_rows)
office_txns.to_csv(OUT / "office_transactions.csv", index=False)

# ---------------------------------------------------------------- credit card transactions
card_rows = []
txn_id = 1
merchants_office = ["Microsoft 365", "Qantas", "Officeworks", "LinkedIn Ads", "Uber",
                     "CPD Seminar Co", "Dell Technologies", "Virgin Australia"]
merchants_disb = ["Land Registry Search Fee", "Court Filing Fee", "Process Server",
                   "Title Search Provider", "Council Rates Certificate", "Barrister Brief Fee"]
for _ in range(1100):
    is_disb = rng.random() < 0.4
    date = START + timedelta(days=int(rng.integers(0, DAYS)))
    matter_id = rng.choice(matters.matter_id) if is_disb else None
    card_rows.append({
        "txn_id": f"CC{str(txn_id).zfill(6)}",
        "card_type": rng.choice(["Amex", "Visa"], p=[0.45, 0.55]),
        "date": date.date(),
        "matter_id": matter_id,
        "merchant": rng.choice(merchants_disb) if is_disb else rng.choice(merchants_office),
        "amount": round(float(rng.lognormal(5.8 if is_disb else 5.2, 0.9)), 2),
        "charged_to": "Trust reimbursable" if is_disb else "Office (firm expense)",
        "location_id": rng.choice(locations.location_id),
    })
    txn_id += 1
card_txns = pd.DataFrame(card_rows)
card_txns.to_csv(OUT / "credit_card_transactions.csv", index=False)

# ---------------------------------------------------------------- infotrack transactions
infotrack_rows = []
txn_id = 1
conv_matters = matters[matters.matter_type == "Property Law"]
services = ["Title search", "PEXA settlement fee", "Council rates search", "Land tax certificate",
            "Building & pest inspection lodgement", "Water rates search"]
for _, m in conv_matters.iterrows():
    for _ in range(int(rng.integers(1, 4))):
        date = rand_date_in_matter(m)
        infotrack_rows.append({
            "txn_id": f"IT{str(txn_id).zfill(6)}", "matter_id": m.matter_id,
            "location_id": m.location_id, "date": date.date(),
            "service_type": rng.choice(services),
            "amount": round(float(rng.lognormal(4.8, 0.6)), 2),
            "paid_from": rng.choice(["Trust", "Office"], p=[0.7, 0.3]),
            "status": rng.choice(["Settled", "Pending reimbursement"], p=[0.88, 0.12]),
        })
        txn_id += 1
infotrack_txns = pd.DataFrame(infotrack_rows)
infotrack_txns.to_csv(OUT / "infotrack_transactions.csv", index=False)

# ---------------------------------------------------------------- rapidpay transactions
rapidpay_rows = []
txn_id = 1
for _, m in matters[matters.status == "Closed"].iterrows():
    if rng.random() < 0.55:
        date = rand_date_in_matter(m)
        gross = round(m.fee_estimate * float(rng.uniform(0.5, 1.1)), 2)
        method = rng.choice(["Visa", "Amex", "Mastercard"], p=[0.4, 0.25, 0.35])
        fee_rate = 0.017 if method != "Amex" else 0.028
        fee = round(gross * fee_rate, 2)
        rapidpay_rows.append({
            "txn_id": f"RP{str(txn_id).zfill(6)}", "matter_id": m.matter_id,
            "location_id": m.location_id, "date": date.date(),
            "gross_amount": gross, "merchant_fee": fee, "net_amount": round(gross - fee, 2),
            "payment_method": method,
            "destination_account": rng.choice(["Office", "Trust"], p=[0.75, 0.25]),
        })
        txn_id += 1
rapidpay_txns = pd.DataFrame(rapidpay_rows)
rapidpay_txns.to_csv(OUT / "rapidpay_transactions.csv", index=False)

# ---------------------------------------------------------------- commbiz reconciliation
recon_rows = []
recon_id = 1
for loc in locations.location_id:
    for acct in ["Office", "Trust"]:
        bank_bal = float(rng.uniform(80000, 650000)) if acct == "Office" else float(rng.uniform(150000, 900000))
        for d in pd.date_range(START, END, freq="MS"):
            bank_bal += float(rng.normal(4000 if acct == "Office" else 8000, 15000))
            variance = round(float(rng.normal(0, 250)), 2) if rng.random() < 0.92 else round(float(rng.normal(0, 3500)), 2)
            recon_rows.append({
                "recon_id": f"RC{str(recon_id).zfill(5)}", "account_type": acct,
                "location_id": loc, "period_end": d.date(),
                "bank_balance": round(bank_bal, 2),
                "ledger_balance": round(bank_bal - variance, 2),
                "variance": variance,
                "status": "Reconciled" if abs(variance) < 500 else "Investigate",
            })
            recon_id += 1
commbiz = pd.DataFrame(recon_rows)
commbiz.to_csv(OUT / "commbiz_reconciliation.csv", index=False)

# ---------------------------------------------------------------- commission
commission_rows = []
cid = 1
for _, m in matters[matters.referred_matter].iterrows():
    date = rand_date_in_matter(m)
    commission_rows.append({
        "commission_id": f"CM{str(cid).zfill(5)}", "commission_type": "Referral",
        "matter_id": m.matter_id, "location_id": m.location_id, "date": date.date(),
        "source": m.referral_source,
        "amount": round(m.fee_estimate * float(rng.uniform(0.05, 0.15)), 2),
    })
    cid += 1
for _, r in rapidpay_txns.iterrows():
    commission_rows.append({
        "commission_id": f"CM{str(cid).zfill(5)}", "commission_type": "Merchant fee (RapidPay)",
        "matter_id": r.matter_id, "location_id": r.location_id, "date": r.date,
        "source": "RapidPay", "amount": r.merchant_fee,
    })
    cid += 1
commission = pd.DataFrame(commission_rows)
commission.to_csv(OUT / "commission.csv", index=False)

print("Generated:")
for f in sorted(OUT.glob("*.csv")):
    print(" -", f.name, len(pd.read_csv(f)), "rows")
