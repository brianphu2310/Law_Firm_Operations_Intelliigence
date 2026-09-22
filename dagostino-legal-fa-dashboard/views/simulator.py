"""Decision Simulator — the flagship page: test a decision on the last 12 months of actuals, see the gap to budget,
find what it would take to close it, and see how much risk sits in the plan."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core import simulate as S
from core import ui
from core.theme import TEAL, INDIGO, AMBER, RED, GREEN, INK, MUTED, BLUE

TARGET_KINDS = ["Match the FY26 budget operating profit", "Reach the FY26 budget margin", "Add a custom profit uplift"]
LEVER_KEYS = list(S.DEFAULTS)


# ---- callbacks (they run before the widgets are drawn, so they may set widget values safely) ----
def _load(state):
    for k, v in state.items():
        st.session_state[k] = v


def _preset(name):
    _load(S.preset_state(name))


def _apply_lever(lever, value):
    st.session_state[lever] = value


def _save(name, r, s):
    ss = st.session_state
    ss["saved_scen"].append(S.scenario_summary(name, r, s))
    ss["sim_name"] = f"Scenario {len(ss['saved_scen']) + 1}"


def _fmt_need(row, util0):
    lever, x, ch = row["lever"], row["required"], row["change"]
    if x is None or pd.isna(x):
        return "Not enough on its own"
    if abs(ch) < 1e-9:
        return "Already met by your current levers"
    return {"sim_util": f"{ch:+.1f} pp  (to {util0 * 100 + x:.1f}% utilisation)", "sim_rate": f"{ch:+.1f}% on all rates", "sim_real": f"{ch:+.1f} pp realisation",
            "sim_recov": f"{ch:+.1f} pp recovery", "sim_infl": f"{ch:+.1f}% on overheads"}[lever]


def render(M, cur, cmp):
    ss = st.session_state
    ui.restore_state({**S.DEFAULTS, "sim_target_kind": TARGET_KINDS[0], "sim_uplift": 100000, "saved_scen": []})
    p, f = S.base_actuals(M)
    bt = S.budget_targets(M)
    base = S.project(f, S.DEFAULTS)

    st.markdown(f'<div class="sim-hero"><div><div class="sim-hero-kicker">★ FLAGSHIP TOOL</div><div class="sim-hero-title">Decision Simulator</div>'
                f'<div class="sim-hero-sub">Test a decision before you make it. Change hiring, pricing, utilisation, collections or overheads and see profit, margin and the gap to '
                f'budget instantly, then find out what it would take to close that gap.</div></div>'
                f'<div class="sim-hero-tag">Base: last 12 months, annualised · {p.start:%b %y} – {p.end:%b %y}</div></div>', unsafe_allow_html=True)

    # ------------------------------------------------------------- quick start
    with ui.card("s0"):
        ui.card_title("Start from a decision", "one click loads the levers; adjust anything afterwards")
        cols = st.columns(len(S.PRESETS) + 1)
        for i, (name, col) in enumerate(zip(S.PRESETS, cols)):
            col.button(name, key=f"act_preset_{i}", on_click=_preset, args=(name,), help=S.PRESET_HELP[name], width="stretch")
        cols[-1].button("Reset", key="act_reset", on_click=_load, args=(S.DEFAULTS,), help="Back to today's run-rate", width="stretch")

    left, right = st.columns([1, 2.3])
    with left:
        with ui.card("s1"):
            ui.card_title("Levers")
            for key, label, fmt in [("sim_util", "Utilisation change (pp)", "%+.1f"), ("sim_rate", "Rate increase (%)", "%.1f"), ("sim_real", "Realisation change (pp)", "%+.1f"),
                                    ("sim_recov", "Disbursement recovery change (pp)", "%+.0f"), ("sim_infl", "Overhead change (%)", "%+.1f")]:
                lo, hi, step = S.BOUNDS[key]
                st.slider(label, lo, hi, key=key, step=step, format=fmt)
            st.slider("New fee earners", 0, 3, key="sim_hires")
            if ss["sim_hires"]:
                st.selectbox("Role of new hire(s)", list(S.ROLES), key="sim_role")
                lo, hi, step = S.BOUNDS["sim_ramp"]
                st.slider("Year-one productivity of a new hire", lo, hi, key="sim_ramp", step=step, format="%d%%",
                          help="Share of the firm's utilisation a new hire bills in year one. Assumes enough work exists to keep them busy.")
            lo, hi, step = S.BOUNDS["sim_dso"]
            st.slider("Change in days to collect (DSO)", lo, hi, key="sim_dso", help="Negative = clients pay faster")
    s = {k: ss[k] for k in LEVER_KEYS}
    r = S.project(f, s)
    m0, m1 = base["op0"] / base["rev0"], S.margin(r)

    with right:
        gap = r["op1"] - bt["op"]
        ui.kpi_row([
            dict(label="Revenue", value=ui.fmt_money(r["rev1"]), d=(r["rev1"] - r["rev0"]) / r["rev0"], label_cmp="vs base", accent=TEAL, sub=f"base {ui.fmt_money(r['rev0'])}"),
            dict(label="Operating profit", value=ui.fmt_money(r["op1"]), d=(r["op1"] - r["op0"]) / r["op0"], label_cmp="vs base", accent=TEAL, sub=f"{ui.fmt_money(r['op1'] - r['op0'], sign=True)} a year"),
            dict(label="Operating margin", value=ui.fmt_pct(m1), d=m1 - m0, kind="pp", label_cmp="vs base", accent=TEAL, sub=f"base {ui.fmt_pct(m0)}"),
            dict(label="Effective rate", value=f"${r['eff1']:,.0f}/hr", d=(r["eff1"] - r["eff0"]) / r["eff0"], label_cmp="vs base", accent=TEAL, sub=f"base ${r['eff0']:,.0f}/hr"),
            dict(label="Gap to FY26 budget", value=ui.fmt_money(gap, sign=True), label_cmp=None, accent=GREEN if gap >= 0 else RED, color=GREEN if gap >= 0 else RED,
                 sub=f"budget profit {ui.fmt_money(bt['op'])}"),
        ], spacer_after=6, min_h=88)
        with ui.card("s2"):
            ui.card_title("Operating profit bridge", "base → scenario, annual · axis does not start at zero")
            fee_eff = r["fees1"] - r["fees0"]
            disb_eff = (r["rev1"] - r["fees1"]) - (r["rev0"] - r["fees0"])
            cost_eff = -(r["cost1"] - r["cost0"])
            fig = go.Figure(go.Waterfall(x=["Base profit", "Fees", "Disbursement recovery", "Costs", "Scenario profit"], y=[r["op0"], fee_eff, disb_eff, cost_eff, 0],
                                         measure=["absolute", "relative", "relative", "relative", "total"], increasing=dict(marker=dict(color=GREEN)), decreasing=dict(marker=dict(color=RED)),
                                         totals=dict(marker=dict(color=TEAL)), hovertemplate="%{x}: $%{y:,.0f}<extra></extra>"))
            fig.add_hline(y=bt["op"], line_dash="dot", line_color=AMBER, annotation_text=f"FY26 budget {ui.fmt_money(bt['op'])}", annotation_font_size=10, annotation_position="top left")
            fig.update_layout(**ui.base_layout(250))
            lo_y = min(r["op0"], r["op1"], bt["op"]) * 0.85
            fig.update_yaxes(range=[lo_y, max(r["op0"], r["op1"], bt["op"]) * 1.06])
            ui.show(ui.style_axes(fig, "$.2s"), key="sim_wf")
        c1, c2 = st.columns(2)
        with c1:
            with ui.card("s3"):
                ui.card_title("What moves profit most", "one unit of each lever, per year")
                eff = S.lever_ranking(f)
                fig = go.Figure(go.Bar(y=[e[0] for e in eff], x=[e[1] for e in eff], orientation="h", marker_color=[GREEN if e[1] > 0 else RED for e in eff], hovertemplate="%{y}: %{x:+,.0f} a year<extra></extra>"))
                fig.update_layout(**ui.base_layout(240))
                ui.show(ui.style_axes(fig, "$.2s"), key="sim_tor")
        with c2:
            with ui.card("s4"):
                ui.card_title("Capacity, cash and hiring effects")
                rows = [("Billable hours (annual)", f"{r['hours0']:,.0f} → {r['hours1']:,.0f}"), ("Utilisation", f"{r['util0']:.1%} → {r['util1']:.1%}"), ("Realisation", f"{r['real0']:.1%} → {r['real1']:.1%}"),
                        ("One-off cash effect of DSO change", f'<span style="color:{GREEN if r["dso_cash"] >= 0 else RED}">{ui.fmt_money(r["dso_cash"], sign=True)}</span>')]
                if s["sim_hires"]:
                    rows += [("Cost of new hire(s) a year", ui.fmt_money(r["hire_cost"])), ("Fees from new hire(s), year one", ui.fmt_money(r["hire_fees"])),
                             ("Net contribution, year one", f'<span style="color:{GREEN if r["hire_net"] >= 0 else RED}">{ui.fmt_money(r["hire_net"], sign=True)}</span>'),
                             ("Productivity needed to break even", f"{r['hire_breakeven_ramp']:.0%} of the firm average")]
                st.markdown('<table class="simple"><tbody>' + "".join(f'<tr><td>{a}</td><td class="num">{b}</td></tr>' for a, b in rows) + "</tbody></table>", unsafe_allow_html=True)
                ui.spacer(6)
                if s["sim_hires"] and s["sim_ramp"] < r["hire_breakeven_ramp"] * 100:
                    ui.note("At this productivity the new hire does not cover their own cost in year one.", "warn")
                if r["util1"] > 0.95:
                    ui.note("Utilisation above about 95% is rarely sustainable: check burnout and quality risk before planning on it.", "warn")

    # ------------------------------------------------------------ goal seek
    with ui.card("s5"):
        ui.card_title("What would it take?", "goal-seek: how far must each lever move on its own?")
        g1, g2 = st.columns([1.6, 1])
        kind = g1.selectbox("Target", TARGET_KINDS, key="sim_target_kind")
        if kind == TARGET_KINDS[2]:
            uplift = g2.number_input("Extra profit a year ($)", 0, 2_000_000, step=25_000, key="sim_uplift")
            goal = dict(target_op=base["op0"] + uplift); tgt_txt = f"operating profit of {ui.fmt_money(goal['target_op'])} a year"
        elif kind == TARGET_KINDS[1]:
            goal = dict(target_margin=bt["margin"]); tgt_txt = f"an operating margin of {bt['margin']:.1%}"
        else:
            goal = dict(target_op=bt["op"]); tgt_txt = f"operating profit of {ui.fmt_money(bt['op'])} a year"
        cur_val = r["op1"] if "target_op" in goal else S.margin(r)
        tgt_val = goal.get("target_op", goal.get("target_margin"))
        gap_txt = (f"{ui.fmt_money(tgt_val - cur_val)} short" if tgt_val > cur_val else "already met") if "target_op" in goal else (f"{(tgt_val - cur_val) * 100:.1f} pp short" if tgt_val > cur_val else "already met")
        st.markdown(f'<div class="note">Target: <b>{tgt_txt}</b>. Your scenario gives {ui.fmt_money(cur_val) if "target_op" in goal else f"{cur_val:.1%}"} ({gap_txt}).</div>', unsafe_allow_html=True)
        gs = S.goal_seek(f, s, **goal)
        for _, row in gs.iterrows():
            a, b, c, d = st.columns([1.7, 2.6, 1.3, 0.9], vertical_alignment="center")
            a.markdown(f'<div class="goal-txt"><b>{row["label"]}</b></div>', unsafe_allow_html=True)
            b.markdown(f'<div class="goal-txt">{_fmt_need(row, r["util0"])}</div>', unsafe_allow_html=True)
            kind_ = {"Comfortable": "good", "Already met": "good", "Stretch": "warn"}.get(row["difficulty"], "bad")
            c.markdown(ui.pill(row["difficulty"], kind_), unsafe_allow_html=True)
            ok = row["apply_value"] is not None and not pd.isna(row["apply_value"]) and row["difficulty"] != "Already met"
            d.button("Apply", key=f"act_apply_{row['lever']}", disabled=not ok, on_click=_apply_lever, args=(row["lever"], row["apply_value"]) if ok else (row["lever"], 0))
        ui.note("Each line is one lever moved on its own, on top of the levers you have already set. \"Apply\" loads the required value into the slider (rounded up to the slider step).")

    # ---------------------------------------------------------------- risk
    c1, c2 = st.columns([1.15, 1])
    with c1:
        with ui.card("s6"):
            ui.card_title("How sure are we?", "operating profit if only part of the improvement is delivered")
            dr = S.delivery_range(f, s)
            fig = go.Figure(go.Bar(x=[f"{int(d * 100)}% delivered" for d in dr["delivery"]], y=dr["op"], marker_color=[TEAL, "#5bb4bd", "#a7d8de"],
                                   text=[ui.fmt_money(v) for v in dr["op"]], textposition="outside", hovertemplate="%{x}: $%{y:,.0f}<extra></extra>"))
            fig.add_hline(y=bt["op"], line_dash="dot", line_color=AMBER, annotation_text="FY26 budget", annotation_font_size=10, annotation_position="bottom right")
            fig.add_hline(y=base["op0"], line_dash="dot", line_color="#94a3b8", annotation_text="base run-rate", annotation_font_size=10, annotation_position="bottom left")
            fig.update_layout(**ui.base_layout(240, margin=dict(l=8, r=8, t=26, b=4)))
            fig.update_yaxes(range=[min(base["op0"], dr["op"].min(), bt["op"]) * 0.9, max(bt["op"], dr["op"].max()) * 1.08])
            ui.show(ui.style_axes(fig, "$.2s"), key="sim_risk")
            if abs(dr["op"].iloc[0] - dr["op"].iloc[2]) < 1:
                ui.note("Nothing to haircut yet: load a decision above (or move a lever) to see how much of the result depends on delivery.")
            if dr["op"].iloc[0] > base["op0"] and dr["op"].iloc[2] < bt["op"] <= dr["op"].iloc[0]:
                ui.note("The plan reaches budget only if most of the improvement is delivered: there is little margin for error.", "warn")
    with c2:
        with ui.card("s7"):
            ui.card_title("Saved scenarios", "compare options side by side")
            n1, n2 = st.columns([2.2, 1])
            name = n1.text_input("Scenario name", value=f"Scenario {len(ss['saved_scen']) + 1}", key="sim_name", label_visibility="collapsed")
            n2.button("Save", key="act_save", on_click=_save, args=(name, r, s), width="stretch")
            base_row = dict(Scenario="Base (last 12 months)", Revenue=base["rev0"], Costs=base["cost0"], OperatingProfit=base["op0"], Margin=m0, Utilisation=base["util0"], Levers="none")
            tbl = pd.DataFrame([base_row] + ss["saved_scen"])
            tbl[["Revenue", "Costs", "OperatingProfit"]] = tbl[["Revenue", "Costs", "OperatingProfit"]].round(0)
            tbl["vs base"] = (tbl["OperatingProfit"] - base["op0"]).round(0)
            st.dataframe(tbl[["Scenario", "OperatingProfit", "vs base", "Margin", "Levers"]], hide_index=True, width="stretch",
                         column_config={"OperatingProfit": ui.money_col("Op. profit"), "vs base": ui.money_col("vs base"), "Margin": st.column_config.NumberColumn("Margin", format="percent")})
            b1, b2 = st.columns(2)
            with b1:
                ui.csv_button(tbl, "scenarios", "scen")
            if ss["saved_scen"]:
                b2.button("Clear", key="act_clear", on_click=lambda: ss.__setitem__("saved_scen", []), width="stretch")

    with st.expander("How the simulator works"):
        st.markdown(f"""
* **Base:** the last 12 months of actuals ({p.start:%d %b %y} – {p.end:%d %b %y}), scaled to a full year.
* **Utilisation** scales the existing team's billable hours; **rates** and **realisation** scale the fee earned on each hour; **disbursement recovery** changes how much of search and filing costs is billed on.
* **New fee earners** bill at the firm's utilisation × their year-one productivity, at the role's standard rate, and add pay plus about ${S.HIRE_OVERHEAD:,} a year of overhead each.
* **Overheads** are all costs except fee-earner payroll and searches/filing fees; searches and filing costs move with total hours.
* **Days to collect** changes cash once (it does not change profit): each day is about one day of billed revenue including GST.
* **Goal-seek** solves each lever on its own, on top of the levers you have set, to reach the target exactly, then rounds up to the slider step.
* **How sure are we?** applies only part of the *improvements* (better utilisation, rates, realisation, recovery, overhead cuts and the productivity of new hires); setbacks and a hire's pay are never softened.
* Holds volumes, mix and client behaviour constant except for the levers, and assumes enough work exists for any new hire. It is a decision aid, not a forecast.""")

    ui.keep_state(LEVER_KEYS + ["sim_target_kind", "sim_uplift"])
