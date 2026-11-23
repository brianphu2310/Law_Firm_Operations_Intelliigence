"""Builds the Power BI report (PBIR: one JSON file per page and per visual) on top of the semantic model.

Every visual is declared in a few lines with the helpers below; the JSON is validated against Microsoft's published
PBIR schemas in tests/test_powerbi.py. Canvas 1280 x 720 (16:9).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from core import platforms as PL, simulate as S

SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition"
V_CONTAINER = f"{SCHEMA}/visualContainer/2.0.0/schema.json"
V_PAGE = f"{SCHEMA}/page/1.4.0/schema.json"
W, H = 1280, 720
SB = 188                      # dark sidebar width; page content is laid out on 1280 and scaled into the rest
KX = (W - SB) / W
SIDEBAR, SIDEBAR_ON, SIDEBAR_TEXT, SIDEBAR_MUTED = "#151b2c", "#0a8496", "#e2e8f0", "#8b95a7"
TEAL, INK, MUTED, LINE, BG = "#0a8496", "#0f172a", "#64748b", "#dbe6ee", "#f3f6fa"
BORDER = "#0f172a"          # outline of every chart block and tile
GREEN, RED, AMBER = "#047857", "#b91c1c", "#b45309"


def _id(*parts):
    return hashlib.sha1("/".join(map(str, parts)).encode()).hexdigest()[:20]


def lit(v):
    if isinstance(v, bool):
        return {"expr": {"Literal": {"Value": "true" if v else "false"}}}
    if isinstance(v, int):
        return {"expr": {"Literal": {"Value": f"{v}L"}}}
    if isinstance(v, float):
        return {"expr": {"Literal": {"Value": f"{v}D"}}}
    return {"expr": {"Literal": {"Value": "'" + str(v).replace("'", "''") + "'"}}}


def colour(c):
    return {"solid": {"color": lit(c)}}


def colour_measure(table, measure):
    return {"solid": {"color": {"expr": {"Measure": {"Expression": {"SourceRef": {"Entity": table}}, "Property": measure}}}}}


# --------------------------------------------------------------------------------------------------------- fields ---
def series_colours(table, column, colours):
    """dataPoint fills for named series values (e.g. a map legend), keyed by the value."""
    out = []
    for value, c in colours.items():
        out.append({"properties": {"fill": colour(c)},
                    "selector": {"data": [{"scopeId": {"Comparison": {"ComparisonKind": 0,
                                                                     "Left": {"Column": {"Expression": {"SourceRef": {"Entity": table}}, "Property": column}},
                                                                     "Right": {"Literal": {"Value": "'" + value + "'"}}}}}]}})
    return out


BAND_COLOURS = {"Under 5 km": "#0a8496", "5–10 km": "#f2b134", "Over 10 km": "#e2665a"}


MAP_EXTENTS = json.loads((Path(__file__).resolve().parent / "assets" / "maps" / "extents.json").read_text())


def map_image(name):
    return {"image": {"name": lit(f"map_{name}.png"),
                      "url": {"expr": {"ResourcePackageItem": {"PackageName": "RegisteredResources", "PackageType": 1, "ItemName": f"map_{name}.png"}}},
                      "scaling": lit("Fit")}}


def catchment_map(p, x, y, w, h, title, subtitle, key=None, size=0.0, image="catchment", bands=True, legend=True, plain_bg=False):
    """Matters by client suburb (sample data) as a scatter chart over a static basemap image: longitude on X, latitude on Y,
    axes pinned to the image's extent. Unlike Power BI's map visuals it needs no Bing/Azure map service, so it works where an
    organisation has switched maps off, in PDF exports and in Publish to web."""
    lon0, lat0, lon1, lat1 = MAP_EXTENTS[image]
    roles = {"Category": [F.c("Suburb", "suburb", "Suburb")], "X": [F.s("Suburb", "longitude", "Longitude")],
             "Y": [F.s("Suburb", "latitude", "Latitude")], "Size": [F.m(M, "Matters Last 12 Months", "Matters, last 12 months")]}
    axis = lambda lo, hi: [{"properties": {"show": lit(False), "start": lit(float(lo)), "end": lit(float(hi)), "gridlineShow": lit(False),
                                           "showAxisTitle": lit(False)}}]
    objects = {"categoryAxis": axis(lon0, lon1), "valueAxis": axis(lat0, lat1),
               "plotArea": [{"properties": {"image": map_image(image), "transparency": lit(0.0)}}],
               "bubbles": [{"properties": {"bubbleSize": lit(size)}}],
               "dataPoint": [{"properties": {"defaultColor": colour("#2a9fb0")}}],
               "categoryLabels": [{"properties": {"show": lit(False)}}]}
    if bands:
        roles["Series"] = [F.c("Suburb", "Distance band", "Distance to nearest office")]
        objects["dataPoint"] = series_colours("Suburb", "Distance band", BAND_COLOURS)
        objects["legend"] = [{"properties": {"show": lit(legend), "position": lit("Bottom")}}]
    else:
        objects["legend"] = [{"properties": {"show": lit(False)}}]
    extra = {"background": False, "border": False} if plain_bg else {}
    p.add("scatterChart", x, y, w, h, roles=roles, objects=objects, title=title, subtitle=subtitle, **extra, **({"key": key} if key else {}))


class F:
    """A field reference: F.m('Measures', 'Revenue'), F.c('Branch', 'branch_name'), F.s('Where to Hire', 'priority') (sum)."""

    def __init__(self, kind, table, name, label=None):
        self.kind, self.table, self.name, self.label = kind, table, name, label

    @classmethod
    def m(cls, table, name, label=None):
        from .model import RENAMED
        return cls("m", table, RENAMED.get(name, name), label or (name if name in RENAMED else None))

    @classmethod
    def c(cls, table, name, label=None):
        return cls("c", table, name, label)

    @classmethod
    def s(cls, table, name, label=None):
        return cls("s", table, name, label)

    def expr(self, source=None):
        ref = {"Source": source} if source else {"Entity": self.table}
        if self.kind == "m":
            return {"Measure": {"Expression": {"SourceRef": ref}, "Property": self.name}}
        col = {"Column": {"Expression": {"SourceRef": ref}, "Property": self.name}}
        if self.kind == "s":
            return {"Aggregation": {"Expression": col, "Function": 0}}
        return col

    @property
    def query_ref(self):
        base = f"{self.table}.{self.name}"
        return f"Sum({base})" if self.kind == "s" else base

    def projection(self):
        p = {"field": self.expr(), "queryRef": self.query_ref, "nativeQueryRef": self.label or self.name}
        if self.label:
            p["displayName"] = self.label
        return p


ALL_FIELDS: list[F] = []      # every field used, checked against the model in tests


def container_objects(title=None, subtitle=None, background=True, border=True, padding=None):
    o = {}
    if title:
        o["title"] = [{"properties": {"show": lit(True), "text": lit(title), "fontSize": lit(11.0), "bold": lit(True), "fontColor": colour(INK)}}]
    else:
        o["title"] = [{"properties": {"show": lit(False)}}]
    if subtitle:
        o["subTitle"] = [{"properties": {"show": lit(True), "text": lit(subtitle), "fontSize": lit(9.0), "fontColor": colour(MUTED)}}]
    o["background"] = [{"properties": {"show": lit(background), "color": colour("#FFFFFF"), "transparency": lit(0.0)}}]
    o["border"] = [{"properties": {"show": lit(border), "color": colour(BORDER), "radius": lit(12.0), "width": lit(1.0)}}]
    o["dropShadow"] = [{"properties": {"show": lit(False)}}]
    if padding is not None:
        o["padding"] = [{"properties": {"top": lit(float(padding)), "bottom": lit(float(padding)), "left": lit(float(padding)), "right": lit(float(padding))}}]
    return o


class Page:
    def __init__(self, name, display, section, order, hidden=False, platform=None):
        self.name, self.display, self.section, self.order = name, display, section, order
        self.visuals = []
        self.z = 0
        self.hidden, self.platform = hidden, platform
        self.filters = []

    def add(self, vtype, x, y, w, h, roles=None, objects=None, title=None, subtitle=None, sort=None, filters=None, sync=None,
            background=True, border=True, vco_extra=None, padding=None, key=None, raw=False):
        if not raw:                       # content area: right of the sidebar
            x, w = SB + x * KX, w * KX
        self.z += 1
        vid = _id(self.name, key or f"{vtype}{self.z}")
        visual = {"visualType": vtype}
        if roles:
            qs = {}
            for role, fields in roles.items():
                qs[role] = {"projections": [f.projection() for f in fields]}
                ALL_FIELDS.extend(fields)
            visual["query"] = {"queryState": qs}
            refs = {pf.query_ref for fl in roles.values() for pf in fl}
            if sort and sort[0].query_ref in refs:     # Power BI sorts only by fields the visual shows
                f, direction = sort
                ALL_FIELDS.append(f)
                visual["query"]["sortDefinition"] = {"sort": [{"field": f.expr(), "direction": direction}], "isDefaultSort": False}
        if objects and vtype == "shape":
            # the shape visual has states (default / hover / pressed): fill and outline only apply with a "default" selector,
            # otherwise Power BI paints the theme colour; and its rounding is set by roundEdge
            for k in ("fill", "outline"):
                for e in objects.get(k, []):
                    e.setdefault("selector", {"id": "default"})
            for e in objects.get("fill", []):
                e["properties"].setdefault("show", lit(True))
            for e in objects.get("shape", []):
                if e["properties"].get("tileShape") == lit("rectangleRounded"):
                    e["properties"].setdefault("roundEdge", lit(10))
        if objects and vtype == "card":
            # show the measure's own format ($1,625,320), not Power BI's automatic K / M units
            for e in objects.get("labels", []):
                e["properties"].setdefault("labelDisplayUnits", lit(1.0))
        if objects:
            visual["objects"] = objects
        vco = container_objects(title, subtitle, background, border, padding)
        if vco_extra:
            vco.update(vco_extra)
        visual["visualContainerObjects"] = vco
        if sync:
            visual["syncGroup"] = {"groupName": sync, "fieldChanges": True, "filterChanges": True}
        visual["drillFilterOtherVisuals"] = True
        v = {"$schema": V_CONTAINER, "name": vid, "position": {"x": float(x), "y": float(y), "z": self.z * 1000, "width": float(w), "height": float(h),
                                                                 "tabOrder": self.z * 1000}, "visual": visual}
        if filters:
            v["filterConfig"] = {"filters": filters}
        self.visuals.append(v)
        return v

    def json(self):
        extra = {}
        if self.filters:
            extra["filterConfig"] = {"filters": self.filters}
        if self.hidden:
            extra["visibility"] = "HiddenInViewMode"
        return {"$schema": V_PAGE, "name": self.name, "displayName": self.display, "displayOption": "FitToPage", "height": H, "width": W, **extra,
                "objects": {"background": [{"properties": {"color": colour(BG), "transparency": lit(0.0)}}],
                            "outspace": [{"properties": {"color": colour("#e9eef4"), "transparency": lit(0.0)}}]}}


# ------------------------------------------------------------------------------------------------- visual helpers ---
def text(page, x, y, w, h, runs, align="left", background=False, border=False, key=None):
    """runs: list of paragraphs; each paragraph a list of (text, size, colour, bold)."""
    paras = []
    for para in runs:
        tr = []
        for t, size, col, bold in para:
            style = {"fontSize": f"{size}pt", "color": col, "fontFamily": "Segoe UI"}
            if bold:
                style["fontWeight"] = "bold"
            tr.append({"value": t, "textStyle": style})
        paras.append({"textRuns": tr, "horizontalTextAlignment": align})
    return page.add("textbox", x, y, w, h, objects={"general": [{"properties": {"paragraphs": paras}}]}, background=background, border=border, key=key)


def card(page, x, y, w, h, field, label=None, size=20.0, colour_field=None, key=None):
    lab = {"show": lit(True), "fontSize": lit(9.0), "color": colour(MUTED)}
    labels = {"fontSize": lit(size), "color": colour_field or colour(INK)}
    objs = {"labels": [{"properties": labels}], "categoryLabels": [{"properties": lab if label is not False else {"show": lit(False)}}]}
    if label:
        field = F(field.kind, field.table, field.name, label)
    return page.add("card", x, y, w, h, roles={"Values": [field]}, objects=objs, border=False, background=False, key=key)


def kpi(page, x, y, w, h, value, label, caption=None, colour_field=None, caption_colour=None, size=18.0):
    """A KPI tile: white box, label + big value, a caption line underneath."""
    page.add("shape", x, y, w, h, objects={"shape": [{"properties": {"tileShape": lit("rectangleRounded")}}],
                                            "fill": [{"properties": {"fillColor": colour("#FFFFFF"), "transparency": lit(0.0)}}],
                                            "outline": [{"properties": {"show": lit(True), "lineColor": colour(BORDER), "weight": lit(1.0)}}]},
             background=False, border=False)
    card(page, x + 4, y + 2, w - 8, h - (26 if caption else 6), value, label, size, colour_field)
    if caption:
        c = F(caption.kind, caption.table, caption.name, " ")
        page.add("card", x + 4, y + h - 28, w - 8, 24, roles={"Values": [c]},
                 objects={"labels": [{"properties": {"fontSize": lit(8.0), "color": caption_colour or colour(MUTED)}}],
                          "categoryLabels": [{"properties": {"show": lit(False)}}]}, background=False, border=False)


def slicer(page, x, y, w, h, field, mode="Dropdown", title=None, sync=None, default=None, horizontal=False, single=True, key=None, force=False):
    """force=True keeps exactly one item selected (period, preset); lever slicers start empty so the preset's value applies."""
    objs = {"data": [{"properties": {"mode": lit(mode)}}],
            "selection": [{"properties": {"strictSingleSelect": lit(force), "singleSelect": lit(single), "selectAllCheckboxEnabled": lit(False)}}],
            "header": [{"properties": {"show": lit(bool(title)), "text": lit(title or ""), "fontSize": lit(9.0), "fontColor": colour(MUTED)}}],
            "items": [{"properties": {"fontSize": lit(9.0)}}]}
    if horizontal:
        objs["general"] = [{"properties": {"orientation": lit(1.0)}}]
    if default is not None:
        objs.setdefault("general", [{"properties": {}}])
        objs["general"][0]["properties"]["filter"] = {"filter": in_filter(field, [default])}
    return page.add("slicer", x, y, w, h, roles={"Values": [field]}, objects=objs, sync=sync, key=key, padding=2)


