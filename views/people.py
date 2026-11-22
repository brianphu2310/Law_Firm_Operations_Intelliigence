"""People — headcount, fee-earner performance, capacity, pay economics and branch staffing (formerly "Team")."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core import metrics as X
from core import ui
from core.period import delta, has_data
from core import simulate as SIM
from core.ref import AS_OF, AREAS, ATTORNEYS, BRANCHES, DEPT_DRIVERS
from core.theme import AREA_COLORS, TEAL, INDIGO, AMBER, RED, GREEN, INK, MUTED, BLUE

TARGET_UTIL = 0.85


def render(M, cur, cmp):
    ui.page_header("People", "Headcount, fee-earner performance, capacity, pay and branch staffing", ui.period_tag(cur, cmp))
    at = X.att_table(M, cur)
    ap = X.att_table(M, cmp) if cmp is not None and has_data(cmp) else None
    lab = ui.cmp_label(cmp)
    tot = at[["hours", "capacity", "value", "fees", "cost", "contribution"]].sum()
    n_fe, n_sup = int((at["capacity"] > 0).sum()), sum(b["support"] for b in BRANCHES)
    util, real, eff = tot["hours"] / tot["capacity"], tot["fees"] / tot["value"], tot["fees"] / tot["hours"]
    if ap is not None:
        tp = ap[["hours", "capacity", "value", "fees", "cost", "contribution"]].sum()
        up_, rp_, ep_ = tp["hours"] / tp["capacity"], tp["fees"] / tp["value"], tp["fees"] / tp["hours"]
    ui.kpi_row([
        dict(label="Headcount", value=f"{n_fe + n_sup}", label_cmp=None, accent=TEAL, sub=f"{n_fe} fee earners · {n_sup} support"),
        dict(label="Utilisation", value=ui.fmt_pct(util), d=(util - up_) if ap is not None else None, kind="pp", label_cmp=lab, accent=TEAL, sub=f"target {TARGET_UTIL:.0%}"),
        dict(label="Realisation", value=ui.fmt_pct(real), d=(real - rp_) if ap is not None else None, kind="pp", label_cmp=lab, accent=TEAL),
        dict(label="Effective rate", value=f"${eff:,.0f}/hr", d=delta(eff, ep_) if ap is not None else None, label_cmp=lab, accent=TEAL),
        dict(label="Fees billed", value=ui.fmt_money(tot["fees"]), d=delta(tot["fees"], tp["fees"]) if ap is not None else None, label_cmp=lab, accent=TEAL),
        dict(label="Contribution after pay", value=ui.fmt_money(tot["contribution"]), d=delta(tot["contribution"], tp["contribution"]) if ap is not None else None, label_cmp=lab, accent=TEAL, sub="fees − fee-earner payroll"),
    ])

    tabs = st.tabs(["Performance", "Where to hire", "Departments", "Branches & staffing", "Capacity & hours", "Pay & economics"])

    # ------------------------------------------------------------ performance
    with tabs[0]:
        c1, c2 = st.columns([1.55, 1])
        with c1:
            with ui.card("t1"):
                ui.card_title("Fee-earner scorecard", cur.label)
                out = at.reset_index().rename(columns={"index": "short"})
                out["fees_ap"] = ap["fees"].values if ap is not None else np.nan
                out["chg"] = np.where(out["fees_ap"] > 0, (out["fees"] - out["fees_ap"]) / out["fees_ap"], np.nan)
                show = out[["attorney", "role", "hours", "util", "realisation", "eff_rate", "fees", "contribution"]].copy()
                show[["hours", "eff_rate", "fees", "contribution"]] = show[["hours", "eff_rate", "fees", "contribution"]].round(0)
                st.dataframe(show, hide_index=True, width="stretch", height=322, column_config={
                    "attorney": st.column_config.TextColumn("Fee earner", width=112), "role": st.column_config.TextColumn("Role", width=150),
                    "hours": st.column_config.NumberColumn("Hours", format="%,d", width=56), "util": st.column_config.ProgressColumn("Utilisation", format="percent", min_value=0, max_value=1.1, width=96),
                    "realisation": st.column_config.NumberColumn("Realis.", format="percent", width=66), "eff_rate": ui.money_col("Rate /hr"), "fees": ui.money_col("Fees"),
                    "contribution": ui.money_col("Contribution")})
                under = at[at["util"] < TARGET_UTIL - 0.03]
                if len(under):
                    ui.note("Below the utilisation target: " + ", ".join(f"{s_} ({u:.0%})" for s_, u in under["util"].items()) + ".", "warn")
                else:
                    ui.note(f"Every fee earner is within 3 points of the {TARGET_UTIL:.0%} utilisation target, so the team has little room to absorb a leaver's work.", "good")
        with c2:
            with ui.card("t3"):
                ui.card_title("Utilisation vs realisation", "bubble = fees billed")
                fig = go.Figure(go.Scatter(x=at["util"], y=at["realisation"], mode="markers+text", text=[s_.split(",")[0] for s_ in at.index], textposition="top center", textfont=dict(size=9),
                                           marker=dict(size=np.clip(at["fees"] / 6000, 9, 38), color=TEAL, opacity=0.65, line=dict(color="#fff", width=1)),
                                           customdata=np.c_[at["attorney"], at["fees"]], hovertemplate="%{customdata[0]}<br>util %{x:.0%} · real %{y:.0%} · fees $%{customdata[1]:,.0f}<extra></extra>"))
                fig.add_vline(x=TARGET_UTIL, line_dash="dot", line_color="#94a3b8", annotation_text="target", annotation_font_size=9)
                fig.update_layout(**ui.base_layout(168)); fig.update_xaxes(tickformat=".0%")
                ui.style_axes(fig, ".0%")
                fig.update_yaxes(range=[at["realisation"].min() - 0.02, at["realisation"].max() + 0.03])
                ui.show(fig, key="t_ur")
            with ui.card("t2"):
                ui.card_title("Fees vs pay by fee earner")
                a = at.sort_values("fees")
                fig = go.Figure()
                fig.add_trace(go.Bar(y=a.index, x=a["fees"], orientation="h", name="Fees billed", marker_color=TEAL))
                fig.add_trace(go.Bar(y=a.index, x=a["cost"], orientation="h", name="Pay", marker_color="#94a3b8"))
                fig.update_layout(**ui.base_layout(168, legend=True), barmode="group"); fig.update_yaxes(tickfont=dict(size=9))
                ui.show(ui.style_axes(fig, "$,.0s"), key="t_fc")

    # ------------------------------------------------------------ capacity
    with tabs[4]:
        c1, c2 = st.columns([1.2, 1])
        with c1:
            with ui.card("t5"):
                ui.card_title("Billable hours by month", "last 12 months (full-month equivalents)")
                h = X.att_monthly(M, cur.end, 12, "hours")
                fig = go.Figure(go.Heatmap(z=h.T.values, x=[d.strftime("%b %y") for d in h.index], y=list(h.columns), colorscale=[[0, "#f1f5f9"], [0.5, "#86c9d1"], [1, "#0a8496"]],
                                           text=h.T.round(0).values, texttemplate="%{text:.0f}", hovertemplate="%{y} · %{x}: %{z:.0f} hrs<extra></extra>", showscale=False))
                fig.update_layout(**ui.base_layout(372, margin=dict(l=8, r=8, t=6, b=4))); fig.update_yaxes(autorange="reversed")
                ui.show(fig, key="t_heat")
        with c2:
            with ui.card("t6"):
                ui.card_title("Capacity used", "billable hours vs available hours in the period")
                a = at.sort_values("util")
                fig = go.Figure()
                fig.add_trace(go.Bar(y=a.index, x=a["capacity"], orientation="h", name="Capacity", marker_color="#e2e8f0"))
                fig.add_trace(go.Bar(y=a.index, x=a["hours"], orientation="h", name="Billable hours", marker_color=[GREEN if u >= TARGET_UTIL else AMBER for u in a["util"]]))
                fig.update_layout(**ui.base_layout(330, legend=True), barmode="overlay")
                ui.show(ui.style_axes(fig, ",.0f"), key="t_cap")
                spare = float((at["capacity"] * 0.95 - at["hours"]).clip(lower=0).sum())
                ui.note(f"Spare capacity up to 95% utilisation: about <b>{spare:,.0f} hours</b> in the period. That is the room the team has to absorb more work before hiring.")

    # -------------------------------------------------------------- pay
    with tabs[5]:
        f = X.fin_sum(M, cur)
        ptot = f["payroll_fee"] + f["payroll_support"]
        k = st.columns(4)
        k[0].metric("Fee-earner payroll", ui.fmt_money(f["payroll_fee"]), f"{f['payroll_fee'] / f['revenue']:.1%} of revenue", delta_color="off")
        k[1].metric("Support-staff payroll", ui.fmt_money(f["payroll_support"]), f"{f['payroll_support'] / f['revenue']:.1%} of revenue", delta_color="off")
        k[2].metric("Total payroll", ui.fmt_money(ptot), f"{ptot / f['revenue']:.1%} of revenue", delta_color="off")
        k[3].metric("Revenue per fee earner (a year)", ui.fmt_money(f["revenue"] / cur.days * 365 / max(n_fe, 1)), delta_color="off")
        c1, c2 = st.columns([1.55, 1])
        with c1:
            with ui.card("t8"):
                ui.card_title("Rates, pay and break-even", "break-even hours = pay in the period ÷ effective rate")
                rows = []
                for a_ in ATTORNEYS:
                    r = at.loc[a_["short"]]
                    rows.append(dict(attorney=a_["name"], role=a_["role"], bill_rate=a_["bill_rate"], pay_rate=a_["pay_rate"], eff_rate=r["eff_rate"], margin_hr=r["eff_rate"] - a_["pay_rate"],
                                     multiple=r["eff_rate"] / a_["pay_rate"], breakeven=r["breakeven_hours"], hours=r["hours"]))
                df = pd.DataFrame(rows)
                df[["eff_rate", "margin_hr", "breakeven", "hours"]] = df[["eff_rate", "margin_hr", "breakeven", "hours"]].round(0)
                st.dataframe(df, hide_index=True, width="stretch", height=322, column_config={
                    "attorney": st.column_config.TextColumn("Fee earner", width=112), "role": st.column_config.TextColumn("Role", width=150), "bill_rate": ui.money_col("Std rate"), "pay_rate": ui.money_col("Pay /hr"),
                    "eff_rate": ui.money_col("Eff. rate"), "margin_hr": ui.money_col("Margin /hr"), "multiple": st.column_config.NumberColumn("Fee ÷ pay", format="%.1f×"),
                    "breakeven": st.column_config.NumberColumn("Break-even hrs", format="%,d"), "hours": st.column_config.NumberColumn("Hours", format="%,d")})
        with c2:
            with ui.card("t9"):
                ui.card_title("Contribution per fee earner", "fees − pay, " + cur.label)
                a = at.sort_values("contribution")
                fig = go.Figure(go.Bar(y=a.index, x=a["contribution"], orientation="h", marker_color=[GREEN if v > 0 else RED for v in a["contribution"]], hovertemplate="%{y}: $%{x:,.0f}<extra></extra>"))
                fig.update_layout(**ui.base_layout(318))
                ui.show(ui.style_axes(fig, "$,.0s"), key="t_contrib")

    # --------------------------------------------------------------- branches
    with tabs[3]:
        bt = X.branch_table(M, cur)
        bt["ratio"] = bt["support"] / bt["fee_earners"]
        bt["rev_per_support"] = bt["revenue"] / bt["support"]
        with ui.card("t11"):
            ui.card_title("Branch results and staffing", "shared overheads allocated by fee share; support payroll by headcount")
            out = bt.reset_index()[["branch", "fee_earners", "support", "ratio", "active_matters", "util", "revenue", "rev_per_support", "cost", "op_profit", "margin"]].copy()
            out[["revenue", "rev_per_support", "cost", "op_profit"]] = out[["revenue", "rev_per_support", "cost", "op_profit"]].round(0)
            st.dataframe(out, hide_index=True, width="stretch", height=142, column_config={
                "branch": "Branch", "fee_earners": "Fee earners", "support": "Support", "ratio": st.column_config.NumberColumn("Support per lawyer", format="%.1f"),
                "active_matters": "Active matters", "util": st.column_config.NumberColumn("Utilisation", format="percent"), "revenue": ui.money_col("Revenue"),
                "rev_per_support": ui.money_col("Revenue per support"), "cost": ui.money_col("Costs"), "op_profit": ui.money_col("Op. profit"),
                "margin": st.column_config.NumberColumn("Margin", format="percent")})
        c1, c2 = st.columns(2)
        with c1:
            with ui.card("t12"):
                ui.card_title("Revenue and profit by branch")
                fig = go.Figure()
                fig.add_trace(go.Bar(x=bt.index, y=bt["revenue"], name="Revenue", marker_color=TEAL))
                fig.add_trace(go.Bar(x=bt.index, y=bt["op_profit"], name="Operating profit", marker_color=INDIGO))
                fig.update_layout(**ui.base_layout(190, legend=True), barmode="group")
                ui.show(ui.style_axes(fig, "$,.0s"), key="t_br")
        with c2:
            with ui.card("t13"):
                ui.card_title("Margin and support staff per lawyer")
                fig = go.Figure()
                fig.add_trace(go.Bar(x=bt.index, y=bt["margin"], name="Operating margin", marker_color="#86c9d1", text=[f"{m:.0%}" for m in bt["margin"]], textposition="inside"))
                fig.add_trace(go.Scatter(x=bt.index, y=bt["ratio"], name="Support per lawyer (right)", yaxis="y2", mode="lines+markers+text", line=dict(color=INK, width=2.5),
                                         text=[f"{r:.1f}" for r in bt["ratio"]], textposition="top center"))
                fig.update_layout(**ui.base_layout(190, legend=True))
                ui.style_axes(fig, ".0%")
                fig.update_layout(yaxis2=dict(overlaying="y", side="right", tickformat=".1f", showgrid=False, tickfont=dict(size=9), range=[0, bt["ratio"].max() * 1.35]))
                fig.update_yaxes(range=[0, bt["margin"].max() * 1.25], selector=dict(overlaying=None))
                ui.show(fig, key="t_br2")
        weak = bt["margin"].idxmin()
        ui.sim_cta(f"<b>{weak}</b> has {bt.loc[weak, 'ratio']:.1f} support staff per lawyer and the lowest margin ({bt.loc[weak, 'margin']:.0%}). "
                   "Test cutting two support roles, with NES redundancy pay, before hiring.", preset="Cut 2 support roles", key="people")

    # -------------------------------------------------------------- where to hire
    with tabs[1]:
        pa = X.practice_area_table(M)
        top = pa.index[0]
        c1, c2 = st.columns([1.55, 1])
        with c1:
            with ui.card("t14"):
                ui.card_title("Where to hire: demand, pressure and margin by practice area", "last 12 months · priority = 40% pressure, 35% demand growth, 25% margin")
                out = pa.reset_index()[["area", "verdict", "matters_opened", "matters_growth", "util", "eff_rate", "margin", "priority"]].copy()
                out[["eff_rate", "priority"]] = out[["eff_rate", "priority"]].round(0)
                out["matters_growth"] = out["matters_growth"] * 100; out["margin"] = out["margin"] * 100
                st.dataframe(out, hide_index=True, width="stretch", height=212, column_config={
                    "area": "Practice area", "verdict": "Verdict", "matters_opened": st.column_config.NumberColumn("New matters", format="%d"),
                    "matters_growth": st.column_config.NumberColumn("Growth", format="%+.0f%%"),
                    "util": st.column_config.ProgressColumn("Lawyers' utilisation", format="percent", min_value=0.7, max_value=1.0, width=130),
                    "eff_rate": ui.money_col("Rate /hr"), "margin": st.column_config.NumberColumn("Margin", format="%.0f%%"),
                    "priority": st.column_config.ProgressColumn("Priority", format="%d", min_value=0, max_value=100, width=90)})
                ui.note("Pressure = utilisation of the lawyers already doing the area's work. Margin = fees less those lawyers' pay, allocated by hours.")
            with ui.card("t15"):
                ui.card_title("One associate hire: year-one profit by practice area", "60% as busy as the area's lawyers in year one")
                _, ltm = SIM.base_actuals(M)
                ctx = SIM.context(M)
                base = SIM.project(ltm, SIM.DEFAULTS, ctx=ctx)["op1"]
                gains = {a: SIM.project(ltm, {**SIM.preset_state("Hire an associate"), "sim_hire_area": a}, ctx=ctx)["op1"] - base for a in pa.index}
                fig = go.Figure(go.Bar(x=list(gains), y=list(gains.values()), marker_color=[TEAL if a == top else "#94a3b8" for a in gains],
                                       text=[ui.fmt_money(v, sign=True) for v in gains.values()], textposition="outside", hovertemplate="%{x}: %{y:+,.0f}<extra></extra>"))
                fig.update_layout(**ui.base_layout(150, margin=dict(l=8, r=8, t=16, b=4)))
                fig.update_yaxes(range=[0, max(gains.values()) * 1.25])
                ui.show(ui.style_axes(fig, "$,.0s"), key="t_hire_area")
        with c2:
            with ui.card("t16"):
                ui.card_title("Pressure vs demand", "bubble = fees")
                colors = {"Hire here first": TEAL, "Next in line": AMBER, "Hold": "#94a3b8"}
                fig = go.Figure(go.Scatter(x=pa["util"], y=pa["matters_growth"], mode="markers+text", text=pa.index, textposition="top center", textfont=dict(size=9),
                                           marker=dict(size=np.clip(pa["fees"] / 60000, 12, 46), color=[colors[v] for v in pa["verdict"]], opacity=0.75, line=dict(color="#fff", width=1)),
                                           hovertemplate="%{text}<br>utilisation %{x:.0%} · new matters %{y:+.0%}<extra></extra>"))
                fig.update_layout(**ui.base_layout(300))
                fig.update_xaxes(tickformat=".0%", title=dict(text="lawyers' utilisation", font=dict(size=10)))
                ui.style_axes(fig, "+.0%")
                fig.update_yaxes(title=dict(text="growth in new matters", font=dict(size=10)))
                ui.show(fig, key="t_pressure")
            r0 = pa.iloc[0]
            ui.sim_cta(f"<b>{top}</b>: lawyers at {r0['util']:.0%} and new matters {r0['matters_growth']:+.0%}. Test hiring an associate there.",
                       key="hire_area", state={**SIM.PRESETS["Hire an associate"], "sim_hire_area": top})

    # -------------------------------------------------------------- departments
    with tabs[2]:
        dt = X.department_table(M)
        c1, c2 = st.columns([1.55, 1])
        with c1:
            with ui.card("t17"):
                ui.card_title("Support staff against workload", "last 12 months · benchmarks are assumptions, listed below")
                out = dt[["branch", "department", "headcount", "volume", "needed", "gap", "status", "cost_of_gap"]].copy()
                out[["volume", "cost_of_gap"]] = out[["volume", "cost_of_gap"]].round(0)
                st.dataframe(out, hide_index=True, width="stretch", height=300, row_height=33, column_config={
                    "branch": "Office", "department": "Department", "headcount": st.column_config.NumberColumn("Staff", format="%d"),
                    "volume": st.column_config.NumberColumn("Workload", format="%,d", help="Inquiries, active matters, transactions or dollars, by department"),
                    "needed": st.column_config.NumberColumn("Needed", format="%.1f"), "gap": st.column_config.NumberColumn("Gap", format="%+.1f"),
                    "status": "Status", "cost_of_gap": ui.signed_money_col("Gap × pay, a year")})
                bench = " · ".join(f"<b>{d}</b>: {v['note']}" for d, v in DEPT_DRIVERS.items())
                st.markdown(f'<div class="tbl-note" style="line-height:1.4">{bench}</div>', unsafe_allow_html=True)
        with c2:
            with ui.card("t18"):
                ui.card_title("Staff vs needed")
                lab = [f"{b[:4]} · {d.split(' ')[0]}" for b, d in zip(dt["branch"], dt["department"])]
                fig = go.Figure()
                fig.add_trace(go.Bar(y=lab, x=dt["needed"], orientation="h", name="Needed", marker_color="#cbd5e1"))
                fig.add_trace(go.Bar(y=lab, x=dt["headcount"], orientation="h", name="Staff",
                                     marker_color=[RED if s_ == "Over-staffed" else (AMBER if s_ in ("Stretched", "Under-staffed") else TEAL) for s_ in dt["status"]]))
                fig.update_layout(**ui.base_layout(300, legend=True), barmode="group"); fig.update_yaxes(tickfont=dict(size=9), autorange="reversed")
                ui.show(ui.style_axes(fig, ",.0f"), key="t_dept")
            over = dt[dt["status"] == "Over-staffed"].sort_values("gap", ascending=False)
            if len(over):
                o = over.iloc[0]
                ui.sim_cta(f"<b>{o['branch']} {o['department'].lower()}</b>: {o['headcount']} staff for {o['needed']:.1f} roles of work. Test a restructure.",
                           key="dept", state={"sim_cut_support": int(o["gap"]), "sim_support_dept": o["department"], "sim_cut_years": 3})
