# Law Firm Treasury & Credit Strategy Dashboard

A Streamlit portfolio project built for an **FP&A / Treasury Credit Strategy Analyst** application
to **D'Agostino Solicitors Pty Ltd**, modelling how money moves through the firm.

The data model is deliberately aligned to the firm's real structure:
- **Two offices**: Liverpool (larger, original office) and Camden (newer satellite office), NSW
- **Four practice areas**: Family Law, Wills, Probate & Estates, Property Law, General Litigation
- Property Law drives most InfoTrack/settlement disbursement activity (searches, PEXA settlements)
- Family Law and General Litigation are the practice areas most likely to brief counsel

All figures are synthetic — no real client, financial, or staff data is used or was accessed.

## What it models

| Concept | Role |
|---|---|
| **Office account** | The firm's own money — fee income, operating expenses |
| **Trust account** | Client money held on statutory trust — legally separate, reconciled |
| **Credit cards (Amex, Visa)** | Firm expenses (office) and pre-paid disbursements (reimbursed from trust) |
| **LEAP** | System of record for matters, billing, and trust ledgers (represented via the underlying transaction tables) |
| **InfoTrack** | Disbursement generator — property searches, settlements, lodgements |
| **RapidPay** | Client card payment collection; takes a merchant fee |
| **CommBiz** | The actual bank (CBA) portal — where office/trust bank balances live, reconciled monthly |
| **Commission** | Tracked two ways: referral commission (matter-sourcing) and RapidPay merchant fees |
| **Location, matter type, client, counsel** | The dimensions everything is filtered/sliced by |

## Project structure

```
lawfirm_treasury_app/
├── app.py                          # Home dashboard (interactive, filterable)
├── utils.py                        # Shared data loading + filter helpers
├── requirements.txt
├── data/
│   ├── generate_data.py            # Synthetic data generator (re-run to reshuffle)
│   └── *.csv                       # 11 generated tables
└── pages/
    ├── 1_Trust_Account.py
    ├── 2_Office_Account_and_Cards.py
    ├── 3_Payments_and_Rails.py
    ├── 4_Commission_Analysis.py
    └── 5_Matters_and_Clients.py
```

## Run it

```bash
pip install -r requirements.txt
streamlit run app.py
```

Every page has a sidebar filter (location, matter type, date range) that drives all charts and
tables on that page — the "interactive dashboard" for the home page in particular.

## Regenerating data

The data is fully synthetic (seeded, so reproducible) and links matters → clients, locations,
counsel, and every transaction table together consistently. Edit `data/generate_data.py` and
re-run it to change volumes, distributions, or add new fields.

## Notes for the interview / write-up

- The ER relationship diagram (office ↔ trust ↔ cards ↔ InfoTrack ↔ LEAP ↔ RapidPay ↔ CommBiz ↔
  commission ↔ location/matter type/client/counsel) is the conceptual model this app is built on —
  worth including as a slide alongside the live app.
- Commission is deliberately split into **referral commission** and **RapidPay merchant fee**
  since those are different economic events (revenue-share vs cost-of-collection) that a credit
  strategy analyst would want to see separately.
- CommBiz reconciliation includes a `status` field (`Reconciled` / `Investigate`) so you can
  demo a trust-account risk/compliance angle, not just a P&L view.