def in_filter(field, values):
    def lv(v):
        return {"Literal": {"Value": f"{v}L" if isinstance(v, int) else ("'" + str(v).replace("'", "''") + "'")}}
    return {"Version": 2, "From": [{"Name": "t", "Entity": field.table, "Type": 0}],
            "Where": [{"Condition": {"In": {"Expressions": [field.expr("t")], "Values": [[lv(v)] for v in values]}}}]}


def cat_filter(field, value, name):
    ALL_FIELDS.append(field)
    return {"name": name, "field": field.expr(), "type": "Categorical", "filter": in_filter(field, [value])}


def range_filter(field, lo, hi, name):
    def cmp(kind, v):
        return {"Comparison": {"ComparisonKind": kind, "Left": field.expr("t"), "Right": {"Literal": {"Value": f"{v}L"}}}}
    ALL_FIELDS.append(field)
    return {"name": name, "field": field.expr(), "type": "Advanced",
            "filter": {"Version": 2, "From": [{"Name": "t", "Entity": field.table, "Type": 0}],
                       "Where": [{"Condition": {"And": {"Left": cmp(2, lo), "Right": cmp(4, hi)}}}]}}


def chart(page, vtype, x, y, w, h, category, values, title=None, series=None, subtitle=None, sort=None, y2=None, labels=False, legend=True, colours=None, point_colours=None):
    roles = {"Category": category if isinstance(category, list) else [category], "Y": values}
    if series:
        roles["Series"] = [series]
    if y2:
        roles["Y2"] = y2
    objs = {"legend": [{"properties": {"show": lit(legend), "position": lit("Top"), "fontSize": lit(8.0)}}],
            "categoryAxis": [{"properties": {"fontSize": lit(8.0), "showAxisTitle": lit(False)}}],
            "valueAxis": [{"properties": {"fontSize": lit(8.0), "showAxisTitle": lit(False)}}],
            "labels": [{"properties": {"show": lit(labels), "fontSize": lit(8.0)}}]}
    if colours:
        objs["dataPoint"] = [{"properties": {"fill": colour(c)}, "selector": {"metadata": f.query_ref}} for f, c in colours]
    if point_colours:                                  # one colour per category value
        objs["dataPoint"] = series_colours(category.table, category.name, point_colours)
    return page.add(vtype, x, y, w, h, roles=roles, objects=objs, title=title, subtitle=subtitle, sort=sort)


def table(page, x, y, w, h, fields, title=None, subtitle=None, sort=None, filters=None, matrix_rows=None, matrix_cols=None, font=8.0):
    objs = {"columnHeaders": [{"properties": {"fontSize": lit(font), "fontColor": colour(MUTED), "bold": lit(True)}}],
            "values": [{"properties": {"fontSize": lit(font)}}], "total": [{"properties": {"show": lit(False)}}],
            "grid": [{"properties": {"gridHorizontal": lit(True), "rowPadding": lit(2.0)}}]}
    if matrix_rows:
        roles = {"Rows": matrix_rows, "Values": fields}
        if matrix_cols:
            roles["Columns"] = matrix_cols
        objs["rowHeaders"] = [{"properties": {"fontSize": lit(font)}}]
        objs["subTotals"] = [{"properties": {"rowSubtotals": lit(False), "columnSubtotals": lit(False)}}]
        return page.add("pivotTable", x, y, w, h, roles=roles, objects=objs, title=title, subtitle=subtitle, sort=sort, filters=filters)
    return page.add("tableEx", x, y, w, h, roles={"Values": fields}, objects=objs, title=title, subtitle=subtitle, sort=sort, filters=filters)


def nav_button(page, x, y, w, h, label, target, active):
    objs = {"icon": [{"properties": {"show": lit(False)}, "selector": {"id": "default"}}],
            "text": [{"properties": {"show": lit(True)}},
                     {"properties": {"text": lit(label), "fontSize": lit(10.0), "fontColor": colour("#FFFFFF" if active else "#e6f6f8"),
                                     "bold": lit(active)}, "selector": {"id": "default"}}],
            "fill": [{"properties": {"show": lit(True), "fillColor": colour("#066a79" if active else TEAL), "transparency": lit(0.0)}, "selector": {"id": "default"}}],
            "outline": [{"properties": {"show": lit(False)}, "selector": {"id": "default"}}]}
    link = {"visualLink": [{"properties": {"show": lit(True), "type": lit("PageNavigation"), "navigationSection": lit(target)}}]}
    return page.add("actionButton", x, y, w, h, objects=objs, background=False, border=False, vco_extra=link, key=f"nav-{label}")


