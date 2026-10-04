# Skills demonstrated

Where each data analyst / data engineer skill is shown in this repository. Every path exists and is covered by tests.
All data is simulated (fixed seed); the skills are real, the dataset is not.

| Skill | Evidence |
|---|---|
| **SQL: CTEs, joins, CASE** | all ten queries in [`sql/analysis/`](../sql/analysis), e.g. `sql/analysis/07_receivables_ageing_by_client.sql` |
| **SQL: window functions** (RANK, LAG, NTILE, PERCENT_RANK, running totals, moving-average frames, share-of-total) | `sql/analysis/01_utilisation_by_attorney.sql`, `sql/analysis/03_realisation_trend.sql` (ratio of rolling sums), `sql/analysis/06_client_concentration.sql` (cumulative share and HHI), `sql/analysis/08_payment_behaviour_by_client.sql` (LAG by client, NTILE), `sql/analysis/10_trust_account_balances.sql` |
| **SQL: pivots and variance analysis** | `sql/analysis/09_pnl_actual_vs_budget.sql` (conditional aggregation over scenario rows, FY-to-date variance) |
| **Law-firm operations analytics** (utilisation, WIP, realisation, receivables, concentration, trust) | `sql/analysis/01_utilisation_by_attorney.sql`, `sql/analysis/02_wip_by_matter_age.sql`, `sql/analysis/03_realisation_trend.sql`, `sql/analysis/04_practice_area_profitability.sql`, `sql/analysis/07_receivables_ageing_by_client.sql`, `sql/analysis/10_trust_account_balances.sql` |
| **Dimensional modelling** (star schema, grain, surrogate keys, scenario dimension, role-playing dates, snapshot facts) | `warehouse/schema.sql`, `docs/DATA_MODEL.md` |
| **Data mapping** (source-to-target, transformation rules, wide-to-long, pro-rating) | `docs/DATA_DICTIONARY.md`, `warehouse/build.py` |
| **ETL / pipeline design** (extract, transform, load; idempotent rebuild; audit tables) | `warehouse/build.py` (`extract`, `transform`, `load`, `etl_load_audit`, `etl_meta`) |
| **Data quality** (completeness, uniqueness, referential integrity, validity, reconciliation to app metrics, informational observations) | `warehouse/quality.py`, `docs/DATA_QUALITY.md` |
| **Constraints and performance** (PK/FK/CHECK/UNIQUE, indexes, query-plan test) | `warehouse/schema.sql`, `tests/test_warehouse.py` |
| **Testing** (unit, integration, fault injection, doc-drift and output-freshness tests) | `tests/test_warehouse.py`, `tests/test_sql_queries.py`, `tests/test_docs.py`, plus the app's `tests/test_reconciliation.py` |
| **CI** (tests plus warehouse build, DQ suite and queries on every push) | `.github/workflows/ci.yml` |
| **Reproducibility** (fixed seed, deterministic outputs, committed result files) | `core/model.py`, `docs/query_results/03_realisation_trend.csv` |
| **Python / pandas / NumPy** | `warehouse/build.py`, `core/model.py`, `core/metrics.py` |
| **Dashboarding / BI** | `app.py`, `core/metrics.py` (Streamlit, Plotly) |
| **Financial analysis** (P&L vs budget, working capital, cash, FY outlook) | `core/metrics.py`, `docs/METHODOLOGY.md`, `sql/analysis/09_pnl_actual_vs_budget.sql` |
| **Documentation** | `README.md`, `docs/ARCHITECTURE.md`, `docs/DATA_MODEL.md` |

## Not claimed

* No real data, no API or web ingestion, no production database or cloud warehouse: the target is SQLite on simulated data.
* No orchestration tool (Airflow, dbt, etc.); the pipeline is a plain Python module run from the command line and CI.
* No time-entry or per-matter cost data in the simulation, so WIP ageing is by matter age and "matter profitability" is billing performance against estimated value; profitability with cost is at practice-area level using an hours-based salary allocation.
* Dimensions are type 1 (no history); a type-2 design is described but not faked.
