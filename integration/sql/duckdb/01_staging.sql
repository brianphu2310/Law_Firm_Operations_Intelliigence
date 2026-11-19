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
           (payload->>'$.asAt')::timestamp::date as as_at,
           row_number() over (partition by record_uid order by last_modified desc, loaded_at desc) as rn
    from raw.leap_trust_balances) where rn = 1;

create or replace view staging.stg_tc_matters as
select * exclude (rn) from (
    select record_uid as tc_matter_id, payload->>'$.number' as matter_number, payload->>'$.title' as title,
           (payload->>'$.status')::int as status_code, payload->>'$.clientName' as client_name,
           payload->>'$.externalSystemId' as leap_matter_id, payload->>'$.origin' as origin,
           payload->'$.matterType'->>'$.category' as matter_type, (payload->>'$.openedDate')::timestamp::date as opened_date,
           row_number() over (partition by record_uid order by last_modified desc, loaded_at desc) as rn
    from raw.triconvey_matters) where rn = 1;

create or replace view staging.stg_tc_trust as
select * exclude (rn) from (
    select payload->>'$.contactName' as client_name, (payload->>'$.balance')::decimal(14,2) as balance,
           (payload->>'$.asAt')::timestamp::date as as_at,
           row_number() over (partition by record_uid order by last_modified desc, loaded_at desc) as rn
    from raw.triconvey_trust_balances) where rn = 1;

create or replace view staging.stg_infotrack_orders as
select * exclude (rn) from (
    select record_uid as order_id, (payload->>'$.dateOrdered')::timestamp::date as ordered_date,
           payload->>'$.clientReference' as matter_number, payload->>'$.serviceName' as service,
           (payload->>'$.totalFeeExGst')::decimal(14,2) as fee_ex_gst, payload->>'$.status' as status,
           (payload->>'$.registryFeeExGst')::decimal(14,2) as registry_fee_ex_gst, (payload->>'$.serviceFeeExGst')::decimal(14,2) as service_fee_ex_gst,
           row_number() over (partition by record_uid order by last_modified desc, loaded_at desc) as rn
    from raw.infotrack_orders) where rn = 1;

create or replace view staging.stg_pexa_workspaces as
select * exclude (rn) from (
    select record_uid as workspace_id, payload->>'$.subscriberReference' as matter_number,
           (payload->>'$.settlementDate')::timestamp::date as settlement_date, payload->>'$.status' as status,
           (payload->>'$.settlementAmount')::decimal(16,2) as settlement_amount, (payload->>'$.pexaFee')::decimal(14,2) as pexa_fee,
           row_number() over (partition by record_uid order by last_modified desc, loaded_at desc) as rn
    from raw.pexa_workspaces) where rn = 1;

-- ------------------------------------------------------------------------------------------------------------------
-- Transition period: LEAP (frozen at the final collection) -> triConvey, InfoTrack -> TriSearch
-- ------------------------------------------------------------------------------------------------------------------
create or replace view staging.stg_tc_invoices as
select * exclude (rn) from (
    select payload->>'$.invoiceNumber' as invoice_number, payload->>'$.matterNumber' as matter_number, payload->>'$.clientName' as client_name,
           (payload->>'$.issueDate')::timestamp::date as issue_date, (payload->>'$.amountExTax')::decimal(14,2) as amount_ex_tax,
           (payload->>'$.tax')::decimal(14,2) as tax, (payload->>'$.total')::decimal(14,2) as total,
           (payload->>'$.balanceDue')::decimal(14,2) as balance_due, payload->>'$.status' as status, payload->>'$.origin' as origin,
           row_number() over (partition by record_uid order by last_modified desc, loaded_at desc) as rn
    from raw.triconvey_invoices) where rn = 1;

create or replace view staging.stg_tc_trust_recon as
select * exclude (rn) from (
    select (payload->>'$.periodEnd')::timestamp::date as period_end, (payload->>'$.dueDate')::timestamp::date as due_date,
           (payload->>'$.bankBalance')::decimal(14,2) as bank_balance, (payload->>'$.depositsNotBanked')::decimal(14,2) as deposits_not_banked,
           (payload->>'$.unpresentedCheques')::decimal(14,2) as unpresented_cheques, (payload->>'$.cashBookBalance')::decimal(14,2) as cash_book_balance,
           (payload->>'$.ledgerTotal')::decimal(14,2) as ledger_total, (payload->>'$.ledgersListed')::int as ledgers_listed,
           payload->>'$.status' as status,
           row_number() over (partition by record_uid order by last_modified desc, loaded_at desc) as rn
    from raw.triconvey_trust_reconciliation) where rn = 1;

