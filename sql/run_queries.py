"""Run every sql/analysis/*.sql query against the warehouse and write the results to docs/query_results/*.csv.

    python sql/run_queries.py                  # builds the warehouse in memory, runs all queries
    python sql/run_queries.py --db warehouse.db

Outputs are committed so reviewers can see the results without running anything. They are deterministic
(fixed simulation seed, explicit ORDER BY in every query).
"""
from __future__ import annotations

import argparse
import csv
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from warehouse.build import build_warehouse  # noqa: E402

QUERY_DIR = ROOT / "sql" / "analysis"
OUT_DIR = ROOT / "docs" / "query_results"


def query_files(query_dir: Path = QUERY_DIR) -> list[Path]:
    return sorted(query_dir.glob("*.sql"))


def run_query(con: sqlite3.Connection, sql_path: Path) -> tuple[list[str], list[tuple]]:
    cur = con.execute(sql_path.read_text())
    cols = [d[0] for d in cur.description]
    return cols, cur.fetchall()


def write_csv(path: Path, cols: list[str], rows: list[tuple]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(cols)
        w.writerows(rows)


def run_all(con: sqlite3.Connection, out_dir: Path = OUT_DIR, query_dir: Path = QUERY_DIR) -> dict[str, int]:
    counts = {}
    for p in query_files(query_dir):
        cols, rows = run_query(con, p)
        write_csv(out_dir / f"{p.stem}.csv", cols, rows)
        counts[p.stem] = len(rows)
    return counts


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", default=":memory:", help="warehouse.db path, or ':memory:' to build on the fly")
    ap.add_argument("--out", default=str(OUT_DIR))
    args = ap.parse_args(argv)
    con = build_warehouse(":memory:") if args.db == ":memory:" else sqlite3.connect(args.db)
    for name, n in run_all(con, Path(args.out)).items():
        print(f"{name:40s}{n:>6d} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
