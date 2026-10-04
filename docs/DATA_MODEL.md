# Data model

A Kimball-style star schema in SQLite (`warehouse.db`, built by `python -m warehouse.build`, gitignored). It is loaded from the
**simulated** dataset in `core/model.py` (fixed seed): a fictional firm, clients, matters and invoices. DDL:
[`warehouse/schema.sql`](../warehouse/schema.sql). Column-level detail and the source-to-target mapping:
[DATA_DICTIONARY.md](DATA_DICTIONARY.md).

```mermaid
erDiagram
    dim_date ||--o{ fact_invoice : "issue / due / paid"
    dim_date ||--o{ dim_matter : "opened / closed"
    dim_date ||--o{ fact_attorney_month : "month"
    dim_date ||--o{ fact_time_by_area : "month"
    dim_date ||--o{ fact_monthly_pnl : "month"
    dim_date ||--o{ fact_monthly_snapshot : "month / snapshot date"
    dim_date ||--o{ fact_trust_balance : "month"
    dim_date ||--o{ fact_trust_txn : "transaction date"
    dim_branch ||--o{ dim_attorney : "home branch"
    dim_branch ||--o{ dim_matter : ""
    dim_branch ||--o{ fact_invoice : ""
    dim_practice_area ||--o{ dim_client : "primary area"
    dim_practice_area ||--o{ dim_matter : ""
    dim_practice_area ||--o{ fact_invoice : ""
    dim_practice_area ||--o{ fact_time_by_area : ""
    dim_attorney ||--o{ dim_client : "relationship partner"
    dim_attorney ||--o{ dim_matter : "responsible"
    dim_attorney ||--o{ fact_invoice : ""
    dim_attorney ||--o{ fact_attorney_month : ""
    dim_attorney ||--o{ fact_time_by_area : ""
    dim_client ||--o{ dim_matter : "instructs"
    dim_client ||--o{ fact_invoice : "billed"
    dim_client ||--o{ fact_trust_balance : "holds"
    dim_client ||--o{ fact_trust_txn : ""
    dim_matter ||--|| fact_matter_position : "as-of position"
    dim_scenario ||--o{ fact_monthly_pnl : "Actual / Budget"

    fact_invoice {
        int invoice_key PK
        text invoice_number UK
        int client_key FK
        int practice_area_key FK
        int attorney_key FK
        int branch_key FK
        int issue_date_key FK
        int due_date_key FK
        int paid_date_key FK
        real amount_ex_gst
        real gst_amount
        real amount_total
        int days_to_pay
        int is_paid
    }
    fact_matter_position {
        int matter_key PK
        int as_of_date_key FK
        real estimated_value
        real billed_to_date
        real wip_balance
        real progress_ratio
        int days_open
    }
    fact_attorney_month {
        int attorney_key PK
        int month_start_date_key PK
        real month_fraction_elapsed
        real capacity_hours
        real billable_hours
        real standard_value
        real fees_realised
        real salary_cost
    }
    fact_time_by_area {
        int attorney_key PK
        int practice_area_key PK
        int month_start_date_key PK
        real billable_hours
        real standard_value
        real fees_realised
        real allocated_salary_cost
    }
    fact_monthly_pnl {
        int month_start_date_key PK
        int scenario_key PK
        real fees
        real revenue
        real total_costs
        real operating_profit
    }
    fact_monthly_snapshot {
        int month_start_date_key PK
        real wip_balance
        real cash_balance
        real receivables_incl_gst
        real trust_balance
        int matters_active
    }
    fact_trust_balance {
        int client_key PK
        int month_start_date_key PK
        real closing_balance
    }
    fact_trust_txn {
        int trust_txn_key PK
        int client_key FK
        int txn_date_key FK
        text txn_type
        real amount
    }
    dim_matter {
        int matter_key PK
        text matter_id UK
        int client_key FK
        int practice_area_key FK
        int attorney_key FK
        int branch_key FK
        text status
        int opened_date_key FK
        int closed_date_key FK
    }
    dim_client {
        int client_key PK
        text client_name UK
        int primary_practice_area_key FK
        int relationship_attorney_key FK
        text country
        int has_trust_account
    }
    dim_attorney {
        int attorney_key PK
        text attorney_short UK
        int home_branch_key FK
        real bill_rate
        real pay_rate
    }
    dim_branch {
        int branch_key PK
        text branch_name UK
    }
    dim_practice_area {
        int practice_area_key PK
        text practice_area UK
    }
    dim_scenario {
        int scenario_key PK
        text scenario_name UK
    }
    dim_date {
        int date_key PK
        text full_date UK
        text fy_label
    }
```

