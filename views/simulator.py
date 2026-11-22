"""Decision Simulator — test a decision on the last 12 months of actuals before making it: pricing, hiring, redundancies,
a new branch or a platform switch. Shows profit, the gap to budget, the cash needed up front, what it would take to close
the gap, and how much of the result depends on delivery. Built to fit one laptop screen: levers left, results right."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core import metrics as X
from core import simulate as S
from core import ui
from core.period import stock_at
from core.ref import AS_OF
from core.theme import TEAL, AMBER, RED, GREEN, INK, MUTED, FAINT

TARGET_KINDS = ["Match the FY26 budget operating profit", "Reach the FY26 budget margin", "Add a custom profit uplift"]
LEVER_KEYS = list(S.DEFAULTS)
MIN_CASH = 60_000                       # minimum operating balance the firm keeps in the office account
PANEL_H = 508                           # height of the results panel; the lever panel is taller by the KPI row (fits 1440 × 810)


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


def _slider(key, label, fmt=None, help=None):
    lo, hi, step = S.BOUNDS[key]
    st.slider(label, lo, hi, key=key, step=step, format=fmt, help=help)


def _rows(rows):
    st.markdown('<table class="simple compact"><tbody>' + "".join(f'<tr><td>{a}</td><td class="num">{b}</td></tr>' for a, b in rows) + "</tbody></table>",
                unsafe_allow_html=True)


def _signed(v):
    return f'<span style="color:{GREEN if v >= 0 else RED};font-weight:600">{ui.fmt_money(v, sign=True)}</span>'


def render(M, cur, cmp):
    ss = st.session_state
    ui.restore_state({**S.DEFAULTS, "sim_target_kind": TARGET_KINDS[0], "sim_uplift": 100000, "saved_scen": []})
    ctx = S.context(M)
    p, f = S.base_actuals(M)
    bt = S.budget_targets(M)
    base = S.project(f, S.DEFAULTS, ctx=ctx)

    st.markdown(f'<style>div[class*="st-key-cardblock_s2_"] {{ min-height:{PANEL_H + 28}px; }}</style>', unsafe_allow_html=True)
    ui.page_header("★ Decision Simulator", "Test a decision before you make it: pricing, hiring, redundancies, a new branch or a platform switch",
                   f"Base: last 12 months · {p.start:%b %y} – {p.end:%b %y}")

    # ---------------------------------------------------------------- presets
    ui.spacer(2)
    names = list(S.PRESETS)
    cols = st.columns(len(names) + 1, gap="small")
    for i, (name, col) in enumerate(zip(names, cols)):
        col.button(S.PRESET_SHORT[name], key=f"act_preset_{i}", on_click=_preset, args=(name,), help=S.PRESET_HELP[name], width="stretch")
    cols[-1].button("Reset", key="act_reset", on_click=_load, args=(S.DEFAULTS,), help="Back to today's run-rate", width="stretch")

    # ------------------------------------------------- levers (drawn first so results use them)
    left, right = st.columns([1, 2.55], gap="small")
    with left:
        with ui.card("s1"):
            lt = st.tabs(["Pricing & time", "People", "Branch & system"])
            if True:
                with lt[0], st.container(height=PANEL_H + 50, border=False):
                    _slider("sim_util", "Utilisation change (pp)", "%+.1f")
                    _slider("sim_rate", "Rate increase (%)", "%.1f")
                    _slider("sim_real", "Realisation change (pp)", "%+.1f")
                    _slider("sim_recov", "Disbursement recovery (pp)", "%+.0f")
                    _slider("sim_infl", "Overhead change (%)", "%+.1f")
                    _slider("sim_dso", "Change in days to collect", None, "Negative = clients pay faster. Changes cash once, not profit.")
                with lt[1], st.container(height=PANEL_H + 50, border=False):
                    st.slider("New fee earners", 0, 3, key="sim_hires")
                    if ss["sim_hires"]:
                        c1, c2 = st.columns(2)
                        c1.selectbox("Role", list(S.ROLES), key="sim_role")
                        with c2:
                            _slider("sim_ramp", "Year-one productivity", "%d%%", "Share of the firm's utilisation a new hire bills in year one.")
                    st.slider("Fee earners leaving", 0, 2, key="sim_cut_fe")
                    if ss["sim_cut_fe"]:
                        c1, c2 = st.columns(2)
                        c1.selectbox("Role leaving", list(S.ROLES), key="sim_cut_role")
                        with c2:
                            _slider("sim_keep_work", "Work kept (%)", "%d%%", "Share of the leaver's billable work the rest of the team picks up.")
                    _slider("sim_cut_support", "Support roles cut")
                    if ss["sim_cut_fe"] or ss["sim_cut_support"]:
                        _slider("sim_cut_years", "Years of service of those leaving", "%d yrs", "Sets NES redundancy and notice pay.")
                with lt[2], st.container(height=PANEL_H + 50, border=False):
                    st.toggle("Open a new branch", key="sim_branch")
                    if ss["sim_branch"]:
                        c1, c2 = st.columns(2)
                        with c1:
                            _slider("sim_branch_fe", "Associates")
                            _slider("sim_branch_rent", "Rent / month", "$%d")
                            _slider("sim_branch_ramp", "Months to full speed", "%d")
                        with c2:
                            _slider("sim_branch_support", "Support staff")
                            _slider("sim_branch_fitout", "Fit-out (one-off)", "$%d")
                    st.selectbox("Practice-management platform", list(ctx["platforms"]), key="sim_platform",
                                 help="First-year saving and migration cost come from the platform evaluation pages (sidebar).")

    s = {k: ss[k] for k in LEVER_KEYS}
    r = S.project(f, s, ctx=ctx)
    m0, m1 = base["op0"] / base["rev0"], S.margin(r)

    # cash position after the decision: today's balance and the 13-week low point, less one-off cash, plus any DSO release
    cash_now = stock_at(M["stock"], "cash", AS_OF)
    low0 = float(X.cash_forecast(M)["closing"].min())
    low1 = low0 + r["cash_effect"]
    monthly_cost = r["cost1"] / 12

    with right:
        gap = r["op1"] - bt["op"]
        ui.kpi_row([
            dict(label="Operating profit (a year)", value=ui.fmt_money(r["op1"]), d=(r["op1"] - r["op0"]) / r["op0"], label_cmp="vs base", accent=TEAL,
                 sub=f"{ui.fmt_money(r['op1'] - r['op0'], sign=True)} vs today"),
            dict(label="Operating margin", value=ui.fmt_pct(m1), d=m1 - m0, kind="pp", label_cmp="vs base", accent=TEAL, sub=f"base {ui.fmt_pct(m0)}"),
            dict(label="Gap to FY26 budget", value=ui.fmt_money(gap, sign=True), label_cmp=None, accent=GREEN if gap >= 0 else RED, color=GREEN if gap >= 0 else RED,
                 sub=f"budget profit {ui.fmt_money(bt['op'])}"),
            dict(label="Cash needed up front", value=ui.fmt_money(r["one_off"]), label_cmp=None, accent=AMBER if r["one_off"] else TEAL,
                 sub="fit-out, redundancy, migration"),
            dict(label="13-week cash low point", value=ui.fmt_money(low1), label_cmp=None, accent=RED if low1 < MIN_CASH else TEAL, color=RED if low1 < MIN_CASH else INK,
                 sub=f"today {ui.fmt_money(low0)} · minimum $60K"),
        ], min_h=0)
        with ui.card("s2"):
            rt = st.tabs(["Profit bridge", "Effects & cash", "What would it take?", "How sure are we?", "Saved scenarios", "Method"])
            with rt[0]:
                _bridge(r, bt, f, ctx)
            with rt[1]:
                _effects(r, s, cash_now, low0, low1, monthly_cost)
            with rt[2]:
                _goal(f, s, r, base, bt, ctx)
            with rt[3]:
                _risk(f, s, base, bt, ctx)
            with rt[4]:
                _scenarios(r, s, base, m0)
            with rt[5]:
                _method(p, ctx)
    ui.keep_state(LEVER_KEYS + ["sim_target_kind", "sim_uplift"])


# ------------------------------------------------------------------- tabs
CH = PANEL_H - 118                       # chart height inside the results card


def _bridge(r, bt, f, ctx):
    fee_eff = r["fees1"] - r["fees0"]
    disb_eff = (r["rev1"] - r["fees1"]) - (r["rev0"] - r["fees0"])
    cost_eff = -(r["cost1"] - r["cost0"])
    c1, c2 = st.columns([1.75, 1], gap="medium")
    with c1:
        fig = go.Figure(go.Waterfall(x=["Today's profit", "Fees", "Disb. recovery", "Costs", "Scenario profit"], y=[r["op0"], fee_eff, disb_eff, cost_eff, 0],
                                     measure=["absolute", "relative", "relative", "relative", "total"], increasing=dict(marker=dict(color=GREEN)), decreasing=dict(marker=dict(color=RED)),
                                     totals=dict(marker=dict(color=TEAL)), hovertemplate="%{x}: $%{y:,.0f}<extra></extra>",
                                     text=[("" if abs(v) < 500 else ui.fmt_money(v, sign=i in (1, 2, 3))) for i, v in enumerate([r["op0"], fee_eff, disb_eff, cost_eff, r["op1"]])],
                                     textposition="outside"))
        fig.add_hline(y=bt["op"], line_dash="dot", line_color=AMBER, annotation_text=f"FY26 budget {ui.fmt_money(bt['op'])}", annotation_font_size=10, annotation_position="top left")
        fig.update_layout(**ui.base_layout(CH, margin=dict(l=8, r=8, t=18, b=4)))
        vals = [r["op0"], r["op1"], bt["op"]]
        fig.update_yaxes(range=[min(vals) * 0.82, max(vals) * 1.1])
        ui.show(ui.style_axes(fig, "$.2s"), key="sim_wf")
        st.markdown(f'<div class="tbl-note">Annual, run-rate. The axis does not start at zero. One-off costs are not in operating profit: see "Effects &amp; cash".</div>',
                    unsafe_allow_html=True)
    with c2:
        st.markdown('<div class="mini-title">What moves profit most</div><div class="tbl-note">one unit of each lever, a year</div>', unsafe_allow_html=True)
        eff = S.lever_ranking(f, ctx=ctx)
        fig = go.Figure(go.Bar(y=[e[0] for e in eff], x=[e[1] for e in eff], orientation="h", marker_color=[GREEN if e[1] > 0 else RED for e in eff],
                               hovertemplate="%{y}: %{x:+,.0f} a year<extra></extra>"))
        fig.update_layout(**ui.base_layout(CH - 26, margin=dict(l=4, r=8, t=4, b=4)))
        fig.update_yaxes(tickfont=dict(size=9))
        ui.show(ui.style_axes(fig, "$.2s"), key="sim_tor")


def _effects(r, s, cash_now, low0, low1, monthly_cost):
    c1, c2 = st.columns(2, gap="medium")
    rows = [("Billable hours a year", f"{r['hours0']:,.0f} → {r['hours1']:,.0f}"), ("Utilisation", f"{r['util0']:.1%} → {r['util1']:.1%}")]
    if s["sim_hires"]:
        rows += [("New hire(s): fees − cost, year one", _signed(r["hire_net"])), ("Productivity a hire needs to break even", f"{r['hire_breakeven_ramp']:.0%}")]
    if s["sim_cut_fe"]:
        rows += [("Fee earners leaving: pay saved", _signed(r["cut_saving"])), ("Fees lost (after work kept)", _signed(-r["cut_fees_lost"]))]
    if s["sim_cut_support"]:
        rows += [("Support roles cut: pay saved a year", _signed(r["support_saving"]))]
    if s["sim_branch"]:
        pb = f"{r['branch_payback']} months" if r["branch_payback"] else "not within 5 years"
        rows += [("New branch: fees − costs, year one", _signed(r["branch_net"])), ("New branch at full speed, a year", _signed(r["branch_net_full"])),
                 ("Fit-out earned back after", pb)]
    if s["sim_platform"] != S.CURRENT_PLATFORM:
        rows += [("Platform: first-year saving", _signed(r["platform_annual"]))]
    with c1:
        st.markdown('<div class="mini-title">Profit effects (a year)</div>', unsafe_allow_html=True)
        _rows(rows)
        if r["util1"] > 0.95:
            ui.note("Utilisation above about 95% is rarely sustainable: check burnout and quality risk.", "warn")
        if s["sim_cut_fe"] and r["cut_fees_lost"] > r["cut_saving"]:
            ui.note("The fee earner(s) leaving bill more than they cost: this cut lowers profit.", "warn")
        if s["sim_hires"] and s["sim_ramp"] < (r["hire_breakeven_ramp"] or 0) * 100:
            ui.note("At this productivity the new hire does not cover their own cost in year one.", "warn")
    with c2:
        st.markdown('<div class="mini-title">Cash</div>', unsafe_allow_html=True)
        crow = []
        if r["redundancy"] or r["notice_pay"]:
            sb = "none: small-business exemption" if r["small_business"] else f"{r['redundancy_weeks']} weeks each (NES)"
            crow += [(f"Redundancy pay · {sb}", ui.fmt_money(r["redundancy"])), (f"Notice pay · {r['notice_weeks']} weeks each", ui.fmt_money(r["notice_pay"]))]
        if r["branch_fitout"]:
            crow += [("Branch fit-out", ui.fmt_money(r["branch_fitout"]))]
        if r["platform_one_off"]:
            crow += [("Platform migration and go-live dip", ui.fmt_money(r["platform_one_off"]))]
        if r["dso_cash"]:
            crow += [("Cash released by collecting faster" if r["dso_cash"] > 0 else "Cash tied up by collecting slower", _signed(r["dso_cash"]))]
        crow += [("Office account today", ui.fmt_money(cash_now)), ("13-week low point: today → after", f"{ui.fmt_money(low0)} → <b>{ui.fmt_money(low1)}</b>"),
                 ("Cash cover after the decision", f"{(cash_now + r['cash_effect']) / monthly_cost:.1f} months")]
        _rows(crow)
        if low1 < MIN_CASH:
            ui.note(f"This takes the account below the ${MIN_CASH / 1000:.0f}K minimum balance. Fund it first: lower partner drawings, a loan, or stage the spend.", "warn")
        elif r["one_off"]:
            ui.note("Assumes every one-off cost is paid in the first week: the worst case for the low point.")


def _goal(f, s, r, base, bt, ctx):
    g1, g2 = st.columns([1.6, 1])
    kind = g1.selectbox("Target", TARGET_KINDS, key="sim_target_kind", label_visibility="collapsed")
    if kind == TARGET_KINDS[2]:
        uplift = g2.number_input("Extra profit a year ($)", 0, 2_000_000, step=25_000, key="sim_uplift", label_visibility="collapsed")
        goal = dict(target_op=base["op0"] + uplift); tgt_txt = f"operating profit of {ui.fmt_money(goal['target_op'])} a year"
    elif kind == TARGET_KINDS[1]:
        goal = dict(target_margin=bt["margin"]); tgt_txt = f"an operating margin of {bt['margin']:.1%}"
    else:
        goal = dict(target_op=bt["op"]); tgt_txt = f"operating profit of {ui.fmt_money(bt['op'])} a year"
    cur_val = r["op1"] if "target_op" in goal else S.margin(r)
    tgt_val = goal.get("target_op", goal.get("target_margin"))
    gap_txt = (f"{ui.fmt_money(tgt_val - cur_val)} short" if tgt_val > cur_val else "already met") if "target_op" in goal else (f"{(tgt_val - cur_val) * 100:.1f} pp short" if tgt_val > cur_val else "already met")
    st.markdown(f'<div class="note">Target: <b>{tgt_txt}</b>. Your scenario gives {ui.fmt_money(cur_val) if "target_op" in goal else f"{cur_val:.1%}"} ({gap_txt}). '
                f'Each line moves one lever on its own, on top of your current levers.</div>', unsafe_allow_html=True)
    gs = S.goal_seek(f, s, ctx=ctx, **goal)
    for _, row in gs.iterrows():
        a, b, c, d = st.columns([1.7, 2.6, 1.4, 0.9], vertical_alignment="center")
        a.markdown(f'<div class="goal-txt"><b>{row["label"]}</b></div>', unsafe_allow_html=True)
        b.markdown(f'<div class="goal-txt">{_fmt_need(row, r["util0"])}</div>', unsafe_allow_html=True)
        kind_ = {"Comfortable": "good", "Already met": "good", "Stretch": "warn"}.get(row["difficulty"], "bad")
        c.markdown(ui.pill(row["difficulty"], kind_), unsafe_allow_html=True)
        ok = row["apply_value"] is not None and not pd.isna(row["apply_value"]) and row["difficulty"] != "Already met"
        d.button("Apply", key=f"act_apply_{row['lever']}", disabled=not ok, on_click=_apply_lever, args=(row["lever"], row["apply_value"]) if ok else (row["lever"], 0))


def _risk(f, s, base, bt, ctx):
    dr = S.delivery_range(f, s, ctx=ctx)
    c1, c2 = st.columns([1.6, 1], gap="medium")
    with c1:
        fig = go.Figure(go.Bar(x=[f"{int(d * 100)}% delivered" for d in dr["delivery"]], y=dr["op"], marker_color=[TEAL, "#5bb4bd", "#a7d8de"],
                               text=[ui.fmt_money(v) for v in dr["op"]], textposition="outside", hovertemplate="%{x}: $%{y:,.0f}<extra></extra>"))
        fig.add_hline(y=bt["op"], line_dash="dot", line_color=AMBER, annotation_text="FY26 budget", annotation_font_size=10, annotation_position="bottom right")
        fig.add_hline(y=base["op0"], line_dash="dot", line_color="#94a3b8", annotation_text="today", annotation_font_size=10, annotation_position="bottom left")
        fig.update_layout(**ui.base_layout(CH, margin=dict(l=8, r=8, t=26, b=4)))
        fig.update_yaxes(range=[min(base["op0"], dr["op"].min(), bt["op"]) * 0.88, max(bt["op"], dr["op"].max()) * 1.08])
        ui.show(ui.style_axes(fig, "$.2s"), key="sim_risk")
    with c2:
        st.markdown('<div class="mini-title">Operating profit if only part of the plan is delivered</div>', unsafe_allow_html=True)
        ui.note("Only the uncertain parts are cut back: better utilisation, rates, realisation and recovery, overhead savings, a new hire's or branch's "
                "productivity, and work kept after someone leaves. Pay, rent and other setbacks are never softened.")
        if abs(dr["op"].iloc[0] - dr["op"].iloc[2]) < 1:
            ui.note("Nothing to cut back yet: load a decision or move a lever.")
        elif dr["op"].iloc[0] > base["op0"] and dr["op"].iloc[2] < bt["op"] <= dr["op"].iloc[0]:
            ui.note("The plan reaches budget only if most of it is delivered: little margin for error.", "warn")
        elif dr["op"].iloc[2] < base["op0"]:
            ui.note("At half delivery this plan earns less than doing nothing.", "warn")


def _scenarios(r, s, base, m0):
    ss = st.session_state
    n1, n2, n3 = st.columns([2.2, 1, 1])
    name = n1.text_input("Scenario name", value=f"Scenario {len(ss['saved_scen']) + 1}", key="sim_name", label_visibility="collapsed")
    n2.button("Save", key="act_save", on_click=_save, args=(name, r, s), width="stretch")
    if ss["saved_scen"]:
        n3.button("Clear", key="act_clear", on_click=lambda: ss.__setitem__("saved_scen", []), width="stretch")
    base_row = dict(Scenario="Today (last 12 months)", Revenue=base["rev0"], Costs=base["cost0"], OperatingProfit=base["op0"], Margin=m0, Utilisation=base["util0"], OneOff=0.0, Levers="none")
    tbl = pd.DataFrame([base_row] + ss["saved_scen"])
    tbl[["Revenue", "Costs", "OperatingProfit", "OneOff"]] = tbl[["Revenue", "Costs", "OperatingProfit", "OneOff"]].round(0)
    tbl["vs today"] = (tbl["OperatingProfit"] - base["op0"]).round(0)
    st.dataframe(tbl[["Scenario", "OperatingProfit", "vs today", "Margin", "OneOff", "Levers"]], hide_index=True, width="stretch", height=PANEL_H - 170,
                 column_config={"OperatingProfit": ui.money_col("Op. profit"), "vs today": ui.signed_money_col("vs today"), "OneOff": ui.money_col("One-off cash"),
                                "Margin": st.column_config.NumberColumn("Margin", format="percent")})
    ui.csv_button(tbl, "scenarios", "scen")


def _method(p, ctx):
    st.markdown(f"""<div class="method">
