# Methodology

Every number on every page is derived from one deterministic model (`core/model.py`). This document states the definitions
and formulas so they can be reviewed without reading the code. All amounts are in Australian dollars; GST is 10%.

## 1. Reporting periods

Monthly data is stored as **full-month equivalents** (the month in progress is scaled up by days elapsed). To answer a question
for any date range, each month is weighted by the share of its days that fall inside the range:

`period value = Σ (monthly value × days of that month inside the period ÷ days in that month)`

This is why month-to-date, quarter-to-date, financial years and custom ranges all reconcile exactly. The Australian financial
year runs 1 July – 30 June (FY26 = 1 Jul 2025 – 30 Jun 2026). Balances at the period end: WIP and cash are interpolated between month-end values; receivables are computed exactly from the
invoice ledger on that date; trust shows the latest month-end balance.

Comparison periods: *prior period* shifts the window back by one comparable unit (a month, quarter, half-year or year for the presets, so a
quarter-to-date is compared with the same point in the previous quarter; an equal-length window immediately before for custom ranges);
*same period last year* shifts it back 12 months. Data starts 1 Jul 2023, so
comparisons that would fall earlier show "n/a".

## 2. Firm KPIs

| KPI | Definition |
|---|---|
| Capacity | Active fee earners × 190 hours per month |
| Utilisation | Billable hours ÷ capacity |
| Value at standard rates | Billable hours × the fee earner's standard rate (with the annual rate review applied) |
| Realisation | Fees billed ÷ value at standard rates |
| Effective rate | Fees billed ÷ billable hours |
| Revenue | Professional fees + disbursements recovered (ex GST) |
| Operating profit | Revenue − operating costs, **before** partner drawings, income tax and depreciation |
| Operating margin | Operating profit ÷ revenue |
| Contribution after pay | Fees billed − fee-earner payroll |
| Break-even hours | Fee-earner payroll cost in the period ÷ effective rate |
| WIP | Work recorded but not yet billed: opening WIP + value − write-offs − fees billed |
| DSO | Receivables (incl. GST) ÷ (invoices issued in the last 90 days incl. GST ÷ 90) |
| Lock-up days | (WIP + receivables ex GST) ÷ (revenue billed in the last 90 days ex GST ÷ 90) |

**Receivables ageing** buckets open invoices by days past the due date (due = issue + 30 days): not yet due, 1–30, 31–60, 61–90, 90+.

## 3. Budget and outlook

* **Budget** uses the same cost model as actuals but with smooth, noise-free drivers (seasonality, rate reviews, wage inflation).
  Payroll, rent, software and insurance therefore equal budget exactly. In the actuals, marketing, professional fees, cards, merchant
  fees, commissions, bank fees and other overheads carry random variation around their budget values, which is where cost variances come from.
* **Variance sign convention:** favourable is positive. For revenue, variance = actual − budget; for costs, variance = budget − actual.
* **FY outlook** = year-to-date actuals + remaining budget (including the rest of the current month), where remaining revenue is
  scaled by the YTD revenue ratio (actual ÷ budget) and remaining costs by the YTD cost ratio. It assumes today's run-rate persists.

## 4. Cash

* Office cash = collections − operating costs − GST credits − quarterly BAS payments − partner drawings.
* Partner drawings are modelled as a share of the previous month's operating profit; that share, and the opening balance, are
  solved so the balance lands exactly on the reference figure at the as-of date while staying above a $60K working minimum.
* **13-week cash forecast** (weeks starting the day after the as-of date):
  1. *Open invoices* are collected on issue date + the client's typical days-to-pay; overdue invoices are assumed to clear
     within about three weeks.
  2. *Future billing* follows the budgeted run-rate and is collected 4–9 weeks after issue (15% / 30% / 30% / 15% / 10% at weeks 4 / 5 / 6 / 7 / 9).
  3. *Outflows:* fortnightly payroll, monthly rent, overheads and suppliers spread weekly, the quarterly BAS payment, and monthly drawings.
* **Trust money** belongs to clients. It is tracked per client, never appears in revenue or office cash, and no client ledger may go negative.

## 5. Platform evaluation

Each platform is evaluated as a move **away from the current system** (LEAP + InfoTrack) over 36 months.

* **Run-cost** = 12 × (seat price × seats + per-search fee × searches per month), at today's prices and volumes.
* **Monthly cost path** applies each vendor's annual price escalator and search-volume growth (default 5% a year).
* **Incremental cash flow (month *t*)** = productivity benefit − (new cost + parallel running − current cost) − one-off costs.
  * *Parallel running:* both systems are paid until go-live (implementation weeks ÷ 4.345, rounded up).
  * *One-offs:* migration cost in month 0, plus a productivity dip at cut-over (default: a 10% loss of fee-earner output lasting two weeks).
  * *Productivity benefit* = assumed extra billable hours per fee earner per month (for example 3.5 for Smokeball) × fee earners × effective rate
    × benefit-realisation share × ramp-up (linear over 6 months from go-live) × 3% annual growth. The current system has no benefit by definition.
