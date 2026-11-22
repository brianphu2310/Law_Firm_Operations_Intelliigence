"""Writes the Power BI project: powerbi/LawFirmDecisionSupport.pbip (+ .SemanticModel and .Report folders).

    python -m powerbi.build            # exports data/powerbi/*.csv, then writes the project
    python -m powerbi.build --no-export

Open LawFirmDecisionSupport.pbip in Power BI Desktop (Windows). Data loads from the CSVs in the GitHub repo
(parameter BaseUrl); change it under Transform data > Edit parameters to load from a fork or a local copy.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from core import metrics as X, simulate as S
from core.model import build_model as build_firm
from core.period import stock_at
from core.ref import AS_OF

from . import exports, model as MD, report as RP, sim_spec as SP
from .tmdl import guid, q

ROOT = Path(__file__).resolve().parent
NAME = "LawFirmDecisionSupport"
PROJECT = ROOT / NAME
THEME_NAME = "DecisionSupport"


def _write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _json(path, obj):
    _write(path, json.dumps(obj, indent=2, ensure_ascii=False) + "\n")


def platform_file(kind, display):
    return {"$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
            "metadata": {"type": kind, "displayName": display}, "config": {"version": "2.0", "logicalId": guid(kind, display)}}


def theme():
    return {
        "name": THEME_NAME,
        "dataColors": ["#0a8496", "#2f7fd8", "#6b5bd6", "#f2b134", "#e2665a", "#34a37a", "#94a3b8", "#d946ef", "#0e7490", "#b45309"],
        "background": "#FFFFFF", "foreground": "#0f172a", "tableAccent": "#0a8496",
        "good": "#047857", "neutral": "#b45309", "bad": "#b91c1c", "maximum": "#0a8496", "center": "#e0f2f4", "minimum": "#ffffff",
        "textClasses": {"title": {"fontFace": "Segoe UI Semibold", "fontSize": 11, "color": "#0f172a"},
                        "label": {"fontFace": "Segoe UI", "fontSize": 9, "color": "#334155"},
                        "callout": {"fontFace": "Segoe UI Semibold", "fontSize": 20, "color": "#0f172a"}},
        "visualStyles": {"*": {"*": {"background": [{"show": True, "color": {"solid": {"color": "#FFFFFF"}}, "transparency": 0}],
                                     "border": [{"show": True, "color": {"solid": {"color": "#dbe6ee"}}, "radius": 12}],
                                     "dropShadow": [{"show": False}]}},
                         "page": {"*": {"background": [{"color": {"solid": {"color": "#f3f6fa"}}, "transparency": 0}]}}},
    }


def write_model(consts, tables, levers, ctx):
    sm = PROJECT.parent / f"{NAME}.SemanticModel"
    if sm.exists():
        shutil.rmtree(sm)
    tbls, rels, expr = MD.build_model(consts, tables, levers, ctx)
    d = sm / "definition"
    _json(sm / "definition.pbism", {"$schema": "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json",
                                    "version": "4.2", "settings": {}})
    _json(sm / ".platform", platform_file("SemanticModel", NAME))
    _write(d / "database.tmdl", "database\n\tcompatibilityLevel: 1601\n")
    refs = "\n".join(f"ref table {q(t.name)}" for t in tbls)
    _write(d / "model.tmdl", "model Model\n\tculture: en-US\n\tdefaultPowerBIDataSourceVersion: powerBI_V3\n\tsourceQueryCulture: en-AU\n"
                             "\tdataAccessOptions\n\t\tlegacyRedirects\n\t\treturnErrorValuesAsNull\n\n"
                             "annotation __PBI_TimeIntelligenceEnabled = 0\n\n" + refs + "\n")
    _write(d / "expressions.tmdl", expr)
    _write(d / "relationships.tmdl", "\n\n".join(rels) + "\n")
    for t in tbls:
        _write(d / "tables" / f"{t.name}.tmdl", t.render())
    return tbls


def write_report(levers, facts):
    rp = PROJECT.parent / f"{NAME}.Report"
    if rp.exists():
        shutil.rmtree(rp)
    RP.ALL_FIELDS.clear()
    pages = RP.build_pages(facts, levers)
    d = rp / "definition"
    _json(rp / "definition.pbir", {"$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
                                   "version": "4.0", "datasetReference": {"byPath": {"path": f"../{NAME}.SemanticModel"}}})
    _json(rp / ".platform", platform_file("Report", NAME))
    base_theme = ROOT / "assets" / "CY24SU10.json"
    _write(rp / "StaticResources" / "SharedResources" / "BaseThemes" / "CY24SU10.json", base_theme.read_text(encoding="utf-8"))
    _json(rp / "StaticResources" / "RegisteredResources" / f"{THEME_NAME}.json", theme())
    _json(d / "version.json", {"$schema": f"{RP.SCHEMA}/versionMetadata/1.0.0/schema.json", "version": "2.0.0"})
    _json(d / "report.json", {
        "$schema": f"{RP.SCHEMA}/report/1.3.0/schema.json",
        "themeCollection": {"baseTheme": {"name": "CY24SU10", "reportVersionAtImport": "5.61", "type": "SharedResources"},
                            "customTheme": {"name": f"{THEME_NAME}.json", "reportVersionAtImport": "5.61", "type": "RegisteredResources"}},
        "layoutOptimization": "None",
        "resourcePackages": [{"name": "SharedResources", "type": "SharedResources", "items": [{"name": "CY24SU10", "path": "BaseThemes/CY24SU10.json", "type": "BaseTheme"}]},
                             {"name": "RegisteredResources", "type": "RegisteredResources", "items": [{"name": f"{THEME_NAME}.json", "path": f"{THEME_NAME}.json", "type": "CustomTheme"}]}],
        "settings": {"useStylableVisualContainerHeader": True, "defaultDrillFilterOtherVisuals": True, "allowChangeFilterTypes": True,
                     "useEnhancedTooltips": True, "useDefaultAggregateDisplayName": True},
    })
    _json(d / "pages" / "pages.json", {"$schema": f"{RP.SCHEMA}/pagesMetadata/1.0.0/schema.json", "pageOrder": [p.name for p in pages],
                                       "activePageName": pages[0].name})
    for p in pages:
        _json(d / "pages" / p.name / "page.json", p.json())
        for v in p.visuals:
            _json(d / "pages" / p.name / "visuals" / v["name"] / "visual.json", v)
    return pages


def write_pbip():
    _json(PROJECT.parent / f"{NAME}.pbip", {"$schema": "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json",
                                            "version": "1.0", "artifacts": [{"report": {"path": f"{NAME}.Report"}}], "settings": {"enableAutoRecovery": True}})


def inputs(M=None):
    M = M or build_firm()
    p, f = S.base_actuals(M)
    ctx = S.context(M)
    bt = S.budget_targets(M)
    from views.simulator import MIN_CASH
    consts = SP.build_constants(f, ctx, bt, stock_at(M["stock"], "cash", AS_OF), float(X.cash_forecast(M)["closing"].min()), MIN_CASH)
    return M, f, ctx, consts, SP.build_tables(ctx), SP.build_levers(ctx)


def main(export=True):
    M = exports.export_all() if export else None
    M, f, ctx, consts, tables, levers = inputs(M)
    from core import platforms as P
    inp = P.base_inputs(M)
    rk = P.ranking(inp).sort_values("rank")
    top = rk.iloc[0]
    facts = dict(run_rate=f"${P.run_rate(P.BASELINE, inp):,.0f}", best=top["name"], npv=f"+${top['npv']:,.0f}")
    tbls = write_model(consts, tables, levers, ctx)
    pages = write_report(levers, facts)
    write_pbip()
    n_meas = sum(len(t.measures) for t in tbls)
    n_vis = sum(len(p.visuals) for p in pages)
    print(f"{NAME}: {len(tbls)} tables, {n_meas} measures, {len(pages)} pages, {n_vis} visuals")


if __name__ == "__main__":
    main(export="--no-export" not in sys.argv)
