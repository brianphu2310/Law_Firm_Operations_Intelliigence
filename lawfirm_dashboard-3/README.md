# Apex Legal — Operations Dashboard (Streamlit)

Built from the Figma design at:
https://www.figma.com/design/v2XzNdUJW2v3tcIcR28sCf/Untitled?node-id=3-4
and extended into a full practice-management app.

Every nav item is a real, separately-rendered section — not a static
image. Filters, search, sortable tables, an editable payroll, and a
what-if simulator all actually work.

## Run it

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Structure

**Top nav:** Overview · Matters · Clients · Calendar · Finance · Team · Simulator

- **Overview** — KPI row, Matter Activity Trend, Workload donut, Critical
  Partner Metrics, Attorney Utilization heatmap, Billing & Trust status,
  upcoming court dates.
- **Matters** (3 tabs)
  - *Matter List* — search + filter by practice area / status / branch
  - *Matter Types* — value and count breakdown by practice area
  - *Locations* — a live map (`st.map`) of the 3 branches (Richmond,
    Camden, Liverpool) with headcount, active matters, revenue, and cost
    per branch, plus an active-matters-by-branch chart
- **Clients** — roster, sortable by billing/matters/tenure, top-clients chart
- **Calendar** — date-range + attorney filters, grouped by month
- **Finance** (10 tabs)
  - *Office Account* — balance, 6-month income vs expense, recent transactions
  - *Trust Account* — total held, per-client balances, recent trust transactions
  - *CommBiz* — bank-feed reconciliation status (Office + Trust accounts)
  - *MYOB* — P&L snapshot (Revenue / Wages / Overheads / Net Profit) and sync status
  - *Billing & Invoices* — status-filterable invoice list with live totals
  - *Commission* — referral/internal commission by matter, payable vs paid
  - *RapidPay* — card-payment volume, merchant fee rate, fees paid, transactions
  - *InfoTrack* — property/title search orders and spend
  - *Council* — council rate/planning searches, mapped to each branch's
    real council (Richmond → Hawkesbury City Council, Camden → Camden
    Council, Liverpool → Liverpool City Council)
  - *Card Expenses* — Amex vs Visa spend, filterable by card and branch,
    spend-by-category chart
- **Team** (2 tabs)
  - *Roster* — attorney cards, utilization, detail view (hours, assigned
    matters, deadlines)
  - *Payroll & Pay Rates* — **editable** per-attorney pay rate
    (`st.number_input`), monthly payroll cost recomputes live
- **Simulator** — three linked what-if controls:
  1. Firm-wide pay-rate uplift/cut slider
  2. Hire N more people (role, branch, utilization assumption) →
     estimated added cost & revenue
  3. Take over another branch (name, est. revenue/cost, attorneys
     transferring) → included/excluded via a checkbox

  All three feed a single "Baseline vs Projected" P&L chart at the
  bottom (Revenue / Cost / Net Margin), so you can see the combined
  effect of adjusting pay rates *and* hiring *and* a branch acquisition
  at once.

Data stays consistent across sections: the 3 branches (with real Sydney
coordinates), 4 attorneys, matters, and clients are shared everywhere —
e.g. Rachel Zane's row in the Overview heatmap, her card in Team, and
"Zane, R." in the Matters list and Calendar are all the same person.

## Swapping in real data

Everything lives in the **DATA** section near the top of `app.py`:
`BRANCHES`, `ATTORNEYS`, `CLIENTS`, `MATTERS`, `DEADLINES`, `INVOICES`,
`TRUST_LEDGER`, `TRUST_TXNS`, `OFFICE_TXNS`, `COMMBIZ_STATUS`,
`MYOB_PL`, `COMMISSIONS`, `RAPIDPAY_TXNS`, `INFOTRACK_ORDERS`,
`COUNCIL_SEARCHES`, `CARD_EXPENSES`, `KPIS`, `TREND`, `WORKLOAD`. Replace
these with reads from your real sources (CommBiz export/API, MYOB API,
RapidPay/InfoTrack exports, practice-management system) and keep the
same shape — every section function reads from these variables.

## Notes on fidelity / substitutions

- Streamlit's native button/tab widgets can't be restyled with
  pixel-perfect precision — close to the Figma design, not identical.
- The Figma design used a real avatar photo asset I couldn't retrieve
  (no network access to Figma's asset host from this environment), so
  the app uses a teal initials avatar instead.
- CommBiz, MYOB, InfoTrack, and RapidPay sections show realistic sample
  data/status but are not wired to those services — they're built as
  drop-in points for when you connect the real integrations.
