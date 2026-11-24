"""Export every warehouse table to CSV so the same data can be loaded into Snowflake and read by Excel Power Query.

    python -m warehouse.export                 # -> data/warehouse/<table>.csv (committed)

The files are deterministic (fixed simulation seed, explicit sort order), so the committed copy is checked in CI.
All data is SIMULATED.
"""
from __future__ import annotations

import argparse
import csv
import sqlite3
from pathlib import Path

from warehouse.build import LOAD_ORDER, ROOT, build_warehouse

OUT_DIR = ROOT / "data" / "warehouse"


def _fmt(v):
    if v is None:
        return ""
    if isinstance(v, float):
        return f"{v:.4f}".rstrip("0").rstrip(".") if v != int(v) else str(int(v))
    return v


def export(con: sqlite3.Connection, out_dir: Path = OUT_DIR) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for t in LOAD_ORDER:
        cols = [r[1] for r in con.execute(f"PRAGMA table_info({t})")]
        pk = [r[1] for r in sorted(con.execute(f"PRAGMA table_info({t})"), key=lambda r: r[5]) if r[5]] or cols[:1]
        rows = con.execute(f"SELECT * FROM {t} ORDER BY {', '.join(pk)}").fetchall()
        p = out_dir / f"{t}.csv"
        with p.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(cols)
            w.writerows([[_fmt(v) for v in r] for r in rows])
        paths.append(p)
    return paths


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=str(OUT_DIR))
    a = ap.parse_args(argv)
    paths = export(build_warehouse(":memory:"), Path(a.out))
    print(f"wrote {len(paths)} tables to {a.out}")


if __name__ == "__main__":
    main()