# ------------------------------------------------------------------------------------------------------------ pages --
M = "Key Measures"   # "Measures" is a reserved table name in Power BI
SIM = "Simulator"


def side_button(page, y, label, target, active, size=10.0, key=None, h=26):
    objs = {"icon": [{"properties": {"show": lit(False)}, "selector": {"id": "default"}}],
            "text": [{"properties": {"show": lit(True)}},
                     {"properties": {"text": lit(label), "fontSize": lit(size), "fontColor": colour("#FFFFFF" if active else SIDEBAR_TEXT),
                                     "bold": lit(active), "horizontalAlignment": lit("left"), "leftMargin": lit(12.0)}, "selector": {"id": "default"}}],
            "fill": [{"properties": {"show": lit(True), "fillColor": colour(SIDEBAR_ON if active else SIDEBAR), "transparency": lit(0.0)}, "selector": {"id": "default"}}],
            "outline": [{"properties": {"show": lit(False)}, "selector": {"id": "default"}}]}
    link = {"visualLink": [{"properties": {"show": lit(True), "type": lit("PageNavigation"), "navigationSection": lit(target)}}]}
    return page.add("actionButton", 10, y, SB - 20, h, objects=objs, background=False, border=False, vco_extra=link, key=key or f"side-{label}", raw=True)


def sidebar(page, sections, platforms):
    """Dark sidebar on every page: app name, the pages, and the seven platform + search combinations."""
    page.add("shape", 0, 0, SB, H, objects={"shape": [{"properties": {"tileShape": lit("rectangle")}}],
                                            "fill": [{"properties": {"fillColor": colour(SIDEBAR), "transparency": lit(0.0)}}],
                                            "outline": [{"properties": {"show": lit(False)}}]}, background=False, border=False, key="sidebar", raw=True)
    page.add("textbox", 8, 12, SB - 12, 46, objects={"general": [{"properties": {"paragraphs": [
        {"textRuns": [{"value": "⚖ Decision Support", "textStyle": {"fontSize": "11.5pt", "color": "#FFFFFF", "fontWeight": "bold", "fontFamily": "Segoe UI"}}]},
        {"textRuns": [{"value": "Law firm · sample data", "textStyle": {"fontSize": "8pt", "color": SIDEBAR_MUTED, "fontFamily": "Segoe UI"}}]}]}}]},
        background=False, border=False, key="brand", raw=True)
    y = 66
    page.add("textbox", 12, y, SB - 20, 24, objects={"general": [{"properties": {"paragraphs": [
        {"textRuns": [{"value": "PAGES", "textStyle": {"fontSize": "7.5pt", "color": SIDEBAR_MUTED, "fontWeight": "bold", "fontFamily": "Segoe UI"}}]}]}}]},
        background=False, border=False, key="lbl-pages", raw=True)
    y += 24
    for label, target in sections:
        side_button(page, y, label, target, active=label.replace("★ ", "") == page.section)
        y += 29
    y += 8
    page.add("textbox", 12, y, SB - 20, 24, objects={"general": [{"properties": {"paragraphs": [
        {"textRuns": [{"value": "PLATFORMS", "textStyle": {"fontSize": "7.5pt", "color": SIDEBAR_MUTED, "fontWeight": "bold", "fontFamily": "Segoe UI"}}]}]}}]},
        background=False, border=False, key="lbl-platforms", raw=True)
    y += 24
    for name, target in platforms:          # practice-management platform + search provider
        label = name
        side_button(page, y, label, target, active=page.platform == name, size=9.0, key=f"plat-{name}", h=24)
        y += 27


def frame(page, title, subtitle, nav, sub_tabs=None):
    """Sidebar, header band and period slicer common to every page."""
    sidebar(page, *nav)
    page.add("shape", 0, 0, W, 60, objects={"shape": [{"properties": {"tileShape": lit("rectangle")}}],
                                            "fill": [{"properties": {"fillColor": colour(TEAL), "transparency": lit(0.0)}}],
                                            "outline": [{"properties": {"show": lit(False)}}]}, background=False, border=False, key="band")
    text(page, 14, 4, 900, 54, [[(title, 17, "#FFFFFF", True)], [(subtitle, 9, "#d9f2f5", False)]], key="title")
    if page.section not in ("Simulator", "Platforms", "Check"):
        slicer(page, 1030, 8, 236, 44, F.c("Period", "Period"), "Dropdown", None, sync="period", default="FY26 Q1 QTD", key="period", force=True)
    if sub_tabs:
        x = 14
        for label, target in sub_tabs:
            active = target == page.name
            page.add("actionButton", x, 66, 170, 26, objects={
                "icon": [{"properties": {"show": lit(False)}, "selector": {"id": "default"}}],
                "text": [{"properties": {"show": lit(True)}}, {"properties": {"text": lit(label), "fontSize": lit(9.0), "fontColor": colour(TEAL if active else MUTED),
                                                                              "bold": lit(active)}, "selector": {"id": "default"}}],
                "fill": [{"properties": {"show": lit(True), "fillColor": colour("#e0f2f4" if active else "#FFFFFF"), "transparency": lit(0.0)}, "selector": {"id": "default"}}],
                "outline": [{"properties": {"show": lit(True), "lineColor": colour(TEAL if active else LINE), "weight": lit(1.0)}, "selector": {"id": "default"}}]},
                background=False, border=False, vco_extra={"visualLink": [{"properties": {"show": lit(True), "type": lit("PageNavigation"), "navigationSection": lit(target)}}]},
                key=f"tab-{label}")
            x += 176


def build_pages(ctx_facts, levers):
    P = {}
    specs = [("overview", "Overview", "Overview"), ("finance_pl", "Finance · P&L", "Finance"), ("finance_cash", "Finance · Cash & billing", "Finance"),
             ("finance_trust", "Finance · Trust & costs", "Finance"), ("people_perf", "People · Performance", "People"),
             ("people_hire", "People · Hiring & departments", "People"), ("people_branch", "People · Branches & pay", "People"),
             ("matters", "Matters", "Matters"), ("matters_map", "Matters · Map", "Matters"), ("clients", "Clients", "Clients"), ("clients_mkt", "Clients · Marketing", "Clients"),
             ("calendar", "Calendar", "Calendar"), ("sim_decide", "Simulator · Decide", "Simulator"),
             ("sim_test", "Simulator · Test", "Simulator"), ("check", "Method & check", "Check")]
    for i, (n, d, s) in enumerate(specs):
        P[n] = Page(_id("page", n), d, s, i)
    plat_pages = []
    for j, name in enumerate(PL.NAMES):
        pg = Page(_id("page", "platform", name), f"Platform · {PL.PLATFORMS[name]['short']}", "Platforms", 100 + j, hidden=j > 0, platform=name)
        plat_pages.append(pg)
    sections = [("Overview", P["overview"].name), ("Finance", P["finance_pl"].name), ("People", P["people_perf"].name),
                ("Matters", P["matters"].name), ("Clients", P["clients"].name), ("Calendar", P["calendar"].name),
                ("★ Simulator", P["sim_decide"].name), ("Check", P["check"].name)]
    nav = (sections, [(pg.platform, pg.name) for pg in plat_pages])
    fin_tabs = [("P&L & outlook", P["finance_pl"].name), ("Cash & billing", P["finance_cash"].name), ("Trust & costs", P["finance_trust"].name)]
    ppl_tabs = [("Performance", P["people_perf"].name), ("Hiring & departments", P["people_hire"].name), ("Branches & pay", P["people_branch"].name)]
    cli_tabs = [("Clients", P["clients"].name), ("Marketing", P["clients_mkt"].name)]
    sim_tabs = [("Decide", P["sim_decide"].name), ("Test the plan", P["sim_test"].name)]

    best = next(pg for pg in plat_pages if pg.platform == ctx_facts["answers"][0]["Answer"].split(": ", 1)[-1]) if ctx_facts.get("answers") else plat_pages[0]
    targets = {"Platform": ("Platform", best.name), "Simulator": ("Simulator", P["sim_decide"].name), "People": ("People", P["people_hire"].name),
               "Clients": ("Marketing", P["clients_mkt"].name)}
    overview(P["overview"], nav, ctx_facts, targets)
    finance_pl(P["finance_pl"], nav, fin_tabs)
    finance_cash(P["finance_cash"], nav, fin_tabs)
    finance_trust(P["finance_trust"], nav, fin_tabs)
    people_perf(P["people_perf"], nav, ppl_tabs)
    people_hire(P["people_hire"], nav, ppl_tabs)
    people_branch(P["people_branch"], nav, ppl_tabs)
    mat_tabs = [("Ledger", P["matters"].name), ("Map", P["matters_map"].name)]
    matters(P["matters"], nav, mat_tabs)
    matters_map(P["matters_map"], nav, mat_tabs, ctx_facts)
    clients(P["clients"], nav, cli_tabs)
    clients_mkt(P["clients_mkt"], nav, cli_tabs)
    calendar(P["calendar"], nav)
    for pg in plat_pages:
        platform(pg, nav)
    sim_decide(P["sim_decide"], nav, sim_tabs, levers)
    sim_test(P["sim_test"], nav, sim_tabs, levers)
    check(P["check"], nav)
    pages = list(P.values())
    return pages[:12] + plat_pages + pages[12:]


