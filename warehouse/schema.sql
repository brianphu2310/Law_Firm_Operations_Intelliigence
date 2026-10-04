-- Dimensional model (star schema) for the simulated law-firm operations dataset.
-- SQLite dialect. Surrogate keys are integers assigned deterministically by the loader; business keys are UNIQUE.
-- Monetary amounts are AUD. Flow measures for the month containing the as-of date are pro-rated to the days elapsed
-- (see month_fraction_elapsed), so SUMs equal what the app reports for any period ending on the as-of date.
PRAGMA foreign_keys = ON;

CREATE TABLE etl_meta (meta_key TEXT PRIMARY KEY, meta_value TEXT NOT NULL);
CREATE TABLE etl_load_audit (table_name TEXT PRIMARY KEY, row_count INTEGER NOT NULL);

-- ---------------------------------------------------------------- dimensions
CREATE TABLE dim_date (
    date_key         INTEGER PRIMARY KEY,           -- yyyymmdd
    full_date        TEXT NOT NULL UNIQUE,
    year             INTEGER NOT NULL,
    quarter          INTEGER NOT NULL,
    month            INTEGER NOT NULL,
    month_name       TEXT NOT NULL,
    month_start_date TEXT NOT NULL,
    day_of_month     INTEGER NOT NULL,
    day_of_week      INTEGER NOT NULL,              -- 1 = Monday .. 7 = Sunday
    day_name         TEXT NOT NULL,
    is_weekend       INTEGER NOT NULL CHECK (is_weekend IN (0, 1)),
    is_month_end     INTEGER NOT NULL CHECK (is_month_end IN (0, 1)),
    fy_start_year    INTEGER NOT NULL,              -- Australian financial year (1 Jul - 30 Jun)
    fy_label         TEXT NOT NULL,
    fy_quarter       INTEGER NOT NULL
);

CREATE TABLE dim_branch (
    branch_key        INTEGER PRIMARY KEY,
    branch_name       TEXT NOT NULL UNIQUE,
    council_area      TEXT NOT NULL,
    latitude          REAL NOT NULL,
    longitude         REAL NOT NULL,
    support_headcount INTEGER NOT NULL,
    base_monthly_rent REAL NOT NULL
);

CREATE TABLE dim_practice_area (
    practice_area_key INTEGER PRIMARY KEY,
    practice_area     TEXT NOT NULL UNIQUE
);

CREATE TABLE dim_scenario (
    scenario_key  INTEGER PRIMARY KEY,
    scenario_name TEXT NOT NULL UNIQUE               -- Actual / Budget
);

CREATE TABLE dim_attorney (
    attorney_key     INTEGER PRIMARY KEY,
    attorney_short   TEXT NOT NULL UNIQUE,
    attorney_name    TEXT NOT NULL,
    role             TEXT NOT NULL,
    home_branch_key  INTEGER NOT NULL REFERENCES dim_branch (branch_key),
    start_date_key   INTEGER NOT NULL REFERENCES dim_date (date_key),
    target_hours_per_month REAL NOT NULL,
    bill_rate        REAL NOT NULL CHECK (bill_rate > 0),   -- standard hourly rate at the as-of rate index
    pay_rate         REAL NOT NULL CHECK (pay_rate > 0),    -- internal cost per hour
    realisation_factor REAL NOT NULL                        -- generator parameter
);

CREATE TABLE dim_client (
    client_key               INTEGER PRIMARY KEY,
    client_name              TEXT NOT NULL UNIQUE,
    primary_practice_area_key INTEGER NOT NULL REFERENCES dim_practice_area (practice_area_key),
    relationship_attorney_key INTEGER NOT NULL REFERENCES dim_attorney (attorney_key),
    client_since_year        INTEGER NOT NULL,
    country                  TEXT NOT NULL,
    has_trust_account        INTEGER NOT NULL CHECK (has_trust_account IN (0, 1))
);

