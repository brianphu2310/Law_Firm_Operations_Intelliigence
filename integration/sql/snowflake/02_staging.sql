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
