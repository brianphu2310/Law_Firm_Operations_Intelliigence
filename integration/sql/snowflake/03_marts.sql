-- MARTS (Snowflake): same definitions as integration/sql/duckdb/02_marts.sql.
use database law_firm;

create or replace view marts.revenue_monthly as
select date_trunc('month', invoice_date)::date as month, practice_area,
       sum(line_amount_ex_gst) as revenue_ex_gst, count(distinct invoice_uid) as invoices
from staging.stg_invoice_lines group by 1, 2;

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
join staging.stg_customers c on c.customer_uid = i.customer_uid
cross join staging.stg_report_date r
where i.balance_due > 0 and i.invoice_date <= r.as_at;

create or replace view marts.collection_performance as
with lp as (select invoice_uid, max(payment_date) as paid_date from staging.stg_payment_allocations group by 1)
select i.practice_area,
       count(*)                                    as invoices,
       count_if(i.status = 'Closed')               as fully_paid,
       round(avg(iff(i.status = 'Closed', datediff('day', i.invoice_date, lp.paid_date), null)), 1) as avg_days_to_pay,
       round(100 * count_if(i.status = 'Closed' and lp.paid_date <= i.due_date) / nullif(count_if(i.status = 'Closed'), 0), 1) as pct_paid_on_time,
       sum(i.balance_due)                          as outstanding
from staging.stg_invoices i left join lp on lp.invoice_uid = i.invoice_uid
group by 1;

-- ---------------------------------------------------------------------------------------------------------------------
-- Cross-system reconciliations (same definitions as integration/sql/duckdb/02_marts.sql)
-- ---------------------------------------------------------------------------------------------------------------------
create or replace view marts.invoice_sync_recon as
select coalesce(l.invoice_number, m.invoice_number) as invoice_number, l.matter_number, coalesce(l.client_name, c.customer_name) as client_name,
       l.total as leap_total, m.total_amount as myob_total,
       case when m.invoice_uid is null then 'Missing in MYOB'
            when l.invoice_number is null then 'Missing in LEAP'
            when l.total <> m.total_amount then 'Amount differs'
            else 'Matched' end as result
from staging.stg_leap_invoices l
full outer join staging.stg_invoices m on m.invoice_number = l.invoice_number
left join staging.stg_customers c on c.customer_uid = m.customer_uid;

create or replace view marts.migration_recon as
with leap_active as (select * from staging.stg_leap_matters where status in ('Open', 'On Hold')),
     tc as (select matter_number, count(*) as copies from staging.stg_tc_matters group by 1)
select coalesce(l.matter_number, tc.matter_number) as matter_number, l.client_name, l.practice_area, l.status as leap_status,
       coalesce(tc.copies, 0) as triconvey_copies,
       case when l.matter_number is null then 'Unexpected in triConvey'
            when tc.copies is null then 'Not migrated'
            when tc.copies > 1 then 'Duplicated'
            else 'Migrated' end as outcome
from leap_active l full outer join tc on tc.matter_number = l.matter_number;

create or replace view marts.trust_migration_recon as
select coalesce(l.client_name, t.client_name) as client_name, l.balance as leap_balance, t.balance as triconvey_balance,
       coalesce(t.balance, 0) - coalesce(l.balance, 0) as difference,
       iff(abs(coalesce(t.balance, 0) - coalesce(l.balance, 0)) < 0.005, 'Matched', 'Difference') as result
from staging.stg_leap_trust l full outer join staging.stg_tc_trust t on t.client_name = l.client_name;

create or replace view marts.disbursements_by_matter as
with it as (select matter_number, count(*) as searches, sum(fee_ex_gst) as search_fees from staging.stg_infotrack_orders group by 1),
     px as (select matter_number, count(*) as workspaces, sum(pexa_fee) as pexa_fees from staging.stg_pexa_workspaces group by 1)
select m.matter_number, m.client_name, m.practice_area, m.status,
       coalesce(it.searches, 0) as searches, coalesce(it.search_fees, 0) as search_fees,
       coalesce(px.workspaces, 0) as pexa_workspaces, coalesce(px.pexa_fees, 0) as pexa_fees,
       coalesce(it.search_fees, 0) + coalesce(px.pexa_fees, 0) as total_disbursements
from staging.stg_leap_matters m
left join it on it.matter_number = m.matter_number
left join px on px.matter_number = m.matter_number
where it.matter_number is not null or px.matter_number is not null;

create or replace view marts.migration_exceptions as
select 'Matter' as kind, matter_number as reference, client_name, outcome as finding, null::number(14,2) as amount
from marts.migration_recon where outcome <> 'Migrated'
union all
select 'Trust balance', client_name, client_name, 'Trust balance differs', difference
from marts.trust_migration_recon where result <> 'Matched';
