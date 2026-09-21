"""Simulator — what-if analysis on the last twelve months of actuals."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core import metrics as X
from core import ui
from core.model import GST
from core.period import Period
from core.ref import AS_OF
from core.theme import TEAL, INDIGO, AMBER, RED, GREEN, INK, MUTED

ROLES = {"Associate": dict(bill=380, pay=120), "Senior Associate": dict(bill=520, pay=170), "Partner": dict(bill=650, pay=210)}
# lever values are stored in the units the analyst sees: percentage points, percent, hires, days
DEFAULTS = dict(sim_util=0.0, sim_rate=0.0, sim_real=0.0, sim_hires=0, sim_role="Associate", sim_ramp=75, sim_infl=0.0, sim_recov=0.0, sim_dso=0)
HIRE_OVERHEAD = 9000        # desk, software, insurance and recruitment per new fee earner per year (assumption)
LTM_DAYS = 352              # length of the "last 12 months" window (1 Oct 24 – 17 Sep 25) in days


def _base(M):
    p = Period(AS_OF.replace(day=1) - pd.DateOffset(months=11), AS_OF, "Last 12 months")
    return p, X.fin_sum(M, p)


def project(f, s):
    """Annualised P&L under the scenario. f = last-12-month actuals; s = lever values (pp / % / count / days)."""
    k = 365.0 / LTM_DAYS                                            # scale the 352-day window to a full year
    hours0, fees0, val0 = f["hours"] * k, f["fees"] * k, f["value_std"] * k
    util0, real0 = f["hours"] / f["capacity"], f["fees"] / f["value_std"]
    std_rate0 = val0 / hours0
    hires, role, ramp = int(s["sim_hires"]), ROLES[s["sim_role"]], s["sim_ramp"] / 100.0
    util1 = util0 + s["sim_util"] / 100.0
    real1 = real0 + s["sim_real"] / 100.0
    rate_up = 1 + s["sim_rate"] / 100.0
    hours1 = hours0 * util1 / util0                                 # existing team: hours scale with utilisation
    hire_hours = hires * 190 * 12 * util1 * ramp                    # new hires bill at the firm's utilisation × year-one productivity
    fees1 = hours1 * std_rate0 * rate_up * real1 + hire_hours * role["bill"] * rate_up * real1
    hrs_ratio = (hours1 + hire_hours) / hours0
    disb_cost1 = f["disb_cost"] * k * hrs_ratio
    disb_bill1 = disb_cost1 * (f["disb_billed"] / f["disb_cost"] + s["sim_recov"] / 100.0)
    rev0, rev1 = (f["fees"] + f["disb_billed"]) * k, fees1 + disb_bill1
    over0 = (f["total_costs"] - f["payroll_fee"] - f["disb_cost"]) * k
    cost0 = f["total_costs"] * k
    cost1 = f["payroll_fee"] * k + hires * role["pay"] * 190 * 12 + disb_cost1 + over0 * (1 + s["sim_infl"] / 100.0) + hires * HIRE_OVERHEAD
    return dict(rev0=rev0, rev1=rev1, cost0=cost0, cost1=cost1, op0=rev0 - cost0, op1=rev1 - cost1, fees0=fees0, fees1=fees1, hours0=hours0, hours1=hours1 + hire_hours,
                util0=util0, util1=util1, eff0=fees0 / hours0, eff1=fees1 / (hours1 + hire_hours), real0=real0, real1=real1,
                dso_cash=-s["sim_dso"] * rev1 * (1 + GST) / 365.0, over0=over0)                       # slower payment (+days) ties up cash → negative


def render(M, cur, cmp):
    ui.page_header("Simulator", "Test a decision on the last twelve months of actuals before committing to it", "Base: last 12 months, annualised")
    p, f = _base(M)
    ss = st.session_state
    for k, v in DEFAULTS.items():
        ss.setdefault(k, v)
    ss.setdefault("saved_scen", [])

    left, right = st.columns([1, 2.3])
    with left:
        with ui.card("s1"):
            ui.card_title("Levers")
            st.slider("Utilisation change (pp)", -10.0, 10.0, key="sim_util", step=0.5, format="%+.1f", help="Percentage points added to today's utilisation")
            st.slider("Rate increase (%)", 0.0, 10.0, key="sim_rate", step=0.5, format="%.1f")
            st.slider("Realisation change (pp)", -5.0, 5.0, key="sim_real", step=0.5, format="%+.1f")
            st.slider("Disbursement recovery change (pp)", -10.0, 10.0, key="sim_recov", step=1.0, format="%+.0f")
            st.slider("Overhead inflation (%)", 0.0, 10.0, key="sim_infl", step=0.5, format="%.1f")
            st.slider("New fee earners", 0, 3, key="sim_hires")
            if ss["sim_hires"]:
                st.selectbox("Role of new hire(s)", list(ROLES), key="sim_role")
                st.slider("Year-one productivity of a new hire", 40, 100, key="sim_ramp", step=5, format="%d%%",
                          help="Share of the firm's utilisation a new hire bills in year one. Assumes enough work exists to keep them busy.")
            st.slider("Change in DSO (days)", -15, 15, key="sim_dso", help="Positive = clients pay slower")
            if st.button("Reset levers", key="act_reset"):
                for k, v in DEFAULTS.items():
                    ss[k] = v
                st.rerun()
    s = {k: ss[k] for k in DEFAULTS}
    r = project(f, s)
    with right:
        ui.kpi_row([
            dict(label="Revenue", value=ui.fmt_money(r["rev1"]), d=(r["rev1"] - r["rev0"]) / r["rev0"], label_cmp="vs base", accent=TEAL, sub=f"base {ui.fmt_money(r['rev0'])}"),
            dict(label="Operating profit", value=ui.fmt_money(r["op1"]), d=(r["op1"] - r["op0"]) / r["op0"], label_cmp="vs base", accent=TEAL, sub=f"{ui.fmt_money(r['op1'] - r['op0'], sign=True)} a year"),
            dict(label="Operating margin", value=ui.fmt_pct(r["op1"] / r["rev1"]), d=r["op1"] / r["rev1"] - r["op0"] / r["rev0"], kind="pp", label_cmp="vs base", accent=TEAL, sub=f"base {ui.fmt_pct(r['op0'] / r['rev0'])}"),
            dict(label="Effective rate", value=f"${r['eff1']:,.0f}/hr", d=(r["eff1"] - r["eff0"]) / r["eff0"], label_cmp="vs base", accent=TEAL),
        ], spacer_after=6, min_h=88)
        with ui.card("s2"):
            ui.card_title("Operating profit bridge", "base → scenario, annual")
            fee_eff = r["fees1"] - r["fees0"]
            disb_eff = (r["rev1"] - r["fees1"]) - (r["rev0"] - r["fees0"])
            cost_eff = -(r["cost1"] - r["cost0"])
            fig = go.Figure(go.Waterfall(x=["Base op. profit", "Fees", "Disbursement recovery", "Costs", "Scenario op. profit"], y=[r["op0"], fee_eff, disb_eff, cost_eff, 0], measure=["absolute", "relative", "relative", "relative", "total"],
                                         increasing=dict(marker=dict(color=GREEN)), decreasing=dict(marker=dict(color=RED)), totals=dict(marker=dict(color=TEAL)), hovertemplate="%{x}: $%{y:,.0f}<extra></extra>"))
            fig.update_layout(**ui.base_layout(250))
            ui.show(ui.style_axes(fig, "$.2s"), key="sim_wf")
        c1, c2 = st.columns(2)
        with c1:
            with ui.card("s3"):
                ui.card_title("What moves profit most", "effect of one unit of each lever")
                base_s = dict(DEFAULTS)
                base_op = project(f, base_s)["op1"]
                tests = {"+1 pp utilisation": dict(sim_util=1.0), "+1% rates": dict(sim_rate=1.0), "+1 pp realisation": dict(sim_real=1.0),
                         "+5 pp disb. recovery": dict(sim_recov=5.0), "−1% overhead inflation": dict(sim_infl=-1.0),
                         "+1 Associate hire (50% productive)": dict(sim_hires=1, sim_role="Associate", sim_ramp=50)}
                eff = sorted(((n, project(f, {**base_s, **t})["op1"] - base_op) for n, t in tests.items()), key=lambda x: x[1])
                fig = go.Figure(go.Bar(y=[e[0] for e in eff], x=[e[1] for e in eff], orientation="h", marker_color=[GREEN if e[1] > 0 else RED for e in eff], hovertemplate="%{y}: %{x:+,.0f} a year<extra></extra>"))
                fig.update_layout(**ui.base_layout(240))
                ui.show(ui.style_axes(fig, "$,.0s"), key="sim_tor")
        with c2:
            with ui.card("s4"):
                ui.card_title("Cash and capacity effects")
                hire_row = (f'<tr><td>Extra cost per new hire (pay + overhead)</td><td class="num">{ui.fmt_money(ROLES[s["sim_role"]]["pay"] * 190 * 12 + HIRE_OVERHEAD)}</td></tr>' if s["sim_hires"] else "")
                st.markdown(f"""
