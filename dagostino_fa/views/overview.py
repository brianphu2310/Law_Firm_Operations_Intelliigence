"""Overview — one-screen executive view. Every number comes from the model for the selected reporting period."""
import math
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core import metrics as X
from core import ui
from core.charts import branch_globe_fig, revenue_stream_fig, utilisation_treemap, PAYMENT_METHODS
from core.period import delta, stock_at, has_data
from core.ref import AS_OF, AREAS
from core.theme import (inject_css, TEAL, TEAL_TINT, INK, MUTED, FAINT, CARD, SHADOW, AREA_COLORS)

SCREEN_H = 890            # visible browser height in px – all cards/globe are derived from this one number


def _cmp_label(cmp):
    if cmp is None:
        return None
    return "vs LY" if "last year" in cmp.label else "vs prior"


def render(M, cur, cmp):
    _avail = SCREEN_H - 179
    ROW_H = max(168, min(240, round(_avail * 0.31)))
    HERO_H = max(236, min(290, _avail - 2 * ROW_H))
    ROW_H = max(168, min(240, (_avail - HERO_H) // 2))
    GLOBE_TOP = 24
    GLOBE_H = HERO_H - GLOBE_TOP - 32
    GLOBE_H -= GLOBE_H % 2
    RIGHT_GAP = 14
    CX = GLOBE_H // 2 + RIGHT_GAP
    CY = GLOBE_TOP + GLOBE_H // 2
    NOTCH_R = GLOBE_H / 2 - 0.5
    SC_H, BL_H, TL_H = HERO_H - 23, ROW_H - 44, ROW_H - 44

    inject_css(f"""<style>
    div[data-testid="stElementContainer"]:has(.fit-css), .element-container:has(.fit-css) {{ display:none !important; }}
    .block-container {{ padding-bottom:0.3rem !important; }}
    /* Streamlit's markdown wrapper has margin-bottom:-1rem, so the KPI card must keep margin-bottom:16px to compensate */
    .kpi-card {{ margin-bottom:16px !important; }}
    .st-key-topbar {{ padding:6px 16px !important; }}
    .bar-row {{ margin-bottom:9px; }} .bar-head {{ margin-bottom:3px; }}
    div[class*="st-key-cardblock_"] {{ box-shadow:{SHADOW} !important; }}
    div[class*="st-key-cardblock_r2"], div[class*="st-key-cardblock_r3"] {{ flex:0 0 {ROW_H}px !important; height:{ROW_H}px !important; min-height:{ROW_H}px !important; max-height:{ROW_H}px !important; overflow:hidden !important; }}
    .rev-legend {{ flex-wrap:wrap; gap:2px 9px !important; }} .rev-legend .legend-item {{ font-size:10px; gap:4px; }}
    .deadline-item {{ display:flex; gap:12px; align-items:center; margin-bottom:12px; }}
    .deadline-title, .deadline-sub {{ white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
    div[class*="st-key-heroblock"], div[class*="st-key-herowrap"], div[class*="st-key-herocard"] {{ flex:0 0 {HERO_H}px !important; height:{HERO_H}px !important; min-height:{HERO_H}px !important; max-height:{HERO_H}px !important; }}
    div[class*="st-key-heroblock"] {{ position:relative; background:transparent !important; border:none !important; padding:0 !important; }}
    div[class*="st-key-herowrap"] {{ filter:drop-shadow(0 10px 13px rgba(15,23,42,0.17)) drop-shadow(0 3px 4px rgba(15,23,42,0.10)); }}
    div[class*="st-key-herocard"] {{ background:{CARD} !important; border-radius:18px !important; border:1px solid #dbe6ee !important;
        padding:0.7rem {CX + NOTCH_R + 10}px 0.6rem 0.85rem !important; overflow:hidden;
        -webkit-mask: radial-gradient(circle {NOTCH_R}px at calc(100% - {CX}px) {CY}px, transparent {NOTCH_R - 1}px, #000 {NOTCH_R}px);
                mask: radial-gradient(circle {NOTCH_R}px at calc(100% - {CX}px) {CY}px, transparent {NOTCH_R - 1}px, #000 {NOTCH_R}px); }}
    div[class*="st-key-heroglobe"] {{ position:absolute; top:{GLOBE_TOP}px; right:{RIGHT_GAP}px; width:{GLOBE_H}px; height:{GLOBE_H}px; z-index:5; text-align:center; }}
    div[class*="st-key-heroglobe"] .globe-cap {{ font-size:10.5px; color:{MUTED}; white-space:nowrap; text-align:center; }}
    div[class*="st-key-heroglobe"] > div:first-child {{ margin:0 !important; }}
    section[data-testid="stSidebar"] [data-testid="stPlotlyChart"] {{ overflow:visible !important; }}
    section[data-testid="stSidebar"] [data-testid="stPlotlyChart"] .js-plotly-plot {{ margin-left:-9px; }}
    </style>""")

    FX = """
.sc-wrap { display:flex; flex-direction:column; gap:6px; height:__SC_H__px; }
.sc-title { font-size:13.5px; font-weight:700; color:__INK__; line-height:1.2; flex:0 0 auto; }
.sc-row { flex:1 1 0; min-height:0; display:flex; flex-direction:column; justify-content:center; gap:6px; padding:0 2px; }
.sc-row + .sc-row { border-top:1px solid #f1f4f8; }
.sc-top { display:flex; align-items:baseline; justify-content:space-between; gap:8px; min-width:0; }
.sc-lbl { font-size:11px; color:__MUTED__; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; min-width:0; }
.sc-pct { font-size:15px; font-weight:700; flex-shrink:0; line-height:1; }
.sc-track { height:8px; border-radius:99px; background:#eef1f6; overflow:hidden; }
.sc-fill { height:100%; border-radius:99px; animation:scGrow .9s cubic-bezier(.2,.8,.2,1) both; animation-delay:var(--d); }
.sc-total { flex:0 0 auto; display:flex; align-items:center; justify-content:space-between; gap:10px; padding:7px 14px; border-radius:14px; color:#fff; background:linear-gradient(100deg, #0a8496, #2f7fd8); }
.sc-total .big { font-size:21px; font-weight:800; line-height:1; flex-shrink:0; }
.sc-total .txt { font-size:10.5px; line-height:1.25; text-align:right; min-width:0; }
@keyframes scGrow { from { width:0; } }
.bl-wrap { display:flex; align-items:center; gap:12px; height:__BL_H__px; }
.bl-svg { flex:0 0 auto; height:100%; aspect-ratio:1; max-width:52%; overflow:visible; }
.bl-ring { animation:blDraw 1.3s cubic-bezier(.3,.7,.2,1) both; animation-delay:var(--rd); }
.bl-legend { flex:1; min-width:0; display:flex; flex-direction:column; justify-content:center; gap:10px; }
.bl-item { display:flex; align-items:center; gap:8px; min-width:0; }
.bl-dot { width:9px; height:9px; border-radius:50%; flex-shrink:0; }
.bl-txt { flex:1; min-width:0; }
.bl-lab { font-size:11px; color:__MUTED__; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.bl-lab .s { display:none; }
.bl-pct { font-size:9.5px; color:__FAINT__; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.bl-val { font-size:14px; font-weight:800; color:__INK__; flex-shrink:0; }
div[class*="st-key-cardblock_r"] .card-title { overflow:hidden; text-overflow:ellipsis; }
@media (max-width:1330px) { .bl-lab .f { display:none; } .bl-lab .s { display:inline; } .bl-pct { display:none; } .bl-svg { max-width:48%; } }
@keyframes blDraw { from { stroke-dasharray:0 var(--c); } }
.tl { position:relative; display:flex; flex-direction:column; justify-content:space-between; height:__TL_H__px; }
.tl-line { position:absolute; left:22px; top:16px; bottom:16px; width:2px; border-radius:2px; background:#dbe7ec; }
.tl-item { position:relative; z-index:1; display:flex; align-items:center; gap:10px; min-width:0; padding:2px 8px 2px 0; border-radius:12px; animation:tlIn .45s ease-out both; animation-delay:var(--d); }
.tl-badge { width:44px; height:32px; border-radius:10px; flex-shrink:0; display:flex; align-items:center; justify-content:center; font-size:11.5px; font-weight:800; background:var(--t); color:var(--ac); box-shadow:0 0 0 3px #fff; }
.tl-body { min-width:0; flex:1; }
.tl-body .deadline-title, .tl-body .deadline-sub { white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.tl-chip { flex-shrink:0; font-size:9.5px; font-weight:700; padding:2px 7px; border-radius:99px; background:var(--t); color:var(--ac); }
@keyframes tlIn { from { opacity:0; transform:translateY(6px); } }
@media (prefers-reduced-motion: reduce) { .sc-fill, .bl-ring, .tl-item { animation:none !important; } }
"""
    FX = (FX.replace("__SC_H__", str(SC_H)).replace("__BL_H__", str(BL_H)).replace("__TL_H__", str(TL_H))
            .replace("__INK__", INK).replace("__MUTED__", MUTED).replace("__FAINT__", FAINT))
    FX = "\n".join(l for l in FX.splitlines() if l.strip())
    inject_css('<style>\n' + FX + '\n</style>')

    H = X.headline(M, cur, cmp)
    fc, fp, rc, rp = H["fc"], H["fp"], H["rc"], H["rp"]
    lab = _cmp_label(cmp)
    end = cur.end
    dl = lambda a, b: delta(a, b) if fp is not None else None
    ppd = lambda a, b: (a - b) if (fp is not None and b is not None and not np.isnan(b)) else None

    # ---------------- KPIs ----------------
    top_short = H["top"].split(",")[0]
    kpis = [
        dict(label="Active matters", value=f"{H['active']:.0f}", d=delta(H["active"], H["active_p"]), label_cmp=lab, spark=X.spark(M, "matters_active", end, 12, "stock") if False else None),
        dict(label="Billable hours", value=ui.fmt_num(fc["hours"]), d=dl(fc["hours"], fp["hours"] if fp is not None else None), label_cmp=lab, spark=X.spark(M, "hours", end)),
        dict(label="Collected revenue (ex GST)", value=ui.fmt_money(fc["collections_ex"]), d=dl(fc["collections_ex"], fp["collections_ex"] if fp is not None else None), label_cmp=lab, spark=X.spark(M, "collections_ex", end)),
        dict(label="Utilisation", value=ui.fmt_pct(rc["util"]), d=ppd(rc["util"], rp.get("util")), kind="pp", label_cmp=lab, spark=None),
        dict(label="Deadlines · next 30 days", value=f"{H['deadlines']}", d=delta(H["deadlines"], H["deadlines_next"]) if False else None, label_cmp=None, sub=f"{H['deadlines_next']} more in the following 30 days"),
        dict(label=f"Top biller · {top_short}", value=ui.fmt_money(H["top_fees"]), d=dl(H["top_fees"], H["top_fees_p"]), label_cmp=lab, sub=None),
    ]
    # sparklines: monthly series (12 m to period end)
    act_s = X.monthly(M, "matters_active", end, 12, "stock")
    kpis[0]["spark"] = act_s.values.tolist()
    kpis[3]["spark"] = (X.monthly(M, "hours", end, 12) / X.monthly(M, "capacity", end, 12)).values.tolist()
    kpis[5]["spark"] = X.att_monthly(M, end, 12, "fees")[H["top"]].values.tolist()
    ui.kpi_row(kpis, min_h=0)

    # ---------------- HERO: funnel + stage conversion in a notched card, globe inside the notch ----------------
    stages = ["Inquiries", "Consultations Booked", "Consultations Held", "Engagement Letters Sent", "New Matters Opened"]
    vals = [int(round(fc[c])) for c in ["inquiries", "booked", "held", "letters", "matters_opened"]]
    vals = [max(v, 1) for v in vals]
    for i in range(1, 5):                       # keep the funnel monotonically decreasing after rounding
        vals[i] = min(vals[i], vals[i - 1])
    with st.container(key="heroblock"):
        with st.container(key="herowrap"):
            with st.container(key="herocard"):
                fc1, fc2 = st.columns([1.35, 1])
                with fc1:
                    st.markdown('<div class="card-title">Matter Intake Funnel</div>', unsafe_allow_html=True)
                    st.caption(f"From first inquiry to a new matter · {cur.label}")
                    ff = go.Figure(go.Funnel(y=stages, x=vals, textinfo="value+percent initial", textfont=dict(size=11, color="#ffffff", family="Inter, sans-serif"),
                                             marker=dict(color=[TEAL, "#2f9aa8", "#5bb4bd", "#86c9d1", "#b1dee3"], line=dict(color="#ffffff", width=1.5)),
                                             connector=dict(line=dict(color="#e2e8f0", width=1)), hovertemplate="%{y}: %{x}<extra></extra>"))
                    ff.update_layout(margin=dict(l=8, r=8, t=2, b=2), height=HERO_H - 84, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(family="Inter, sans-serif", color=INK, size=11))
                    ui.show(ff, key="ov_funnel")
                with fc2:
                    SC = [("#0a8496", "#4fb6c4"), ("#2f7fd8", "#7ab0ec"), ("#6366f1", "#a3a6f6"), ("#9061d6", "#bda2ec")]
                    rows = ""
                    for i in range(1, 5):
                        pct = round(vals[i] / vals[i - 1] * 100)
                        c1, c2 = SC[i - 1]
                        rows += (f'<div class="sc-row" title="{vals[i-1]} → {vals[i]}"><div class="sc-top"><span class="sc-lbl">{stages[i-1]} → {stages[i]}</span>'
                                 f'<span class="sc-pct" style="color:{c1};">{pct}%</span></div><div class="sc-track"><div class="sc-fill" '
                                 f'style="width:{pct}%;background:linear-gradient(90deg,{c1},{c2});--d:{0.08 * i:.2f}s;"></div></div></div>')
                    ov = round(vals[-1] / vals[0] * 100)
                    st.markdown(f'<div class="sc-wrap"><div class="sc-title">Stage Conversion</div>{rows}<div class="sc-total"><span class="big">{ov}%</span>'
                                f'<span class="txt">{vals[-1]} of {vals[0]} inquiries<br>became new matters</span></div></div>', unsafe_allow_html=True)
        with st.container(key="heroglobe"):
            gfig, g_total, g_n = branch_globe_fig(M, end, height=GLOBE_H)
            ui.show(gfig, key="ov_globe", **{})
            st.markdown(f'<div class="globe-cap"><b style="color:{INK};">{g_total}</b> active matters · <b style="color:{INK};">{g_n}</b> countries · drag to rotate</div>', unsafe_allow_html=True)

    # ---------------- ROW 2 ----------------
    COLS = [1.3, 1.15, 1.0]
    CH2 = ROW_H - 62
    c1, c2, c3 = st.columns(COLS)
    with c1:
        with ui.card("r2_trend"):
            st.markdown('<div class="card-title">Billable Hours Trend</div>', unsafe_allow_html=True)
            show_areas = ["Litigation", "Corporate", "IP Portfolio"]
            lg = "".join(f'<span class="legend-item"><span class="legend-dot" style="background:{AREA_COLORS[a]}"></span>{a}</span>' for a in show_areas)
            st.markdown(f'<div class="legend-row">{lg}</div>', unsafe_allow_html=True)
            f = go.Figure()
            for a in show_areas:
                s = X.monthly(M, f"hours_{a}", end, 12)
                f.add_trace(go.Bar(x=[d.strftime("%b %y") for d in s.index], y=s.round(0), marker_color=AREA_COLORS[a], hovertemplate="%{x}: %{y:,.0f} hrs<extra>" + a + "</extra>"))
            f.update_layout(**ui.base_layout(CH2), barmode="group", bargap=0.3, bargroupgap=0.12)
            f.update_xaxes(showgrid=False, tickfont=dict(size=8.5)); f.update_yaxes(showgrid=True, gridcolor="#f1f5f9", tickfont=dict(size=8.5))
            ui.show(f, key="ov_trend")
    with c2:
        with ui.card("r2_rev"):
            st.markdown('<div class="card-title">Revenue by Practice Area</div>', unsafe_allow_html=True)
            lg = "".join(f'<span class="legend-item"><span class="legend-dot" style="background:{c}"></span>{m}</span>' for m, c in PAYMENT_METHODS)
            st.markdown(f'<div class="legend-row rev-legend"><span style="font-size:10px; font-weight:700; color:{MUTED};">Payment&nbsp;Method</span>{lg}</div>', unsafe_allow_html=True)
            fees = pd.Series({a: fc[f"fees_{a}"] for a in AREAS})
            fr = revenue_stream_fig(fees, height=CH2 - 4)
            cats = ["Corporate", "Litigation", "IP<br>Portfolio", "Employ-<br>ment", "Advisory"]
            fr.update_xaxes(tickmode="array", tickvals=AREAS, ticktext=cats, tickangle=0, tickfont=dict(size=8), range=[-0.4, len(cats) - 0.6])
            fr.update_layout(margin=dict(l=8, r=8, t=2, b=2))
            for an in fr.layout.annotations:
                if an.x == AREAS[0]:
                    an.update(xanchor="left", xshift=4)
            ui.show(fr, key="ov_rev")
    with c3:
        with ui.card("r2_donut"):
            st.markdown('<div class="card-title">Workload By Practice Area</div>', unsafe_allow_html=True)
            hrs = {a: fc[f"hours_{a}"] for a in AREAS}
            groups = {"Corporate": hrs["Corporate"], "Litigation": hrs["Litigation"], "IP Portfolio": hrs["IP Portfolio"], "Employment & Advisory": hrs["Employment"] + hrs["Advisory"]}
            tot = sum(groups.values())
            dcols = [TEAL, "#3ba7b3", "#7bc4cd", "#b7dee2"]
            f2 = go.Figure(go.Pie(labels=list(groups), values=list(groups.values()), hole=0.68, marker=dict(colors=dcols, line=dict(color="#ffffff", width=2)),
                                  textinfo="none", sort=False, hovertemplate="%{label}: %{percent}<extra></extra>"))
            dlay = ui.base_layout(ROW_H - 96); dlay["margin"] = dict(l=2, r=2, t=2, b=2); f2.update_layout(**dlay)
            f2.add_annotation(text=f"<b style='font-size:17px;'>{H['active']:.0f}</b><br><span style='font-size:9px; color:{FAINT};'>Active matters</span>", x=0.5, y=0.5, showarrow=False, align="center", font=dict(family="Inter, sans-serif", color=INK))
            ui.show(f2, key="ov_donut")
            leg = "".join(f'<div class="donut-legend-item" style="margin-bottom:0;"><span class="legend-dot" style="background:{c}"></span>{l} ({v / tot * 100:.0f}%)</div>' for (l, v), c in zip(groups.items(), dcols))
            st.markdown(f'<div style="display:grid; grid-template-columns:1fr 1fr; gap:3px 10px;">{leg}</div>', unsafe_allow_html=True)

    # ---------------- ROW 3 ----------------
    t1, t2, t3 = st.columns(COLS)
    with t1:
        with ui.card("r3_util"):
            st.markdown('<div class="card-title">Attorney Utilisation — Hours by Practice Area</div>', unsafe_allow_html=True)
            ui.show(utilisation_treemap(H["at"], ROW_H - 44), key="ov_tree")
    with t2:
        with ui.card("r3_bill"):
            st.markdown(f'<div class="card-title">Trust, WIP &amp; Receivables · {end:%d %b %y}</div>', unsafe_allow_html=True)
            ui.spacer(4)
            stk = M["stock"]
            trust = stock_at(stk, "trust", end); wip = stock_at(stk, "wip", end); ar = X.ar_total(M, end)
            BL = [("Trust funds held", trust, "#0a8496", "#4fb6c4", "Trust"), ("Work in progress (unbilled)", wip, "#6366f1", "#a3a6f6", "WIP"),
                  ("Receivables (billed, unpaid)", ar, "#f59e0b", "#fbbf24", "Receivables")]
            total = trust + wip + ar
            defs, rings, legend = "", "", ""
            for n, (lab_, v, c1_, c2_, short) in enumerate(BL):
                pct = v / total * 100
                r = 64 - n * 14; circ = 2 * math.pi * r; track = circ * 0.75; fill = track * pct / 100
                defs += f'<linearGradient id="blg{n}" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{c1_}"/><stop offset="1" stop-color="{c2_}"/></linearGradient>'
                rings += (f'<circle cx="80" cy="80" r="{r}" fill="none" stroke="#eef1f6" stroke-width="9" stroke-linecap="round" stroke-dasharray="{track:.2f} {circ:.2f}" transform="rotate(135 80 80)"/>'
                          f'<circle class="bl-ring" cx="80" cy="80" r="{r}" fill="none" stroke="url(#blg{n})" stroke-width="9" stroke-linecap="round" stroke-dasharray="{fill:.2f} {circ:.2f}" transform="rotate(135 80 80)" style="--c:{circ:.2f};--rd:{n * 0.2:.2f}s;"/>')
                legend += (f'<div class="bl-item" title="{lab_}"><span class="bl-dot" style="background:{c1_};"></span><div class="bl-txt"><div class="bl-lab"><span class="f">{lab_}</span><span class="s">{short}</span></div>'
                           f'<div class="bl-pct">{pct:.0f}% of funds employed</div></div><span class="bl-val">{ui.fmt_money(v)}</span></div>')
            svg = (f'<svg class="bl-svg" viewBox="0 0 160 160"><defs>{defs}</defs>{rings}<text x="80" y="79" text-anchor="middle" font-size="16" font-weight="800" fill="{INK}" font-family="Inter, sans-serif">{ui.fmt_money(total)}</text>'
                   f'<text x="80" y="92" text-anchor="middle" font-size="7.5" font-weight="600" fill="{FAINT}" letter-spacing="1.2" font-family="Inter, sans-serif">TOTAL</text></svg>')
            st.markdown(f'<div class="bl-wrap">{svg}<div class="bl-legend">{legend}</div></div>', unsafe_allow_html=True)
    with t3:
        with ui.card("r3_dead"):
            st.markdown('<div class="card-title">Upcoming Court Appearances &amp; Filings</div>', unsafe_allow_html=True)
            ui.spacer(4)
            dlt = M["deadlines"]; nxt = dlt[dlt["date"] >= AS_OF].head(4 if ROW_H >= 208 else 3)
            items = ""
            for n, (_, d) in enumerate(nxt.iterrows()):
                days = (d["date"] - AS_OF).days
                ac, tint = ("#b45309", "#fffbeb") if days <= 30 else (TEAL, TEAL_TINT)
                items += (f'<div class="tl-item" style="--ac:{TEAL};--t:{TEAL_TINT};--d:{0.06 * n:.2f}s;" title="{d["title"]}"><div class="tl-badge">{d["date"]:%b %d}</div>'
                          f'<div class="tl-body"><div class="deadline-title">{d["title"]}</div><div class="deadline-sub">{d["court"]} · Assigned: {d["attorney"]}</div></div>'
                          f'<span class="tl-chip" style="--ac:{ac};--t:{tint};">in {days}d</span></div>')
            st.markdown(f'<div class="tl"><div class="tl-line"></div>{items}</div>', unsafe_allow_html=True)
