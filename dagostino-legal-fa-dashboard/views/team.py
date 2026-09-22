"""Team — fee-earner performance, capacity, payroll economics and branch results."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core import metrics as X
from core import ui
from core.period import delta, has_data
from core import simulate as SIM
from core.ref import AS_OF, AREAS, ATTORNEYS, BRANCHES
from core.theme import AREA_COLORS, TEAL, INDIGO, AMBER, RED, GREEN, INK, MUTED, BLUE

TARGET_UTIL = 0.85


def render(M, cur, cmp):
    ui.page_header("Team", "Fee-earner performance, capacity, pay and branch results", ui.period_tag(cur, cmp))
    at = X.att_table(M, cur)
    ap = X.att_table(M, cmp) if cmp is not None and has_data(cmp) else None
    lab = ui.cmp_label(cmp)
    tot = at[["hours", "capacity", "value", "fees", "cost", "contribution"]].sum()
    util, real, eff = tot["hours"] / tot["capacity"], tot["fees"] / tot["value"], tot["fees"] / tot["hours"]
    if ap is not None:
        tp = ap[["hours", "capacity", "value", "fees", "cost", "contribution"]].sum()
        up_, rp_, ep_ = tp["hours"] / tp["capacity"], tp["fees"] / tp["value"], tp["fees"] / tp["hours"]
    ui.kpi_row([
        dict(label="Fee earners", value=f"{int((at['capacity'] > 0).sum())}", label_cmp=None, accent=TEAL, sub="partners and associates"),
        dict(label="Utilisation", value=ui.fmt_pct(util), d=(util - up_) if ap is not None else None, kind="pp", label_cmp=lab, accent=TEAL, sub=f"target {TARGET_UTIL:.0%}"),
        dict(label="Realisation", value=ui.fmt_pct(real), d=(real - rp_) if ap is not None else None, kind="pp", label_cmp=lab, accent=TEAL),
        dict(label="Effective rate", value=f"${eff:,.0f}/hr", d=delta(eff, ep_) if ap is not None else None, label_cmp=lab, accent=TEAL),
        dict(label="Fees billed", value=ui.fmt_money(tot["fees"]), d=delta(tot["fees"], tp["fees"]) if ap is not None else None, label_cmp=lab, accent=TEAL),
        dict(label="Contribution after pay", value=ui.fmt_money(tot["contribution"]), d=delta(tot["contribution"], tp["contribution"]) if ap is not None else None, label_cmp=lab, accent=TEAL, sub="fees − fee-earner payroll"),
    ], spacer_after=6)
    _, ltm = SIM.base_actuals(M)
    one_pp = dict(SIM.lever_ranking(ltm))["+1 pp utilisation"]
    ui.sim_cta(f"Each extra point of utilisation is worth about <b>{ui.fmt_money(one_pp)} a year</b> in operating profit. Test a plan for the team.", preset="Lift utilisation +3 pp", key="team")
    ui.spacer(4)

    tabs = st.tabs(["Performance", "Capacity & hours", "Pay & economics", "Branches"])

    # ------------------------------------------------------------ performance
    with tabs[0]:
        with ui.card("t1"):
            ui.card_title("Fee-earner scorecard", cur.label)
            out = at.reset_index().rename(columns={"index": "short"})
            out["fees_ap"] = ap["fees"].values if ap is not None else np.nan
            out["chg"] = np.where(out["fees_ap"] > 0, (out["fees"] - out["fees_ap"]) / out["fees_ap"], np.nan)
            show = out[["attorney", "role", "branch", "hours", "util", "realisation", "eff_rate", "fees", "chg", "contribution"]].copy()
            show[["hours", "eff_rate", "fees", "contribution"]] = show[["hours", "eff_rate", "fees", "contribution"]].round(0)
            st.dataframe(show, hide_index=True, width="stretch", height=340, column_config={
                "attorney": st.column_config.TextColumn("Attorney", width=130), "role": st.column_config.TextColumn("Role", width=170), "branch": st.column_config.TextColumn("Branch", width=90),
                "hours": st.column_config.NumberColumn("Hours", format="%,d", width=80), "util": st.column_config.ProgressColumn("Utilisation", format="percent", min_value=0, max_value=1.1, width=130),
                "realisation": st.column_config.NumberColumn("Realisation", format="percent", width=100), "eff_rate": ui.money_col("Eff. rate /hr"), "fees": ui.money_col("Fees"),
                "chg": st.column_config.NumberColumn("Δ fees", format="percent", width=80), "contribution": ui.money_col("Contribution")})
        c2, c3 = st.columns(2)
        with c2:
            with ui.card("t2"):
                ui.card_title("Fees vs cost by fee earner")
                a = at.sort_values("fees")
                fig = go.Figure()
                fig.add_trace(go.Bar(y=a.index, x=a["fees"], orientation="h", name="Fees billed", marker_color=TEAL))
                fig.add_trace(go.Bar(y=a.index, x=a["cost"], orientation="h", name="Payroll cost", marker_color="#94a3b8"))
                fig.update_layout(**ui.base_layout(300, legend=True), barmode="group")
                ui.show(ui.style_axes(fig, "$,.0s"), key="t_fc")
        with c3:
            with ui.card("t3"):
                ui.card_title("Utilisation vs realisation", "bubble = fees billed")
                fig = go.Figure(go.Scatter(x=at["util"], y=at["realisation"], mode="markers+text", text=[s.split(",")[0] for s in at.index], textposition="top center", textfont=dict(size=9),
                                           marker=dict(size=np.clip(at["fees"] / 5000, 10, 46), color=TEAL, opacity=0.65, line=dict(color="#fff", width=1)),
                                           customdata=np.c_[at["attorney"], at["fees"]], hovertemplate="%{customdata[0]}<br>util %{x:.0%} · real %{y:.0%} · fees $%{customdata[1]:,.0f}<extra></extra>"))
                fig.add_vline(x=TARGET_UTIL, line_dash="dot", line_color="#94a3b8", annotation_text="target", annotation_font_size=9)
                fig.update_layout(**ui.base_layout(300)); fig.update_xaxes(title=dict(text="utilisation", font=dict(size=10)), tickformat=".0%"); fig.update_yaxes(title=dict(text="realisation", font=dict(size=10)))
                ui.show(ui.style_axes(fig, ".0%"), key="t_ur")
        with ui.card("t4"):
            ui.card_title("Fees by practice area", "per fee earner")
            fig = go.Figure([go.Bar(y=at.index, x=at[f"f_{k}"], orientation="h", name=k, marker_color=AREA_COLORS[k]) for k in AREAS])
            fig.update_layout(**ui.base_layout(300, legend=True), barmode="stack")
            ui.show(ui.style_axes(fig, "$,.0s"), key="t_area")

    # ------------------------------------------------------------ capacity
    with tabs[1]:
        c1, c2 = st.columns([1.2, 1])
        with c1:
            with ui.card("t5"):
                ui.card_title("Billable hours by month", "last 12 months (full-month equivalents)")
                h = X.att_monthly(M, cur.end, 12, "hours")
                fig = go.Figure(go.Heatmap(z=h.T.values, x=[d.strftime("%b %y") for d in h.index], y=list(h.columns), colorscale=[[0, "#f1f5f9"], [0.5, "#86c9d1"], [1, "#0a8496"]],
                                           text=h.T.round(0).values, texttemplate="%{text:.0f}", hovertemplate="%{y} · %{x}: %{z:.0f} hrs<extra></extra>", showscale=False))
                fig.update_layout(**ui.base_layout(300, margin=dict(l=8, r=8, t=6, b=4))); fig.update_yaxes(autorange="reversed")
                ui.show(fig, key="t_heat")
        with c2:
            with ui.card("t6"):
                ui.card_title("Capacity used", "hours vs available hours in the period")
                a = at.sort_values("util")
                fig = go.Figure()
                fig.add_trace(go.Bar(y=a.index, x=a["capacity"], orientation="h", name="Capacity", marker_color="#e2e8f0"))
                fig.add_trace(go.Bar(y=a.index, x=a["hours"], orientation="h", name="Billable hours", marker_color=[GREEN if u >= TARGET_UTIL else AMBER for u in a["util"]]))
                fig.update_layout(**ui.base_layout(300, legend=True), barmode="overlay")
                ui.show(ui.style_axes(fig, ",.0f"), key="t_cap")
        with ui.card("t7"):
            ui.card_title("Hours by fee earner and practice area", cur.label)
            fig = go.Figure([go.Bar(x=at.index, y=at[f"h_{k}"], name=k, marker_color=AREA_COLORS[k]) for k in AREAS])
            fig.update_layout(**ui.base_layout(250, legend=True), barmode="stack")
            ui.show(ui.style_axes(fig, ",.0f"), key="t_hoursarea")
            under = at[at["util"] < TARGET_UTIL - 0.03]
            if len(under):
                ui.note("Below the utilisation target: " + ", ".join(f"{s} ({u:.0%})" for s, u in under["util"].items()) + ". Check for new-starter ramp-up, leave or work not being recorded.", "warn")
            else:
                ui.note("Every fee earner is within 3 points of the utilisation target.", "good")

    # -------------------------------------------------------------- pay
    with tabs[2]:
        with ui.card("t8"):
            ui.card_title("Rates, cost and break-even", "hourly economics per fee earner")
            rows = []
            for a_ in ATTORNEYS:
                r = at.loc[a_["short"]]
                rows.append(dict(attorney=a_["name"], role=a_["role"], bill_rate=a_["bill_rate"], pay_rate=a_["pay_rate"], eff_rate=r["eff_rate"], margin_hr=r["eff_rate"] - a_["pay_rate"],
                                 multiple=r["eff_rate"] / a_["pay_rate"], breakeven=r["breakeven_hours"], hours=r["hours"]))
            df = pd.DataFrame(rows)
            df[["eff_rate", "margin_hr", "breakeven", "hours"]] = df[["eff_rate", "margin_hr", "breakeven", "hours"]].round(0)
            st.dataframe(df, hide_index=True, width="stretch", height=340, column_config={
                "attorney": st.column_config.TextColumn("Attorney", width=130), "role": st.column_config.TextColumn("Role", width=170), "bill_rate": ui.money_col("Std rate /hr"), "pay_rate": ui.money_col("Pay /hr"),
                "eff_rate": ui.money_col("Eff. rate /hr"), "margin_hr": ui.money_col("Margin /hr"), "multiple": st.column_config.NumberColumn("Fee ÷ pay", format="%.1f×"),
                "breakeven": st.column_config.NumberColumn("Break-even hrs", format="%,d"), "hours": st.column_config.NumberColumn("Hours", format="%,d")})
            ui.note("Break-even hours = payroll cost in the period ÷ effective rate: the hours a fee earner must bill just to cover their own pay.")
        with ui.card("t9"):
            ui.card_title("Contribution per fee earner", cur.label)
            a = at.sort_values("contribution")
            fig = go.Figure(go.Bar(y=a.index, x=a["contribution"], orientation="h", marker_color=[GREEN if v > 0 else RED for v in a["contribution"]], hovertemplate="%{y}: $%{x:,.0f}<extra></extra>"))
            fig.update_layout(**ui.base_layout(280))
            ui.show(ui.style_axes(fig, "$,.0s"), key="t_contrib")
        with ui.card("t10"):
            f = X.fin_sum(M, cur)
            ui.card_title("Payroll as a share of revenue", cur.label)
            ptot = f["payroll_fee"] + f["payroll_support"]
            k = st.columns(4)
            k[0].metric("Fee-earner payroll", ui.fmt_money(f["payroll_fee"]), f"{f['payroll_fee'] / f['revenue']:.1%} of revenue", delta_color="off")
            k[1].metric("Support-staff payroll", ui.fmt_money(f["payroll_support"]), f"{f['payroll_support'] / f['revenue']:.1%} of revenue", delta_color="off")
            k[2].metric("Total payroll", ui.fmt_money(ptot), f"{ptot / f['revenue']:.1%} of revenue", delta_color="off")
            k[3].metric("Revenue per fee earner (annualised)", ui.fmt_money(f["revenue"] / cur.days * 365 / max(int((at["capacity"] > 0).sum()), 1)), delta_color="off")

    # --------------------------------------------------------------- branches
    with tabs[3]:
        bt = X.branch_table(M, cur)
        with ui.card("t11"):
            ui.card_title("Branch results", "shared overheads allocated by fee share (general) and headcount (support payroll)")
            out = bt.reset_index()[["branch", "council", "fee_earners", "support", "headcount", "active_matters", "hours", "util", "revenue", "cost", "op_profit", "margin"]].copy()
            out[["hours", "revenue", "cost", "op_profit"]] = out[["hours", "revenue", "cost", "op_profit"]].round(0)
            st.dataframe(out, hide_index=True, width="stretch", column_config={
                "branch": "Branch", "council": "Council", "fee_earners": "Fee earners", "support": "Support", "headcount": "Headcount", "active_matters": "Active matters", "hours": st.column_config.NumberColumn("Hours", format="%d"),
                "util": st.column_config.NumberColumn("Utilisation", format="percent"), "revenue": ui.money_col("Revenue"), "cost": ui.money_col("Costs"), "op_profit": ui.money_col("Op. profit"), "margin": st.column_config.NumberColumn("Margin", format="percent")})
        c1, c2 = st.columns(2)
        with c1:
            with ui.card("t12"):
                ui.card_title("Revenue and profit by branch")
                fig = go.Figure()
                fig.add_trace(go.Bar(x=bt.index, y=bt["revenue"], name="Revenue", marker_color=TEAL))
                fig.add_trace(go.Bar(x=bt.index, y=bt["op_profit"], name="Operating profit", marker_color=INDIGO))
                fig.update_layout(**ui.base_layout(260, legend=True), barmode="group")
                ui.show(ui.style_axes(fig, "$,.0s"), key="t_br")
        with c2:
            with ui.card("t13"):
                ui.card_title("Margin and revenue per head")
                fig = go.Figure()
                fig.add_trace(go.Bar(x=bt.index, y=bt["revenue"] / bt["headcount"], name="Revenue per head", marker_color="#86c9d1"))
                fig.add_trace(go.Scatter(x=bt.index, y=bt["margin"], name="Margin (right)", yaxis="y2", mode="lines+markers", line=dict(color=INK, width=2.5)))
                fig.update_layout(**ui.base_layout(260, legend=True), yaxis2=dict(overlaying="y", side="right", tickformat=".0%", showgrid=False, tickfont=dict(size=9)))
                ui.show(ui.style_axes(fig, "$,.0s"), key="t_br2")
