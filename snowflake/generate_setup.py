"""Write snowflake/01_setup_and_load.sql from the warehouse schema, so Snowflake always has the same tables and columns.

    python snowflake/generate_setup.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from warehouse.build import LOAD_ORDER, build_warehouse  # noqa: E402

TYPES = {"INTEGER": "NUMBER(38,0)", "REAL": "FLOAT", "TEXT": "VARCHAR"}
DATE_COLUMNS = {"full_date", "month_start_date"}


def main():
    con = build_warehouse(":memory:")
    out = ["-- Snowflake: create the warehouse tables and load them from the CSV files in data/warehouse/ (generated, do not edit by hand).",
           "-- Regenerate with: python snowflake/generate_setup.py   ·   Run in Snowsight as a role that can create a database.",
           "--",
           "-- Load the files one of two ways:",
           "--   Snowsight: Data > Add Data > Load files into a stage, choose LAW_FIRM.ANALYTICS.WAREHOUSE_FILES, upload data/warehouse/*.csv",
           "--   SnowSQL:   PUT file://data/warehouse/*.csv @LAW_FIRM.ANALYTICS.WAREHOUSE_FILES AUTO_COMPRESS = TRUE;",
           "",
           "CREATE DATABASE IF NOT EXISTS LAW_FIRM;",
           "CREATE SCHEMA IF NOT EXISTS LAW_FIRM.ANALYTICS;",
           "USE SCHEMA LAW_FIRM.ANALYTICS;",
           "",
           "CREATE OR REPLACE FILE FORMAT CSV_WITH_HEADER TYPE = CSV SKIP_HEADER = 1 FIELD_OPTIONALLY_ENCLOSED_BY = '\"' EMPTY_FIELD_AS_NULL = TRUE NULL_IF = ('');",
           "CREATE STAGE IF NOT EXISTS WAREHOUSE_FILES FILE_FORMAT = CSV_WITH_HEADER;",
           "",
           "CREATE OR REPLACE TABLE ETL_META (META_KEY VARCHAR, META_VALUE VARCHAR);",
           "INSERT INTO ETL_META VALUES ('as_of_date', '2025-09-17'), ('data', 'SIMULATED');",
           ""]
    for t in LOAD_ORDER:
        cols = list(con.execute(f"PRAGMA table_info({t})"))
        defs = []
        for _, name, typ, notnull, _, pk in cols:
            st = "DATE" if name in DATE_COLUMNS else TYPES.get(typ.upper(), "VARCHAR")
            defs.append(f"    {name.upper():<26} {st}{' NOT NULL' if notnull or pk else ''}")
        pks = [c[1].upper() for c in sorted(cols, key=lambda c: c[5]) if c[5]]
        if pks:
            defs.append(f"    PRIMARY KEY ({', '.join(pks)})")
        out.append(f"CREATE OR REPLACE TABLE {t.upper()} (\n" + ",\n".join(defs) + "\n);")
        out.append(f"COPY INTO {t.upper()} FROM @WAREHOUSE_FILES PATTERN = '(.*/)?{t}[.]csv([.]gz)?' ON_ERROR = ABORT_STATEMENT;")
        out.append("")
    out.append("-- Check: every table loaded the same number of rows as the local build (compare with docs/DATA_QUALITY.md).")
    out.append("SELECT TABLE_NAME, ROW_COUNT FROM LAW_FIRM.INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = 'ANALYTICS' ORDER BY TABLE_NAME;")
    (ROOT / "snowflake" / "01_setup_and_load.sql").write_text("\n".join(out) + "\n")
    print("wrote snowflake/01_setup_and_load.sql")


if __name__ == "__main__":
    main()
