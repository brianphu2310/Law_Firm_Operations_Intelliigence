# Business requirements: cut-over reconciliation and exceptions control

| | |
|---|---|
| **Change** | Practice management LEAP → triConvey (Smokeball); search supplier InfoTrack → TriSearch |
| **Cut-over** | LEAP frozen Fri 29 Aug 2025 · buffer Mon 1 Sep · go-live Tue 2 Sep 2025 (hard cut-over, no dual running) |
| **Hard deadline** | August trust reconciliation (r48) due **Fri 19 Sep 2025**, 15 working days after month end |
| **Sponsor** | Principal / Managing Partner (see [STAKEHOLDERS.md](STAKEHOLDERS.md)) |
| **Status** | Simulated project; requirements delivered and tested in this repository |

## 1. Problem statement

The vendor migrates active matters, unpaid invoices and **hand-keyed** trust opening balances. It does not migrate paid
invoices, the general ledger or trust history, and it does not check the firm's month-end obligations. August straddles
both systems (LEAP holds 1–29 Aug, triConvey holds 2–31 Aug), so the August r48 statements **cannot come from one
system**, and nobody's standard migration test covers them.

At the same time, the new search supplier charges matters at a different point (when an order is *placed*, and only if
an auto-disbursement setting is ticked) from the old one (when an order *completes*). Disbursements can therefore go
missing or double up across the switch without anyone noticing until a client is under-billed.

**Business impact if unmanaged:** an unbalanced trust reconciliation is a regulatory breach that must be reported; a
client ledger in debit is a breach from the first dollar (r40(2)); missed disbursements are revenue the firm pays for and
never recovers.

## 2. Objectives and success measures

| # | Objective | Measure | Target |
|---|---|---|---|
| O1 | Prove the migration is complete | Active matters in LEAP at freeze vs matters in triConvey | 100% matched, 0 duplicates |
| O2 | Keep revenue and receivables intact | LEAP + triConvey invoices vs MYOB; open AR before vs after | 472 / 472 matched; AR difference $0.00 |
| O3 | Lodge a balanced August r48 reconciliation on time | Statement 1 (bank) and statement 2 (ledgers) both reconcile to the cash book | $0.00 difference by 19 Sep 2025 |
| O4 | Bill every search to the right matter | Supplier orders vs ledger disbursements | Every order matched or explained |
| O5 | Give the team one list of what to fix | Findings in the exceptions log with owner and due date | 100% of findings logged and assigned |

## 3. Scope

**In scope:** matters, matter-type mapping, open invoices and AR, trust opening balances and the August r48 statements,
search-supplier disbursements for August and September 2025, the exceptions log, the cut-over checks in the pipeline and
the app's Transition page.

**Out of scope:** document migration, staff training, data conversion of closed matters and paid invoices (they stay in
LEAP as the record, retained for seven years under s147), supplier refunds and GST variances on supplier invoices
(listed as not simulated in [TRANSITION.md](../TRANSITION.md)).

## 4. Assumptions and constraints

| Type | Item |
|---|---|
| Constraint | No dual running: once LEAP is frozen, anything entered after the final collection is not migrated |
| Constraint | Trust records must stay computerised, auditable and backed up (r38–41) |
| Assumption | TriSearch's service fee is 34/38 of InfoTrack's; vendors do not publish it (`TRISEARCH_FEE_RATIO` in `core/transition.py`) |
| Assumption | Neither LEAP nor TriSearch publishes an open API; the API shapes in the mock are illustrative |
| Dependency | MYOB stays the general ledger before and after the change; its invoice list is the control total |

## 5. Business requirements and traceability

| ID | Requirement | Priority | Delivered by | Verified by |
|---|---|---|---|---|
| BR-01 | Every active LEAP matter at the freeze must exist exactly once in triConvey | Must | `marts.migration_recon` | UAT-01, UAT-02 |
| BR-02 | Every matter type must map to a triConvey type; unmapped types defaulting to "General" must be flagged | Must | `marts.matter_type_mapping_recon` | UAT-03 |
| BR-03 | Every open invoice must carry over with the same amount including GST | Must | `marts.ar_migration_recon` | UAT-04 |
| BR-04 | LEAP + triConvey invoices must equal MYOB invoices | Must | `marts.invoice_sync_recon` | UAT-05 |
| BR-05 | Each client's trust opening balance in triConvey must equal the LEAP closing balance | Must | `marts.trust_migration_recon` | UAT-06 |
| BR-06 | Both August r48 statements must reconcile, and the app must show working days left to the deadline | Must | `marts.trust_r48_status`, Transition page → Trust (r48) | UAT-07, UAT-08 |
| BR-07 | No client trust ledger may go into debit at any point | Must | `test_trust_ledgers_never_negative_and_match_transactions` | UAT-09 |
| BR-08 | Every search order (InfoTrack and TriSearch) must match a ledger disbursement, or be classified by cause | Must | `marts.supplier_disbursement_recon` | UAT-10, UAT-11 |
| BR-09 | Supplier references re-typed with different spacing or case must still match | Should | Reference normalisation in `core/transition.py` | UAT-12 |
| BR-10 | Nothing may be dated after the freeze in LEAP, or before go-live in triConvey | Must | `test_nothing_is_dated_across_the_freeze_in_the_wrong_system` | UAT-13 |
| BR-11 | All findings must land in one exceptions log with kind, reference and amount | Must | `marts.migration_exceptions`, Transition page → Exceptions log | UAT-14 |
| BR-12 | The daily load must stop, not load silently, when API counts and loaded counts differ | Must | n8n workflow, `test_count_mismatch_is_recorded_not_loaded_silently` | UAT-15 |
| BR-13 | Partners must be able to see the cut-over status without opening SQL | Should | Transition page (r48 clock, four tabs) | UAT-16 |

## 6. Non-functional requirements

| ID | Requirement | How it is met |
|---|---|---|
| NFR-01 | Vendor APIs are reached with least privilege | OAuth 2.0 client credentials, per-resource scopes ([AUTH.md](../AUTH.md)) |
| NFR-02 | No secrets in the repository | `test_secrets_are_never_committed` |
| NFR-03 | The same checks give the same answer on every platform | DuckDB, Snowflake and Excel Power Query all return the same 28 findings |
| NFR-04 | Re-running the load is safe | Incremental watermarks and de-duplication in staging (`test_incremental_load_only_pulls_changes_and_staging_deduplicates`) |

## 7. Sign-off

| Role | Signs off on |
|---|---|
| Principal / Managing Partner | Scope, go / no-go, acceptance of residual risk |
| Trust Account Manager | BR-05 to BR-07 (trust) |
| Finance / Accounts Officer | BR-03, BR-04, BR-08 (revenue, AR, disbursements) |
| Practice Manager | BR-01, BR-02, BR-13 (matters, reporting) |