create or replace view staging.stg_trisearch_orders as
select * exclude (rn) from (
    select payload->>'$.orderNumber' as order_id, (payload->>'$.placedAt')::timestamp::date as ordered_date,
           payload->>'$.reference' as matter_ref, payload->>'$.product' as service, (payload->>'$.feeExGst')::decimal(14,2) as fee_ex_gst,
           (payload->>'$.registryFeeExGst')::decimal(14,2) as registry_fee_ex_gst, (payload->>'$.serviceFeeExGst')::decimal(14,2) as service_fee_ex_gst,
           payload->>'$.state' as status,
           row_number() over (partition by record_uid order by last_modified desc, loaded_at desc) as rn
    from raw.trisearch_orders) where rn = 1;

-- one shape for both suppliers; the matter reference is normalised (letters and digits, upper case) so a re-typed 'm20250413' still lands
create or replace view staging.stg_supplier_orders as
select * from (
    select 'InfoTrack' as supplier, cast(order_id as varchar) as order_id, ordered_date, matter_number as matter_ref, service, fee_ex_gst,
           registry_fee_ex_gst, service_fee_ex_gst, status from staging.stg_infotrack_orders
    union all
    select 'TriSearch', order_id, ordered_date, matter_ref, service, fee_ex_gst, registry_fee_ex_gst, service_fee_ex_gst, status
    from staging.stg_trisearch_orders);

create or replace view staging.stg_leap_disbursements as
select * exclude (rn) from (
    select 'LEAP' as system, payload->>'$.matterNumber' as matter_number, (payload->>'$.date')::timestamp::date as disb_date,
           (payload->>'$.amountExGst')::decimal(14,2) as amount_ex_gst, payload->>'$.supplier' as supplier,
           payload->>'$.supplierOrderRef' as supplier_order_ref, payload->>'$.postedBy' as posted_by,
           row_number() over (partition by record_uid order by last_modified desc, loaded_at desc) as rn
    from raw.leap_disbursements) where rn = 1;

create or replace view staging.stg_tc_disbursements as
select * exclude (rn) from (
    select 'triConvey' as system, payload->>'$.matterNumber' as matter_number, (payload->>'$.date')::timestamp::date as disb_date,
           (payload->>'$.amountExGst')::decimal(14,2) as amount_ex_gst, payload->>'$.supplier' as supplier,
           payload->>'$.supplierOrderRef' as supplier_order_ref, payload->>'$.postedBy' as posted_by,
           row_number() over (partition by record_uid order by last_modified desc, loaded_at desc) as rn
    from raw.triconvey_disbursements) where rn = 1;

create or replace view staging.stg_pms_disbursements as
select * from staging.stg_leap_disbursements union all select * from staging.stg_tc_disbursements;

-- the two practice-management systems seen as one ledger of matters and invoices across the transition
create or replace view staging.stg_pms_matters as
select matter_number, client_name, 'LEAP' as system from staging.stg_leap_matters
union all
select distinct matter_number, client_name, 'triConvey' from staging.stg_tc_matters where origin = 'Created in triConvey';

create or replace view staging.stg_pms_invoices as
select invoice_number, matter_number, client_name, issue_date, amount_ex_tax, tax, total, 'LEAP' as system from staging.stg_leap_invoices
union all
select invoice_number, matter_number, client_name, issue_date, amount_ex_tax, tax, total, 'triConvey'
from staging.stg_tc_invoices where origin = 'Created in triConvey';

-- the cut-over dates, derived from the data itself: LEAP's last day, and the first day triConvey holds migrated matters
create or replace view staging.stg_cutover as
select (select max(as_at) from staging.stg_leap_trust) as final_collection,
       (select min(last_updated) from (select (payload->>'$.lastUpdated')::timestamp::date as last_updated from raw.triconvey_matters
                                       where payload->>'$.origin' = 'Migrated')) as go_live;