# ---- Overview
# one chart type per question, each the natural shape for its answer
TILE_CHART = {0: "clusteredBarChart",          # software: ranking of savings
              1: "gauge",                      # branch: cash low point against the minimum balance
              2: "clusteredColumnChart",       # hiring: year-one gain by area
              3: "clusteredBarChart",          # support: roles over (+) or under (-) the work
              4: "lineChart",                  # pay: cost rising with the pay increase
              5: "treemap"}                    # growth: new matters per $1,000 by channel (biggest box = best value)


def answer_chart(p, i, row, cx, cy):
    flt = [cat_filter(F.c("Answer Chart", "Order"), int(row["Order"]), _id(p.name, "ch", i))]
    vt = TILE_CHART[i]
    unit = "Answer Chart Roles" if i == 3 else "Answer Chart $"
    lab = {"show": lit(True), "fontSize": lit(8.0), "color": colour("#334155"),
           "labelDisplayUnits": lit(1.0 if i == 3 else 1000.0), "labelPrecision": lit(1 if i == 3 else 0)}
    fill = [{"properties": {"fill": colour_measure(M, "Answer Chart Colour")}, "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}]}}]
    box = dict(background=False, border=False, filters=flt, key=f"c{i}")
    if vt == "gauge":
        p.add("gauge", cx + 40, cy + 60, 333, 106,
              roles={"Y": [F.m(M, "Answer Gauge Value", "Cash low point after")], "TargetValue": [F.m(M, "Answer Gauge Target", "Minimum balance")],
                     "MinValue": [F.m(M, "Answer Gauge Min", "Min")], "MaxValue": [F.m(M, "Answer Gauge Max", "Max")]},
              objects={"dataPoint": [{"properties": {"fill": colour("#e2665a"), "target": colour(INK)}}],
                       "calloutValue": [{"properties": {"show": lit(True), "fontSize": lit(14.0), "color": colour("#e2665a"),
                                                        "labelDisplayUnits": lit(1000.0), "labelPrecision": lit(0)}}],
                       "labels": [{"properties": {"show": lit(True), "fontSize": lit(7.0), "labelDisplayUnits": lit(1000.0)}}],
                       "target": [{"properties": {"show": lit(True), "fontSize": lit(8.0), "labelDisplayUnits": lit(1000.0)}}]}, **box)
        return
    roles = {"Category": [F.c("Answer Chart", "Item")], "Y": [F.m(M, unit, "Value")]}
    objs = {"legend": [{"properties": {"show": lit(False)}}], "labels": [{"properties": dict(lab)}], "dataPoint": fill}
    if vt == "treemap":
        roles = {"Group": [F.c("Answer Chart", "Item")], "Values": [F.m(M, "Answer Chart Per 1K", "New matters per $1,000")]}
        objs["labels"] = [{"properties": {"show": lit(True), "fontSize": lit(8.5), "color": colour("#FFFFFF"), "labelPrecision": lit(1)}}]
        objs["categoryLabels"] = [{"properties": {"show": lit(True), "fontSize": lit(8.5), "color": colour("#FFFFFF")}}]
    else:
        objs["categoryAxis"] = [{"properties": {"show": lit(True), "fontSize": lit(8.0), "showAxisTitle": lit(False), "color": colour("#334155")}}]
        objs["valueAxis"] = [{"properties": {"show": False if vt != "lineChart" else False, "showAxisTitle": lit(False)}}]
        objs["valueAxis"][0]["properties"]["show"] = lit(False)
    if vt == "lineChart":
        objs.pop("dataPoint")
        objs["dataPoint"] = [{"properties": {"fill": colour(TEAL)}}]
        objs["lineStyles"] = [{"properties": {"showMarker": lit(True), "markerSize": lit(5.0), "strokeWidth": lit(2.5)}}]
    p.add(vt, cx + 8, cy + 60, 397, 106, roles=roles, objects=objs, **box)


def overview(p, nav, facts, targets):
    """The whole project on one screen: firm health, then the Principal's six questions with the answer the model gives."""
    frame(p, "Overview", "Six decisions for the Principal of a three-office law firm, answered from one model · sample data, as of 17 Sep 2025", nav)
    x = [14 + i * 314 for i in range(4)]
    kpi(p, x[0], 68, 306, 78, F.m(M, "Revenue"), "Revenue this period", F.m(M, "Revenue Δ"))
    kpi(p, x[1], 68, 306, 78, F.m(M, "Operating Profit"), "Operating profit this period", F.m(M, "Profit vs Budget Caption"))
    kpi(p, x[2], 68, 306, 78, F.m(M, "Utilisation"), "Fee-earner utilisation", F.m(M, "Utilisation Δ"))
    kpi(p, x[3], 68, 306, 78, F.m(M, "Cash Low Point"), "Cash low point, next 13 weeks", F.m(M, "Cash Caption"))
    for i, row in enumerate(facts["answers"]):
        cx, cy = 14 + (i % 3) * 421, 154 + (i // 3) * 178
        p.add("shape", cx, cy, 413, 170, objects={"shape": [{"properties": {"tileShape": lit("rectangleRounded")}}],
                                                  "fill": [{"properties": {"fillColor": colour("#FFFFFF"), "transparency": lit(0.0)}}],
                                                  "outline": [{"properties": {"show": lit(True), "lineColor": colour(BORDER), "weight": lit(1.0)}}]},
              background=False, border=False, key=f"tile{i}")
        p.add("shape", cx, cy + 14, 5, 26, objects={"shape": [{"properties": {"tileShape": lit("rectangle")}}],
                                                    "fill": [{"properties": {"fillColor": colour(TEAL), "transparency": lit(0.0)}}],
                                                    "outline": [{"properties": {"show": lit(False)}}]}, background=False, border=False, key=f"accent{i}")
        text(p, cx + 12, cy + 6, 280, 24, [[(f"{i + 1}  ", 10, TEAL, True), (row["Question"].upper(), 8, MUTED, True)]], key=f"q{i}")
        flt = lambda tag: [cat_filter(F.c("Answers", "Order"), int(row["Order"]), _id(p.name, tag, i))]
        p.add("card", cx + 8, cy + 28, 397, 30, roles={"Values": [F.m(M, "Answer", " ")]},
              objects={"labels": [{"properties": {"fontSize": lit(13.0), "color": colour(INK)}}], "categoryLabels": [{"properties": {"show": lit(False)}}]},
              background=False, border=False, filters=flt("ans"), key=f"a{i}")
        answer_chart(p, i, row, cx, cy)
        label, target = targets[row["Page"]]
        p.add("actionButton", cx + 297, cy + 7, 108, 22, objects={
            "icon": [{"properties": {"show": lit(False)}, "selector": {"id": "default"}}],
            "text": [{"properties": {"show": lit(True)}}, {"properties": {"text": lit(f"{label} →"), "fontSize": lit(8.5), "fontColor": colour(TEAL), "bold": lit(True)},
                                                          "selector": {"id": "default"}}],
            "fill": [{"properties": {"show": lit(True), "fillColor": colour("#e0f2f4"), "transparency": lit(0.0)}, "selector": {"id": "default"}}],
            "outline": [{"properties": {"show": lit(False)}, "selector": {"id": "default"}}]},
            background=False, border=False, vco_extra={"visualLink": [{"properties": {"show": lit(True), "type": lit("PageNavigation"), "navigationSection": lit(target)}}]},
            key=f"go{i}")
    chart(p, "lineClusteredColumnComboChart", 14, 510, 624, 202, F.c("Date", "month_start_date", "Month"), [F.m(M, "Trend Operating Profit", "Operating profit")],
          "Profit against budget, month by month", y2=[F.m(M, "Trend Budget Operating Profit", "Budget")], subtitle="12 months to the period end")
    # where clients come from: the map on the left, the two numbers that matter on the right
    p.add("shape", 644, 510, 622, 202, objects={"shape": [{"properties": {"tileShape": lit("rectangleRounded")}}],
                                                "fill": [{"properties": {"fillColor": colour("#FFFFFF"), "transparency": lit(0.0)}}],
                                                "outline": [{"properties": {"show": lit(True), "lineColor": colour(BORDER), "weight": lit(1.0)}}]},
          background=False, border=False, key="ovmaptile")
    catchment_map(p, 648, 512, 312, 198, "Where clients come from", "Matters, last 12 months, by client suburb",
                  key="ovmap", image="overview", bands=True, legend=True, plain_bg=True)
    card(p, 964, 548, 296, 46, F.m(M, "Matters 10km+ Share"), False, 26.0, colour("#e2665a"), key="ovfar")
    p.add("card", 964, 592, 296, 28, roles={"Values": [F.m(M, "Matters 10km+ Caption", " ")]},
          objects={"labels": [{"properties": {"fontSize": lit(8.5), "color": colour(MUTED)}}], "categoryLabels": [{"properties": {"show": lit(False)}}]},
          background=False, border=False, key="ovfarcap")
    card(p, 964, 626, 296, 38, F.m(M, "Best Branch Site"), False, 18.0, colour("#7c3aed"), key="ovsite")
    p.add("card", 964, 662, 296, 28, roles={"Values": [F.m(M, "Best Branch Site Caption", " ")]},
          objects={"labels": [{"properties": {"fontSize": lit(8.5), "color": colour(MUTED)}}], "categoryLabels": [{"properties": {"show": lit(False)}}]},
          background=False, border=False, key="ovsitecap")


# ---- Finance
def finance_pl(p, nav, tabs):
    frame(p, "Finance · P&L and outlook", "Profit and loss against budget for the period, and where the financial year is heading", nav, tabs)
    kpi(p, 14, 130, 202, 78, F.m(M, "Revenue"), "Revenue", F.m(M, "Revenue Δ"))
    kpi(p, 222, 130, 202, 78, F.m(M, "Operating Profit"), "Operating profit")
    kpi(p, 430, 130, 202, 78, F.m(M, "Profit vs Budget"), "Profit vs budget")
    kpi(p, 638, 130, 202, 78, F.m(M, "Operating Margin"), "Operating margin")
    kpi(p, 846, 130, 202, 78, F.m(M, "FY Forecast Profit"), "FY26 forecast profit")
    kpi(p, 1054, 130, 212, 78, F.m(M, "FY Profit Gap"), "FY26 forecast vs budget")
    table(p, 14, 216, 560, 496, [F.m(M, "P&L Actual", "Actual"), F.m(M, "P&L Budget", "Budget"), F.m(M, "P&L Variance", "Variance"),
                                 F.m(M, "P&L Variance %", "Var %")], "P&L vs budget", "Favourable variance is positive",
          matrix_rows=[F.c("P&L Line", "Line")], sort=(F.c("P&L Line", "Order"), "Ascending"))
    chart(p, "lineClusteredColumnComboChart", 580, 216, 686, 246, F.c("Date", "month_start_date", "Month"), [F.m(M, "Trend Operating Profit", "Profit")],
          "Operating profit vs budget by month", y2=[F.m(M, "Trend Budget Operating Profit", "Budget")], subtitle="12 months to the period end")
    chart(p, "lineClusteredColumnComboChart", 580, 468, 686, 244, F.c("FY Outlook", "month", "Month"),
          [F.m(M, "FY Path Actual Profit", "Actual"), F.m(M, "FY Path Forecast Profit", "Forecast")], "FY26 outlook: profit by month",
          y2=[F.m(M, "FY Path Budget Profit", "Budget")], subtitle="Year to date actual, rest of year = budget × year-to-date performance")


def finance_cash(p, nav, tabs):
    frame(p, "Finance · Cash & billing", "13-week cash forecast, receivables ageing, work in progress and collection speed", nav, tabs)
    kpi(p, 14, 130, 202, 78, F.m(M, "Office Cash"), "Office account")
    kpi(p, 222, 130, 202, 78, F.m(M, "Cash Low Point"), "13-week low point")
    kpi(p, 430, 130, 202, 78, F.m(M, "Receivables"), "Receivables (incl GST)")
    kpi(p, 638, 130, 202, 78, F.m(M, "WIP"), "Work in progress")
    kpi(p, 846, 130, 202, 78, F.m(M, "DSO"), "Days to collect (DSO)")
    kpi(p, 1054, 130, 212, 78, F.m(M, "Lockup Days"), "Lock-up days")
    chart(p, "lineClusteredColumnComboChart", 14, 216, 760, 248, F.c("Cash Forecast", "week_start", "Week starting"),
          [F.m(M, "Cash Inflow", "Money in"), F.m(M, "Cash Outflow", "Money out")], "13-week cash forecast",
          y2=[F.m(M, "Cash Closing", "Closing balance"), F.m(M, "Cash Minimum", "Minimum balance")],
          subtitle="Collections from open invoices and run-rate billing; payroll, rent, BAS and drawings")
    chart(p, "clusteredColumnChart", 780, 216, 486, 248, F.c("AR Ageing", "Bucket"), [F.m(M, "AR Amount", "Receivables")], "Receivables ageing",
          sort=(F.c("AR Ageing", "Order"), "Ascending"), labels=True, legend=False, subtitle="Days past due at the period end")
    chart(p, "lineChart", 14, 470, 620, 242, F.c("Date", "month_start_date", "Month"), [F.m(M, "Trend WIP", "WIP"), F.m(M, "Trend Receivables", "Receivables")],
          "WIP and receivables by month", subtitle="Month-end balances")
    table(p, 640, 470, 626, 242, [F.c("Client Period", "client", "Client"), F.c("Client Period", "ar", "Receivables"), F.c("Client Period", "overdue", "Overdue"),
                                  F.c("Client Period", "days_to_pay", "Avg days to pay")], "Who owes the firm", sort=(F.c("Client Period", "ar"), "Descending"))


def finance_trust(p, nav, tabs):
    frame(p, "Finance · Trust account & costs", "Client money held in trust, and where supplier and card spend goes", nav, tabs)
    kpi(p, 14, 130, 300, 78, F.m(M, "Trust Funds"), "Trust funds held (period end)")
    kpi(p, 320, 130, 300, 78, F.m(M, "Supplier Spend"), "Search & council spend (all time)")
    kpi(p, 626, 130, 300, 78, F.m(M, "Card Spend"), "Card expenses (all time)")
    kpi(p, 932, 130, 334, 78, F.m(M, "Disbursement Recovery"), "Disbursement recovery (period)")
    chart(p, "areaChart", 14, 216, 620, 240, F.c("Date", "month_start_date", "Month"), [F.m(M, "Trend Trust", "Trust balance")], "Trust account balance",
          subtitle="Month-end, all clients", legend=False)
    table(p, 640, 216, 626, 240, [F.c("Trust Txn", "txn_date_key", "Date key"), F.c("Client", "client_name", "Client"), F.c("Trust Txn", "txn_type", "Type"),
                                  F.c("Trust Txn", "amount", "Amount")], "Latest trust transactions", sort=(F.c("Trust Txn", "txn_date_key"), "Descending"))
    chart(p, "columnChart", 14, 462, 620, 250, F.c("Date", "fy_label", "Financial year"), [F.m(M, "Supplier Spend", "Spend")], "Search and council spend",
          F.c("Supplier Order", "supplier"), "By financial year and supplier")
    chart(p, "clusteredBarChart", 640, 462, 300, 250, F.c("Cards", "category"), [F.m(M, "Card Spend", "Spend")], "Card expenses by category",
          sort=(F.m(M, "Card Spend"), "Descending"), legend=False)
    table(p, 946, 462, 320, 250, [F.c("Commissions", "referrer", "Referrer"), F.c("Commissions", "matter", "Matter"), F.c("Commissions", "amount", "Amount"),
                                  F.c("Commissions", "status", "Status")], "Referral commissions")


# ---- People
def people_perf(p, nav, tabs):
    frame(p, "People · Performance", "How busy and how profitable each fee earner is this period", nav, tabs)
    kpi(p, 14, 130, 248, 78, F.m(M, "Utilisation"), "Firm utilisation", F.m(M, "Utilisation Δ"))
    kpi(p, 268, 130, 248, 78, F.m(M, "Realisation"), "Realisation")
    kpi(p, 522, 130, 248, 78, F.m(M, "Effective Rate"), "Effective rate per hour")
    kpi(p, 776, 130, 248, 78, F.m(M, "Billable Hours"), "Billable hours", F.m(M, "Hours Δ"))
    kpi(p, 1030, 130, 236, 78, F.m(M, "Top Biller Fees"), "Top biller fees", F.m(M, "Top Biller"))
    table(p, 14, 216, 760, 260, [F.c("Attorney", "attorney_name", "Fee earner"), F.c("Attorney", "role", "Role"), F.m(M, "Attorney Hours", "Hours"),
                                 F.m(M, "Attorney Utilisation", "Utilisation"), F.m(M, "Attorney Realisation", "Realisation"),
                                 F.m(M, "Attorney Effective Rate", "Eff. rate"), F.m(M, "Attorney Fees", "Fees"), F.m(M, "Attorney Cost", "Pay"),
                                 F.m(M, "Attorney Contribution", "Contribution")], "Fee-earner performance", sort=(F.m(M, "Attorney Fees"), "Descending"))
    chart(p, "clusteredBarChart", 780, 216, 486, 260, F.c("Attorney", "attorney_short"), [F.m(M, "Attorney Utilisation", "Utilisation")],
          "Utilisation by fee earner", sort=(F.m(M, "Attorney Utilisation"), "Descending"), labels=True, legend=False)
    chart(p, "lineChart", 14, 482, 620, 230, F.c("Date", "month_start_date", "Month"), [F.m(M, "Trend Attorney Utilisation", "Utilisation")], "Utilisation by month",
          F.c("Attorney", "attorney_short"), "12 months to the period end")
    chart(p, "columnChart", 640, 482, 626, 230, F.c("Attorney", "attorney_short"), [F.m(M, "Area Hours", "Hours")], "Hours by practice area",
          F.c("Practice Area", "practice_area"), "Who does which work")


def people_hire(p, nav, tabs):
    frame(p, "People · Where to hire and departments", "Which practice area needs the next lawyer, and which support teams are over or under the workload", nav, tabs)
    card(p, 14, 128, 420, 40, F.m(M, "Hire First"), False, 15.0)
    chart(p, "clusteredBarChart", 14, 172, 420, 230, F.c("Where to Hire", "area"), [F.s("Where to Hire", "priority", "Priority (0–100)")], "Hiring priority",
          sort=(F.s("Where to Hire", "priority"), "Descending"), labels=True, legend=False,
          subtitle="40% how busy the lawyers are, 35% growth in new matters, 25% margin")
    p.add("scatterChart", 440, 128, 400, 274, roles={"Category": [F.c("Where to Hire", "area")], "X": [F.s("Where to Hire", "util", "Lawyers' utilisation")],
                                                    "Y": [F.s("Where to Hire", "matters_growth", "Growth in new matters")], "Size": [F.s("Where to Hire", "fees", "Fees")]},
          objects={"categoryLabels": [{"properties": {"show": lit(True), "fontSize": lit(8.0)}}]}, title="Pressure vs demand", subtitle="Top right = hire here")
    table(p, 846, 128, 420, 274, [F.c("Where to Hire", "area", "Area"), F.c("Where to Hire", "util", "Utilisation"), F.c("Where to Hire", "matters_growth", "New matters"),
                                  F.c("Where to Hire", "margin", "Margin"), F.c("Where to Hire", "verdict", "Verdict")], "Practice areas",
          sort=(F.c("Where to Hire", "rank"), "Ascending"))
    chart(p, "clusteredBarChart", 14, 408, 560, 304, F.c("Dept Workload", "department"), [F.s("Dept Workload", "headcount", "Staff"), F.s("Dept Workload", "needed", "Needed for the workload")],
          "Support staff vs workload", subtitle="Headcount against benchmarks (all branches)")
    table(p, 580, 408, 686, 304, [F.c("Dept Workload", "branch", "Office"), F.c("Dept Workload", "department", "Department"), F.c("Dept Workload", "headcount", "Staff"),
                                  F.c("Dept Workload", "needed", "Needed"), F.c("Dept Workload", "gap", "Gap"), F.c("Dept Workload", "status", "Status"),
                                  F.c("Dept Workload", "cost_of_gap", "Cost of the gap a year")], "Department by office", sort=(F.c("Dept Workload", "gap"), "Descending"))


def people_branch(p, nav, tabs):
    frame(p, "People · Branches, staffing and pay", "Office profitability and headcount, and what a pay review costs", nav, tabs)
    table(p, 14, 128, 760, 190, [F.c("Branch Period", "branch", "Office"), F.c("Branch Period", "fee_earners", "Fee earners"), F.c("Branch Period", "support", "Support"),
                                 F.c("Branch Period", "util", "Utilisation"), F.c("Branch Period", "revenue", "Revenue"), F.c("Branch Period", "cost", "Cost"),
                                 F.c("Branch Period", "op_profit", "Profit"), F.c("Branch Period", "margin", "Margin"), F.c("Branch Period", "active_matters", "Active matters")],
          "Branches this period")
    table(p, 780, 128, 486, 190, [F.m(M, "Headcount", "Staff")], "Support staff by office and department", matrix_rows=[F.c("Department", "department")],
          matrix_cols=[F.c("Branch", "branch_name")])
    chart(p, "clusteredColumnChart", 14, 324, 620, 260, F.c("Branch Period", "branch"), [F.s("Branch Period", "revenue", "Revenue"), F.s("Branch Period", "cost", "Cost")],
          "Revenue and cost by office")
    table(p, 640, 324, 626, 260, [F.c("Attorney", "attorney_name", "Fee earner"), F.c("Attorney", "role", "Role"), F.c("Attorney", "bill_rate", "Bill rate"),
                                  F.c("Attorney", "pay_rate", "Pay rate"), F.m(M, "Attorney Break-even Hours", "Break-even hours"), F.m(M, "Attorney Contribution", "Contribution")],
          "Pay and economics", sort=(F.m(M, "Attorney Contribution"), "Descending"), subtitle="Hourly rates; break-even = hours needed to cover pay")
    kpi(p, 14, 590, 300, 122, F.m(M, "Market Wage Growth"), "Market wage growth (ABS WPI, private)")
    kpi(p, 320, 590, 300, 122, F.m(SIM, "Sim Pay Rise Cost"), "Cost of a 3% pay rise, a year")
    kpi(p, 626, 590, 300, 122, F.m(SIM, "Sim Pay Rise Rate"), "Rate rise that pays for it (%)")
    text(p, 932, 590, 334, 122, [[("Pay below market wage growth risks losing people. Pay cuts generally need the employee's agreement and cannot go "
                                   "below award minimums. Test a pay review in the Simulator.", 9, MUTED, False)]], background=True, border=True)


# ---- Matters
def matter_slicers(p, y):
    slicer(p, 14, y, 300, 40, F.c("Matter", "status"), "Dropdown", "Status", single=False, sync="m-status", key="s-status")
    slicer(p, 320, y, 300, 40, F.c("Practice Area", "practice_area"), "Dropdown", "Practice area", single=False, sync="m-area", key="s-area")
    slicer(p, 626, y, 300, 40, F.c("Branch", "branch_name"), "Dropdown", "Office", single=False, sync="m-office", key="s-office")


def matters_map(p, nav, tabs, facts):
    cf = facts["catchment"]
    frame(p, "Matters · Map", "Where the work comes from, and where a new branch would reach the clients the offices are far from", nav, tabs)
    matter_slicers(p, 100)
    catchment_map(p, 14, 146, 520, 566, "Where clients come from: matters by client suburb",
                  f"Last 12 months · colour = distance to the nearest office · {cf['far']} of {cf['total']} matters from 10+ km away")
    p.add("map", 540, 146, 726, 250, roles={"Category": [F.c("Country Geo", "Country")], "Size": [F.m(M, "Matter Count", "Matters")]},
          objects={"bubbles": [{"properties": {"bubbleSize": lit(10.0)}}], "dataPoint": [{"properties": {"defaultColor": colour(TEAL)}}],
                   "categoryLabels": [{"properties": {"show": lit(True)}}], "mapStyles": [{"properties": {"mapTheme": lit("grayscale")}}]},
          title="Matters by client country", subtitle="All matters on the ledger · bubble size = number of matters")
    table(p, 540, 402, 440, 310, [F.c("Branch Sites", "candidate_site", "Site"), F.s("Branch Sites", "underserved_matters_ltm", "Matters in reach"),
                                  F.s("Branch Sites", "est_value_ltm", "Est. value"), F.c("Branch Sites", "nearest_office", "Nearest office"),
                                  F.s("Branch Sites", "km_to_nearest_office", "km")],
          "Where a new branch would help most",
          f"Last year's matters from 10+ km away that a new office would bring within 10 km",
          sort=(F.s("Branch Sites", "underserved_matters_ltm"), "Descending"))
    chart(p, "clusteredColumnChart", 986, 402, 280, 310, F.c("Suburb", "Distance band"), [F.m(M, "Matters Last 12 Months", "Matters")],
          "Distance to nearest office", labels=True, legend=False, subtitle="Matters, last 12 months",
          sort=(F.c("Suburb", "Distance band"), "Ascending"), point_colours=BAND_COLOURS)


def matters(p, nav, tabs):
    frame(p, "Matters", "Every matter on the ledger: status, value, billing and work in progress", nav, tabs)
    kpi(p, 14, 100, 248, 78, F.m(M, "Active Matters"), "Active matters (period end)", F.m(M, "Active Matters Δ"))
    kpi(p, 268, 100, 248, 78, F.m(M, "Matters Opened"), "New matters this period")
    kpi(p, 522, 100, 248, 78, F.m(M, "Matter Estimated Value"), "Estimated value (all matters)")
    kpi(p, 776, 100, 248, 78, F.m(M, "Matter Billed"), "Billed to date")
    kpi(p, 1030, 100, 236, 78, F.m(M, "Matter WIP"), "Work in progress")
    matter_slicers(p, 186)
    table(p, 14, 232, 912, 480, [F.c("Matter", "matter_id", "Matter"), F.c("Matter", "matter_name", "Name"), F.c("Matter", "status", "Status"),
                                 F.c("Attorney", "attorney_short", "Lawyer"), F.c("Matter Position", "estimated_value", "Est. value"),
                                 F.c("Matter Position", "billed_to_date", "Billed"), F.c("Matter Position", "wip_balance", "WIP"),
                                 F.c("Matter Position", "progress_ratio", "Progress"), F.c("Matter Position", "days_open", "Days open")], "Matter ledger",
          sort=(F.c("Matter Position", "wip_balance"), "Descending"))
    chart(p, "clusteredColumnChart", 932, 186, 334, 170, F.c("Date", "month_start_date", "Month"), [F.m(M, "Trend Matters Opened", "Opened"), F.m(M, "Trend Matters Closed", "Closed")],
          "Matters opened and closed")
    chart(p, "clusteredBarChart", 932, 362, 334, 170, F.c("Matter Position", "Age bucket"), [F.m(M, "Matter WIP", "WIP")], "WIP by matter age", legend=False, labels=True)
    p.add("donutChart", 932, 538, 334, 174, roles={"Category": [F.c("Matter", "country")], "Y": [F.m(M, "Matter Count", "Matters")]},
          objects={"legend": [{"properties": {"show": lit(True), "position": lit("Right"), "fontSize": lit(8.0)}}]}, title="Matters by country")


# ---- Clients
def clients(p, nav, tabs):
    frame(p, "Clients", "Revenue, concentration, receivables and how quickly each client pays", nav, tabs)
    kpi(p, 14, 128, 300, 78, F.m(M, "Client Revenue"), "Billed this period (ex GST)")
    kpi(p, 320, 128, 300, 78, F.m(M, "Top 5 Client Share"), "Top 5 clients' share")
    kpi(p, 626, 128, 300, 78, F.m(M, "Client Receivables"), "Receivables")
    kpi(p, 932, 128, 334, 78, F.m(M, "Client Overdue"), "Overdue")
    table(p, 14, 214, 760, 498, [F.c("Client Period", "client", "Client"), F.c("Client Period", "practice", "Practice"), F.c("Client Period", "attorney", "Partner"),
                                 F.c("Client Period", "revenue", "Revenue"), F.c("Client Period", "prev", "Prior period"), F.c("Client Period", "share", "Share"),
                                 F.c("Client Period", "ar", "Receivables"), F.c("Client Period", "days_to_pay", "Days to pay"),
                                 F.c("Client Period", "active_matters", "Active matters")], "Client league", sort=(F.c("Client Period", "revenue"), "Descending"))
    chart(p, "clusteredBarChart", 780, 214, 486, 250, F.c("Client Period", "client"), [F.s("Client Period", "revenue", "Revenue")], "Concentration: revenue by client",
          sort=(F.s("Client Period", "revenue"), "Descending"), legend=False)
    p.add("scatterChart", 780, 470, 486, 242, roles={"Category": [F.c("Client Period", "client")], "X": [F.s("Client Period", "days_to_pay", "Average days to pay")],
                                                    "Y": [F.s("Client Period", "ar", "Receivables")], "Size": [F.s("Client Period", "revenue", "Revenue")]},
          title="Payment behaviour", subtitle="Slow payers with big balances are top right")


def clients_mkt(p, nav, tabs):
    frame(p, "Clients · Marketing", "Where new clients come from and what each channel costs per new matter (last 12 months)", nav, tabs)
    kpi(p, 14, 128, 300, 78, F.m(M, "Marketing Spend"), "Marketing spend (last 12 months)")
    kpi(p, 320, 128, 300, 78, F.m(M, "Marketing Matters"), "New matters from marketing")
    kpi(p, 626, 128, 300, 78, F.m(M, "Cost per Matter"), "Average cost per new matter")
    kpi(p, 932, 128, 334, 78, F.m(M, "Fees per Dollar"), "Fees per marketing dollar")
    chart(p, "clusteredBarChart", 14, 214, 620, 250, F.c("Marketing", "channel"), [F.s("Marketing", "cost_per_matter", "Cost per new matter")], "Cost per new matter by channel",
          sort=(F.s("Marketing", "cost_per_matter"), "Ascending"), labels=True, legend=False, subtitle="Lower is better")
    table(p, 640, 214, 626, 250, [F.c("Marketing", "channel", "Channel"), F.c("Marketing", "spend", "Spend"), F.c("Marketing", "inquiries", "Inquiries"),
                                  F.c("Marketing", "matters", "New matters"), F.c("Marketing", "conversion", "Conversion"), F.c("Marketing", "fees", "Fees"),
                                  F.c("Marketing", "fees_per_dollar", "Fees per $")], "Channels")
    chart(p, "lineChart", 14, 470, 620, 242, F.c("Date", "month_start_date", "Month"), [F.m(M, "Trend Inquiries", "Inquiries"), F.m(M, "Trend Matters Opened", "New matters")],
          "Inquiries and new matters by month")
    text(p, 640, 470, 626, 242, [[("How to use this", 11, INK, True)],
                                 [("Spend splits the firm's actual marketing cost by channel mix; referrals are paid by commission. New-matter fees use the average fees "
                                   "billed per matter in the year, weighted by each channel's typical matter value. Test extra spend on a channel in the Simulator: "
                                   "it buys inquiries at 40% of today's cost per inquiry, with diminishing returns, and the team only takes new work up to 95% utilisation.",
                                   9, MUTED, False)]], background=True, border=True)


# ---- Calendar
def calendar(p, nav):
    frame(p, "Calendar", "Court appearances, filings and completions across all matters (as of 17 Sep 2025)", nav)
    kpi(p, 14, 100, 300, 78, F.m(M, "Deadlines Next 30 Days"), "Deadlines · next 30 days", F.m(M, "Deadlines Caption"))
    kpi(p, 320, 100, 300, 78, F.m(M, "Deadline Count"), "Deadlines on the calendar")
    table(p, 14, 186, 760, 526, [F.c("Deadlines", "date", "Date"), F.c("Deadlines", "title", "Event"), F.c("Deadlines", "type", "Type"), F.c("Deadlines", "court", "Court"),
                                 F.c("Deadlines", "attorney", "Lawyer"), F.c("Deadlines", "matter_id", "Matter")], "Agenda",
          sort=(F.c("Deadlines", "date"), "Ascending"))
    chart(p, "columnChart", 780, 100, 486, 300, F.c("Deadlines", "date", "Date"), [F.m(M, "Deadline Count", "Events")], "Events by date", F.c("Deadlines", "type"))
    chart(p, "clusteredBarChart", 780, 406, 486, 306, F.c("Deadlines", "attorney"), [F.m(M, "Deadline Count", "Events")], "Workload by lawyer",
          sort=(F.m(M, "Deadline Count"), "Descending"), labels=True, legend=False)


# ---- Platform
def platform(p, nav):
    name = p.platform
    pl = PL.PLATFORMS[name]
    frame(p, f"Platform · {name}", f"{pl['tagline']}. 3-year cash flows, NPV, scorecard and risk against staying on LEAP + InfoTrack", nav)
    for t in ("Platform Risks", "Platform Gantt", "Platform NPV Grid"):
        p.filters.append({"name": _id(p.name, t), "field": F.c(t, "Platform").expr(), "type": "Categorical",
                          "filter": in_filter(F.c(t, "Platform"), [name])})
        ALL_FIELDS.append(F.c(t, "Platform"))
    me = F.c("Platforms", "Platform")
    tiles = [(F.m(M, "Platform Verdict"), "Verdict"), (F.s("Platforms", "NPV"), "NPV, 3 years"), (F.s("Platforms", "Payback"), "Payback (months)"),
             (F.s("Platforms", "RunRate"), "Run cost a year"), (F.s("Platforms", "OneOff"), "One-off cost"), (F.s("Platforms", "Score"), "Weighted score")]
    for i, (fld, lab) in enumerate(tiles):
        x = 14 + i * 210
        p.add("shape", x, 68, 202, 70, objects={"shape": [{"properties": {"tileShape": lit("rectangleRounded")}}],
                                                "fill": [{"properties": {"fillColor": colour("#FFFFFF"), "transparency": lit(0.0)}}],
                                                "outline": [{"properties": {"show": lit(True), "lineColor": colour(BORDER), "weight": lit(1.0)}}]},
              background=False, border=False)
        f2 = F(fld.kind, fld.table, fld.name, lab)
        p.add("card", x + 4, 70, 194, 66, roles={"Values": [f2]},
              objects={"labels": [{"properties": {"fontSize": lit(16.0 if i else 13.0), "color": colour(INK)}}],
                       "categoryLabels": [{"properties": {"show": lit(True), "fontSize": lit(9.0), "color": colour(MUTED)}}]},
              background=False, border=False, filters=[cat_filter(me, name, _id(p.name, "f", i))], key=f"kpi{i}")
    table(p, 14, 146, 760, 196, [F.c("Platforms", "Platform", "Platform"), F.c("Platforms", "Verdict", "Verdict"), F.c("Platforms", "NPV", "NPV (3 years)"),
                                 F.c("Platforms", "Payback", "Payback (months)"), F.c("Platforms", "RunRate", "Run cost a year"), F.c("Platforms", "OneOff", "One-off"),
                                 F.c("Platforms", "Score", "Score"), F.c("Platforms", "Rank", "Rank")], "Ranking (50% score, 50% NPV)",
          sort=(F.c("Platforms", "Rank"), "Ascending"))
    chart(p, "clusteredBarChart", 780, 146, 486, 196, F.c("Platforms", "Short"), [F.s("Platforms", "NPV", "NPV")], "NPV against staying on LEAP + InfoTrack",
          sort=(F.s("Platforms", "NPV"), "Descending"), labels=True, legend=False)
    chart(p, "lineChart", 14, 348, 620, 210, F.c("Platform Cashflow", "Month"), [F.m(M, "Platform Cumulative", "Cumulative net benefit")], "Cumulative cash flow",
          F.c("Platform Cashflow", "Platform"), "Month 1 = contract signed. Crosses zero at payback")
    table(p, 640, 348, 626, 210, [F.m(M, "Platform Criterion Score", "Score")], "Scorecard (weights: cost 30, integration 25, reliability 20, support 15, speed 10)",
          matrix_rows=[F.c("Platform Scores", "Criterion")], matrix_cols=[F.c("Platforms", "Short")])
    table(p, 14, 564, 620, 148, [F.c("Platform Risks", "risk", "Risk"), F.c("Platform Risks", "score", "Score"), F.c("Platform Risks", "mitigation", "Mitigation")],
          f"Risks: {pl['short']}", sort=(F.c("Platform Risks", "score"), "Descending"))
    table(p, 640, 564, 310, 148, [F.c("Platform Gantt", "Phase", "Phase"), F.c("Platform Gantt", "StartWeek", "From week"), F.c("Platform Gantt", "EndWeek", "To week")],
          "Implementation plan", sort=(F.c("Platform Gantt", "Order"), "Ascending"))
    table(p, 956, 564, 310, 148, [F.m(M, "Platform Grid NPV", "NPV")], "NPV sensitivity", matrix_rows=[F.c("Platform NPV Grid", "Volume")],
          matrix_cols=[F.c("Platform NPV Grid", "Realisation")])


# ---- Simulator
LEVER_LAYOUT = [  # three columns of slicers on the left of both Simulator pages
    ("Pricing & growth", ["sim_util", "sim_rate", "sim_real", "sim_recov", "sim_infl", "sim_dso", "sim_mkt_channel", "sim_mkt_extra",
                          "sim_new_area", "sim_new_area_type", "sim_platform"]),
    ("Hiring, cuts & pay", ["sim_hires", "sim_role", "sim_ramp", "sim_hire_area", "sim_cut_fe", "sim_cut_role", "sim_keep_work", "sim_cut_years",
                            "sim_pay_fe", "sim_pay_support"]),
    ("Support & branch", ["sim_cut_support", "sim_support_dept", "sim_add_support", "sim_branch", "sim_branch_fe", "sim_branch_support",
                          "sim_branch_rent", "sim_branch_fitout", "sim_branch_ramp"]),
]


def lever_slicers(p, levers):
    by = {lv.key: lv for lv in levers}
    col_w, x0, y0 = 128, 14, 162
    p.add("shape", 10, 158, 402, 556, objects={"shape": [{"properties": {"tileShape": lit("rectangleRounded")}}],
                                                "fill": [{"properties": {"fillColor": colour("#FFFFFF"), "transparency": lit(0.0)}}],
                                                "outline": [{"properties": {"show": lit(True), "lineColor": colour(BORDER), "weight": lit(1.0)}}]},
          background=False, border=False, key="leverpanel")
    for gi, (title, keys) in enumerate(LEVER_LAYOUT):
        x = x0 + 4 + gi * (col_w + 4)
        text(p, x, y0, col_w, 22, [[(title, 9, TEAL, True)]], key=f"grp{gi}")
        for i, k in enumerate(keys):
            lv = by[k]
            slicer(p, x, y0 + 24 + i * 48, col_w, 46, F.c(lv.table, lv.label), "Dropdown", lv.label, sync=f"lever-{k}", key=f"lv-{k}")


def sim_decide(p, nav, tabs, levers):
    frame(p, "Decision Simulator", "Test a decision before you make it: pricing, hiring and staffing, pay, marketing, a new matter type, a branch or a platform switch", nav, tabs)
    slicer(p, 14, 104, 1252, 40, F.c("Sim Preset", "Short"), "Basic", None, sync="preset", horizontal=True, key="preset", force=True, default="Today")
    lever_slicers(p, levers)
    k = [("Sim Operating Profit", "Operating profit (a year)", "Sim Profit Caption", None), ("Sim Margin", "Operating margin", "Sim Margin Caption", None),
         ("Sim Gap to Budget", "Gap to FY26 budget", "Sim Gap Caption", "Sim Gap Colour"), ("Sim One-off Cash", "Cash needed up front", None, None),
         ("Sim Low Point", "13-week cash low point", "Sim Low Caption", "Sim Low Colour")]
    x = 420
    for name, label, cap, colr in k:
        kpi(p, x, 160, 166, 80, F.m(SIM, name), label, F.m(SIM, cap) if cap else None, colour_measure(SIM, colr) if colr else None, size=14.0)
        x += 170
    p.add("waterfallChart", 420, 246, 500, 270, roles={"Category": [F.c("Sim Bridge Step", "Step")], "Y": [F.m(SIM, "Sim Bridge Value", "Profit")]},
          objects={"labels": [{"properties": {"show": lit(True), "fontSize": lit(8.0)}}],
                   "sentimentColors": [{"properties": {"increaseFill": colour(GREEN), "decreaseFill": colour(RED), "totalFill": colour(TEAL)}}]},
          title="Profit bridge: today → scenario", subtitle="Annual, run-rate. One-off costs are cash, not profit", sort=(F.c("Sim Bridge Step", "Order"), "Ascending"))
    chart(p, "clusteredBarChart", 926, 246, 340, 270, F.c("Sim Lever Test", "Test"), [F.m(SIM, "Sim Lever Effect", "Profit a year")], "What moves profit most",
          sort=(F.m(SIM, "Sim Lever Effect"), "Ascending"), labels=True, legend=False, subtitle="One unit of each lever, from today")
    table(p, 420, 522, 600, 190, [F.c("Sim Effect Line", "Line", "Effect"), F.m(SIM, "Sim Effect", "Value")], "Effects & cash",
          sort=(F.c("Sim Effect Line", "Order"), "Ascending"))
    card(p, 1026, 522, 240, 92, F.m(SIM, "Sim Scenario Summary"), "Levers in this scenario", 8.0)
    card(p, 1026, 620, 240, 92, F.m(SIM, "Sim Warning"), "Warnings", 8.0)


def sim_test(p, nav, tabs, levers):
    frame(p, "Decision Simulator · Test the plan", "What it would take to hit a target, how sure we are, and every preset side by side", nav, tabs)
    slicer(p, 14, 104, 1252, 40, F.c("Sim Preset", "Short"), "Basic", None, sync="preset", horizontal=True, key="preset", force=True, default="Today")
    lever_slicers(p, levers)
    slicer(p, 420, 160, 260, 40, F.c("Sim Goal Target", "Target"), "Dropdown", "Target", key="target")
    slicer(p, 686, 160, 200, 40, F.c("Sim Goal Uplift", "Extra profit a year"), "Dropdown", "Extra profit a year (for 'plus extra')", key="uplift")
    card(p, 892, 160, 374, 40, F.m(SIM, "Sim Goal Caption"), False, 8.0)
    table(p, 420, 206, 846, 160, [F.c("Sim Goal Row", "Lever", "Lever"), F.m(SIM, "Sim Goal Need", "What it would take"), F.m(SIM, "Sim Goal Difficulty", "Difficulty")],
          "What would it take?", "Each lever on its own, rounded to the slider step", sort=(F.c("Sim Goal Row", "Order"), "Ascending"))
    chart(p, "clusteredColumnChart", 420, 372, 420, 340, F.c("Sim Delivery", "Label"), [F.m(SIM, "Sim Profit at Delivery", "Operating profit")], "How sure are we?",
          sort=(F.c("Sim Delivery", "Delivery"), "Descending"), labels=True, legend=False,
          subtitle="Profit if only part of the improvement is delivered. Pay, rent and setbacks are never softened")
    table(p, 846, 372, 420, 340, [F.c("Sim Compare", "Short", "Scenario"), F.m(SIM, "Sim Compare Profit", "Op. profit"), F.m(SIM, "Sim Compare vs Today", "vs today"),
                                  F.m(SIM, "Sim Margin", "Margin"), F.m(SIM, "Sim One-off Cash", "One-off cash")], "Every preset side by side",
          sort=(F.c("Sim Compare", "Order"), "Ascending"))


# ---- Method & check
def check(p, nav):
    frame(p, "Method & check", "How the Simulator works, its assumptions, and a live check of every DAX result against the Python engine", nav)
    card(p, 14, 100, 620, 44, F.m(SIM, "Check Passed"), False, 13.0)
    table(p, 14, 150, 620, 562, [F.c("Sim Expected", "Preset", "Preset"), F.c("Sim Expected", "Metric", "Metric"), F.m(SIM, "Check Python", "Python"),
                                 F.m(SIM, "Check DAX", "DAX"), F.m(SIM, "Check Difference", "Difference"), F.m(SIM, "Check Result", "Result")],
          "DAX vs Python, every preset", "Python = core/simulate.py (tested in CI); DAX = this report's measures")
    table(p, 640, 100, 626, 330, [F.c("Sim Assumption", "Assumption", "Assumption"), F.c("Sim Assumption", "Value", "Value")], "Assumptions",
          sort=(F.c("Sim Assumption", "Order"), "Ascending"))
    text(p, 640, 436, 626, 276, [
        [("Method", 11, INK, True)],
        [("Base: the last 12 months of actuals, scaled to a full year. Utilisation scales the team's hours; rates and realisation scale the fee on each hour. "
          "Hires bill at the firm's utilisation × year-one productivity (or the chosen area's rate and workload). People leaving: pay saved, fees lost except "
          "the share the team keeps; NES redundancy (s 119) and notice (s 117) are paid once. A branch ramps up in a straight line; fit-out is cash, not profit. "
          "Marketing buys inquiries at 40% of the channel's current cost with diminishing returns, billing 35% of a typical matter in year one, up to 95% "
          "utilisation. A new matter type ramps to its mature volume; the launch campaign is one-off cash. Cash: one-off costs are paid in week one of the "
          "13-week forecast. Sample data. A decision aid, not legal or financial advice.", 8, MUTED, False)]], background=True, border=True)
