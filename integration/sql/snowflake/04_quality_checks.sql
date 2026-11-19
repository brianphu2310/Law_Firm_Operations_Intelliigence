-- QUALITY CHECKS (Snowflake): every row should return failures = 0.
use database law_firm;
select 'No duplicate invoices after de-duplication' as check_name, count(*) - count(distinct invoice_uid) as failures from staging.stg_invoices
union all select 'Invoice total = subtotal + GST (10%)',
       count_if(abs(total_amount - subtotal - total_tax) > 0.005 or abs(total_tax - round(subtotal * 0.1, 2)) > 0.005) from staging.stg_invoices
union all select 'Invoice subtotal = sum of its lines', count_if(abs(i.subtotal - l.s) > 0.005)
from staging.stg_invoices i join (select invoice_uid, sum(line_amount_ex_gst) s from staging.stg_invoice_lines group by 1) l on l.invoice_uid = i.invoice_uid
union all select 'Balance due = total - payments applied', count_if(abs(i.total_amount - coalesce(p.p, 0) - i.balance_due) > 0.005)
from staging.stg_invoices i left join (select invoice_uid, sum(amount_applied) p from staging.stg_payment_allocations group by 1) p on p.invoice_uid = i.invoice_uid
union all select 'Closed invoices have zero balance, open ones a positive balance', count_if((status = 'Closed') <> (balance_due = 0)) from staging.stg_invoices
union all select 'Every invoice links to a known client', count_if(c.customer_uid is null)
from staging.stg_invoices i left join staging.stg_customers c on c.customer_uid = i.customer_uid
union all select 'No payment dated before its invoice', count_if(p.payment_date < i.invoice_date)
from staging.stg_payment_allocations p join staging.stg_invoices i on i.invoice_uid = p.invoice_uid
union all select 'Practice-management invoices (LEAP, then triConvey) = MYOB invoices (number and total)', count_if(result <> 'Matched') from marts.invoice_sync_recon
union all select 'Every invoice belongs to a matter', count_if(m.matter_number is null)
from staging.stg_pms_invoices i left join (select matter_number from staging.stg_leap_matters union select matter_number from staging.stg_tc_matters) m on m.matter_number = i.matter_number
union all select 'Every supplier order (InfoTrack and TriSearch) references a known matter', count_if(matter_number is null) from marts.supplier_disbursement_recon
union all select 'Every PEXA workspace references a LEAP matter', count_if(m.matter_number is null)
from staging.stg_pexa_workspaces w left join staging.stg_leap_matters m on m.matter_number = w.matter_number
union all select 'No order dated before TriSearch went live is a TriSearch order', count_if(ordered_date < (select go_live from staging.stg_cutover)) from staging.stg_trisearch_orders
union all select 'Land title search lines carry the NSW LRS registry fee ($16.36 ex GST)',
       count_if(service = 'Land Title Search' and registry_fee_ex_gst is distinct from 16.36) from staging.stg_supplier_orders
union all select 'Nothing in LEAP is dated after the final collection', count_if(l.issue_date > c.final_collection)
from staging.stg_leap_invoices l, staging.stg_cutover c
-- reconciliation targets from the dashboard (docs/PIPELINE_QUALITY.md): receivables at 17 Sep 2025 = $1,053,551.51
union all select 'Receivables at report date = $1,053,551.51', iff(abs((select sum(balance_due) from marts.aged_receivables) - 1053551.51) > 0.005, 1, 0);


-- Cut-over findings (expected: M-2024-0209 not migrated, M-2024-0277 duplicated, Advisory -> General, INV-1021 GST dropped,
-- Global Trust Bank opening -5,799.21, August r48 ledgers -5,799.21 off the cash book, 22 supplier lines)
select * from marts.migration_exceptions order by kind, reference;
