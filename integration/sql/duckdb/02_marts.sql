-- MARTS (DuckDB): business-ready tables for the dashboard, Excel / Power Query and Metabase.
create schema if not exists marts;

-- Monthly revenue by practice area (ex GST)
create or replace view marts.revenue_monthly as
select date_trunc('month', invoice_date)::date as month, practice_area,
       sum(line_amount_ex_gst) as revenue_ex_gst, count(distinct invoice_uid) as invoices
from staging.stg_invoice_lines group by 1, 2;

-- Open invoices aged by days past due, same buckets as the app's Clients page (core.metrics.ar_ageing)
create or replace view marts.aged_receivables as
select r.as_at, c.customer_code, c.customer_name, i.invoice_number, i.practice_area, i.attorney, i.branch,
       i.invoice_date, i.due_date, i.balance_due,
       datediff('day', i.due_date, r.as_at) as days_past_due,
       case when datediff('day', i.due_date, r.as_at) <= 0  then 'Not yet due'
            when datediff('day', i.due_date, r.as_at) <= 30 then '1–30 days'
            when datediff('day', i.due_date, r.as_at) <= 60 then '31–60 days'
            when datediff('day', i.due_date, r.as_at) <= 90 then '61–90 days'
            else '90+ days' end as ageing_bucket
from staging.stg_invoices i
join staging.stg_customers c using (customer_uid)
cross join staging.stg_report_date r
where i.balance_due > 0 and i.invoice_date <= r.as_at;

-- Collection speed by practice area
create or replace view marts.collection_performance as
with lp as (select invoice_uid, max(payment_date) as paid_date from staging.stg_payment_allocations group by 1)
select i.practice_area,
       count(*)                                                        as invoices,
       count(*) filter (where i.status = 'Closed')                     as fully_paid,
       round(avg(lp.paid_date - i.invoice_date) filter (where i.status = 'Closed'), 1) as avg_days_to_pay,
       round(100.0 * count(*) filter (where i.status = 'Closed' and lp.paid_date <= i.due_date)
             / nullif(count(*) filter (where i.status = 'Closed'), 0), 1) as pct_paid_on_time,
       sum(i.balance_due)                                              as outstanding
from staging.stg_invoices i left join lp using (invoice_uid)
group by 1;
