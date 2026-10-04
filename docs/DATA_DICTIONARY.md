# Data dictionary and source-to-target mapping

Every column in `warehouse/schema.sql`, with the simulated source field it comes from and the transformation rule applied by `warehouse/build.py`.
Source objects come from the app's fixed-seed generator (`core.model.build_model()`): `fin` / `plan` = monthly actual and budget frames, `stock` = month-end balances, `inv` = invoice ledger, `matters` = matter ledger, `H` / `V_ak` / `fees_ak` = hours, value and fees arrays by attorney x area x month, `trust` / `trust_txns` = trust ledger.
**All data is simulated.** "Generator parameter" columns hold simulation inputs, not observations. A test (`tests/test_docs.py`) fails if a warehouse column is missing from this file.

## dim_date
5,479 rows.

| Column | Type | Key | Description | Source -> transformation rule |
|---|---|---|---|---|
| `date_key` | INTEGER | PK | Surrogate key, yyyymmdd integer | Generated: whole calendar years covering the earliest to latest date in the data |
| `full_date` | TEXT |  | ISO date | Generated: calendar spine |
| `year` | INTEGER |  | Calendar year | Generated: calendar spine |
| `quarter` | INTEGER |  | Calendar quarter | Generated: calendar spine |
| `month` | INTEGER |  | Calendar month | Generated: calendar spine |
| `month_name` | TEXT |  | Month name | Generated: calendar spine |
| `month_start_date` | TEXT |  | First day of month (ISO) | Generated; month-rollup join key |
| `day_of_month` | INTEGER |  | Day of month | Generated: calendar spine |
| `day_of_week` | INTEGER |  | 1 = Monday .. 7 = Sunday | Generated: calendar spine |
| `day_name` | TEXT |  | Weekday name | Generated: calendar spine |
| `is_weekend` | INTEGER |  | 1 if Saturday/Sunday | day_of_week >= 6 |
| `is_month_end` | INTEGER |  | 1 if last day of month | Generated: calendar spine |
| `fy_start_year` | INTEGER |  | Australian FY start year (1 Jul - 30 Jun) | year if month >= 7 else year - 1 |
| `fy_label` | TEXT |  | FY label e.g. FY26 | "FY" + two-digit (fy_start_year + 1) |
| `fy_quarter` | INTEGER |  | Fiscal quarter, 1 = Jul-Sep | ((month - 7) mod 12) div 3 + 1 |

## dim_branch
3 rows.

| Column | Type | Key | Description | Source -> transformation rule |
|---|---|---|---|---|
| `branch_key` | INTEGER | PK | Surrogate key | Row order of core.ref.BRANCHES, from 1 |
| `branch_name` | TEXT |  | Office | BRANCHES[].name |
| `council_area` | TEXT |  | Council area | BRANCHES[].council |
| `latitude` | REAL |  | Office latitude | BRANCHES[].lat |
| `longitude` | REAL |  | Office longitude | BRANCHES[].lon |
| `support_headcount` | INTEGER |  | Support staff at the office | BRANCHES[].support |
| `base_monthly_rent` | REAL |  | Monthly rent at the base wage/cost index | BRANCHES[].rent |

## dim_practice_area
5 rows.

| Column | Type | Key | Description | Source -> transformation rule |
|---|---|---|---|---|
| `practice_area_key` | INTEGER | PK | Surrogate key | Row order of core.ref.AREAS, from 1 |
| `practice_area` | TEXT |  | Practice area | AREAS |

## dim_scenario
2 rows.

| Column | Type | Key | Description | Source -> transformation rule |
|---|---|---|---|---|
| `scenario_key` | INTEGER | PK | Surrogate key | 1 = Actual, 2 = Budget |
| `scenario_name` | TEXT |  | Actual or Budget | Fixed; Actual = model.fin, Budget = model.plan |

## dim_attorney
8 rows.

| Column | Type | Key | Description | Source -> transformation rule |
|---|---|---|---|---|
| `attorney_key` | INTEGER | PK | Surrogate key | Row order of core.ref.ATTORNEYS, from 1 |
| `attorney_short` | TEXT |  | Short name (business key) | ATTORNEYS[].short |
| `attorney_name` | TEXT |  | Full name (fictional) | ATTORNEYS[].name |
| `role` | TEXT |  | Role | ATTORNEYS[].role |
| `home_branch_key` | INTEGER | FK -> dim_branch.branch_key | FK to dim_branch | Lookup ATTORNEYS[].branch |
| `start_date_key` | INTEGER | FK -> dim_date.date_key | FK to dim_date: start date | ATTORNEYS[].start -> yyyymmdd |
| `target_hours_per_month` | REAL |  | Capacity: monthly billable-hours target | ATTORNEYS[].target |
| `bill_rate` | REAL |  | Standard hourly rate at the current (FY26) rate index | ATTORNEYS[].bill_rate |
| `pay_rate` | REAL |  | Internal cost per hour at the current wage index | ATTORNEYS[].pay_rate |
| `realisation_factor` | REAL |  | Generator parameter: relative realisation vs firm average (NOT observed) | ATTORNEYS[].real_factor |

