# D'Agostino Legal — Operations Dashboard (Streamlit)

Built from the Figma design at:
https://www.figma.com/design/v2XzNdUJW2v3tcIcR28sCf/Untitled?node-id=3-4,
extended into a full practice-management app, then refined for density,
data realism, and branding.

## Run it

```bash
pip install -r requirements.txt
streamlit run app.py
```

## What changed in this pass

- **Donut chart fixed** — the "Workload By Practice Area" center label
  ("142 / Total Active") used to be a CSS negative-margin overlay, which
  is fragile and can drift or clip depending on render width. It's now a
  native Plotly annotation anchored to the chart's own center — robust
  regardless of screen size.
- **Tighter spacing throughout** — container padding, card padding, and
  the ~50 inter-row spacers were all reduced (new `spacer()` helper at
  10px instead of a full blank line at ~24px), so more fits in one
  screenshot/view with noticeably less scrolling, especially on Overview.
- **Two more charts on Overview** — "Monthly Revenue by Branch" (grouped
  bar, revenue vs cost) and "Invoice Status Breakdown" (Paid /
  Outstanding / Overdue), so the main dashboard reads as a complete
  one-screen report rather than needing a trip to Finance for the same
  signal.
- **Much larger sample dataset** — 4 → 8 attorneys, 8 → 15 clients,
  10 → 24 matters, 6 → 12 deadlines, 8 → 16 invoices, and proportionally
  larger trust/office transaction logs, commissions, RapidPay, InfoTrack,
  Council, and card-expense records. Branch headcounts/revenue/cost were
  scaled up to match. Everything stays cross-referenced (new attorneys
  show up correctly in the Overview heatmap, Team, Matters, Calendar,
  and Payroll).
- **Branding** — firm name is now **D'Agostino Legal** (was "Apex
  Legal"); the profile in the top-right corner is now **Brian Phu,
  Financial Analyst** (was "Clara Sterling, Senior Managing Partner").
  Note: Clara Sterling still exists as an attorney in the firm roster —
  only the *logged-in viewer* shown in the corner changed, since Brian
  Phu is presumably the analyst using this dashboard, not one of the
  billing attorneys.

## Structure

**Top nav:** Overview · Matters · Clients · Calendar · Finance · Team · Simulator

- **Overview** — KPI row, Matter Activity Trend, Workload donut, Critical
  Partner Metrics, Attorney Utilization heatmap, Billing & Trust status,
  upcoming court dates, **+ Revenue by Branch and Invoice Status charts**.
- **Matters** (3 tabs) — Matter List (search/filter), Matter Types
  (value/count by practice area), Locations (live map of Richmond/
  Camden/Liverpool with branch stats).
- **Clients** — roster, sortable, top-clients-by-revenue chart.
- **Calendar** — date-range + attorney filters, grouped by month.
- **Finance** (10 tabs) — Office Account, Trust Account, CommBiz, MYOB,
  Billing & Invoices, Commission, RapidPay, InfoTrack, Council, Card
  Expenses (Amex/Visa).
- **Team** (2 tabs) — Roster (with detail view), Payroll & Pay Rates
  (editable, live-recomputing).
- **Simulator** — pay-rate uplift, hiring scenario, branch-takeover
  scenario, all feeding one baseline-vs-projected P&L chart.

## Swapping in real data

Everything lives in the **DATA** section near the top of `app.py`.
Replace `BRANCHES`, `ATTORNEYS`, `CLIENTS`, `MATTERS`, `DEADLINES`,
`INVOICES`, `TRUST_LEDGER`, `TRUST_TXNS`, `OFFICE_TXNS`,
`COMMBIZ_STATUS`, `MYOB_PL`, `COMMISSIONS`, `RAPIDPAY_TXNS`,
`INFOTRACK_ORDERS`, `COUNCIL_SEARCHES`, `CARD_EXPENSES`, `KPIS`,
`TREND`, `WORKLOAD` with reads from your real sources — every section
function reads from these variables, so the rest of the app updates
automatically.

## Notes on fidelity / substitutions

- Streamlit's native button/tab widgets can't be restyled with
  pixel-perfect precision — close to the Figma design, not identical.
- The Figma design used a real avatar photo asset I couldn't retrieve
  (no network access to Figma's asset host from this environment), so
  the app uses a teal initials avatar instead.
- CommBiz, MYOB, InfoTrack, and RapidPay sections show realistic sample
  data/status but are not wired to those services — they're built as
  drop-in points for when you connect the real integrations.
