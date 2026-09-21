"""Matters — ledger, pipeline flow and WIP/age analysis."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core import metrics as X
from core import ui
from core.period import delta, stock_at, has_data
from core.ref import AS_OF, AREAS, BRANCH_NAMES, ATTORNEYS
from core.theme import AREA_COLORS, TEAL, INDIGO, AMBER, INK, MUTED


def _active_at(mt, d):
    return mt[(mt["opened"] <= d) & (mt["closed"].isna() | (mt["closed"] > d))]


def render(M, cur, cmp):
    ui.page_header("Matters", "Every matter on the ledger: status, value, billing and work in progress", ui.period_tag(cur, cmp))
    mt = M["matters"]
    end = cur.end
    act = _active_at(mt, end)
    opened_c = mt[(mt["opened"] >= cur.start) & (mt["opened"] <= end)]
    closed_c = mt[(mt["closed"] >= cur.start) & (mt["closed"] <= end)]
    lab = ui.cmp_label(cmp)
    has_c = cmp is not None and has_data(cmp)
    if has_c:
        act_p = _active_at(mt, cmp.end)
        op_p = mt[(mt["opened"] >= cmp.start) & (mt["opened"] <= cmp.end)]
        cl_p = mt[(mt["closed"] >= cmp.start) & (mt["closed"] <= cmp.end)]
    age = (pd.Timestamp(end) - act["opened"]).dt.days
    ui.kpi_row([
        dict(label="Active matters", value=f"{len(act)}", d=delta(len(act), len(act_p)) if has_c else None, label_cmp=lab, accent=TEAL, spark=X.monthly(M, "matters_active", end, 12, "stock").values.tolist()),
        dict(label="Opened in period", value=f"{len(opened_c)}", d=delta(len(opened_c), len(op_p)) if has_c else None, label_cmp=lab, accent=TEAL),
        dict(label="Closed in period", value=f"{len(closed_c)}", d=delta(len(closed_c), len(cl_p)) if has_c else None, label_cmp=lab, accent=TEAL),
        dict(label="Average age of active", value=f"{age.mean():.0f} days", label_cmp=None, accent=TEAL, sub=f"median {age.median():.0f} days"),
        dict(label="Estimated value, active", value=ui.fmt_money(act["est_value"].sum()), label_cmp=None, accent=TEAL, sub=f"avg {ui.fmt_money(act['est_value'].mean())} per matter"),
        dict(label="WIP on active matters", value=ui.fmt_money(mt.loc[mt["status"].isin(["Open", "On Hold"]), "wip"].sum()), label_cmp=None, accent=TEAL, sub=f"as of {AS_OF:%d %b %y}"),
    ], spacer_after=6)

    tabs = st.tabs(["Ledger", "Pipeline & flow", "WIP & ageing", "Locations"])

    # ------------------------------------------------------------- Ledger
    with tabs[0]:
        with ui.card("m1"):
            f1, f2, f3, f4, f5 = st.columns([1.1, 1.3, 1.3, 1.1, 1.6])
            status = f1.selectbox("Status", ["Active", "All", "Open", "On Hold", "Closed"], key="m_status")
            areas = f2.multiselect("Practice area", AREAS, key="m_area")
            atts = f3.multiselect("Attorney", [a["short"] for a in ATTORNEYS], key="m_att")
            branch = f4.selectbox("Branch", ["All"] + BRANCH_NAMES, key="m_branch")
            q = f5.text_input("Search matter or client", key="m_q")
            d = mt[mt["opened"] <= AS_OF].copy()
            if status == "Active":
                d = d[d["status"].isin(["Open", "On Hold"])]
            elif status != "All":
                d = d[d["status"] == status]
            if areas: d = d[d["area"].isin(areas)]
            if atts: d = d[d["attorney"].isin(atts)]
            if branch != "All": d = d[d["branch"] == branch]
            if q: d = d[d["name"].str.contains(q, case=False) | d["client"].str.contains(q, case=False)]
            d = d.sort_values("opened", ascending=False)
            c1, c2 = st.columns([6, 1])
            c1.markdown(f'<div class="tbl-note">{len(d)} matters · estimated value {ui.fmt_money(d["est_value"].sum())} · billed {ui.fmt_money(d["billed"].sum())} · WIP {ui.fmt_money(d["wip"].sum())}</div>', unsafe_allow_html=True)
            with c2: ui.csv_button(d.drop(columns=["named"]), "matters", "matters")
            show = d[["id", "name", "client", "area", "attorney", "branch", "status", "opened", "est_value", "billed", "wip", "progress", "days_open"]].copy()
            show["progress"] = show["progress"] * 100
            show[["est_value", "billed", "wip"]] = show[["est_value", "billed", "wip"]].round(0)
            st.dataframe(show, hide_index=True, width="stretch", height=430, column_config={
                "id": st.column_config.TextColumn("ID", width=100), "name": st.column_config.TextColumn("Matter", width=300), "client": st.column_config.TextColumn("Client", width=170), "area": st.column_config.TextColumn("Practice area", width=105),
                "attorney": st.column_config.TextColumn("Attorney", width=95), "branch": st.column_config.TextColumn("Branch", width=80), "status": st.column_config.TextColumn("Status", width=70), "opened": st.column_config.DateColumn("Opened", format="DD MMM YY"),
                "est_value": ui.money_col("Est. value"), "billed": ui.money_col("Billed"), "wip": ui.money_col("WIP"),
                "progress": st.column_config.ProgressColumn("Progress", format="%.0f%%", min_value=0, max_value=100), "days_open": st.column_config.NumberColumn("Days open", format="%d")})

    # ------------------------------------------------------- Pipeline & flow
    with tabs[1]:
        c1, c2 = st.columns([1.5, 1])
        with c1:
            with ui.card("m2"):
                ui.card_title("Matters opened vs closed", "per month, last 18 months")
                o = X.monthly(M, "matters_opened", end, 18); c = X.monthly(M, "matters_closed", end, 18); a = X.monthly(M, "matters_active", end, 18, "stock")
                fig = go.Figure()
                fig.add_trace(go.Bar(x=o.index, y=o.round(0), name="Opened", marker_color=TEAL))
                fig.add_trace(go.Bar(x=c.index, y=-c.round(0), name="Closed", marker_color="#94a3b8"))
                fig.add_trace(go.Scatter(x=a.index, y=a, name="Active (right)", yaxis="y2", line=dict(color=INDIGO, width=2.5)))
                fig.update_layout(**ui.base_layout(270, legend=True), barmode="relative", yaxis2=dict(overlaying="y", side="right", showgrid=False, tickfont=dict(size=9), tickformat=",.0f", dtick=10))
                fig.update_xaxes(tickformat="%b %y")
                ui.show(ui.style_axes(fig), key="m_flow")
                ui.note("The current month is scaled to a full-month equivalent so it is comparable with earlier months.")
        with c2:
            with ui.card("m3"):
                ui.card_title("Active matters by practice area", f"at {end:%d %b %y}")
                g = act.groupby("area").size().reindex(AREAS).fillna(0)
                ui.donut(list(g.index), list(g.values), [AREA_COLORS[a] for a in g.index], h=190, center=f"<b style='font-size:20px'>{int(g.sum())}</b><br><span style='font-size:10px'>active</span>", key="m_donut")
                leg = "".join(f'<div class="donut-legend-item" style="margin-bottom:0;"><span class="legend-dot" style="background:{AREA_COLORS[a]}"></span>{a} ({int(g[a])})</div>' for a in g.index)
                st.markdown(f'<div style="display:grid; grid-template-columns:1fr 1fr; gap:3px 10px;">{leg}</div>', unsafe_allow_html=True)
        c3, c4 = st.columns(2)
        with c3:
            with ui.card("m4"):
                ui.card_title("Intake funnel", cur.label)
                f = X.fin_sum(M, cur)
                stages = ["Inquiries", "Booked", "Held", "Letters sent", "Matters opened"]
                vals = [f["inquiries"], f["booked"], f["held"], f["letters"], f["matters_opened"]]
                fig = go.Figure(go.Funnel(y=stages, x=[round(v) for v in vals], textinfo="value+percent previous", marker=dict(color=[TEAL, "#2f9aa8", "#5bb4bd", "#86c9d1", "#b1dee3"])))
                fig.update_layout(**ui.base_layout(240))
                ui.show(fig, key="m_funnel")
        with c4:
            with ui.card("m5"):
                ui.card_title("Active matters by attorney")
                g = act.groupby(["attorney", "area"]).size().unstack(fill_value=0).reindex(columns=AREAS, fill_value=0)
                g = g.loc[g.sum(1).sort_values().index]
                fig = go.Figure([go.Bar(y=g.index, x=g[a], orientation="h", name=a, marker_color=AREA_COLORS[a]) for a in AREAS])
                fig.update_layout(**ui.base_layout(240, legend=True), barmode="stack")
                ui.show(ui.style_axes(fig), key="m_att_chart")

    # ---------------------------------------------------------- WIP & ageing
    with tabs[2]:
        c1, c2 = st.columns(2)
        live = mt[mt["status"].isin(["Open", "On Hold"])].copy()
        with c1:
            with ui.card("m6"):
                ui.card_title("Active matters by age", f"as of {AS_OF:%d %b %y}")
                bins = [-1, 30, 90, 180, 365, 10**6]; labs = ["0–30 days", "31–90 days", "91–180 days", "181–365 days", "Over 1 year"]
                live["bucket"] = pd.cut((AS_OF - live["opened"]).dt.days, bins=bins, labels=labs)
                g = live.groupby("bucket", observed=False).agg(n=("id", "count"), wip=("wip", "sum")).reindex(labs)
                fig = go.Figure()
                fig.add_trace(go.Bar(x=labs, y=g["n"], name="Matters", marker_color=TEAL))
                fig.add_trace(go.Scatter(x=labs, y=g["wip"], name="WIP $ (right)", yaxis="y2", line=dict(color=AMBER, width=2.5), mode="lines+markers"))
                fig.update_layout(**ui.base_layout(260, legend=True), yaxis2=dict(overlaying="y", side="right", showgrid=False, tickformat="$,.0f", tickfont=dict(size=9)))
                ui.show(ui.style_axes(fig), key="m_age")
        with c2:
            with ui.card("m7"):
                ui.card_title("Largest WIP balances", "top 10 active matters")
                t = live.sort_values("wip", ascending=False).head(10).iloc[::-1]
                fig = go.Figure(go.Bar(y=[n[:38] for n in t["name"]], x=t["wip"], orientation="h", marker_color=[AREA_COLORS[a] for a in t["area"]], hovertemplate="%{y}: $%{x:,.0f}<extra></extra>"))
                fig.update_layout(**ui.base_layout(260, margin=dict(l=8, r=8, t=6, b=4)))
                ui.show(ui.style_axes(fig, None), key="m_wip")
        with ui.card("m8"):
            ui.card_title("WIP and billing by practice area")
            g = live.groupby("area").agg(matters=("id", "count"), est_value=("est_value", "sum"), billed=("billed", "sum"), wip=("wip", "sum")).reindex(AREAS).fillna(0)
            g["billed_pct"] = g["billed"] / g["est_value"]
            g["avg_wip"] = g["wip"] / g["matters"].replace(0, np.nan)
            out = g.reset_index().rename(columns={"area": "Practice area", "matters": "Matters", "est_value": "Est. value", "billed": "Billed", "wip": "WIP", "billed_pct": "Billed % of est.", "avg_wip": "Avg WIP / matter"})
            st.dataframe(out, hide_index=True, width="stretch", column_config={"Est. value": ui.money_col("Est. value"), "Billed": ui.money_col("Billed"), "WIP": ui.money_col("WIP"),
                                                                               "Avg WIP / matter": ui.money_col("Avg WIP / matter"), "Billed % of est.": st.column_config.NumberColumn("Billed % of est.", format="percent")})

    # -------------------------------------------------------------- Locations
    with tabs[3]:
        c1, c2 = st.columns([1, 1.2])
        with c1:
            with ui.card("m9"):
                ui.card_title("Active matters by country")
                g = act.groupby("country").size().sort_values()
                fig = go.Figure(go.Bar(y=g.index, x=g.values, orientation="h", marker_color=TEAL, text=g.values, textposition="outside"))
                fig.update_layout(**ui.base_layout(300))
                ui.show(ui.style_axes(fig, grid=False), key="m_country")
        with c2:
            with ui.card("m10"):
                ui.card_title("Branch view", f"at {end:%d %b %y}")
                bt = X.branch_table(M, cur)
                out = bt.reset_index()[["branch", "council", "fee_earners", "support", "active_matters", "revenue", "op_profit", "margin"]]
                st.dataframe(out.rename(columns={"branch": "Branch", "council": "Council", "fee_earners": "Fee earners", "support": "Support", "active_matters": "Active matters", "revenue": "Revenue", "op_profit": "Op. profit", "margin": "Margin"}),
                             hide_index=True, width="stretch", column_config={"Revenue": ui.money_col("Revenue"), "Op. profit": ui.money_col("Op. profit"), "Margin": st.column_config.NumberColumn("Margin", format="percent")})
                ui.note("Branch results allocate shared overheads by fee share and headcount share.")