## dim_client
23 rows.

| Column | Type | Key | Description | Source -> transformation rule |
|---|---|---|---|---|
| `client_key` | INTEGER | PK | Surrogate key | Dense 1..n ordered by client name |
| `client_name` | TEXT |  | Client (business key) | CLIENTS[].name |
| `primary_practice_area_key` | INTEGER | FK -> dim_practice_area.practice_area_key | FK to dim_practice_area | Lookup CLIENTS[].practice |
| `relationship_attorney_key` | INTEGER | FK -> dim_attorney.attorney_key | FK to dim_attorney | Lookup CLIENTS[].attorney |
| `client_since_year` | INTEGER |  | Year the client relationship began | CLIENTS[].since |
| `country` | TEXT |  | Client country | CLIENTS[].country |
| `has_trust_account` | INTEGER |  | 1 if the client has a trust ledger | client name in TRUST_TARGET -> 0/1 |

## dim_matter
445 rows.

| Column | Type | Key | Description | Source -> transformation rule |
|---|---|---|---|---|
| `matter_key` | INTEGER | PK | Surrogate key | Dense 1..n ordered by matter id |
| `matter_id` | TEXT |  | Business key M-yyyy-nnnn | matters.id |
| `matter_name` | TEXT |  | Matter name; NOT unique | matters.name |
| `client_key` | INTEGER | FK -> dim_client.client_key | FK to dim_client | Lookup matters.client |
| `practice_area_key` | INTEGER | FK -> dim_practice_area.practice_area_key | FK to dim_practice_area | Lookup matters.area |
| `attorney_key` | INTEGER | FK -> dim_attorney.attorney_key | FK to dim_attorney | Lookup matters.attorney |
| `branch_key` | INTEGER | FK -> dim_branch.branch_key | FK to dim_branch | Lookup matters.branch (hand-set on named key matters) |
| `country` | TEXT |  | Matter jurisdiction/country | matters.country |
| `status` | TEXT |  | Open / On Hold / Closed | matters.status |
| `opened_date_key` | INTEGER | FK -> dim_date.date_key | FK to dim_date | matters.opened -> yyyymmdd |
| `closed_date_key` | INTEGER | FK -> dim_date.date_key | FK to dim_date; NULL unless Closed | matters.closed -> yyyymmdd; NaT -> NULL |
| `is_named_matter` | INTEGER |  | 1 if one of the hand-defined key matters | matters.named -> 0/1 |

## fact_invoice
472 rows.

