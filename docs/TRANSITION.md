# The transition: LEAP → triConvey (Smokeball) and InfoTrack → TriSearch

This project models one cut-over in a small NSW law firm: the practice management system changes from **LEAP** to
**triConvey** (Smokeball's conveyancing product) and the search supplier changes from **InfoTrack** to **TriSearch**.
The question the data answers is: *what did the cut-over leave behind, who has to fix it, and by when?*

Everything is simulated. No real firm, client or matter data is used. The rules and mechanics behind the simulation come
from public vendor documentation and NSW legislation. Where a detail is not public it is labelled as an assumption below.

## Timeline used in the model

| Event | Date (sample data) | Source of the rule |
|---|---|---|
| Final data collection (LEAP frozen) | Fri 29 Aug 2025 | Smokeball's migration guide describes a final collection, then a buffer, then go-live |
| Buffer day | Mon 1 Sep 2025 | Anything entered after the final collection is not migrated |
| triConvey go-live, TriSearch becomes the supplier | Tue 2 Sep 2025 | Hard cut-over, not dual running |
| Report date shown in the app | Wed 17 Sep 2025 | The app's fixed "as at" date |
| August trust reconciliation due | Fri 19 Sep 2025 | 15 working days after month end (NSW Uniform General Rules 2015, r48) |

Constants live in [`core/transition.py`](../core/transition.py) and are used by the data generator, the SQL checks and the app.

## What the cut-over does to the data

| Area | Behaviour modelled | Basis |
|---|---|---|
| Staff, contacts, active matters, unbilled WIP, unpaid invoices | Migrate. Legacy matter numbers are kept | Smokeball migration documentation (sourced) |
| Paid invoices, trust and operating history, general ledger, accounts payable | Do **not** migrate. Stay in LEAP as the historical record | Smokeball migration documentation (sourced) |
| Trust balances | Arrive as **hand-keyed opening balances** per client ledger | Smokeball documentation (sourced) |
| Matter types without a mapping | Default to "General" | Smokeball documentation (sourced) |
| Documents | Load later, over several days | Smokeball documentation (sourced) |

## Planted defects (so the reconciliations have something to find)

Each defect is deliberate, generated in [`integration/sources_export.py`](../integration/sources_export.py), and a test
checks that the reconciliations find **exactly** these and nothing else.

| # | Defect | Where it is caught | Basis |
|---|---|---|---|
| 1 | One active matter not migrated | `marts.migration_recon` | Inferred (typical migration miss) |
| 2 | One matter migrated twice | `marts.migration_recon` | Inferred |
| 3 | 12 Advisory matters fall to "General" because the type has no mapping | `marts.matter_type_mapping_recon` | Sourced default, inferred scenario |
| 4 | One open invoice carried over without its GST (−$3,135.99) | `marts.ar_migration_recon` | Inferred |
| 5 | Global Trust Bank opening balance keyed **$5,799.21 short** (a receipt posted in LEAP after the final extract) | `marts.trust_migration_recon` | Inferred |
| 6 | August trust statement 2 (ledgers) is **$5,799.21 off the cash book** while statement 1 (bank) balances | `marts.trust_r48_status` | Rule sourced (r48), scenario inferred |
| 7 | Supplier orders placed in the buffer window, re-keyed by hand: 2 missing, 1 duplicate, 1 amount keyed with GST | `marts.supplier_disbursement_recon` | Inferred |
| 8 | 18 TriSearch orders with no ledger line (auto-disbursement setting off on 8–9 Sep) | `marts.supplier_disbursement_recon` | Mechanism sourced, dates assumed |
| 9 | 2 TriSearch references re-typed differently | Matched after normalising | Inferred |

Total: **28 findings** in `marts.migration_exceptions` (2 matter, 1 matter type, 1 invoice, 1 trust balance,
1 trust reconciliation, 22 disbursement).

## Trust accounting rules used

NSW *Legal Profession Uniform General Rules 2015*:

- **r48**: two statements each month (bank to cash book, and client ledgers to cash book), due 15 working days after month end.
- **r38–41**: computerised trust records, with audit trail and backups.
- **r40(2)**: a client ledger must not go into debit. A $1 overdraw is a breach, and irregularity reporting applies (s154 of the Uniform Law).
- **s147**: seven-year retention of trust records.
- The register of investments is r59. An earlier draft of this project called it "Section 285 investments"; that was wrong and has been removed.
- The Law Society of NSW publishes no guidance specific to a software conversion, so the project does not claim any.

**Why August is the interesting month:** it straddles both systems. LEAP holds 1–29 Aug, triConvey holds 2–31 Aug with hand-keyed
opening balances. The r48 statements therefore cannot come from a single system, and no vendor test migration checks them.

## Search supplier switch

| Mechanic | InfoTrack | TriSearch | Basis |
|---|---|---|---|
| When the matter is charged | When the order **completes** | When the order is **placed**, only if "Automatically create a disbursement for each order" is ticked | Vendor help pages (sourced) |
| Billing | Monthly invoice | Per order | Vendor help pages (sourced) |
| Refunds | Net of a $15 fee, from a US source | Not modelled | InfoTrack terms (sourced), D7 not simulated |
| NSW LRS land title search | $16.36 ex GST ($18.00 inc), FY25/26 | same | NSW LRS fee schedule (sourced) |
| Service fee on top of the registry fee | Not published | Not published | **Assumption:** TriSearch charges 34/38 of InfoTrack's service fee ([`core/transition.py`](../core/transition.py), `TRISEARCH_FEE_RATIO`) |
| API | Illustrative | **No public API documentation.** Response shape (`skip`/`take`/`continuation`) is illustrative | Honest limit |

Reconciliation classes used by the cut-over checks: Matched · Timing · On supplier feed, not in ledger · Duplicate in ledger ·
Amount differs · Matter differs. A timing class exists in SQL for InfoTrack orders not yet complete; no planted case exercises it.

## Sourced, inferred, placeholder

Every scenario in the research report is tagged **S** (sourced), **I** (inferred from how the systems work) or **P**
(placeholder numbers). In this repository:

- **Sourced:** cut-over mechanics, what migrates and what does not, r48 timing, trust rules, NSW search fee, supplier charge-timing mechanics.
- **Inferred:** which specific mistakes happen and how often, the Friday-receipt trust gap, the re-keying errors.
- **Placeholder:** dollar amounts of supplier service fees, the dates the auto-disbursement setting was off, all names and amounts.

The research report with the full scenario list is kept alongside the repo owner's notes, not in this repository.

## Honest limits

- A simulated cut-over. It shows the **method** (what to reconcile, in what order, with what deadline), not what happened at any real firm.
- Not simulated: GST variance on supplier invoices (D8), supplier refunds (D7), document load, staff time and cost of the cut-over.
- Snowflake SQL for the new views has been run on a Snowflake trial account (20 Nov 2026) and returns the same 28 findings as DuckDB.
- The Power Query workbook was refreshed in Excel on the cut-over data and agrees with DuckDB and Snowflake.
- The n8n Cloud workflow, the Render mock API and the Auth0 `trisearch:read` scope are live; one end-to-end run loaded 7,927 records from 16 resources.

## Where to look

| What | File |
|---|---|
| Dates and constants | [`core/transition.py`](../core/transition.py) |
| Data generation and planted defects | [`integration/sources_export.py`](../integration/sources_export.py) |
| Mock TriSearch route | [`integration/mock_api.py`](../integration/mock_api.py) |
| Staging and marts (DuckDB) | [`integration/sql/duckdb/`](../integration/sql/duckdb) |
| Checks and reconciliations | [`integration/quality.py`](../integration/quality.py), [PIPELINE_QUALITY.md](PIPELINE_QUALITY.md) |
| App page | Removed from the dashboard (Nov 2026): the cut-over is now told as the reason the platform evaluation exists; the checks still run in the pipeline |
| Tests | [`tests/test_transition.py`](../tests/test_transition.py), [`tests/test_integration_pipeline.py`](../tests/test_integration_pipeline.py) |
