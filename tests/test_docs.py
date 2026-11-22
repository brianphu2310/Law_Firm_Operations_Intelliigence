"""Docs and generated files must not drift: every warehouse column is documented, links resolve, and committed outputs are current."""
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from warehouse.build import build_warehouse


def _read(*p):
    return (ROOT.joinpath(*p)).read_text(encoding="utf-8")


def _tables(con):
    return [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'etl_%'")]


def test_every_warehouse_column_is_in_the_data_dictionary():
    con = build_warehouse(":memory:")
    dd = _read("docs", "DATA_DICTIONARY.md")
    missing = []
    for t in _tables(con):
        assert f"## {t}" in dd, t
        section = dd.split(f"## {t}\n")[1].split("\n## ")[0]
        for col in (r[1] for r in con.execute(f"PRAGMA table_info({t})")):
            if f"| `{col}` |" not in section:
                missing.append(f"{t}.{col}")
    assert not missing, missing


def test_data_model_mentions_every_table_and_has_mermaid_er():
    con = build_warehouse(":memory:")
    dm = _read("docs", "DATA_MODEL.md")
    assert "erDiagram" in dm
    for t in _tables(con):
        assert t in dm, t


def test_readme_and_docs_link_to_real_files():
    for doc in [ROOT / "README.md", *sorted((ROOT / "docs").glob("*.md")), *sorted((ROOT / "docs" / "ba").glob("*.md"))]:
        for link in re.findall(r"\]\(([^)#]+)", doc.read_text()):
            if not link.startswith("http"):
                assert (doc.parent / link).exists(), f"{doc.name} links to missing {link}"


def test_snowflake_setup_creates_every_warehouse_table():
    con = build_warehouse(":memory:")
    sf = _read("snowflake", "01_setup_and_load.sql")
    for t in _tables(con):
        assert f"CREATE OR REPLACE TABLE {t.upper()} (" in sf, t
        assert f"COPY INTO {t.upper()} " in sf, t


def test_generated_snowflake_files_are_current(tmp_path, monkeypatch):
    import importlib.util
    for gen, out in (("generate_setup.py", "01_setup_and_load.sql"), ("generate_queries.py", "02_decision_queries.sql")):
        before = _read("snowflake", out)
        spec = importlib.util.spec_from_file_location("gen", ROOT / "snowflake" / gen)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.main()
        assert _read("snowflake", out) == before, f"snowflake/{out} is stale - run: python snowflake/{gen}"


def test_snowflake_queries_use_no_sqlite_functions():
    sf = _read("snowflake", "02_decision_queries.sql")
    assert not re.search(r"julianday|strftime|(?<![_A-Za-z])date\(", sf, re.I)
    assert sf.count("DATEADD") >= 6


def test_ci_runs_the_tests_and_the_sql_layer():
    ci = _read(".github", "workflows", "ci.yml")
    for step in ("pytest", "warehouse.build", "warehouse.quality", "run_queries", "warehouse.export", "excel.build_pack"):
        assert step in ci, step


def test_warehouse_db_is_gitignored():
    assert "warehouse.db" in _read(".gitignore")
