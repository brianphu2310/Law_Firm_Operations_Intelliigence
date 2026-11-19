-- MARTS (DuckDB): business-ready tables for the dashboard, Excel / Power Query.
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

-- ------------------------------------------------------------------------------------------------------------------
-- Cross-system reconciliations
-- ------------------------------------------------------------------------------------------------------------------
-- Every invoice raised in LEAP (until the final collection) or in triConvey (after go-live) must reach MYOB with the same total
create or replace view marts.invoice_sync_recon as
select coalesce(l.invoice_number, m.invoice_number) as invoice_number, l.matter_number, coalesce(l.client_name, c.customer_name) as client_name,
       l.system as pms_system, l.total as leap_total, m.total_amount as myob_total,
       case when m.invoice_uid is null then 'Missing in MYOB'
            when l.invoice_number is null then 'Missing in practice management'
            when l.total <> m.total_amount then 'Amount differs'
            else 'Matched' end as result
from staging.stg_pms_invoices l
full outer join staging.stg_invoices m on m.invoice_number = l.invoice_number
left join staging.stg_customers c on c.customer_uid = m.customer_uid;

-- Cut-over: every matter active in LEAP at the final collection should appear exactly once in triConvey
create or replace view marts.migration_recon as
with leap_active as (select * from staging.stg_leap_matters where status in ('Open', 'On Hold')),
     tc as (select matter_number, count(*) as copies from staging.stg_tc_matters where origin = 'Migrated' group by 1)
select coalesce(l.matter_number, tc.matter_number) as matter_number, l.client_name, l.practice_area, l.status as leap_status,
       coalesce(tc.copies, 0) as triconvey_copies,
       case when l.matter_number is null then 'Unexpected in triConvey'
            when tc.copies is null then 'Not migrated'
            when tc.copies > 1 then 'Duplicated'
            else 'Migrated' end as outcome
from leap_active l full outer join tc on tc.matter_number = l.matter_number;

-- Matter types: an unmapped type silently becomes 'General'. One row per LEAP practice area, active matters only
create or replace view marts.matter_type_mapping_recon as
with m as (select distinct l.matter_number, l.practice_area, t.matter_type
           from staging.stg_leap_matters l join staging.stg_tc_matters t on t.matter_number = l.matter_number and t.origin = 'Migrated'
           where l.status in ('Open', 'On Hold'))
select practice_area, count(*) as matters, sum(case when matter_type = practice_area then 1 else 0 end) as same_type,
       sum(case when matter_type = 'General' and practice_area <> 'General' then 1 else 0 end) as fell_to_general,
       case when sum(case when matter_type = 'General' and practice_area <> 'General' then 1 else 0 end) > 0 then 'No matter-type mapping' else 'Mapped' end as result
from m group by 1;

-- Receivables: every invoice outstanding in LEAP at the final collection should arrive in triConvey with the same total
create or replace view marts.ar_migration_recon as
select l.invoice_number, l.matter_number, l.client_name, l.total as leap_total, t.total as triconvey_total,
       coalesce(t.total, 0) - l.total as difference,
       case when t.invoice_number is null then 'Not migrated'
            when abs(t.total - l.total) < 0.005 then 'Matched' else 'Amount differs' end as result
from staging.stg_leap_invoices l
left join staging.stg_tc_invoices t on t.invoice_number = l.invoice_number and t.origin = 'Migrated'
where l.status = 'Outstanding';

-- Trust: opening balances per client, LEAP at the final collection vs what the firm keyed into triConvey
create or replace view marts.trust_migration_recon as
select coalesce(l.client_name, t.client_name) as client_name, l.balance as leap_balance, t.balance as triconvey_balance,
       coalesce(t.balance, 0) - coalesce(l.balance, 0) as difference,
       case when abs(coalesce(t.balance, 0) - coalesce(l.balance, 0)) < 0.005 then 'Matched' else 'Difference' end as result
from staging.stg_leap_trust l full outer join staging.stg_tc_trust t on t.client_name = l.client_name;

-- Trust: the month-end reconciliation that straddles both systems (Uniform General Rules r48): two statements, one deadline
create or replace view marts.trust_r48_status as
select r.period_end, r.due_date, (select as_at from staging.stg_report_date) as as_at, r.status,
       r.bank_balance, r.unpresented_cheques, r.deposits_not_banked, r.cash_book_balance, r.ledger_total, r.ledgers_listed,
       r.bank_balance - r.unpresented_cheques + r.deposits_not_banked - r.cash_book_balance as bank_vs_cash_book,
       r.ledger_total - r.cash_book_balance as ledgers_vs_cash_book,
       case when abs(r.bank_balance - r.unpresented_cheques + r.deposits_not_banked - r.cash_book_balance) < 0.005 then 'Balances' else 'Does not balance' end as statement_1_bank,
       case when abs(r.ledger_total - r.cash_book_balance) < 0.005 then 'Balances' else 'Does not balance' end as statement_2_ledgers
from staging.stg_tc_trust_recon r;

