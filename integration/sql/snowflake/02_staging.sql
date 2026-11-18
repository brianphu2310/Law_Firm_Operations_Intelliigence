-- STAGING (Snowflake): flatten the VARIANT payloads, keep the latest version of each record.
use database law_firm;

create or replace view staging.stg_customers as
select payload:UID::varchar as customer_uid, payload:DisplayID::varchar as customer_code,
       payload:CompanyName::varchar as customer_name, payload:Addresses[0]:Country::varchar as country
from raw.myob_customers
qualify row_number() over (partition by record_uid order by last_modified desc, loaded_at desc) = 1;

create or replace view staging.stg_invoices as
select payload:UID::varchar                       as invoice_uid,
       payload:Number::varchar                    as invoice_number,
       payload:Date::timestamp_ntz::date          as invoice_date,
       payload:Terms:DueDate::timestamp_ntz::date as due_date,
       payload:Customer:UID::varchar              as customer_uid,
       payload:Lines[0]:Job:Name::varchar         as practice_area,
       payload:Salesperson:Name::varchar          as attorney,
       payload:Category:Name::varchar             as branch,
       payload:Subtotal::number(14,2)             as subtotal,
       payload:TotalTax::number(14,2)             as total_tax,
       payload:TotalAmount::number(14,2)          as total_amount,
       payload:BalanceDueAmount::number(14,2)     as balance_due,
       payload:Status::varchar                    as status,
       payload                                    as _payload
from raw.myob_invoices
qualify row_number() over (partition by record_uid order by last_modified desc, loaded_at desc) = 1;

create or replace view staging.stg_invoice_lines as
select i.invoice_uid, i.invoice_number, i.invoice_date,
       l.value:RowID::int                 as line_no,
       l.value:Account:DisplayID::varchar as account_code,
       l.value:Job:Name::varchar          as practice_area,
       l.value:TaxCode:Code::varchar      as tax_code,
       l.value:Total::number(14,2)        as line_amount_ex_gst
from staging.stg_invoices i, lateral flatten(input => i._payload:Lines) l;

create or replace view staging.stg_payment_allocations as
select p.payload:UID::varchar as payment_uid, p.payload:Date::timestamp_ntz::date as payment_date,
       p.payload:Customer:UID::varchar as customer_uid, a.value:UID::varchar as invoice_uid,
       a.value:AmountApplied::number(14,2) as amount_applied
from raw.myob_customer_payments p, lateral flatten(input => p.payload:Invoices) a
qualify row_number() over (partition by p.record_uid, a.value:UID::varchar order by p.last_modified desc, p.loaded_at desc) = 1;

create or replace view staging.stg_report_date as
select max(last_sync_date)::date as as_at from raw.myob_company_file;

-- ---------------------------------------------------------------------------------------------------------------------
-- Other systems (simulated): LEAP, triConvey (Smokeball-shaped), InfoTrack, PEXA
-- ---------------------------------------------------------------------------------------------------------------------
create or replace view staging.stg_leap_matters as
select payload:matterNumber::varchar as matter_number, payload:matterDescription::varchar as description,
       payload:clientName::varchar as client_name, payload:practiceArea::varchar as practice_area,
       payload:responsibleStaff::varchar as responsible, payload:branch::varchar as branch, payload:status::varchar as status,
       payload:openedDate::timestamp_ntz::date as opened_date, payload:closedDate::timestamp_ntz::date as closed_date,
       record_uid as leap_matter_id
from raw.leap_matters
qualify row_number() over (partition by record_uid order by last_modified desc, loaded_at desc) = 1;

create or replace view staging.stg_leap_invoices as
select payload:invoiceNumber::varchar as invoice_number, payload:matterNumber::varchar as matter_number,
       payload:clientName::varchar as client_name, payload:issueDate::timestamp_ntz::date as issue_date,
       payload:amountExTax::number(14,2) as amount_ex_tax, payload:tax::number(14,2) as tax,
       payload:total::number(14,2) as total, payload:status::varchar as status
from raw.leap_invoices
qualify row_number() over (partition by record_uid order by last_modified desc, loaded_at desc) = 1;

create or replace view staging.stg_leap_trust as
select payload:clientName::varchar as client_name, payload:balance::number(14,2) as balance
from raw.leap_trust_balances
qualify row_number() over (partition by record_uid order by last_modified desc, loaded_at desc) = 1;

create or replace view staging.stg_tc_matters as
select record_uid as tc_matter_id, payload:number::varchar as matter_number, payload:title::varchar as title,
       payload:status::int as status_code, payload:clientName::varchar as client_name,
       payload:externalSystemId::varchar as leap_matter_id
from raw.triconvey_matters
qualify row_number() over (partition by record_uid order by last_modified desc, loaded_at desc) = 1;

create or replace view staging.stg_tc_trust as
select payload:contactName::varchar as client_name, payload:balance::number(14,2) as balance
from raw.triconvey_trust_balances
qualify row_number() over (partition by record_uid order by last_modified desc, loaded_at desc) = 1;

create or replace view staging.stg_infotrack_orders as
select record_uid as order_id, payload:dateOrdered::timestamp_ntz::date as ordered_date,
       payload:clientReference::varchar as matter_number, payload:serviceName::varchar as service,
       payload:totalFeeExGst::number(14,2) as fee_ex_gst, payload:status::varchar as status
from raw.infotrack_orders
qualify row_number() over (partition by record_uid order by last_modified desc, loaded_at desc) = 1;

create or replace view staging.stg_pexa_workspaces as
select record_uid as workspace_id, payload:subscriberReference::varchar as matter_number,
       payload:settlementDate::timestamp_ntz::date as settlement_date, payload:status::varchar as status,
       payload:settlementAmount::number(16,2) as settlement_amount, payload:pexaFee::number(14,2) as pexa_fee
from raw.pexa_workspaces
qualify row_number() over (partition by record_uid order by last_modified desc, loaded_at desc) = 1;
