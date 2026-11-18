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

-- ------------------------------------------------------------------------------------------------------------------
-- Other systems (simulated). Same pattern: flatten JSON, keep the latest version of each record.
-- ------------------------------------------------------------------------------------------------------------------
create or replace view staging.stg_leap_matters as
select * exclude (rn) from (
    select payload->>'$.matterNumber' as matter_number, payload->>'$.matterDescription' as description,
           payload->>'$.clientName' as client_name, payload->>'$.practiceArea' as practice_area,
           payload->>'$.responsibleStaff' as responsible, payload->>'$.branch' as branch, payload->>'$.status' as status,
           (payload->>'$.openedDate')::timestamp::date as opened_date, (payload->>'$.closedDate')::timestamp::date as closed_date,
           record_uid as leap_matter_id,
           row_number() over (partition by record_uid order by last_modified desc, loaded_at desc) as rn
    from raw.leap_matters) where rn = 1;

create or replace view staging.stg_leap_invoices as
select * exclude (rn) from (
    select payload->>'$.invoiceNumber' as invoice_number, payload->>'$.matterNumber' as matter_number,
           payload->>'$.clientName' as client_name, (payload->>'$.issueDate')::timestamp::date as issue_date,
           (payload->>'$.amountExTax')::decimal(14,2) as amount_ex_tax, (payload->>'$.tax')::decimal(14,2) as tax,
           (payload->>'$.total')::decimal(14,2) as total, payload->>'$.status' as status,
           row_number() over (partition by record_uid order by last_modified desc, loaded_at desc) as rn
    from raw.leap_invoices) where rn = 1;

create or replace view staging.stg_leap_trust as
select * exclude (rn) from (
    select payload->>'$.clientName' as client_name, (payload->>'$.balance')::decimal(14,2) as balance,
           row_number() over (partition by record_uid order by last_modified desc, loaded_at desc) as rn
    from raw.leap_trust_balances) where rn = 1;

create or replace view staging.stg_tc_matters as
select * exclude (rn) from (
    select record_uid as tc_matter_id, payload->>'$.number' as matter_number, payload->>'$.title' as title,
           (payload->>'$.status')::int as status_code, payload->>'$.clientName' as client_name,
           payload->>'$.externalSystemId' as leap_matter_id,
           row_number() over (partition by record_uid order by last_modified desc, loaded_at desc) as rn
    from raw.triconvey_matters) where rn = 1;

create or replace view staging.stg_tc_trust as
select * exclude (rn) from (
    select payload->>'$.contactName' as client_name, (payload->>'$.balance')::decimal(14,2) as balance,
           row_number() over (partition by record_uid order by last_modified desc, loaded_at desc) as rn
    from raw.triconvey_trust_balances) where rn = 1;

create or replace view staging.stg_infotrack_orders as
select * exclude (rn) from (
    select record_uid as order_id, (payload->>'$.dateOrdered')::timestamp::date as ordered_date,
           payload->>'$.clientReference' as matter_number, payload->>'$.serviceName' as service,
           (payload->>'$.totalFeeExGst')::decimal(14,2) as fee_ex_gst, payload->>'$.status' as status,
           row_number() over (partition by record_uid order by last_modified desc, loaded_at desc) as rn
    from raw.infotrack_orders) where rn = 1;

create or replace view staging.stg_pexa_workspaces as
select * exclude (rn) from (
    select record_uid as workspace_id, payload->>'$.subscriberReference' as matter_number,
           (payload->>'$.settlementDate')::timestamp::date as settlement_date, payload->>'$.status' as status,
           (payload->>'$.settlementAmount')::decimal(16,2) as settlement_amount, (payload->>'$.pexaFee')::decimal(14,2) as pexa_fee,
           row_number() over (partition by record_uid order by last_modified desc, loaded_at desc) as rn
    from raw.pexa_workspaces) where rn = 1;