-- Search suppliers: one row per supplier order in the cut-over window, matched to the disbursement the practice-management system holds
create or replace view marts.supplier_disbursement_recon as
with window_start as (select min(disb_date) as d from staging.stg_leap_disbursements),
     sup as (select s.*, regexp_replace(upper(s.matter_ref), '[^A-Z0-9]', '', 'g') as ref_key
             from staging.stg_supplier_orders s, window_start w where s.ordered_date >= w.d),
     matters as (select distinct matter_number, regexp_replace(upper(matter_number), '[^A-Z0-9]', '', 'g') as ref_key from
                 (select matter_number from staging.stg_leap_matters union select matter_number from staging.stg_tc_matters)),
     pms as (select supplier_order_ref, count(*) as pms_lines, sum(amount_ex_gst) as pms_amount, min(matter_number) as pms_matter,
                    min(system) as pms_system, min(posted_by) as posted_by
             from staging.stg_pms_disbursements group by 1)
select s.supplier, s.order_id, s.ordered_date, m.matter_number, s.matter_ref as supplier_reference, s.service, s.fee_ex_gst, s.status as supplier_status,
       p.pms_system, p.posted_by, coalesce(p.pms_lines, 0) as pms_lines, p.pms_amount,
       case when p.pms_lines is null and s.supplier = 'InfoTrack' and s.status <> 'Complete' then 'Timing: order not yet complete'
            when p.pms_lines is null then 'On supplier feed, not in ledger'
            when p.pms_lines > 1 then 'Duplicate in ledger'
            when abs(p.pms_amount - s.fee_ex_gst) > 0.005 then 'Amount differs'
            when p.pms_matter is distinct from m.matter_number then 'Matter differs'
            else 'Matched' end as result,
       case when p.pms_lines is null and s.supplier = 'TriSearch' then 'TriSearch charges at order: check the auto-disbursement setting'
            when p.pms_lines is null and s.supplier = 'InfoTrack' and s.ordered_date > (select final_collection from staging.stg_cutover) then 'Ordered after LEAP froze: needs re-keying'
            when s.matter_ref <> m.matter_number then 'Supplier reference typed differently'
            when p.posted_by = 'Manual entry' and abs(p.pms_amount - s.fee_ex_gst) > 0.005 then 'Manual entry'
            else null end as likely_cause
from sup s
left join matters m on m.ref_key = s.ref_key
left join pms p on p.supplier_order_ref = s.order_id;

-- Supplier switch in one table: orders and cost per search by month and supplier
create or replace view marts.supplier_switch_summary as
select date_trunc('month', ordered_date)::date as month, supplier, count(*) as orders, sum(fee_ex_gst) as fees_ex_gst,
       round(avg(fee_ex_gst) filter (where service = 'Land Title Search'), 2) as avg_land_title_fee,
       round(avg(service_fee_ex_gst) filter (where service = 'Land Title Search'), 2) as avg_land_title_service_fee
from staging.stg_supplier_orders
where ordered_date >= (select min(disb_date) from staging.stg_leap_disbursements) - interval 3 month
group by 1, 2;

-- Disbursements by matter: search orders from BOTH suppliers + PEXA workspace fees, against the matter (LEAP or triConvey)
create or replace view marts.disbursements_by_matter as
with it as (select regexp_replace(upper(matter_ref), '[^A-Z0-9]', '', 'g') as ref_key, count(*) as searches, sum(fee_ex_gst) as search_fees
            from staging.stg_supplier_orders group by 1),
     px as (select matter_number, count(*) as workspaces, sum(pexa_fee) as pexa_fees from staging.stg_pexa_workspaces group by 1),
     m as (select matter_number, any_value(client_name) as client_name from staging.stg_pms_matters group by 1)
select m.matter_number, m.client_name, l.practice_area, l.status,
       coalesce(it.searches, 0) as searches, coalesce(it.search_fees, 0) as search_fees,
       coalesce(px.workspaces, 0) as pexa_workspaces, coalesce(px.pexa_fees, 0) as pexa_fees,
       coalesce(it.search_fees, 0) + coalesce(px.pexa_fees, 0) as total_disbursements
from m
left join staging.stg_leap_matters l on l.matter_number = m.matter_number
left join it on it.ref_key = regexp_replace(upper(m.matter_number), '[^A-Z0-9]', '', 'g')
left join px on px.matter_number = m.matter_number
where it.ref_key is not null or px.matter_number is not null;

-- One row per cut-over finding, for the exceptions log
create or replace view marts.migration_exceptions as
select 'Matter' as kind, matter_number as reference, client_name, outcome as finding, null::decimal(14,2) as amount
from marts.migration_recon where outcome <> 'Migrated'
union all
select 'Matter type', practice_area, practice_area, fell_to_general || ' matter(s) defaulted to General', null
from marts.matter_type_mapping_recon where result <> 'Mapped'
union all
select 'Invoice', invoice_number, client_name, result, difference from marts.ar_migration_recon where result <> 'Matched'
union all
select 'Trust balance', client_name, client_name, 'Opening balance differs from LEAP', difference
from marts.trust_migration_recon where result <> 'Matched'
union all
select 'Trust reconciliation', 'r48 ' || strftime(period_end, '%b %Y'), null, 'Ledgers do not balance to the cash book', ledgers_vs_cash_book
from marts.trust_r48_status where statement_2_ledgers <> 'Balances'
union all
select 'Disbursement', supplier || ' ' || order_id, matter_number, result, fee_ex_gst
from marts.supplier_disbursement_recon where result not in ('Matched');