| Column | Type | Key | Description | Source -> transformation rule |
|---|---|---|---|---|
| `invoice_key` | INTEGER | PK | Surrogate key | Dense 1..n ordered by invoice number |
| `invoice_number` | TEXT |  | Business key INV-nnnn | inv.invoice |
| `client_key` | INTEGER | FK -> dim_client.client_key | FK to dim_client | Lookup inv.client |
| `practice_area_key` | INTEGER | FK -> dim_practice_area.practice_area_key | FK to dim_practice_area | Lookup inv.area |
| `attorney_key` | INTEGER | FK -> dim_attorney.attorney_key | FK to dim_attorney | Lookup inv.attorney |
| `branch_key` | INTEGER | FK -> dim_branch.branch_key | FK to dim_branch | Lookup inv.branch (the attorney's branch) |
| `issue_date_key` | INTEGER | FK -> dim_date.date_key | FK to dim_date | inv.issue -> yyyymmdd |
| `due_date_key` | INTEGER | FK -> dim_date.date_key | FK to dim_date | inv.due -> yyyymmdd |
| `paid_date_key` | INTEGER | FK -> dim_date.date_key | FK to dim_date; NULL if unpaid at as-of | inv.paid -> yyyymmdd; NaT -> NULL |
| `amount_ex_gst` | REAL |  | Invoice amount excluding GST (AUD) | inv.ex_gst |
| `gst_amount` | REAL |  | GST (10%) | inv.gst |
| `amount_total` | REAL |  | Invoice total including GST | inv.total |
| `days_to_pay` | INTEGER |  | Calendar days issue -> paid; NULL if unpaid | paid - issue |
| `is_paid` | INTEGER |  | 1 if paid by the as-of date | inv.paid not null -> 0/1 |

## fact_matter_position
445 rows.

| Column | Type | Key | Description | Source -> transformation rule |
|---|---|---|---|---|
| `matter_key` | INTEGER | PK, FK -> dim_matter.matter_key | PK and FK to dim_matter | Lookup matters.id |
| `as_of_date_key` | INTEGER | FK -> dim_date.date_key | FK to dim_date: position date | core.ref.AS_OF -> yyyymmdd |
| `estimated_value` | REAL |  | Estimated total matter value | matters.est_value |
| `billed_to_date` | REAL |  | Fees billed to date | matters.billed |
| `wip_balance` | REAL |  | Unbilled work in progress | matters.wip |
| `progress_ratio` | REAL |  | Share of expected duration elapsed, 0-1 | matters.progress |
| `days_open` | INTEGER |  | Days from opened to closed (or as-of) | matters.days_open |

## fact_attorney_month
196 rows.

| Column | Type | Key | Description | Source -> transformation rule |
|---|---|---|---|---|
| `attorney_key` | INTEGER | PK, FK -> dim_attorney.attorney_key | PK part, FK to dim_attorney | Lookup ATTORNEYS[].short |
| `month_start_date_key` | INTEGER | PK, FK -> dim_date.date_key | PK part, FK to dim_date | months[t] -> yyyymmdd |
| `month_fraction_elapsed` | REAL |  | 1.0, or days elapsed / days in month for the as-of month | model.frac[t] |
| `capacity_hours` | REAL |  | Capacity hours to date | target x month_fraction_elapsed |
| `billable_hours` | REAL |  | Hours recorded | sum over areas of H[a,k,t] x month_fraction_elapsed |
| `standard_value` | REAL |  | Hours x standard rate | sum over areas of V_ak[a,k,t] x month_fraction_elapsed |
| `fees_realised` | REAL |  | Fees billed attributed to the attorney | sum over areas of fees_ak[a,k,t] x month_fraction_elapsed |
| `salary_cost` | REAL |  | Fee-earner salary cost (paid on capacity, regardless of hours) | target x pay_rate x wage_index[t] x month_fraction_elapsed (same formula as core.metrics.att_table) |

## fact_time_by_area
980 rows.

| Column | Type | Key | Description | Source -> transformation rule |
|---|---|---|---|---|
| `attorney_key` | INTEGER | PK, FK -> dim_attorney.attorney_key | PK part, FK to dim_attorney | As above |
| `practice_area_key` | INTEGER | PK, FK -> dim_practice_area.practice_area_key | PK part, FK to dim_practice_area | AREAS index |
| `month_start_date_key` | INTEGER | PK, FK -> dim_date.date_key | PK part, FK to dim_date | months[t] -> yyyymmdd |
| `billable_hours` | REAL |  | Hours in the area | H[a,k,t] x frac |
| `standard_value` | REAL |  | Value at standard rates | V_ak[a,k,t] x frac |
| `fees_realised` | REAL |  | Fees attributed to the area | fees_ak[a,k,t] x frac |
| `allocated_salary_cost` | REAL |  | Attorney-month salary cost allocated by hours share | salary_cost x hours[a,k,t] / sum_k hours[a,k,t]  (allocation rule, not observed) |

## fact_monthly_pnl
63 rows.

| Column | Type | Key | Description | Source -> transformation rule |
|---|---|---|---|---|
| `month_start_date_key` | INTEGER | PK, FK -> dim_date.date_key | PK part, FK to dim_date | months[t] -> yyyymmdd |
| `scenario_key` | INTEGER | PK, FK -> dim_scenario.scenario_key | PK part, FK to dim_scenario | Actual rows from model.fin (to as-of); Budget rows from model.plan (whole plan window) |
| `month_fraction_elapsed` | REAL |  | 1.0, or days elapsed / days in month for the as-of month | model.frac[t]; future budget months = 1.0 |
| `billable_hours` | REAL |  | Hours | fin.hours x frac |
| `capacity_hours` | REAL |  | Capacity hours | fin.capacity x frac |
| `standard_value` | REAL |  | Value at standard rates | fin.value_std x frac |
| `writeoff` | REAL |  | Value written off | fin.writeoff x frac |
| `fees` | REAL |  | Fees billed | fin.fees x frac |
| `disbursements_billed` | REAL |  | Disbursements recharged | fin.disb_billed x frac |
| `revenue` | REAL |  | Fees + disbursements billed | fin.revenue x frac |
| `payroll_fee_earners` | REAL |  | Fee-earner payroll | fin.payroll_fee x frac |
| `disbursement_cost` | REAL |  | Disbursement cost | fin.disb_cost x frac |
| `payroll_support` | REAL |  | Support-staff payroll | fin.payroll_support x frac |
| `rent` | REAL |  | Rent | fin.rent x frac |
| `software` | REAL |  | Software | fin.software x frac |
| `insurance` | REAL |  | Insurance | fin.insurance x frac |
| `marketing` | REAL |  | Marketing | fin.marketing x frac |
| `professional_fees` | REAL |  | Professional fees | fin.prof_fees x frac |
| `cards` | REAL |  | Corporate card spend | fin.cards x frac |
| `merchant_fees` | REAL |  | Card merchant fees | fin.merchant x frac |
| `commission` | REAL |  | Referral commission | fin.commission x frac |
| `bank_fees` | REAL |  | Bank fees | fin.bank_fees x frac |
| `other_costs` | REAL |  | Other costs | fin.other x frac |
| `total_costs` | REAL |  | Sum of the 13 cost lines | fin.total_costs x frac |
| `operating_profit` | REAL |  | Revenue - total costs | fin.op_profit x frac |

## fact_monthly_snapshot
27 rows.

| Column | Type | Key | Description | Source -> transformation rule |
|---|---|---|---|---|
| `month_start_date_key` | INTEGER | PK, FK -> dim_date.date_key | PK and FK to dim_date | stock index -> yyyymmdd |
| `snapshot_date_key` | INTEGER | FK -> dim_date.date_key | FK to dim_date: month end (as-of date for the current month) | stock.date -> yyyymmdd |
| `wip_balance` | REAL |  | Firm WIP balance | stock.wip |
| `cash_balance` | REAL |  | Office bank balance | stock.cash |
| `receivables_incl_gst` | REAL |  | Open receivables incl. GST | stock.ar |
| `trust_balance` | REAL |  | Total client trust money | stock.trust |
| `matters_active` | INTEGER |  | Open + on-hold matters | stock.matters_active |

## fact_trust_balance
189 rows.

| Column | Type | Key | Description | Source -> transformation rule |
|---|---|---|---|---|
| `client_key` | INTEGER | PK, FK -> dim_client.client_key | PK part, FK to dim_client | Column name of model.trust -> client lookup |
| `month_start_date_key` | INTEGER | PK, FK -> dim_date.date_key | PK part, FK to dim_date | model.trust index -> yyyymmdd |
| `closing_balance` | REAL |  | Trust balance at month end (as-of date for the current month) | model.trust (wide) -> long via stack() |

## fact_trust_txn
312 rows.

| Column | Type | Key | Description | Source -> transformation rule |
|---|---|---|---|---|
| `trust_txn_key` | INTEGER | PK | Surrogate key | Dense 1..n ordered by date, client, amount |
| `client_key` | INTEGER | FK -> dim_client.client_key | FK to dim_client | Lookup trust_txns.client |
| `txn_date_key` | INTEGER | FK -> dim_date.date_key | FK to dim_date | trust_txns.date -> yyyymmdd |
| `txn_type` | TEXT |  | Deposit / Disbursement | trust_txns.type |
| `amount` | REAL |  | Signed amount: deposits +, disbursements - | trust_txns.amount |

## Transformations applied across tables

* **Surrogate keys** are dense integers assigned in business-key order, so rebuilds are reproducible.
* **Pro-rating.** The simulator stores monthly flows as full-month equivalents and re-weights by days at query time. The warehouse stores the observed-to-date amount (`x month_fraction_elapsed`) so plain SUMs match the app for any period ending at the as-of date. Stocks (WIP, cash, receivables, trust) are point-in-time and are not pro-rated.
* **Dates** become `yyyymmdd` integer keys into `dim_date`; missing dates (unpaid invoices, open matters) stay NULL rather than a sentinel date.
* **Wide to long.** The trust ledger (month x client matrix) is stacked into `fact_trust_balance` rows; the attorney x area x month arrays become `fact_time_by_area` rows (only months in which the attorney was active).
* **Scenario rows.** Actual (`fin`) and Budget (`plan`) frames are stacked into one fact with a scenario key instead of two tables.
* **Allocation (derived, not observed).** `fact_time_by_area.allocated_salary_cost` splits each attorney-month's salary cost across areas by hours share. It conserves the total (tested).
* **Not loaded:** generator-only parameters on clients (billing weight, payment delay, invoice frequency); the InfoTrack / council search, corporate card, RapidPay, commission and deadline tables (out of scope for this model; they remain available in the app); the operating-funnel columns (`inquiries`, `booked`, `held`, `letters`), which are modelled ratios, not observations.
