# User acceptance testing

**Entry criteria:** final collection done, triConvey test migration loaded, pipeline run complete
(`python -m integration.quality`). **Exit criteria:** every *Must* test passes, or each failure is logged in the
exceptions log with an owner, a fix date and the sponsor's written acceptance.

The **expected result** column is what a clean migration should give. The **result on sample data** column is what this
repository's simulated cut-over actually gives. The defects were planted so the tests have something to find, which is why
several tests fail on purpose.

| ID | Req | Test | Expected result | Result on sample data | Status | Evidence |
|---|---|---|---|---|---|---|
| UAT-01 | BR-01 | Compare active LEAP matters at freeze with triConvey matters | Every matter present | M-2024-0209 not migrated | **Fail** → logged | `marts.migration_recon` |
| UAT-02 | BR-01 | Look for matters present more than once in triConvey | None | M-2024-0277 duplicated | **Fail** → logged | `marts.migration_recon` |
| UAT-03 | BR-02 | Matter types that fell to "General" | None | 12 Advisory matters | **Fail** → logged | `marts.matter_type_mapping_recon` |
| UAT-04 | BR-03 | Open invoice amounts before vs after, incl. GST | $0.00 difference | 1 invoice −$3,135.99 (GST dropped) | **Fail** → logged | `marts.ar_migration_recon` |
| UAT-05 | BR-04 | LEAP + triConvey invoices vs MYOB | All match | 472 / 472 | Pass | `marts.invoice_sync_recon` |
| UAT-06 | BR-05 | LEAP closing vs triConvey opening trust balance per client | $0.00 for every client | Global Trust Bank −$5,799.21 | **Fail** → logged | `marts.trust_migration_recon` |
| UAT-07 | BR-06 | August r48 statement 1 (bank vs cash book) | Balances | Balances | Pass | `marts.trust_r48_status` |
| UAT-08 | BR-06 | August r48 statement 2 (ledgers vs cash book) | Balances | $5,799.21 off, 2 working days left | **Fail** → logged | `marts.trust_r48_status`, Transition page |
| UAT-09 | BR-07 | Any client ledger below zero on any day | None | None | Pass | `tests/test_reconciliation.py` |
| UAT-10 | BR-08 | TriSearch orders with no ledger disbursement | None | 18 orders (8–9 Sep, setting off) | **Fail** → logged | `marts.supplier_disbursement_recon` |
| UAT-11 | BR-08 | Buffer-window orders re-keyed by hand | All match | 2 missing, 1 duplicate, 1 keyed with GST | **Fail** → logged | `marts.supplier_disbursement_recon` |
| UAT-12 | BR-09 | References re-typed with different spacing or case | Still matched | 2 matched after normalising | Pass | `tests/test_transition.py` |
| UAT-13 | BR-10 | Records dated across the freeze in the wrong system | None | None | Pass | `tests/test_integration_pipeline.py` |
| UAT-14 | BR-11 | Every finding above appears once in the exceptions log | 1 row per finding | 28 rows | Pass | `marts.migration_exceptions` |
| UAT-15 | BR-12 | Force an API/loaded count mismatch | Load is stopped and recorded | Recorded, not loaded | Pass | `tests/test_integration_pipeline.py` |
| UAT-16 | BR-13 | A partner opens the Transition page without help | Sees r48 clock, matters, suppliers, exceptions | All four tabs render | Pass | `views/transition.py` |

## Result summary

| | Count |
|---|---|
| Tests | 16 |
| Pass | 8 |
| Fail, logged with owner (planted defects) | 8 |
| Findings in the exceptions log | 28 (2 matter, 1 matter type, 1 invoice, 1 trust balance, 1 trust reconciliation, 22 disbursement) |

**Recommendation on the sample data: no-go for sign-off until UAT-06 and UAT-08 are closed.** The trust gap is the only
finding with a regulatory deadline (19 Sep 2025). The matter, invoice and disbursement findings can be fixed after
go-live because none of them breaches a rule, but each has an owner in the runbook.
