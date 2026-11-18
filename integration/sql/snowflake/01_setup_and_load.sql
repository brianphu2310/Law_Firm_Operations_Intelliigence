-- =====================================================================================================
-- Snowflake setup + load (run in a Snowsight worksheet, nothing to install).
--   A. Run the setup block.
--   B. Snowsight > Data > LAW_FIRM > RAW > Stages > MYOB_FILES > "+ Files": upload integration/data/*.json
--   C. Run the COPY INTO block. Expected rows: 8 accounts, 23 customers, 472 invoices, 444 payments, 1 company file.
-- For scheduled loads use the n8n workflow (integration/n8n) or the Python loader with WAREHOUSE=snowflake.
-- =====================================================================================================
create database if not exists law_firm;
use database law_firm;
create schema if not exists raw;
create schema if not exists staging;
create schema if not exists marts;

create table if not exists raw.myob_accounts          (record_uid varchar, payload variant, last_modified timestamp_ntz, batch_id varchar, loaded_at timestamp_ntz);
create table if not exists raw.myob_customers         (record_uid varchar, payload variant, last_modified timestamp_ntz, batch_id varchar, loaded_at timestamp_ntz);
create table if not exists raw.myob_invoices          (record_uid varchar, payload variant, last_modified timestamp_ntz, batch_id varchar, loaded_at timestamp_ntz);
create table if not exists raw.myob_customer_payments (record_uid varchar, payload variant, last_modified timestamp_ntz, batch_id varchar, loaded_at timestamp_ntz);
create table if not exists raw.myob_company_file      (company_file_uid varchar, name varchar, last_sync_date timestamp_ntz, batch_id varchar, loaded_at timestamp_ntz);
create table if not exists raw.load_audit (batch_id varchar, resource varchar, api_count integer, loaded_count integer,
                                           watermark varchar, status varchar, loaded_at timestamp_ntz);
-- n8n writes text rows here, then promotes them to the typed RAW tables with PARSE_JSON
create table if not exists raw.myob_landing (target_table varchar, record_uid varchar, payload_text varchar,
                                             last_modified timestamp_ntz, batch_id varchar, loaded_at timestamp_ntz);

create file format if not exists raw.json_array type = json strip_outer_array = true;
create stage if not exists raw.myob_files file_format = raw.json_array;

-- ---------------------------------------- C. load the uploaded JSON ----------------------------------------
copy into raw.myob_accounts from (select $1:UID::varchar, $1, $1:LastModified::timestamp_ntz, 'manual-upload', current_timestamp()::timestamp_ntz from @raw.myob_files/accounts.json);
copy into raw.myob_customers from (select $1:UID::varchar, $1, $1:LastModified::timestamp_ntz, 'manual-upload', current_timestamp()::timestamp_ntz from @raw.myob_files/customers.json);
copy into raw.myob_invoices from (select $1:UID::varchar, $1, $1:LastModified::timestamp_ntz, 'manual-upload', current_timestamp()::timestamp_ntz from @raw.myob_files/invoices.json);
copy into raw.myob_customer_payments from (select $1:UID::varchar, $1, $1:LastModified::timestamp_ntz, 'manual-upload', current_timestamp()::timestamp_ntz from @raw.myob_files/customer_payments.json);
copy into raw.myob_company_file from (select $1:Id::varchar, $1:Name::varchar, $1:LastSyncDate::timestamp_ntz, 'manual-upload', current_timestamp()::timestamp_ntz from @raw.myob_files/company_file.json);

select 'invoices' as t, count(*) as n from raw.myob_invoices
union all select 'payments', count(*) from raw.myob_customer_payments
union all select 'customers', count(*) from raw.myob_customers
union all select 'accounts', count(*) from raw.myob_accounts
union all select 'company_file', count(*) from raw.myob_company_file;
