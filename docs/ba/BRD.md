# Business requirements document

## 1. Business need

The Principal of a three-office law firm (Richmond, Camden, Liverpool; 8 fee earners, 17 support staff) has to make several
decisions this year and today has to piece the numbers together from the practice-management system, MYOB, payroll and
spreadsheets. Each decision is made on a different, partial view, and none shows the cash impact.

The first request was narrow: **which practice-management software would save the firm the most?** (the firm pays about $117K a
year for LEAP + InfoTrack). Answering it needed the firm's cost base, utilisation and cash, and the same model can answer the
Principal's other questions. The business need is one place that brings the firm's information together and tests each decision
before it is made.

## 2. Objectives

| # | Objective | Measure of success |
|---|---|---|
| O1 | Answer the six decisions below from one source of truth | Every number on every page reconciles to the same model (tested) |
| O2 | Show the effect of a decision before it is made | Profit, gap to budget, one-off cash and 13-week cash low point for every decision |
| O3 | Make the assumptions visible and challengeable | Every benchmark and assumption is listed in one file and on the Simulator's Method tab |
| O4 | Work for a busy Principal | Every page and tab fits one laptop screen; a recommendation is visible without scrolling |
| O5 | Let finance refresh the numbers in the tools they use | SQL answers and an Excel pack refreshed by Power Query |

## 3. Scope

**In scope:** the six decisions; P&L against budget, FY outlook, cash and 13-week forecast; people, matters, clients, marketing;
the Simulator; the SQL warehouse, Snowflake scripts and Excel pack.
**Out of scope:** live connections to the firm's systems (sample data only); payroll processing; legal advice on employment
decisions; individual performance management.

## 4. The decisions

| ID | Decision | Question the Principal asks | Answer on the sample data |
|---|---|---|---|
| D1 | Software | Should we switch practice-management software, and to which? | Smokeball + GlobalX: best 3-year NPV (+$106K); payback 17 months |
| D2 | Branch | Should we open another branch? | Profitable at full speed (+$539K a year) but the $120K fit-out breaks the minimum cash balance: fund it first |
| D3 | Hiring | Should we hire lawyers, and for which type of matter? | Litigation first (lawyers at 89% utilisation, 60% margin) |
| D4 | Staffing | Are support teams the right size? Add or cut? | Camden reception/admin over-staffed by 1.8 roles; Richmond stretched |
| D5 | Pay | Should pay go up or down, and what can we afford? | 3% costs $119K a year; rates +1.7% would pay for it |
| D6 | Growth | Where is marketing working? Should we open a new type of matter? | Website & SEO cheapest per new matter ($646); Wills & Estates the best new service |

## 5. Business requirements

| ID | Requirement | Decision | Priority | Delivered by |
|---|---|---|---|---|
| BR1 | Compare each platform's 3-year cost, NPV, payback, scorecard and risks against the current system | D1 | Must | Platform pages; `core/platforms.py` |
| BR2 | Show a new branch's year-one result, full-speed result, payback and cash impact | D2 | Must | Simulator → Growth |
| BR3 | Rank practice areas by pressure on their lawyers, demand growth and margin, and recommend where to hire | D3 | Must | People → Where to hire; `sql/analysis/11_where_to_hire.sql` |
| BR4 | Model a hire in a chosen practice area, with year-one productivity and break-even | D3 | Must | Simulator → People & pay |
| BR5 | Compare each support department's headcount with its workload, by office | D4 | Must | People → Departments; `sql/analysis/12_support_staffing.sql` |
| BR6 | Model adding or cutting support roles by department, with NES redundancy and notice pay and the small-business exemption | D4 | Must | Simulator → People & pay |
| BR7 | Model a pay change for fee earners and support staff, compare it with market wage growth, and show the rate rise that would fund it | D5 | Must | Simulator → People & pay |
| BR8 | Show spend, inquiries, new matters and cost per new matter by marketing channel | D6 | Must | Clients → Marketing; `sql/analysis/13_marketing_channels.sql` |
| BR9 | Model extra marketing spend by channel with diminishing returns and the team's capacity | D6 | Should | Simulator → Growth |
| BR10 | Model opening a new matter type: launch cost, ramp-up, year-one and full-speed result, payback | D6 | Should | Simulator → Growth |
| BR11 | For every decision, show the one-off cash and the 13-week cash low point after it | All | Must | Simulator KPI row and Effects & cash |
| BR12 | Show what it would take to close the gap to budget, lever by lever | All | Should | Simulator → What would it take? |
| BR13 | Show the result if only part of a decision is delivered | All | Should | Simulator → How sure are we? |
| BR14 | Provide the hiring, staffing, marketing and P&L answers in SQL and in Excel, refreshable by Power Query | All | Must | `sql/`, `snowflake/`, `excel/` |
| BR15 | Every page and tab fits a 1440 × 810 browser window | All | Must | Checked for all pages and tabs |

## 6. Data needed

| Data | Source in a real firm | In this project |
|---|---|---|
| Fees, hours, rates, realisation by fee earner and practice area | Practice management (LEAP, Smokeball…) | `fact_time_by_area`, `fact_attorney_month` |
| P&L, budget | MYOB / Xero, budget spreadsheet | `fact_monthly_pnl` (Actual and Budget) |
| Matters opened, active, closed | Practice management | `dim_matter` |
| Inquiries and intake funnel | CRM / reception log | `fact_monthly_funnel` |
| Support headcount and pay by department | Payroll | `fact_staffing`, `dim_department` |
| Marketing spend by channel, referral commissions | MYOB, marketing reports | `fact_monthly_pnl`, `dim_marketing_channel` |
| Supplier orders (searches) | InfoTrack / council invoices | `fact_supplier_order` |
| Cash, receivables, trust | MYOB, bank, trust ledger | `fact_monthly_snapshot`, `fact_invoice`, `fact_trust_*` |

## 7. Assumptions and constraints

* Department workload benchmarks, marketing channel mix and new-service economics are assumptions, stated in `core/ref.py`.
* Redundancy and notice pay are NES minimums (Fair Work Act s 117, s 119). Awards, agreements and contracts can give more.
* Market wage growth of 3.4% is the ABS Wage Price Index, private sector, year to the September quarter 2026.
* Results are annual what-ifs on the last 12 months, not forecasts; client behaviour and mix are held constant.

## 8. Risks

| Risk | Effect | Mitigation |
|---|---|---|
| Benchmarks do not fit this firm | Wrong staffing call | Benchmarks shown next to the result; replace with the firm's own timesheets or task logs before acting |
| Decision taken on profit alone | Cash shortfall (branch, new service) | Cash needed and 13-week low point shown for every decision |
| Optimism in ramp-up or marketing returns | Over-investment | "How sure are we?" shows 75% and 50% delivery; marketing has diminishing returns and a capacity cap |
| Employment decisions made from a model | Unfair dismissal or underpayment risk | NES rules applied and flagged as minimums; legal advice before any redundancy |
