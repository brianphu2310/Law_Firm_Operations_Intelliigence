"""Write snowflake/02_decision_queries.sql: the decision queries in Snowflake SQL, translated from sql/analysis/ (SQLite).

    python snowflake/generate_queries.py

Only the date functions differ between the two dialects; everything else (CTEs, window functions, CASE) is the same SQL.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QUERIES = ["09_pnl_actual_vs_budget", "11_where_to_hire", "12_support_staffing", "13_marketing_channels", "14_branch_site"]

RULES = [
    # as-of date and rolling windows
    (r"date\(meta_value, '-2 years', '\+1 day'\)", "DATEADD(day, 1, DATEADD(year, -2, TO_DATE(meta_value)))"),
    (r"date\(meta_value, '-1 year', '\+1 day'\)", "DATEADD(day, 1, DATEADD(year, -1, TO_DATE(meta_value)))"),
    (r"date\(meta_value\)", "TO_DATE(meta_value)"),
    (r"date\(a\.ltm_start, 'start of month'\)", "DATE_TRUNC('month', a.ltm_start)"),
    (r"date\(a\.ltm_start, '-1 day'\)", "DATEADD(day, -1, a.ltm_start)"),
    # partial first month: days from the window start to the next month / days in the month
    (r"\(julianday\(date\(d\.full_date, '\+1 month'\)\) - julianday\(a\.ltm_start\)\) / \(julianday\(date\(d\.full_date, '\+1 month'\)\) - julianday\(d\.full_date\)\)",
     "DATEDIFF(day, a.ltm_start, DATEADD(month, 1, d.full_date)) / DATEDIFF(day, d.full_date, DATEADD(month, 1, d.full_date))"),
]


def translate(sql: str) -> str:
    for pat, rep in RULES:
        sql = re.sub(pat, rep, sql)
    left = re.findall(r"julianday|(?<![_A-Za-z])date\(|strftime", sql, flags=re.I)
    assert not left, f"untranslated SQLite function(s): {set(left)}"
    return sql.replace("Techniques:", "Snowflake dialect (translated from sql/analysis/). Techniques:", 1)


def main():
    parts = ["-- The Principal's decision queries in Snowflake SQL (generated from sql/analysis/, do not edit by hand).",
             "-- Run after 01_setup_and_load.sql. Each query returns the same rows as the local SQLite version in docs/query_results/.",
             "USE SCHEMA LAW_FIRM.ANALYTICS;", ""]
    for q in QUERIES:
        sql = (ROOT / "sql" / "analysis" / f"{q}.sql").read_text().strip()
        parts += [f"-- ============================================================ {q}", translate(sql), ""]
    (ROOT / "snowflake" / "02_decision_queries.sql").write_text("\n".join(parts))
    print("wrote snowflake/02_decision_queries.sql")


if __name__ == "__main__":
    main()
