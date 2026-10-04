"""Documentation must not drift from the warehouse: every column is documented and every doc link resolves."""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from warehouse.build import build_warehouse

DOCS = os.path.join(ROOT, "docs")


def _read(*p):
    with open(os.path.join(ROOT, *p), encoding="utf-8") as f:
        return f.read()


def test_every_warehouse_column_is_in_the_data_dictionary():
    con = build_warehouse(":memory:")
    dd = _read("docs", "DATA_DICTIONARY.md")
    tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'etl_%'")]
    missing = []
    for t in tables:
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
    for (t,) in con.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'etl_%'"):
        assert t in dm, t


def test_skills_doc_points_at_real_files():
    text = _read("docs", "SKILLS_DEMONSTRATED.md")
    paths = set(re.findall(r"`([\w./-]+\.(?:py|sql|md|yml|csv|txt))`", text))
    assert len(paths) >= 10
    for p in paths:
        assert os.path.exists(os.path.join(ROOT, p)), p


def test_readme_links_new_docs_and_they_exist():
    readme = _read("README.md")
    for link in ("docs/DATA_MODEL.md", "docs/DATA_DICTIONARY.md", "docs/DATA_QUALITY.md", "docs/SKILLS_DEMONSTRATED.md", "sql/analysis"):
        assert link in readme, link
        assert os.path.exists(os.path.join(ROOT, link)), link


def test_ci_runs_pipeline_steps():
    ci = _read(".github", "workflows", "ci.yml")
    assert "pytest" in ci and "warehouse.build" in ci and "warehouse.quality" in ci and "run_queries" in ci


def test_warehouse_db_is_gitignored():
    assert "warehouse.db" in _read(".gitignore")
