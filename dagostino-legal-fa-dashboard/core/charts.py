"""Data-driven versions of the signature charts (globe, streamgraph, treemap, waterfalls…)."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go

from .ref import AREAS, COUNTRY_ISO3, AS_OF
from .theme import TEAL, INK, MUTED, FAINT, AREA_COLORS
from .metrics import att_table

PAYMENT_METHODS = [("Cheque", "#d9d3ec"), ("BPAY", "#8fcbe0"), ("EFT / Bank Transfer", "#3ba7b3"), ("Credit Card", "#f3bfcd"), ("Trust Transfer", "#152b4e")]
# share of each practice area's collections by payment method (bottom layer first)
PAYMENT_MIX = {"Corporate": [.05, .10, .30, .22, .33], "Litigation": [.10, .15, .35, .30, .10], "IP Portfolio": [.08, .12, .28, .25, .27],
               "Employment": [.10, .18, .30, .24, .18], "Advisory": [.07, .15, .30, .23, .25]}


def branch_globe_fig(M, date, height=175):
    """Orthographic globe: countries with active matters at `date`, shaded by count."""
    mt = M["matters"]
    act = mt[(mt["opened"] <= date) & (mt["closed"].isna() | (mt["closed"] > date))]
    cc = act.groupby("country").size().sort_values(ascending=False)
    iso = [COUNTRY_ISO3[c] for c in cc.index]
    z = np.sqrt(cc.values.astype(float))
    fig = go.Figure(go.Choropleth(
        locations=iso, locationmode="ISO-3", z=z, zmin=0, zmax=z.max(),
        colorscale=[[0.0, "#d7ecef"], [0.15, "#a9dce1"], [0.35, "#5fc0c8"], [0.55, "#2b9aa3"], [0.75, "#136e75"], [1.0, "#063a3e"]],
        showscale=False, marker_line_color="#ffffff", marker_line_width=0.6,
        customdata=list(zip(cc.index, cc.values)), hovertemplate="%{customdata[0]} — %{customdata[1]} active matters<extra></extra>"))
    fig.update_geos(projection_type="orthographic", projection_rotation=dict(lon=110, lat=-16, roll=0),
                    showland=True, landcolor="#b9d2e0", showocean=True, oceancolor="#cddfec", showcountries=True, countrycolor="#8fabbe",
                    showcoastlines=True, coastlinecolor="#7f9db2", coastlinewidth=0.6, showlakes=True, lakecolor="#cddfec", showframe=False,
                    lonaxis=dict(showgrid=True, gridcolor="#c3d5e2", gridwidth=0.5), lataxis=dict(showgrid=True, gridcolor="#c3d5e2", gridwidth=0.5),
                    bgcolor="rgba(0,0,0,0)")
    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), height=height, paper_bgcolor="rgba(0,0,0,0)", showlegend=False,
                      font=dict(family="Inter, sans-serif", color=MUTED, size=10))
    return fig, int(cc.sum()), len(cc)


def revenue_stream_fig(fees_by_area, height=210, label_threshold=0):
    """Streamgraph of fees by practice area, layered by payment method. fees_by_area: Series indexed by AREAS ($)."""
    cats = list(AREAS)
    totals = [float(fees_by_area[c]) / 1000 for c in cats]
    baseline = [-t / 2.0 for t in totals]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=cats, y=baseline, mode="lines", line=dict(width=0, shape="spline"), hoverinfo="skip", showlegend=False))
    cum, top_start = list(baseline), list(baseline)
    for idx, (method, color) in enumerate(PAYMENT_METHODS):
        vals = [totals[i] * PAYMENT_MIX[c][idx] for i, c in enumerate(cats)]
        if idx == len(PAYMENT_METHODS) - 1:
            top_start = list(cum)
        cum = [cum[i] + vals[i] for i in range(len(cats))]
        fig.add_trace(go.Scatter(x=cats, y=cum, mode="lines", line=dict(width=1, color=color, shape="spline"), fill="tonexty", fillcolor=color,
                                 name=method, customdata=[round(v) for v in vals], hovertemplate="%{x} — " + method + ": $%{customdata}K<extra></extra>"))
    ann = [dict(x=c, y=(top_start[i] + cum[i]) / 2, text=f"${totals[i]:,.0f}K", showarrow=False, font=dict(size=10, color="#ffffff", family="Inter, sans-serif"))
           for i, c in enumerate(cats) if totals[i] >= max(label_threshold, 0.06 * max(totals))]
    fig.update_layout(margin=dict(l=8, r=8, t=4, b=4), height=height, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      showlegend=False, annotations=ann, font=dict(family="Inter, sans-serif", color=MUTED, size=9))
    fig.update_xaxes(showgrid=False, tickfont=dict(size=8))
    fig.update_yaxes(showgrid=False, zeroline=False, showticklabels=False)
    return fig


def _mix(t):
    stops = [(0, (234, 245, 247)), (0.5, (127, 208, 214)), (1, (10, 132, 150))]
    for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
        if t <= t1:
            u = (t - t0) / (t1 - t0)
            return "#%02x%02x%02x" % tuple(round(c0[i] + (c1[i] - c0[i]) * u) for i in range(3))
    return "#0a8496"


def utilisation_treemap(at, height):
    """Treemap of hours: attorney → practice area (from an att_table)."""
    L, P, V, C = [], [], [], []
    for short, r in at.iterrows():
        tot = sum(r[f"h_{k}"] for k in AREAS)
        if tot <= 0:
            continue
        L.append(short); P.append(""); V.append(tot); C.append(tot)
        for k in AREAS:
            if r[f"h_{k}"] >= 1:
                L.append(f"{short} · {k}"); P.append(short); V.append(r[f"h_{k}"]); C.append(r[f"h_{k}"])
    cmax = max(C)
    ft = go.Figure(go.Treemap(labels=L, parents=P, values=V, branchvalues="total", root_color="rgba(0,0,0,0)",
                              marker=dict(colors=[_mix(v / cmax) for v in C], line=dict(color="#ffffff", width=2)),
                              text=[l.split(" · ")[-1] for l in L], texttemplate="<b>%{text}</b><br>%{value:,.0f} hrs",
                              textfont=dict(size=10, color=INK, family="Inter, sans-serif"), hovertemplate="%{label}: %{value:,.0f} hrs<extra></extra>",
                              pathbar=dict(visible=False), tiling=dict(packing="squarify")))
    ft.update_layout(margin=dict(l=2, r=2, t=2, b=2), height=height, paper_bgcolor="rgba(0,0,0,0)", font=dict(family="Inter, sans-serif", color=MUTED, size=10))
    return ft
