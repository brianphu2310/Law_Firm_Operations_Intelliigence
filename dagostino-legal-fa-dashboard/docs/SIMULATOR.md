# Decision Simulator

The Simulator answers "what should we do about it?". It takes the last 12 months of actuals as the base, lets you change the levers a firm
actually controls, and shows the effect on profit, margin and the gap to the FY26 budget.

![Simulator](screenshots/01-simulator-decision.png)

## Use it in two minutes

1. Open **★ Simulator** in the top bar (or follow a link from the Finance or Team pages).
2. Click a decision under **Start from a decision**, or move the sliders yourself.
3. Read the five cards on the right: revenue, operating profit, margin, effective rate and **gap to FY26 budget**.
4. Scroll to **What would it take?**, choose a target and click **Apply** on the lever you would rather pull.
5. Check **How sure are we?** to see how much of the result depends on delivering everything.
6. **Save** the scenario, change the levers, save again and compare them in the table (CSV export available).

## The levers

| Lever | Range | What it changes |
|---|---|---|
| Utilisation change | −10 to +10 pp | Billable hours of the existing team (hours scale with utilisation) |
| Rate increase | 0 to 10% | Standard rates on every hour |
| Realisation change | −5 to +5 pp | Share of standard value that is actually billed |
| Disbursement recovery change | −10 to +10 pp | Share of search and filing costs billed on to clients |
| Overhead change | −10 to +10% | All costs except fee-earner payroll and searches/filing fees |
| New fee earners | 0 to 3 | Adds pay plus about $9,000 a year overhead each; bills at the role's rate × firm utilisation × year-one productivity |
| Year-one productivity | 40 to 100% | How busy a new hire is relative to the firm average |
| Change in days to collect | −15 to +15 days | One-off cash effect only; profit is unchanged |

## Worked example: closing the budget gap

On the sample data the base run-rate is **$2.07M** operating profit a year against a **$2.39M** FY26 budget, a gap of **$326K**.
Under **What would it take?**, with the target "Match the FY26 budget operating profit", each lever on its own would need to move by:

| Lever | Needed | Verdict |
|---|---|---|
| Utilisation | +4.0 pp (to about 90%) | Comfortable |
| Rate increase | +4.7% | Comfortable |
| Realisation | +4.2 pp | Stretch |
| Disbursement recovery | not enough on its own | n/a |
| Overheads | −16.4% | Beyond a realistic range |

Then check the risk: a 3-point utilisation improvement recovers about three quarters of the gap, but only if it is fully delivered. Reading the
"How sure are we?" chart shows what is left if delivery is partial.

## Worked example: should we hire?

Load **Hire an associate** (one associate, 60% as busy as the firm average in year one). Year-one fees are about $406K against a cost of
$283K, a net contribution of about +$124K. The hire only covers their own cost if they reach roughly
**42%** of the firm's average productivity. If only 75% / 50% of the planned ramp-up arrives, operating profit falls to
$2.09M / $1.99M, and at 50% delivery it ends **below** the $2.07M base run-rate. The decision depends on having enough work to keep the hire busy.

## How the numbers are built

See [METHODOLOGY.md, section 6](METHODOLOGY.md#6-decision-simulator) for the formulas. In short:

* Base = last 12 months (1 Oct 24 – 17 Sep 25, 352 days) scaled to a full year.
* With every lever at zero the scenario equals the base exactly (tested).
* **Goal-seek** solves each lever on its own, on top of the levers already set, by bisection, then rounds the answer up to the slider step so applying it still meets the target.
* **Delivery** applies a share of the *improvements* only; setbacks and a hire's pay are never softened.

## Limits

* It is an annual what-if, not a month-by-month forecast; it does not model timing, seasonality or the cost of recruiting delays.
* It holds client behaviour, matter mix and volumes constant apart from the levers, and assumes there is enough work for any new hire.
* The utilisation lever is capped by what is physically possible (goal-seek never proposes more than 100% utilisation or realisation), and above about 95% the page warns that it is unlikely to be sustainable.
* Results are only as good as the base data; the sample data is synthetic.
