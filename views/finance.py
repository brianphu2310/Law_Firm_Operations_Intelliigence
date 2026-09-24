"""Finance — P&L vs budget, FY outlook, cash, billing & WIP, trust account and supplier/cost detail."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core import metrics as X
from core import ui
from core.model import GST
from core.period import Period, delta, has_data, stock_at, flow
from core import simulate as SIM
from core.ref import AS_OF, AREAS, OFFICE_CASH_AT_AS_OF
from core.theme import AREA_COLORS, TEAL, INDIGO, AMBER, RED, GREEN, INK, MUTED, BLUE, VIOLET

REV_LINES = [("Professional fees", "fees"), ("Disbursements recovered", "disb_billed")]
COST_LINES = [("Fee-earner payroll", "payroll_fee"), ("Support-staff payroll", "payroll_support"), ("Searches & filing fees (cost)", "disb_cost"), ("Rent", "rent"),
              ("Software", "software"), ("Insurance", "insurance"), ("Marketing", "marketing"), ("Professional fees", "prof_fees"), ("Card expenses", "cards"),
              ("Merchant fees (RapidPay)", "merchant"), ("Referral commissions", "commission"), ("Bank fees", "bank_fees"), ("Other overheads", "other")]


def _in(df, cur, col="date"):
    return df[(df[col] >= cur.start) & (df[col] <= cur.end + pd.Timedelta(hours=23, minutes=59))]


def _cell(v, kind="money", fav=None):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    txt = ui.fmt_money(v) if kind == "money" else (ui.fmt_pct(v, 1, sign=True) if kind == "pct" else ui.pp(v))
    if fav is None:
        return txt
    return f'<span style="color:{GREEN if fav else RED};font-weight:600">{txt}</span>'


def _pl_table(a, b, p):
    """P&L statement: actual vs budget vs prior period, favourable/(unfavourable) variances coloured."""
    head = ("<thead><tr><th>Line</th><th class='num'>Actual</th><th class='num'>Budget</th><th class='num'>Var $</th><th class='num'>Var %</th>"
            "<th class='num'>Prior period</th><th class='num'>Δ vs prior</th></tr></thead>")
    rows = ""

    def line(label, key, is_cost, cls="", bold=False):
        av, bv = a[key], b[key]
        pv = p[key] if p is not None else None
        var = (bv - av) if is_cost else (av - bv)
        vp = var / abs(bv) if bv else None
        chg = delta(av, pv) if pv is not None else None
        chg_fav = None if chg is None else ((chg <= 0) if is_cost else (chg >= 0))
        return (f'<tr class="{cls}"><td>{label}</td><td class="num">{ui.fmt_money(av)}</td><td class="num">{ui.fmt_money(bv)}</td>'
                f'<td class="num">{_cell(var, fav=var >= 0)}</td><td class="num">{_cell(vp, "pct", fav=None if vp is None else vp >= 0)}</td>'
                f'<td class="num">{ui.fmt_money(pv) if pv is not None else "—"}</td><td class="num">{_cell(chg, "pct", fav=chg_fav)}</td></tr>')

    def section(t):
        return f'<tr class="sub"><td colspan="7">{t}</td></tr>'
    rows += section("Revenue")
    for l, k in REV_LINES:
        rows += line(l, k, False)
    rows += line("Total revenue", "revenue", False, "sub")
    rows += section("Operating costs")
    for l, k in COST_LINES:
        rows += line(l, k, True)
    rows += line("Total operating costs", "total_costs", True, "sub")
    rows += line("Operating profit (before partner drawings)", "op_profit", False, "total")
    ma, mb = a["op_profit"] / a["revenue"], b["op_profit"] / b["revenue"]
    mp = p["op_profit"] / p["revenue"] if p is not None else None
    rows += (f'<tr><td>Operating margin</td><td class="num">{ui.fmt_pct(ma)}</td><td class="num">{ui.fmt_pct(mb)}</td><td class="num">{_cell(ma - mb, "pp", fav=ma >= mb)}</td><td class="num"></td>'
             f'<td class="num">{ui.fmt_pct(mp) if mp is not None else "—"}</td><td class="num">{_cell(ma - mp, "pp", fav=ma >= mp) if mp is not None else "—"}</td></tr>')
    st.markdown(f'<table class="simple">{head}<tbody>{rows}</tbody></table>', unsafe_allow_html=True)


def render(M, cur, cmp):
    ui.page_header("Finance", "Profit & loss, outlook, cash, billing, trust account and supplier costs", ui.period_tag(cur, cmp))
    tabs = st.tabs(["P&L vs budget", "FY outlook", "Cash", "Billing & WIP", "Trust account", "Suppliers & costs"])
    with tabs[0]: _pl(M, cur, cmp)
    with tabs[1]: _outlook(M)
    with tabs[2]: _cash(M, cur, cmp)
    with tabs[3]: _billing(M, cur, cmp)
    with tabs[4]: _trust(M, cur, cmp)
    with tabs[5]: _costs(M, cur, cmp)


# ============================================================================ P&L
def _pl(M, cur, cmp):
    a, b = X.fin_sum(M, cur), X.plan_sum(M, cur)
    p = X.fin_sum(M, cmp) if cmp is not None and has_data(cmp) else None
    lab = ui.cmp_label(cmp)
    ra, rp = X.ratios(a), (X.ratios(p) if p is not None else {})
    ui.kpi_row([
        dict(label="Revenue", value=ui.fmt_money(a["revenue"]), d=delta(a["revenue"], p["revenue"]) if p is not None else None, label_cmp=lab, accent=TEAL, spark=X.spark(M, "revenue", cur.end), sub=f"budget {ui.fmt_money(b['revenue'])} ({delta(a['revenue'], b['revenue']) * 100:+.1f}%)"),
        dict(label="Operating costs", value=ui.fmt_money(a["total_costs"]), d=delta(a["total_costs"], p["total_costs"]) if p is not None else None, up_good=False, label_cmp=lab, accent=TEAL, sub=f"budget {ui.fmt_money(b['total_costs'])}"),
        dict(label="Operating profit", value=ui.fmt_money(a["op_profit"]), d=delta(a["op_profit"], p["op_profit"]) if p is not None else None, label_cmp=lab, accent=TEAL, spark=X.spark(M, "op_profit", cur.end), sub=f"budget {ui.fmt_money(b['op_profit'])}"),
        dict(label="Operating margin", value=ui.fmt_pct(ra["margin"]), d=(ra["margin"] - rp["margin"]) if p is not None else None, kind="pp", label_cmp=lab, accent=TEAL, sub=f"budget {ui.fmt_pct(b['op_profit'] / b['revenue'])}"),
        dict(label="Realisation", value=ui.fmt_pct(ra["realisation"]), d=(ra["realisation"] - rp["realisation"]) if p is not None else None, kind="pp", label_cmp=lab, accent=TEAL, sub="fees billed ÷ value at standard rates"),
        dict(label="Effective rate", value=f"${ra['eff_rate']:,.0f}/hr", d=delta(ra["eff_rate"], rp.get("eff_rate")) if p is not None else None, label_cmp=lab, accent=TEAL, sub="fees billed ÷ billable hours"),
    ], spacer_after=6)
    gap = a["op_profit"] - b["op_profit"]
    if gap < 0:
        ui.sim_cta(f"Operating profit is <b>{ui.fmt_money(-gap)} ({-gap / b['op_profit']:.1%}) behind budget</b> for this period. See what would close the gap over a full year.",
                   target_kind="Match the FY26 budget operating profit", key="pl")
    else:
        ui.sim_cta(f"Operating profit is <b>{ui.fmt_money(gap)} ahead of budget</b>. Test which decisions would protect or extend that lead.", key="pl")
    ui.spacer(4)
    c1, c2 = st.columns([1.55, 1])
    with c1:
        with ui.card("f1"):
            ui.card_title("Income statement", f"{cur.label}; variances are favourable (green) / unfavourable (red)")
            _pl_table(a, b, p)
            ui.note("Operating profit is before partner drawings, income tax and depreciation. Merchant fees and card costs are included in overheads.")
    with c2:
        with ui.card("f2"):
            ui.card_title("Revenue: actual vs budget", "last 12 months (full-month equivalents)")
            r = X.monthly(M, "revenue", cur.end, 12); bud = M["plan"]["revenue"].loc[r.index]
            fig = go.Figure()
            fig.add_trace(go.Bar(x=r.index, y=r.values, name="Actual", marker_color=TEAL))
            fig.add_trace(go.Scatter(x=r.index, y=bud.values, name="Budget", line=dict(color=INK, dash="dot", width=2)))
            fig.update_layout(**ui.base_layout(220, legend=True)); fig.update_xaxes(tickformat="%b %y")
            ui.show(ui.style_axes(fig, "$,.0s"), key="f_rev")
        with ui.card("f3"):
            ui.card_title("Where the cost dollar goes", cur.label)
            items = [(l, a[k]) for l, k in COST_LINES]
            top = sorted(items, key=lambda x: -x[1])
            big, rest = top[:5], sum(v for _, v in top[5:])
            labs = [l for l, _ in big] + ["All other"]; vals = [v for _, v in big] + [rest]
            ui.donut(labs, vals, [TEAL, BLUE, INDIGO, VIOLET, AMBER, "#cbd5e1"], h=170, center=f"<b style='font-size:15px'>{ui.fmt_money(a['total_costs'])}</b>", key="f_costdonut")
            leg = "".join(f'<div class="donut-legend-item" style="margin-bottom:0;"><span class="legend-dot" style="background:{c}"></span>{l} ({v / a["total_costs"]:.0%})</div>' for (l, v), c in zip(zip(labs, vals), [TEAL, BLUE, INDIGO, VIOLET, AMBER, "#cbd5e1"]))
            st.markdown(f'<div style="display:grid; grid-template-columns:1fr; gap:2px;">{leg}</div>', unsafe_allow_html=True)
    with ui.card("f4"):
        ui.card_title("Variance to budget by cost line", "positive = under budget (favourable)")
        rows = [(l, b[k] - a[k]) for l, k in COST_LINES] + [("Revenue shortfall / surplus", a["revenue"] - b["revenue"])]
        rows = sorted(rows, key=lambda x: x[1])
        fig = go.Figure(go.Bar(y=[r[0] for r in rows], x=[r[1] for r in rows], orientation="h", marker_color=[GREEN if r[1] >= 0 else RED for r in rows], hovertemplate="%{y}: %{x:+,.0f}<extra></extra>"))
        fig.update_layout(**ui.base_layout(310))
        ui.show(ui.style_axes(fig, "$,.0s"), key="f_var")


# ======================================================================== outlook
def _outlook(M):
    o = X.fy_outlook(M)
    y = o["path"]
    ui.kpi_row([
        dict(label="FY26 budget revenue", value=ui.fmt_money(o["budget_rev"]), label_cmp=None, accent=TEAL),
        dict(label="FY26 forecast revenue", value=ui.fmt_money(o["fc_rev"]), d=delta(o["fc_rev"], o["budget_rev"]), label_cmp="vs budget", accent=TEAL),
        dict(label="FY26 budget op. profit", value=ui.fmt_money(o["budget_op"]), label_cmp=None, accent=TEAL),
        dict(label="FY26 forecast op. profit", value=ui.fmt_money(o["fc_op"]), d=delta(o["fc_op"], o["budget_op"]), label_cmp="vs budget", accent=TEAL),
        dict(label="YTD revenue vs budget", value=f"{o['r_rev']:.1%}", label_cmp=None, accent=TEAL, sub="drives the revenue forecast"),
        dict(label="YTD costs vs budget", value=f"{o['r_cost']:.1%}", label_cmp=None, accent=TEAL, sub="drives the cost forecast"),
    ], spacer_after=6)
    c1, c2 = st.columns(2)
    with c1:
        with ui.card("fo1"):
            ui.card_title("Cumulative operating profit", "actual + forecast vs budget")
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=y["month"], y=y["budget_op"].cumsum(), name="Budget", line=dict(color=INK, dash="dot", width=2)))
            act = y[y["kind"] == "Actual"]; fc = y[y["kind"] == "Forecast"]
            cum = y["op_profit"].cumsum()
            fig.add_trace(go.Scatter(x=act["month"], y=cum.loc[act.index], name="Actual", line=dict(color=TEAL, width=3)))
            fig.add_trace(go.Scatter(x=pd.concat([act["month"].iloc[-1:], fc["month"]]), y=pd.concat([cum.loc[act.index[-1:]], cum.loc[fc.index]]), name="Forecast", line=dict(color=TEAL, width=3, dash="dash")))
            fig.update_layout(**ui.base_layout(290, legend=True)); fig.update_xaxes(tickformat="%b %y")
            ui.show(ui.style_axes(fig, "$,.0s"), key="fo_cum")
    with c2:
        with ui.card("fo2"):
            ui.card_title("Monthly operating profit", "the current month is a full-month equivalent")
            fig = go.Figure()
            fig.add_trace(go.Bar(x=y["month"], y=y["op_profit"], marker_color=[TEAL if k == "Actual" else "#9bd3db" for k in y["kind"]], name="Actual / forecast"))
            fig.add_trace(go.Scatter(x=y["month"], y=y["budget_op"], name="Budget", line=dict(color=INK, dash="dot", width=2)))
            fig.update_layout(**ui.base_layout(290, legend=True)); fig.update_xaxes(tickformat="%b %y")
            ui.show(ui.style_axes(fig, "$,.0s"), key="fo_bar")
    with ui.card("fo3"):
        ui.card_title("FY26 bridge: budget to forecast operating profit")
        rev_gap = o["fc_rev"] - o["budget_rev"]; cost_gap = -(o["fc_cost"] - o["budget_cost"])
        fig = go.Figure(go.Waterfall(x=["Budget op. profit", "Revenue vs budget", "Costs vs budget", "Forecast op. profit"], y=[o["budget_op"], rev_gap, cost_gap, 0], measure=["absolute", "relative", "relative", "total"],
                                     increasing=dict(marker=dict(color=GREEN)), decreasing=dict(marker=dict(color=RED)), totals=dict(marker=dict(color=TEAL)), hovertemplate="%{x}: $%{y:,.0f}<extra></extra>"))
        fig.update_layout(**ui.base_layout(240))
        ui.show(ui.style_axes(fig, "$,.0s"), key="fo_wf")
        ui.note("Forecast = year-to-date actuals plus the remaining budget scaled by the year-to-date revenue and cost performance. It assumes today's run-rate persists: no new hires, rate changes or one-offs.")


# ============================================================================ cash
def _cash(M, cur, cmp):
    stk = M["stock"]; fin = M["fin"]; end = cur.end
    cash = stock_at(stk, "cash", end)
    wk = X.cash_forecast(M)
    low = wk.loc[wk["closing"].idxmin()]
    f = X.fin_sum(M, cur)
    burn = f["total_costs"] / cur.days * 30.4
    ui.kpi_row([
        dict(label="Office account balance", value=ui.fmt_money(cash), label_cmp=None, accent=TEAL, sub=f"at {end:%d %b %y}"),
        dict(label="Collections in period (incl. GST)", value=ui.fmt_money(f["collections"]), label_cmp=None, accent=TEAL, sub=f"{f['collections'] / (f['revenue'] * (1 + GST)):.0%} of billed revenue"),
        dict(label="Net cash flow in period", value=ui.fmt_money(f["net_cash"], sign=True), label_cmp=None, accent=TEAL, color=GREEN if f["net_cash"] >= 0 else RED, sub="after costs, GST, BAS and drawings"),
        dict(label="Partner drawings", value=ui.fmt_money(f["drawings"]), label_cmp=None, accent=TEAL, sub=f"{f['drawings'] / f['op_profit']:.0%} of operating profit"),
        dict(label="Cash cover", value=f"{cash / burn:.1f} months", label_cmp=None, accent=TEAL, sub="balance ÷ monthly operating costs"),
        dict(label="13-week low point", value=ui.fmt_money(low["closing"]), label_cmp=None, accent=AMBER if low["closing"] < 150000 else TEAL, sub=f"week of {low['week_start']:%d %b}"),
    ], spacer_after=6)
    c1, c2 = st.columns(2)
    with c1:
        with ui.card("fc1"):
            ui.card_title("Office account: month-end balance", "24 months")
            s = stk["cash"].dropna().iloc[-24:]
            fig = go.Figure(go.Scatter(x=stk["date"].loc[s.index], y=s.values, mode="lines+markers", line=dict(color=TEAL, width=2.5), fill="tozeroy", fillcolor="rgba(10,132,150,.10)", hovertemplate="%{x|%d %b %y}: $%{y:,.0f}<extra></extra>"))
            fig.add_hline(y=60000, line_dash="dot", line_color=RED, annotation_text="$60K minimum operating balance", annotation_font_size=9)
            fig.update_layout(**ui.base_layout(260))
            ui.show(ui.style_axes(fig, "$,.0s"), key="fc_bal")
    with c2:
        with ui.card("fc2"):
            ui.card_title("Cash in vs cash out", "monthly, incl. GST")
            m = fin.loc[:AS_OF.replace(day=1), ["cash_in", "cash_out"]].dropna().iloc[-12:]
            fig = go.Figure()
            fig.add_trace(go.Bar(x=m.index, y=m["cash_in"], name="Collections", marker_color=TEAL))
            fig.add_trace(go.Bar(x=m.index, y=-m["cash_out"], name="Costs, GST, BAS & drawings", marker_color="#94a3b8"))
            fig.update_layout(**ui.base_layout(260, legend=True), barmode="relative"); fig.update_xaxes(tickformat="%b %y")
            ui.show(ui.style_axes(fig, "$,.0s"), key="fc_flow")
    with ui.card("fc3"):
        ui.card_title("13-week cash forecast", "open invoices by client payment habit + run-rate billing, payroll, rent, BAS and drawings")
        fig = go.Figure()
        fig.add_trace(go.Bar(x=wk["week_start"], y=wk["in_open"], name="Open invoices", marker_color=TEAL))
        fig.add_trace(go.Bar(x=wk["week_start"], y=wk["in_new"], name="Future billing", marker_color="#86c9d1"))
        for col, nm, colr in [("out_payroll", "Payroll", "#64748b"), ("out_drawings", "Drawings", VIOLET), ("out_bas", "BAS (GST)", AMBER), ("out_rent", "Rent", "#94a3b8"), ("out_opex", "Overheads", "#cbd5e1"), ("out_disb", "Suppliers", "#e2e8f0")]:
            fig.add_trace(go.Bar(x=wk["week_start"], y=wk[col], name=nm, marker_color=colr))
        fig.add_trace(go.Scatter(x=wk["week_start"], y=wk["closing"], name="Closing balance", line=dict(color=INK, width=3), mode="lines+markers"))
        fig.add_hline(y=60000, line_dash="dot", line_color=RED)
        fig.update_layout(**ui.base_layout(320, legend=True), barmode="relative"); fig.update_xaxes(tickformat="%d %b")
        ui.show(ui.style_axes(fig, "$,.0s"), key="fc_13w")
        tbl = wk[["week_start", "opening", "in_open", "in_new", "out_payroll", "out_drawings", "out_bas", "net", "closing"]].copy()
        tbl[tbl.columns[1:]] = tbl[tbl.columns[1:]].round(0)
        st.dataframe(tbl.rename(columns={"week_start": "Week from", "opening": "Opening", "in_open": "Open invoices", "in_new": "Future billing", "out_payroll": "Payroll", "out_drawings": "Drawings", "out_bas": "BAS", "net": "Net", "closing": "Closing"}),
                     hide_index=True, width="stretch", height=250, column_config={"Week from": st.column_config.DateColumn("Week from", format="DD MMM"), **{k: ui.money_col(k) for k in ["Opening", "Open invoices", "Future billing", "Payroll", "Drawings", "BAS", "Net", "Closing"]}})
        ui.note("The forecast is a management estimate: expected payment dates use each client's own average days-to-pay, and overdue invoices are assumed to clear within three weeks.")
        ui.note("Cash cover looks short because partners draw most of each month's profit; work in progress and receivables (see Billing & WIP) are the real buffer, not the bank balance.")


# ============================================================================ billing
def _billing(M, cur, cmp):
    end = cur.end; stk = M["stock"]; inv = M["inv"]
    ar = X.ar_total(M, end); wip = stock_at(stk, "wip", end)
    dso, lock = X.dso(M, end), X.lockup_days(M, end)
    cmp_ok = cmp is not None and has_data(cmp)
    dso_p, lock_p = (X.dso(M, cmp.end), X.lockup_days(M, cmp.end)) if cmp_ok else (None, None)
    lab = ui.cmp_label(cmp)
    issued = _in(inv, cur, "issue"); coll = inv[(inv["paid"] >= cur.start) & (inv["paid"] <= cur.end)]
    ui.kpi_row([
        dict(label="Invoiced in period (ex GST)", value=ui.fmt_money(issued["ex_gst"].sum()), label_cmp=None, accent=TEAL, sub=f"{len(issued)} invoices"),
        dict(label="Collected in period (incl. GST)", value=ui.fmt_money(coll["total"].sum()), label_cmp=None, accent=TEAL, sub=f"{len(coll)} payments"),
        dict(label="Work in progress", value=ui.fmt_money(wip), d=delta(wip, stock_at(stk, "wip", cmp.end)) if cmp_ok else None, up_good=False, label_cmp=lab, accent=TEAL, spark=X.spark(M, "wip", end, 12, "stock")),
        dict(label="Receivables (incl. GST)", value=ui.fmt_money(ar), d=delta(ar, X.ar_total(M, cmp.end)) if cmp_ok else None, up_good=False, label_cmp=lab, accent=TEAL, spark=X.spark(M, "ar", end, 12, "stock")),
        dict(label="DSO", value=f"{dso:.0f} days", d=delta(dso, dso_p) if cmp_ok else None, up_good=False, label_cmp=lab, accent=TEAL),
        dict(label="Lock-up (WIP + debtors)", value=f"{lock:.0f} days", d=delta(lock, lock_p) if cmp_ok else None, up_good=False, label_cmp=lab, accent=TEAL, sub="days of revenue tied up"),
    ], spacer_after=6)
    ui.sim_cta(f"DSO is <b>{dso:.0f} days</b> and lock-up is {lock:.0f} days. See what collecting a week faster is worth in cash.", preset="Collect 7 days faster", key="bill")
    ui.spacer(4)
    c1, c2 = st.columns(2)
    with c1:
        with ui.card("fb1"):
            ui.card_title("WIP and receivables", "month-end, ex GST")
            w = stk[["wip", "ar_ex"]].dropna().iloc[-18:]
            fig = go.Figure()
            fig.add_trace(go.Bar(x=stk["date"].loc[w.index], y=w["wip"], name="WIP", marker_color=INDIGO))
            fig.add_trace(go.Bar(x=stk["date"].loc[w.index], y=w["ar_ex"], name="Receivables", marker_color=AMBER))
            fig.update_layout(**ui.base_layout(260, legend=True), barmode="stack"); fig.update_xaxes(tickformat="%b %y")
            ui.show(ui.style_axes(fig, "$,.0s"), key="fb_wip")
    with c2:
        with ui.card("fb2"):
            ui.card_title("Lock-up days trend", "how long revenue takes to become cash")
            pts = []
            for m in pd.date_range(end.replace(day=1) - pd.DateOffset(months=11), end.replace(day=1), freq="MS"):
                d = min(m + pd.offsets.MonthEnd(0), AS_OF)
                if d >= pd.Timestamp("2023-10-01"):
                    pts.append((d, X.dso(M, d), X.lockup_days(M, d)))
            t = pd.DataFrame(pts, columns=["d", "dso", "lock"])
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=t["d"], y=t["lock"], name="Lock-up", line=dict(color=INDIGO, width=2.5)))
            fig.add_trace(go.Scatter(x=t["d"], y=t["dso"], name="DSO", line=dict(color=AMBER, width=2.5)))
            fig.update_layout(**ui.base_layout(260, legend=True)); fig.update_xaxes(tickformat="%b %y")
            ui.show(ui.style_axes(fig, ",.0f"), key="fb_lock")
    with ui.card("fb3"):
        ui.card_title("Invoice register")
        f1, f2, f3 = st.columns([1.2, 1.4, 1.6])
        stat = f1.selectbox("Status", ["All", "Paid", "Outstanding", "Overdue"], key="fb_status")
        areas = f2.multiselect("Practice area", AREAS, key="fb_area")
        q = f3.text_input("Search client or invoice", key="fb_q")
        d = issued.copy()
        d["status"] = np.where(d["paid"].notna() & (d["paid"] <= end), "Paid", np.where(d["due"] < end, "Overdue", "Outstanding"))
        if stat != "All": d = d[d["status"] == stat]
        if areas: d = d[d["area"].isin(areas)]
        if q: d = d[d["client"].str.contains(q, case=False) | d["invoice"].str.contains(q, case=False)]
        d = d.sort_values("issue", ascending=False)
        c1, c2 = st.columns([6, 1])
        c1.markdown(f'<div class="tbl-note">{len(d)} invoices issued in the period · {ui.fmt_money(d["total"].sum())} incl. GST</div>', unsafe_allow_html=True)
        with c2: ui.csv_button(d, "invoices", "inv")
        out = d[["invoice", "client", "area", "attorney", "issue", "due", "paid", "ex_gst", "gst", "total", "status"]].copy()
        out[["ex_gst", "gst", "total"]] = out[["ex_gst", "gst", "total"]].round(0)
        st.dataframe(out, hide_index=True, width="stretch", height=340, column_config={
            "invoice": "Invoice", "client": "Client", "area": "Practice", "attorney": "Lead", "issue": st.column_config.DateColumn("Issued", format="DD MMM YY"), "due": st.column_config.DateColumn("Due", format="DD MMM YY"),
            "paid": st.column_config.DateColumn("Paid", format="DD MMM YY"), "ex_gst": ui.money_col("Ex GST"), "gst": ui.money_col("GST"), "total": ui.money_col("Total"), "status": "Status"})


# ============================================================================= trust
def _trust(M, cur, cmp):
    end = cur.end; tb = M["trust"]; tx = M["trust_txns"]
    bal = tb.loc[:end].iloc[-1] if len(tb.loc[:end]) else tb.iloc[0]
    d = _in(tx, cur)
    dep = d.loc[d["amount"] > 0, "amount"].sum(); dis = -d.loc[d["amount"] < 0, "amount"].sum()
    cm = M["commbiz"][1]
    ui.kpi_row([
        dict(label="Trust balance", value=ui.fmt_money(bal.sum()), label_cmp=None, accent=TEAL, sub=f"{int((bal > 0).sum())} client ledgers · {tb.loc[:end].index[-1]:%b %y} month-end"),
        dict(label="Deposits in period", value=ui.fmt_money(dep), label_cmp=None, accent=GREEN, sub=f"{int((d['amount'] > 0).sum())} receipts"),
        dict(label="Disbursements in period", value=ui.fmt_money(dis), label_cmp=None, accent=AMBER, sub=f"{int((d['amount'] < 0).sum())} payments"),
        dict(label="Lowest client ledger", value=ui.fmt_money(bal.min()), label_cmp=None, accent=TEAL, color=RED if bal.min() < 0 else INK, sub=("no negative ledgers" if bal.min() >= 0 else "NEGATIVE: investigate now")),
        dict(label="Bank feed (CommBiz)", value=f"{cm['matched']} matched", label_cmp=None, accent=GREEN if cm["unmatched"] == 0 else AMBER, sub=f"{cm['unmatched']} unmatched · synced {cm['last_sync']}"),
    ], spacer_after=6)
    c1, c2 = st.columns([1.4, 1])
    with c1:
        with ui.card("ft1"):
            ui.card_title("Trust balances by client", "month-end, 18 months")
            t = tb.iloc[-18:]
            fig = go.Figure([go.Bar(x=t.index, y=t[c], name=c) for c in tb.columns])
            fig.update_layout(**ui.base_layout(280, legend=True), barmode="stack"); fig.update_xaxes(tickformat="%b %y")
            ui.show(ui.style_axes(fig, "$,.0s"), key="ft_bal")
    with c2:
        with ui.card("ft2"):
            ui.card_title("Balance by client", f"{tb.loc[:end].index[-1]:%b %y}")
            b = bal.sort_values()
            fig = go.Figure(go.Bar(y=b.index, x=b.values, orientation="h", marker_color=TEAL, hovertemplate="%{y}: $%{x:,.0f}<extra></extra>"))
            fig.update_layout(**ui.base_layout(280))
            ui.show(ui.style_axes(fig, "$,.0s"), key="ft_by")
    with ui.card("ft3"):
        ui.card_title("Trust ledger", "receipts and payments in the period")
        ledger = d.sort_values("date", ascending=False).copy(); ledger["amount"] = ledger["amount"].round(0)
        c1, c2 = st.columns([6, 1])
        c1.markdown(f'<div class="tbl-note">{len(ledger)} transactions</div>', unsafe_allow_html=True)
        with c2: ui.csv_button(ledger, "trust_ledger", "trust")
        st.dataframe(ledger, hide_index=True, width="stretch", height=280, column_config={"date": st.column_config.DateColumn("Date", format="DD MMM YY"), "client": "Client", "type": "Type", "amount": ui.money_col("Amount")})
        ui.note("Trust money belongs to clients: it never appears in the firm's revenue or the office cash balance. Each client ledger must reconcile to the bank every month and must never go negative.")


# ============================================================================ costs
def _costs(M, cur, cmp):
    sub = st.tabs(["InfoTrack", "Council searches", "Card expenses", "RapidPay", "Referral commissions"])
    with sub[0]:
        d = _in(M["infotrack"], cur)
        c = st.columns(4)
        c[0].metric("Searches", f"{len(d)}"); c[1].metric("Spend", ui.fmt_money(d["cost"].sum())); c[2].metric("Average cost", f"${d['cost'].mean():,.0f}" if len(d) else "—"); c[3].metric("Pending", f"{int((d['status'] == 'Pending').sum())}")
        a, b = st.columns(2)
        with a:
            with ui.card("fs1"):
                ui.card_title("Spend by search type")
                g = d.groupby("search_type")["cost"].sum().sort_values()
                fig = go.Figure(go.Bar(y=g.index, x=g.values, orientation="h", marker_color=TEAL)); fig.update_layout(**ui.base_layout(240))
                ui.show(ui.style_axes(fig, "$,.0f"), key="fs_it")
        with b:
            with ui.card("fs2"):
                ui.card_title("Monthly spend", "last 12 months")
                g = M["infotrack"].assign(m=M["infotrack"]["date"].dt.to_period("M").dt.to_timestamp()).groupby("m")["cost"].sum().iloc[-12:]
                fig = go.Figure(go.Bar(x=g.index, y=g.values, marker_color=TEAL)); fig.update_layout(**ui.base_layout(240)); fig.update_xaxes(tickformat="%b %y")
                ui.show(ui.style_axes(fig, "$,.0f"), key="fs_itm")
        _table(d, "it", {"date": st.column_config.DateColumn("Date", format="DD MMM YY"), "cost": ui.money_col("Cost")}, ["date", "matter", "search_type", "branch", "cost", "status"])
    with sub[1]:
        d = _in(M["council"], cur)
        c = st.columns(4)
        c[0].metric("Orders", f"{len(d)}"); c[1].metric("Spend", ui.fmt_money(d["cost"].sum())); c[2].metric("Average cost", f"${d['cost'].mean():,.0f}" if len(d) else "—"); c[3].metric("Pending", f"{int((d['status'] == 'Pending').sum())}")
        with ui.card("fs3"):
            ui.card_title("Spend by council")
            g = d.groupby("council")["cost"].sum().sort_values()
            fig = go.Figure(go.Bar(y=g.index, x=g.values, orientation="h", marker_color=INDIGO)); fig.update_layout(**ui.base_layout(200))
            ui.show(ui.style_axes(fig, "$,.0f"), key="fs_co")
        _table(d, "co", {"date": st.column_config.DateColumn("Date", format="DD MMM YY"), "cost": ui.money_col("Cost")}, ["date", "matter", "council", "search_type", "cost", "status"])
    with sub[2]:
        d = _in(M["cards"], cur)
        c = st.columns(4)
        c[0].metric("Transactions", f"{len(d)}"); c[1].metric("Spend", ui.fmt_money(d["amount"].sum())); c[2].metric("Largest", ui.fmt_money(d["amount"].max()) if len(d) else "—"); c[3].metric("Amex / Visa", f"{ui.fmt_money(d.loc[d['card'] == 'Amex', 'amount'].sum())} / {ui.fmt_money(d.loc[d['card'] == 'Visa', 'amount'].sum())}")
        a, b = st.columns(2)
        with a:
            with ui.card("fs4"):
                ui.card_title("By category")
                g = d.groupby("category")["amount"].sum().sort_values(ascending=False)
                ui.donut(list(g.index), list(g.values), [TEAL, BLUE, INDIGO, VIOLET, AMBER, "#94a3b8", "#cbd5e1"][:len(g)], h=200, center=f"<b style='font-size:15px'>{ui.fmt_money(g.sum())}</b>", key="fs_cat")
        with b:
            with ui.card("fs5"):
                ui.card_title("By branch")
                g = d.groupby("branch")["amount"].sum().sort_values()
                fig = go.Figure(go.Bar(y=g.index, x=g.values, orientation="h", marker_color=TEAL)); fig.update_layout(**ui.base_layout(230))
                ui.show(ui.style_axes(fig, "$,.0f"), key="fs_br")
        _table(d, "cd", {"date": st.column_config.DateColumn("Date", format="DD MMM YY"), "amount": ui.money_col("Amount")}, ["date", "card", "merchant", "category", "branch", "amount"])
    with sub[3]:
        d = _in(M["rapidpay"], cur)
        vol, fee = d["amount"].sum(), d["fee"].sum()
        c = st.columns(4)
        c[0].metric("Card payments", f"{len(d)}"); c[1].metric("Volume", ui.fmt_money(vol)); c[2].metric("Merchant fees", ui.fmt_money(fee)); c[3].metric("Effective fee rate", f"{fee / vol:.2%}" if vol else "—")
        with ui.card("fs6"):
            ui.card_title("Volume by card type")
            g = d.groupby("method")["amount"].sum().sort_values()
            fig = go.Figure(go.Bar(y=g.index, x=g.values, orientation="h", marker_color=VIOLET)); fig.update_layout(**ui.base_layout(200))
            ui.show(ui.style_axes(fig, "$,.0f"), key="fs_rp")
        _table(d, "rp", {"date": st.column_config.DateColumn("Date", format="DD MMM YY"), "amount": ui.money_col("Amount"), "fee": st.column_config.NumberColumn("Fee", format="dollar")}, ["date", "client", "method", "amount", "fee"])
        ui.note("Merchant fees are 1.75% of card volume. Encouraging EFT/BPAY payment on large invoices is the cheapest way to cut this cost.")
    with sub[4]:
        cm = M["commissions"].copy()
        c = st.columns(3)
        c[0].metric("Total commissions", ui.fmt_money(cm["amount"].sum())); c[1].metric("Payable", ui.fmt_money(cm.loc[cm["status"] == "Payable", "amount"].sum())); c[2].metric("Paid", ui.fmt_money(cm.loc[cm["status"] == "Paid", "amount"].sum()))
        with ui.card("fs7"):
            ui.card_title("Referral commissions", "external referrers and internal originators")
            st.dataframe(cm.rename(columns={"matter": "Matter", "referrer": "Referrer", "rate_pct": "Rate %", "amount": "Amount", "status": "Status"}), hide_index=True, width="stretch",
                         column_config={"Amount": ui.money_col("Amount"), "Rate %": st.column_config.NumberColumn("Rate %", format="%d%%")})


def _table(d, key, cfg, cols):
    with ui.card(f"fst_{key}"):
        c1, c2 = st.columns([6, 1])
        c1.markdown(f'<div class="tbl-note">{len(d)} rows in the period</div>', unsafe_allow_html=True)
        with c2: ui.csv_button(d, f"{key}_detail", f"csv_{key}")
        out = d[cols].copy()
        for c in out.columns:
            if out[c].dtype.kind == "f":
                out[c] = out[c].round(2 if c == "fee" else 0)
        st.dataframe(out, hide_index=True, width="stretch", height=260, column_config=cfg)