* **NPV** discounts monthly at (1 + r)^(1/12) − 1 (default r = 10%). **IRR** is the monthly IRR annualised. **Payback** is the first
  month (counted from month 1) in which the cumulative net cash flow is positive.
* **Weighted scorecard:** analyst scores (0–100) for Speed, Cost, Reliability, Support, Integration, weighted by adjustable
  weights (default 30 / 25 / 20 / 15 / 10 for Cost / Integration / Reliability / Support / Speed).
* **Decision rank** = 50% weighted score + 50% NPV scaled 0–100 across the seven platforms.
* **Verdict:** *Recommend* if NPV > $50K and score ≥ current − 3; *Consider* if NPV > 0; otherwise *Not recommended*.
* **Scenarios:** Base (50% benefit realised), Downside (25%, migration ×1.4, no volume growth, +2% escalation), Upside (75%, migration ×0.85, +10% volume, −1% escalation).
* **Sensitivity:** NPV over a grid of benefit realisation × search volume, and the break-even benefit-realisation level.

The uplift percentages, prices, migration costs and scores are illustrative assumptions (see the README disclaimer).

## 6. Decision Simulator

An annual what-if on the last 12 months of actuals (352 days, scaled to 365). Let u₀, ρ₀ be today's utilisation and realisation, r₀ the average
standard rate per hour, and a lever value be written with its unit (pp = percentage points).

* Existing team hours: `H₁ = H₀ × (u₀ + Δu) ÷ u₀`
* New-hire hours: `hires × 190 × 12 × (u₀ + Δu) × productivity`
* Fees: `(H₁ × r₀ + hire hours × role rate) × (1 + rate increase) × (ρ₀ + Δρ)`
* Disbursement cost scales with total hours; disbursements billed = cost × (today's recovery ratio + Δrecovery).
* Costs: fee-earner payroll + new-hire pay + disbursement cost + overheads × (1 + overhead change) + about $9K a year overhead per new hire.
* Days to collect: one-off cash effect = −Δdays × scenario revenue × 1.10 ÷ 365 (profit is unchanged).
* **Break-even productivity of a hire** = (pay + overhead) ÷ fees at 100% of firm utilisation.
* **Gap to budget** = scenario operating profit − FY budget operating profit.
* **Goal-seek:** for each lever separately, on top of the levers already set, bisection finds the smallest value that reaches the target operating
  profit (or margin); the answer is rounded up to the slider step so applying it still meets the target. Utilisation and realisation are capped at 100%. A lever
  that cannot reach the target on its own is reported as such.
* **Delivery range:** re-runs the scenario with only 100% / 75% / 50% of the improvements (better utilisation, rates, realisation, recovery, overhead cuts and a hire's
  productivity). Setbacks and a hire's pay are not softened.

With every lever at zero the scenario equals the base exactly (this is tested). Details and worked examples: [SIMULATOR.md](SIMULATOR.md).

## 7. How the sample data is generated

* Hours per attorney and practice area follow a Sep-2025 run-rate with seasonality, a gradual growth ramp, new-starter ramp-up
  and small random noise (fixed seed, so results are reproducible).
* Invoices are issued per client and practice area with weekday issue dates; payment delays are drawn around each client's
  typical days-to-pay, with a small chance of a very late payment. Invoices from the three months before the data window
  provide a realistic opening receivables balance.
* Detail tables (InfoTrack searches, council searches, card expenses, merchant payments) are generated so that they sum exactly
  to the modelled monthly totals.
* The matter ledger combines 33 hand-written key matters with generated ones, then adds or trims generated matters so exactly
  142 are active at the as-of date. Per-matter WIP is scaled to the firm WIP balance.

## 8. What the tests check

`tests/test_reconciliation.py` — balances at the as-of date; profit arithmetic; invoice ledger equals revenue (FY25); cash stays
above the minimum; trust ledgers never negative; matter WIP equals firm WIP; detail tables tie to monthly totals; period presets;
month-to-date revenue equals invoices issued; quarters sum to the year; attorney, branch and client tables sum to firm totals;
ageing sums to receivables; the cash forecast is internally consistent; the outlook budget equals the plan; platform evaluation
sanity; simulator zero-lever equals base.

`tests/test_simulator_engine.py` — every preset is valid; goal-seek answers land exactly on the profit and margin targets and stay valid after
rounding; "already met" and "unreachable" are reported honestly; delivery haircuts scale only improvements; hire break-even is exact; each lever moves profit in the right direction;
`delta()` never divides by zero.

`tests/test_interactions.py` — clicks and edits in the running app: Reset, presets, Apply, Save/Clear, levers surviving navigation, call-to-action links from other pages,
platform scorecard weights updating immediately, and every page surviving reporting periods with no activity (regression tests for past bugs).

`tests/test_app_smoke.py` — every page and every platform dashboard renders without an exception, under several reporting-period settings.