<b>Base:</b> the last 12 months of actuals ({p.start:%d %b %y} – {p.end:%d %b %y}), scaled to a full year. Utilisation scales the team's hours; rates and realisation scale the fee on each hour.<br>
<b>Hiring:</b> new fee earners bill at the firm's utilisation × year-one productivity and cost pay plus ${S.HIRE_OVERHEAD:,} a year each. Assumes the work exists.<br>
<b>Leaving:</b> pay and overhead are saved; their fees go except the share the team keeps. Redundancy and notice pay follow the NES (Fair Work Act s 117, s 119):
employers with fewer than {S.SMALL_BUSINESS} employees are generally exempt from redundancy pay. This firm has {ctx['headcount']} employees. Awards, agreements and contracts can give more.<br>
<b>New branch:</b> associates ramp up in a straight line to full speed; costs are pay, support staff at ${S.SUPPORT_PAY_MONTH:,}/month, rent and ${S.BRANCH_RUNNING:,} a year running costs.
Fit-out is capital: cash, not operating profit.<br>
<b>Platform:</b> first-year saving and migration cost come from the platform evaluation (sidebar).<br>
<b>Cash:</b> every one-off cost is paid in week one of the 13-week forecast. It is a decision aid, not a forecast, and not legal or financial advice.</div>""", unsafe_allow_html=True)
