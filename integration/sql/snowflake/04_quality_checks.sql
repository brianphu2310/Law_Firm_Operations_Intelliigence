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
-- reconciliation targets from the dashboard (docs/PIPELINE_QUALITY.md): receivables at 17 Sep 2025 = $1,053,551.51
union all select 'Receivables at report date = $1,053,551.51', iff(abs((select sum(balance_due) from marts.aged_receivables) - 1053551.51) > 0.005, 1, 0);
