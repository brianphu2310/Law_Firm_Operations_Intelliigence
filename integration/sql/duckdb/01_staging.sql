-- STAGING (DuckDB): flatten the MYOB JSON and keep only the latest version of each record
-- (incremental loads append new versions to RAW; row_number() picks the newest).
create schema if not exists staging;

create or replace view staging.stg_customers as
select * exclude (rn) from (
    select payload->>'$.UID'                    as customer_uid,
           payload->>'$.DisplayID'              as customer_code,
           payload->>'$.CompanyName'            as customer_name,
           payload->'$.Addresses'->0->>'$.Country' as country,
           row_number() over (partition by record_uid order by last_modified desc, loaded_at desc) as rn
    from raw.myob_customers) where rn = 1;

create or replace view staging.stg_invoices as
select * exclude (rn) from (
    select payload->>'$.UID'                              as invoice_uid,
           payload->>'$.Number'                           as invoice_number,
           (payload->>'$.Date')::timestamp::date          as invoice_date,
           (payload->>'$.Terms.DueDate')::timestamp::date as due_date,
           payload->>'$.Customer.UID'                     as customer_uid,
           payload->'$.Lines'->0->>'$.Job.Name'           as practice_area,
           payload->>'$.Salesperson.Name'                 as attorney,
           payload->>'$.Category.Name'                    as branch,
           (payload->>'$.Subtotal')::decimal(14,2)        as subtotal,
           (payload->>'$.TotalTax')::decimal(14,2)        as total_tax,
           (payload->>'$.TotalAmount')::decimal(14,2)     as total_amount,
           (payload->>'$.BalanceDueAmount')::decimal(14,2) as balance_due,
           payload->>'$.Status'                           as status,
           payload                                        as _payload,
           row_number() over (partition by record_uid order by last_modified desc, loaded_at desc) as rn
    from raw.myob_invoices) where rn = 1;

create or replace view staging.stg_invoice_lines as
select i.invoice_uid, i.invoice_number, i.invoice_date,
       (l.line->>'$.RowID')::int               as line_no,
       l.line->>'$.Account.DisplayID'          as account_code,
       l.line->>'$.Job.Name'                   as practice_area,
       l.line->>'$.TaxCode.Code'               as tax_code,
       (l.line->>'$.Total')::decimal(14,2)     as line_amount_ex_gst
from staging.stg_invoices i, unnest(cast(i._payload->'$.Lines' as json[])) as l(line);

create or replace view staging.stg_payment_allocations as
select * exclude (rn) from (
    select p.payload->>'$.UID'                      as payment_uid,
           (p.payload->>'$.Date')::timestamp::date  as payment_date,
           p.payload->>'$.Customer.UID'             as customer_uid,
           a.alloc->>'$.UID'                        as invoice_uid,
           (a.alloc->>'$.AmountApplied')::decimal(14,2) as amount_applied,
           row_number() over (partition by p.record_uid, a.alloc->>'$.UID' order by p.last_modified desc, p.loaded_at desc) as rn
    from raw.myob_customer_payments p, unnest(cast(p.payload->'$.Invoices' as json[])) as a(alloc)) where rn = 1;

-- Report date = the company file's latest sync date (MYOB data is "as at" its last sync)
create or replace view staging.stg_report_date as
select max(last_sync_date)::date as as_at from raw.myob_company_file;
