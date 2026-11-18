-- RAW layer (DuckDB). One row per record per load; the MYOB payload is kept whole as JSON.
create schema if not exists raw;
create table if not exists raw.myob_accounts          (record_uid varchar, payload json, last_modified timestamp, batch_id varchar, loaded_at timestamp);
create table if not exists raw.myob_customers         (record_uid varchar, payload json, last_modified timestamp, batch_id varchar, loaded_at timestamp);
create table if not exists raw.myob_invoices          (record_uid varchar, payload json, last_modified timestamp, batch_id varchar, loaded_at timestamp);
create table if not exists raw.myob_customer_payments (record_uid varchar, payload json, last_modified timestamp, batch_id varchar, loaded_at timestamp);
-- Other systems (simulated): LEAP, triConvey (Smokeball-shaped), InfoTrack, PEXA. Same RAW contract as MYOB.
create table if not exists raw.leap_matters               (record_uid varchar, payload json, last_modified timestamp, batch_id varchar, loaded_at timestamp);
create table if not exists raw.leap_invoices              (record_uid varchar, payload json, last_modified timestamp, batch_id varchar, loaded_at timestamp);
create table if not exists raw.leap_trust_balances        (record_uid varchar, payload json, last_modified timestamp, batch_id varchar, loaded_at timestamp);
create table if not exists raw.triconvey_matters          (record_uid varchar, payload json, last_modified timestamp, batch_id varchar, loaded_at timestamp);
create table if not exists raw.triconvey_trust_balances   (record_uid varchar, payload json, last_modified timestamp, batch_id varchar, loaded_at timestamp);
create table if not exists raw.infotrack_orders           (record_uid varchar, payload json, last_modified timestamp, batch_id varchar, loaded_at timestamp);
create table if not exists raw.pexa_workspaces            (record_uid varchar, payload json, last_modified timestamp, batch_id varchar, loaded_at timestamp);
create table if not exists raw.myob_company_file      (company_file_uid varchar, name varchar, last_sync_date timestamp, batch_id varchar, loaded_at timestamp);
create table if not exists raw.load_audit (batch_id varchar, resource varchar, api_count integer, loaded_count integer,
                                           watermark varchar, status varchar, loaded_at timestamp);