CREATE TABLE dim_matter (
    matter_key        INTEGER PRIMARY KEY,
    matter_id         TEXT NOT NULL UNIQUE,         -- M-2025-0001 (matter names are NOT unique)
    matter_name       TEXT NOT NULL,
    client_key        INTEGER NOT NULL REFERENCES dim_client (client_key),
    practice_area_key INTEGER NOT NULL REFERENCES dim_practice_area (practice_area_key),
    attorney_key      INTEGER NOT NULL REFERENCES dim_attorney (attorney_key),
    branch_key        INTEGER NOT NULL REFERENCES dim_branch (branch_key),
    country           TEXT NOT NULL,
    status            TEXT NOT NULL CHECK (status IN ('Open', 'On Hold', 'Closed')),
    opened_date_key   INTEGER NOT NULL REFERENCES dim_date (date_key),
    closed_date_key   INTEGER REFERENCES dim_date (date_key),   -- NULL unless Closed
    is_named_matter   INTEGER NOT NULL CHECK (is_named_matter IN (0, 1))
);

-- --------------------------------------------------------------------- facts
-- Grain: one row per invoice.
CREATE TABLE fact_invoice (
    invoice_key       INTEGER PRIMARY KEY,
    invoice_number    TEXT NOT NULL UNIQUE,
    client_key        INTEGER NOT NULL REFERENCES dim_client (client_key),
    practice_area_key INTEGER NOT NULL REFERENCES dim_practice_area (practice_area_key),
    attorney_key      INTEGER NOT NULL REFERENCES dim_attorney (attorney_key),
    branch_key        INTEGER NOT NULL REFERENCES dim_branch (branch_key),
    issue_date_key    INTEGER NOT NULL REFERENCES dim_date (date_key),
    due_date_key      INTEGER NOT NULL REFERENCES dim_date (date_key),
    paid_date_key     INTEGER REFERENCES dim_date (date_key),   -- NULL while unpaid at the as-of date
    amount_ex_gst     REAL NOT NULL CHECK (amount_ex_gst > 0),
    gst_amount        REAL NOT NULL CHECK (gst_amount >= 0),
    amount_total      REAL NOT NULL CHECK (amount_total > 0),
    days_to_pay       INTEGER CHECK (days_to_pay >= 0),         -- NULL while unpaid
    is_paid           INTEGER NOT NULL CHECK (is_paid IN (0, 1))
);

-- Grain: one row per matter, position as at the as-of date (periodic snapshot of the matter ledger).
CREATE TABLE fact_matter_position (
    matter_key      INTEGER PRIMARY KEY REFERENCES dim_matter (matter_key),
    as_of_date_key  INTEGER NOT NULL REFERENCES dim_date (date_key),
    estimated_value REAL NOT NULL CHECK (estimated_value > 0),
    billed_to_date  REAL NOT NULL CHECK (billed_to_date >= 0),
    wip_balance     REAL NOT NULL CHECK (wip_balance >= 0),
    progress_ratio  REAL NOT NULL CHECK (progress_ratio BETWEEN 0 AND 1),
    days_open       INTEGER NOT NULL CHECK (days_open >= 0)
);

-- Grain: one row per attorney per month in which the attorney was active (actual months only).
CREATE TABLE fact_attorney_month (
    attorney_key    INTEGER NOT NULL REFERENCES dim_attorney (attorney_key),
    month_start_date_key INTEGER NOT NULL REFERENCES dim_date (date_key),
    month_fraction_elapsed REAL NOT NULL CHECK (month_fraction_elapsed > 0 AND month_fraction_elapsed <= 1),
    capacity_hours  REAL NOT NULL,
    billable_hours  REAL NOT NULL,
    standard_value  REAL NOT NULL,                   -- hours x standard rate
    fees_realised   REAL NOT NULL,                   -- fees billed after write-offs, attributed to this attorney
    salary_cost     REAL NOT NULL,                   -- capacity hours x pay rate x wage index (paid regardless of utilisation)
    PRIMARY KEY (attorney_key, month_start_date_key)
);

-- Grain: attorney x practice area x month (hours, value and fees by area; salary allocated by hours share).
CREATE TABLE fact_time_by_area (
    attorney_key      INTEGER NOT NULL REFERENCES dim_attorney (attorney_key),
    practice_area_key INTEGER NOT NULL REFERENCES dim_practice_area (practice_area_key),
    month_start_date_key INTEGER NOT NULL REFERENCES dim_date (date_key),
    billable_hours    REAL NOT NULL,
    standard_value    REAL NOT NULL,
    fees_realised     REAL NOT NULL,
    allocated_salary_cost REAL NOT NULL,
    PRIMARY KEY (attorney_key, practice_area_key, month_start_date_key)
);