<table class="simple"><tbody>
<tr><td>Billable hours (annual)</td><td class="num">{r['hours0']:,.0f} → {r['hours1']:,.0f}</td></tr>
<tr><td>Utilisation</td><td class="num">{r['util0']:.1%} → {r['util1']:.1%}</td></tr>
<tr><td>Realisation</td><td class="num">{r['real0']:.1%} → {r['real1']:.1%}</td></tr>
<tr><td>One-off cash effect of DSO change</td><td class="num" style="color:{GREEN if r['dso_cash'] >= 0 else RED}">{ui.fmt_money(r['dso_cash'], sign=True)}</td></tr>
{hire_row}
</tbody></table>""", unsafe_allow_html=True)
                ui.spacer(6)
                if s["sim_hires"] and s["sim_ramp"] < 100:
                    ui.note(f"A new {s['sim_role'].lower()} is assumed to be {s['sim_ramp']}% productive in year one; payback on the hire is longer than the annual figure suggests.", "warn")
                if s["sim_util"] > 5:
                    ui.note("Utilisation above about 95% is rarely sustainable: check for burnout and quality risk before planning on it.", "warn")
        with ui.card("s5"):
            ui.card_title("Saved scenarios", "compare options side by side")
            c1, c2 = st.columns([3, 1])
            name = c1.text_input("Scenario name", value=f"Scenario {len(ss['saved_scen']) + 1}", key="sim_name", label_visibility="collapsed")
            if c2.button("Save scenario", key="act_save"):
                ss["saved_scen"].append(dict(Scenario=name, Revenue=r["rev1"], Costs=r["cost1"], OperatingProfit=r["op1"], Margin=r["op1"] / r["rev1"], Utilisation=r["util1"], Levers=", ".join(f"{k.replace('sim_', '')}={v}" for k, v in s.items() if v != DEFAULTS[k])))
                st.rerun()
            base_row = dict(Scenario="Base (last 12 months)", Revenue=r["rev0"], Costs=r["cost0"], OperatingProfit=r["op0"], Margin=r["op0"] / r["rev0"], Utilisation=r["util0"], Levers="")
            tbl = pd.DataFrame([base_row] + ss["saved_scen"])
            tbl[["Revenue", "Costs", "OperatingProfit"]] = tbl[["Revenue", "Costs", "OperatingProfit"]].round(0)
            tbl["vs base"] = tbl["OperatingProfit"] - r["op0"]
            st.dataframe(tbl, hide_index=True, width="stretch", column_config={"Revenue": ui.money_col("Revenue"), "Costs": ui.money_col("Costs"), "OperatingProfit": ui.money_col("Op. profit"), "vs base": ui.money_col("Op. profit vs base"),
                                                                               "Margin": st.column_config.NumberColumn("Margin", format="percent"), "Utilisation": st.column_config.NumberColumn("Utilisation", format="percent")})
            if ss["saved_scen"] and st.button("Clear saved scenarios", key="act_clear"):
                ss["saved_scen"] = []
                st.rerun()
        ui.note("Simple annual what-if on the last twelve months: it holds volumes, mix and client behaviour constant except for the levers above.")
