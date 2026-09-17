# Firm Financial Overview — Streamlit Dashboard

A single-file Streamlit dashboard styled to match the reference "HealthCare
Dashboard" mockup: soft mint gradient background, rounded white cards with
soft shadows, teal accent palette, KPI cards with sparklines, a multi-line
trend chart, a donut chart, insight cards, a data table, and a horizontal
bar chart.

## Run it

```bash
pip install -r requirements.txt
streamlit run app.py
```

## What's in the "Financial Overview" tab

- **KPI row** — Total Revenue, Avg Matter Duration, Avg Invoice Amount,
  Active Attorneys, Open Matters — each with a sparkline and a Vs-PY delta.
- **Revenue Trend By Matter Type** — monthly line chart across Litigation,
  Corporate, and Family Law.
- **Revenue by Client Type** — donut chart (Corporate / Individual /
  Government).
- **Insight cards** — Top Practice Area, Top Client, Most Profitable Matter
  Type.
- **Billable Hours by Attorney & Practice Area** — table with a bold Total
  row.
- **Billable Hours by Practice Area** — horizontal bar chart, derived from
  the same table so the two always agree.

"Billing & Trust" and "Matters" are placeholder tabs — ask and I'll build
those out next with their own KPIs and charts.

## Swapping in real data

Everything currently comes from `build_sample_data()` near the top of
`app.py`, seeded with a fixed random generator so the numbers stay
consistent on every run. To connect real data:

1. Replace the contents of `build_sample_data()` with a read from your
   actual source (CSV, database, API) instead of the `rng.*` calls.
2. Keep the same return shape — `trend`, `hours_df`, `client_mix`, `kpis`,
   `sparks`, `insights` — and the rest of the app (cards, charts, table)
   will pick it up unchanged.
3. If your practice areas, attorney list, or matter types differ, update
   the `PRACTICE_AREAS` / `ATTORNEYS` / `MONTHS` constants near the top.

## Notes on fidelity to the mockup

Streamlit's native widgets (tabs, containers) can't be restyled with
pixel-perfect precision the way a hand-built HTML page can — the CSS in
this file gets the tab bar, card shadows, and corner radii very close to
the reference, but if you want the exact HTML/CSS mockup as a starting
point again, it's the published Artifact from earlier in this
conversation.
