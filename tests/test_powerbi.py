"""Power BI project: the Simulator formulas match the Python engine, the report JSON is valid PBIR, and every field
and DAX reference points at something that exists in the semantic model."""
import json
import math
import random
import re
from pathlib import Path

import pytest

from core import simulate as S
from powerbi import build as B, model as MD, report as RP, sim_spec as SP

ROOT = Path(__file__).resolve().parents[1]
PBI = ROOT / "powerbi"
SCHEMAS = Path(__file__).resolve().parent / "schemas" / "report_definition"


@pytest.fixture(scope="module")
def inp():
    return B.inputs()


@pytest.fixture(scope="module")
def built(inp):
    M, f, ctx, consts, tables, levers = inp
    tbls, rels, expr = MD.build_model(consts, tables, levers, ctx)
    RP.ALL_FIELDS.clear()
    pages = RP.build_pages(dict(run_rate="$1", best="x", npv="+$1", answers=B.load_answers()), levers)
    return tbls, rels, pages


# --------------------------------------------------------------------------------------------- formulas = engine --
def _compare(e, r):
    bad = []
    for k, rk in SP.PROJECT_KEYS.items():
        a, b = e[k], r[rk]
        if a is None or b is None:
            if not (a is None and b is None):
                bad.append((k, a, b))
        elif not math.isclose(float(a), float(b), rel_tol=1e-9, abs_tol=1e-6):
            bad.append((k, a, b))
    return bad


def test_spec_matches_engine_for_every_preset(inp):
    M, f, ctx, consts, tables, levers = inp
    for name in S.PRESETS:
        s = S.preset_state(name)
        for d in (1.0, 0.75, 0.5):
            assert not _compare(SP.evaluate(s, consts, tables, d), S.project(f, s, delivery=d, ctx=ctx)), name


def test_spec_matches_engine_for_random_lever_mixes(inp):
    M, f, ctx, consts, tables, levers = inp
    rng = random.Random(7)
    for _ in range(300):
        s = {}
        for lv in levers:
            if lv.kind == "num":
                s[lv.key] = lv.lo + lv.step * rng.randint(0, int(round((lv.hi - lv.lo) / lv.step)))
            elif lv.kind == "bool":
                s[lv.key] = rng.random() < 0.4
            else:
                s[lv.key] = rng.choice(lv.options)
        d = rng.choice([1.0, 0.75, 0.5])
        assert not _compare(SP.evaluate(s, consts, tables, d), S.project(f, s, delivery=d, ctx=ctx)), s


def test_ramp_sum_closed_form():
    for R in (3, 4.5, 6, 7.5, 12, 18, 24):
        for m in range(1, 61):
            assert math.isclose(SP.ramp_sum(m, R), sum(min(1, i / R) for i in range(1, m + 1)))


# ------------------------------------------------------------------------------------------------- report JSON ----
def _validator(schema_url):
    from jsonschema import Draft7Validator
    from referencing import Registry, Resource

    prefix = RP.SCHEMA + "/"

    def retrieve(uri):
        rel = uri.split("#")[0][len(prefix):]
        return Resource.from_contents(json.loads((SCHEMAS / rel).read_text()))
    reg = Registry(retrieve=retrieve)
    schema = json.loads((SCHEMAS / schema_url[len(prefix):]).read_text())
    return Draft7Validator(schema, registry=reg)


def test_report_files_match_microsoft_schemas():
    files = list((PBI / f"{B.NAME}.Report" / "definition").rglob("*.json"))
    assert len(files) > 400
    cache = {}
    for f in files:
        doc = json.loads(f.read_text(encoding="utf-8"))
        url = doc["$schema"]
        v = cache.setdefault(url, _validator(url))
        errors = sorted(v.iter_errors(doc), key=lambda e: list(e.path))
        assert not errors, f"{f}: {errors[0].message} at {list(errors[0].path)}"


def test_project_files_exist():
    assert (PBI / f"{B.NAME}.pbip").exists()
    sm = PBI / f"{B.NAME}.SemanticModel" / "definition"
    for n in ("model.tmdl", "database.tmdl", "relationships.tmdl", "expressions.tmdl"):
        assert (sm / n).exists()
    assert len(list((sm / "tables").glob("*.tmdl"))) > 90


# --------------------------------------------------------------------------------------------- model references ---
def _inventory(tbls):
    cols = {t.name: {c.name for c in t.columns} for t in tbls}
    measures = {m.name for t in tbls for m in t.measures}
    return cols, measures


def _strip_strings(dax):
    return re.sub(r'"(?:[^"]|"")*"', '""', dax)


def test_every_report_field_exists(built):
    tbls, rels, pages = built
    cols, measures = _inventory(tbls)
    for f in RP.ALL_FIELDS:
        assert f.table in cols, f.table
        if f.kind == "m":
            assert f.name in measures and any(m.name == f.name for t in tbls if t.name == f.table for m in t.measures), (f.table, f.name)
        else:
            assert f.name in cols[f.table], (f.table, f.name)


def test_every_dax_reference_resolves(built):
    tbls, _, _ = built
    cols, measures = _inventory(tbls)
    row_ctx = {"Value", "r", "days_open"}
    for t in tbls:
        exprs = [(m.name, m.expression) for m in t.measures] + [(c.name, c.expression) for c in t.columns if c.expression]
        for name, e in exprs:
            e = _strip_strings(e)
            for tab, col in re.findall(r"'([^']+)'\[([^\]]+)\]", e):
                assert tab in cols and col in cols[tab], (name, tab, col)
            rest = re.sub(r"'[^']+'\[[^\]]+\]", "", e)
            for ref in re.findall(r"\[([^\]]+)\]", rest):
                assert ref in measures or ref in row_ctx or ref in cols[t.name], (name, ref)


def test_dax_brackets_balance(built):
    tbls, _, _ = built
    for t in tbls:
        for m in t.measures:
            e = _strip_strings(m.expression)
            assert e.count("(") == e.count(")"), m.name
            assert e.count("{") == e.count("}"), m.name


def test_relationship_columns_exist(built):
    tbls, _, _ = built
    cols, _ = _inventory(tbls)
    for a, ac, b, bc in MD.RELATIONSHIPS:
        assert ac in cols[a] and bc in cols[b], (a, ac, b, bc)


def test_check_page_covers_every_preset():
    import csv
    rows = list(csv.DictReader((ROOT / "data" / "powerbi" / "sim_expected.csv").open()))
    presets = {r["Preset"] for r in rows}
    assert presets == {"Custom", *S.PRESETS}
    assert len(rows) > 100