-- Grain: one row per month per scenario (Actual / Budget). Budget covers the whole financial year; Actual stops at the as-of date.
CREATE TABLE fact_monthly_pnl (
    month_start_date_key INTEGER NOT NULL REFERENCES dim_date (date_key),
    scenario_key    INTEGER NOT NULL REFERENCES dim_scenario (scenario_key),
    month_fraction_elapsed REAL NOT NULL CHECK (month_fraction_elapsed > 0 AND month_fraction_elapsed <= 1),
    billable_hours  REAL NOT NULL,
    capacity_hours  REAL NOT NULL,
    standard_value  REAL NOT NULL,
    writeoff        REAL NOT NULL,
    fees            REAL NOT NULL,
    disbursements_billed REAL NOT NULL,
    revenue         REAL NOT NULL,
    payroll_fee_earners REAL NOT NULL,
    disbursement_cost   REAL NOT NULL,
    payroll_support REAL NOT NULL,
    rent            REAL NOT NULL,
    software        REAL NOT NULL,
    insurance       REAL NOT NULL,
    marketing       REAL NOT NULL,
    professional_fees REAL NOT NULL,
    cards           REAL NOT NULL,
    merchant_fees   REAL NOT NULL,
    commission      REAL NOT NULL,
    bank_fees       REAL NOT NULL,
    other_costs     REAL NOT NULL,
    total_costs     REAL NOT NULL,
    operating_profit REAL NOT NULL,
    PRIMARY KEY (month_start_date_key, scenario_key)
);

-- Grain: one row per month (stock at month end, or at the as-of date for the current month); actual months only.
CREATE TABLE fact_monthly_snapshot (
    month_start_date_key INTEGER PRIMARY KEY REFERENCES dim_date (date_key),
    snapshot_date_key    INTEGER NOT NULL REFERENCES dim_date (date_key),
    wip_balance          REAL NOT NULL,
    cash_balance         REAL NOT NULL,
    receivables_incl_gst REAL NOT NULL,
    trust_balance        REAL NOT NULL,
    matters_active       INTEGER NOT NULL
);

-- Grain: client trust-account closing balance per month (clients with a trust ledger only).
CREATE TABLE fact_trust_balance (
    client_key           INTEGER NOT NULL REFERENCES dim_client (client_key),
    month_start_date_key INTEGER NOT NULL REFERENCES dim_date (date_key),
    closing_balance      REAL NOT NULL CHECK (closing_balance >= 0),
    PRIMARY KEY (client_key, month_start_date_key)
);

-- Grain: one trust-account deposit or disbursement.
CREATE TABLE fact_trust_txn (
    trust_txn_key  INTEGER PRIMARY KEY,
    client_key     INTEGER NOT NULL REFERENCES dim_client (client_key),
    txn_date_key   INTEGER NOT NULL REFERENCES dim_date (date_key),
    txn_type       TEXT NOT NULL CHECK (txn_type IN ('Deposit', 'Disbursement')),
    amount         REAL NOT NULL,                    -- signed: deposits +, disbursements -
    CHECK ((txn_type = 'Deposit' AND amount > 0) OR (txn_type = 'Disbursement' AND amount < 0))
);

-- ------------------------------------------------------------------- indexes
CREATE INDEX ix_matter_client   ON dim_matter (client_key);
CREATE INDEX ix_matter_area     ON dim_matter (practice_area_key);
CREATE INDEX ix_matter_attorney ON dim_matter (attorney_key);
CREATE INDEX ix_matter_status   ON dim_matter (status);
CREATE INDEX ix_invoice_client  ON fact_invoice (client_key);
CREATE INDEX ix_invoice_area    ON fact_invoice (practice_area_key);
CREATE INDEX ix_invoice_attorney ON fact_invoice (attorney_key);
CREATE INDEX ix_invoice_issue   ON fact_invoice (issue_date_key);
CREATE INDEX ix_invoice_paid    ON fact_invoice (paid_date_key);
CREATE INDEX ix_tba_area        ON fact_time_by_area (practice_area_key, month_start_date_key);
CREATE INDEX ix_am_month        ON fact_attorney_month (month_start_date_key);
CREATE INDEX ix_trust_txn_client ON fact_trust_txn (client_key, txn_date_key);
