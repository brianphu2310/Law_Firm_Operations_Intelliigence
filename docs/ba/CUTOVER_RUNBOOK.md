# Cut-over runbook

Dates follow the sample data. Owners use the roles in [STAKEHOLDERS.md](STAKEHOLDERS.md).

## Timeline

| When | Step | Owner | Done when |
|---|---|---|---|
| T−10 working days | Agree matter-type mapping, including Advisory | Practice Manager | Every LEAP type has a triConvey type (avoids UAT-03) |
| T−5 | Test migration loaded; run the pipeline and UAT | Business Analyst | UAT results circulated |
| T−2 | Go / no-go meeting on the test migration | Principal | Decision recorded |
| **Fri 29 Aug, 5pm** | **Final collection: LEAP frozen.** No receipts, invoices or matters after this time | Practice Manager | Vendor confirms extract |
| Fri 29 Aug, 5pm | Export LEAP trust closing balances per client as the control list | Trust Account Manager | Signed list saved |
| Mon 1 Sep (buffer) | Log every search order and receipt taken today on paper / spreadsheet | All staff | Log handed to Finance |
| Mon 1 Sep | Vendor keys trust opening balances | Vendor | Keyed |
| **Tue 2 Sep** | **Go-live.** triConvey live; TriSearch is the only search supplier | Principal | Staff told |
| Tue 2 Sep, 10am | Check "Automatically create a disbursement for each order" is ticked for every user | Finance Officer | Screenshot per user (prevents UAT-10) |
| Tue 2 Sep | Re-key buffer-day log; run pipeline; compare opening balances to the control list | Finance Officer, Trust Account Manager | UAT-06 at $0.00 |
| Daily to 30 Sep | n8n load at 6am; review new rows in the exceptions log | Business Analyst | Log reviewed, owners told |
| **Fri 19 Sep** | **August r48 statements signed and filed** | Trust Account Manager | Both statements balance |
| Mon 6 Oct | Post-cut-over review; close or accept every open finding | Principal | Log closed |

## Go / no-go criteria

| Criterion | Threshold | Blocks go-live? |
|---|---|---|
| Trust opening balances vs LEAP closing | $0.00 per client | **Yes** |
| Active matters migrated | 100%, no duplicates | No (fix within 5 working days) |
| Open invoices including GST | $0.00 difference | No (fix before the next billing run) |
| Matter types mapped | 100% | No (re-type within 5 working days) |
| Supplier disbursements | Every order matched or explained | No (daily recon) |

## Rollback

There is no dual running, so rollback means **un-freezing LEAP** and abandoning the triConvey load. It is only possible
before any receipt, invoice or trust transaction is entered in triConvey (in practice, before 9am on go-live day). After
that, the only path is forward: fix through the exceptions log.

| Trigger | Action |
|---|---|
| Trust opening balances do not tie and the cause is not found by 9am on go-live | Principal decides: delay go-live by one day, keep LEAP live |
| Vendor extract incomplete (matter count short by more than 1%) | Delay go-live; vendor re-runs the final collection |
| After go-live | No rollback; findings go to the exceptions log with an owner and a due date |

## Exceptions log, worked example (sample data)

| Finding | Kind | Owner | Fix | Due |
|---|---|---|---|---|
| Global Trust Bank opening balance $5,799.21 short | Trust balance | Trust Account Manager | Journal the receipt posted after the extract; re-run statement 2 | 18 Sep 2025 |
| August statement 2 off by $5,799.21 | Trust reconciliation | Trust Account Manager | Clears with the fix above | 19 Sep 2025 |
| 18 TriSearch orders with no ledger line | Disbursement | Finance Officer | Post disbursements to the matters; tick the setting | 12 Sep 2025 |
| Invoice missing GST (−$3,135.99) | Invoice | Finance Officer | Correct the carried-over invoice | Next billing run |
| M-2024-0209 not migrated, M-2024-0277 duplicated | Matter | Practice Manager | Create / merge in triConvey | 9 Sep 2025 |
| 12 Advisory matters typed "General" | Matter type | Practice Manager | Re-type; add the mapping | 9 Sep 2025 |