(Keys and principal attributes only; every column is listed in the data dictionary.)

## Grain

| Table | Type | Grain (one row per...) | Business key | Surrogate / primary key |
|---|---|---|---|---|
| `fact_invoice` | Transaction fact | invoice | `invoice_number` | `invoice_key` |
| `fact_matter_position` | Periodic snapshot fact | matter, as at the as-of date | `matter_id` | `matter_key` |
| `fact_attorney_month` | Periodic snapshot / accumulating-style fact | attorney per active month | attorney + month | (`attorney_key`, `month_start_date_key`) |
| `fact_time_by_area` | Fact | attorney x practice area x active month | attorney + area + month | composite PK |
| `fact_monthly_pnl` | Periodic snapshot fact | month x scenario (Actual / Budget) | month + scenario | composite PK |
| `fact_monthly_snapshot` | Periodic snapshot fact | month (stock balances at month end / as-of date) | month | `month_start_date_key` |
| `fact_trust_balance` | Periodic snapshot fact | client trust ledger x month | client + month | composite PK |
| `fact_trust_txn` | Transaction fact | trust deposit or disbursement | none in source | `trust_txn_key` |
| `dim_matter` | Dimension | matter | `matter_id` (names are NOT unique) | `matter_key` |
| `dim_client` | Dimension | client | `client_name` | `client_key` |
| `dim_attorney` | Dimension | fee earner | `attorney_short` | `attorney_key` |
| `dim_branch`, `dim_practice_area`, `dim_scenario` | Dimensions | office / practice area / scenario | name | integer key |
| `dim_date` | Date dimension | calendar day, contiguous, with Australian financial-year attributes | `full_date` | `date_key` = yyyymmdd |

## Design decisions

* **Pro-rated flows.** Flow measures for the month containing the as-of date are stored as observed-to-date (`x month_fraction_elapsed`), so SUMs reconcile to the app. Stocks are point-in-time. Ratios (utilisation, realisation) are unaffected.
* **Additivity.** Hours, values, fees and costs are additive across attorneys, areas and months. Snapshot stocks (`wip_balance`, `trust_balance`, `matters_active`, `receivables_incl_gst`) are semi-additive: never sum them across months. `month_fraction_elapsed`, ratios and `progress_ratio` are non-additive.
* **Scenario dimension.** Actual and Budget share one fact table keyed by `scenario_key`, so variance is a pivot in SQL rather than a join across two tables.
* **Allocated cost is derived.** `allocated_salary_cost` splits salary by hours share. It supports practice-area contribution analysis; overheads are deliberately not allocated.
* **Role-playing dates.** `dim_date` is joined as issue, due, paid, opened, closed and snapshot dates; the role is in the key column name.
* **Nullable keys instead of sentinel rows** for dates that genuinely do not exist yet (unpaid invoice, open matter); the quality suite checks NULL occurs if and only if the lifecycle state says so.
* **Type-1 dimensions.** The simulator holds one current row per entity, so changes over time (rate rises, matter reassignment) are not tracked. A real implementation would use type-2 rows for rates and matter ownership.
* **Integrity.** Foreign keys are enforced at load and verified with `PRAGMA foreign_key_check`; CHECK constraints guard flags, status, amounts and ratios; indexes cover fact foreign keys and the date columns used in the queries.
* **Lineage / audit.** `etl_meta` records the origin (SIMULATED), seed, as-of date and currency; `etl_load_audit` records the row count loaded into each table.

## Pipeline

```mermaid
flowchart LR
    gen["core/model.py<br/>build_model() - fixed seed"] --> ext["warehouse/build.py<br/>extract()"]
    ext --> tr["transform()<br/>keys, pro-rating, wide-to-long,<br/>scenario stacking, date spine"]
    tr --> ld["load()<br/>schema.sql DDL, FK-ordered bulk insert,<br/>foreign_key_check"]
    ld --> db[("warehouse.db<br/>(gitignored)")]
    db --> dq["warehouse/quality.py<br/>docs/DATA_QUALITY.md"]
    db --> sql["sql/analysis/*.sql<br/>sql/run_queries.py"]
    sql --> csv["docs/query_results/*.csv"]
```
