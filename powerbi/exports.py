"""Analysis tables the Power BI report reads next to the warehouse (data/powerbi/*.csv).

The warehouse (data/warehouse) holds the raw facts and dimensions; Power BI measures (DAX) aggregate those directly.
This module adds the tables whose logic lives in Python and would be awkward or risky to re-implement in DAX:
reporting periods and their month weights, balances at a period end, the decision tables (where to hire, departments,
marketing), the 13-week cash forecast, the FY outlook, the platform evaluation and the Simulator's expected results
(used by the report's Check page). Deterministic: the same seed gives the same files, so CI can diff them.

    python -m powerbi.exports          # -> data/powerbi/*.csv
"""
from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
import pandas as pd

from core import metrics as X, platforms as P, simulate as S
from core.model import build_model
from core.period import _shift, month_weights, presets, stock_at
from core.ref import AS_OF, BRANCHES, MARKET_WAGE_GROWTH, START
from core.simulate import MIN_CASH

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "powerbi"
DEFAULT_PERIOD = "This quarter (QTD)"


def _fmt(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return ""
    if isinstance(v, (bool, np.bool_)):
        return "1" if v else "0"
    if isinstance(v, (pd.Timestamp,)):
        return v.strftime("%Y-%m-%d")
    if isinstance(v, (float, np.floating)):
        v = float(v)
        return str(int(v)) if v == int(v) and abs(v) < 1e15 else f"{v:.6f}".rstrip("0").rstrip(".")
    if isinstance(v, (np.integer,)):
        return str(int(v))
    return str(v)


def write(name, rows, cols, out=OUT):
    out.mkdir(parents=True, exist_ok=True)
    p = out / f"{name}.csv"
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(cols)
        for r in rows:
            w.writerow([_fmt(r.get(c) if isinstance(r, dict) else r[i]) for i, c in enumerate(cols)])
    return p


def mkey(ts):
    return int(pd.Timestamp(ts).strftime("%Y%m%d"))


# ------------------------------------------------------------------------------------------------------ periods ---
def periods():
    """Every reporting period of the app with its comparison window (prior period)."""
    out = []
    for i, (key, (cur, shift)) in enumerate(presets().items()):
        cmp = _shift(cur, -shift, "prior period")
        out.append(dict(key=key, cur=cur, cmp=cmp if cmp.start >= START else None, order=i + 1))
    return out


def export_periods(M, out):
    frac = pd.Series(M["frac"], index=M["months"])
    rows, wrows, srows = [], [], []
    stk = M["stock"]
    mt = M["matters"]
    for p in periods():
        cur, cmp = p["cur"], p["cmp"]
        rows.append(dict(Period=cur.label, Choice=p["key"], Order=p["order"], Start=cur.start, End=cur.end,
                         PriorStart=cmp.start if cmp else None, PriorEnd=cmp.end if cmp else None, Days=cur.days,
                         IsDefault=p["key"] == DEFAULT_PERIOD, EndKey=mkey(cur.end), MonthEndKey=mkey(cur.end.replace(day=1))))
        for role, per in (("Current", cur), ("Prior", cmp)):
            if per is None:
                continue
            w = month_weights(per, M["months"])
            for m, wt in w.items():
                # warehouse facts already hold the elapsed part of the as-of month, so divide by the elapsed fraction
                wrows.append(dict(Period=cur.label, Role=role, MonthKey=mkey(m), Weight=wt / float(frac[m])))
            d = per.end
            act = mt[(mt["opened"] <= d) & (mt["closed"].isna() | (mt["closed"] > d))]
            srows.append(dict(Period=cur.label, Role=role, ActiveMatters=float(stock_at(stk, "matters_active", d)),
                              ActiveMattersCount=len(act), Cash=stock_at(stk, "cash", d), WIP=stock_at(stk, "wip", d),
                              Receivables=X.ar_total(M, d), Trust=stock_at(stk, "trust", d), DSO=X.dso(M, d), Lockup=X.lockup_days(M, d)))
    write("period", rows, list(rows[0]), out)
    write("period_month", wrows, list(wrows[0]), out)
    write("period_balance", srows, list(srows[0]), out)
    return rows


def export_monthly_extra(M, out):
    """Monthly columns of the model that the warehouse P&L does not carry (cash, intake, searches), × elapsed fraction."""
    fin, stk, frac = M["fin"], M["stock"], M["frac"]
    rows = []
    for t, m in enumerate(M["months"][:M["T_act"]]):
        r = fin.loc[m]
        k = float(frac[t])
        rows.append(dict(MonthKey=mkey(m), Fraction=k, CollectionsExGST=r["collections_ex"] * k, CashIn=r["cash_in"] * k, CashOut=r["cash_out"] * k,
                         NetCash=r["net_cash"] * k, GSTNet=r["gst_net"] * k, Drawings=r["drawings"] * k, MattersOpened=r["matters_opened"] * k,
                         MattersClosed=r["matters_closed"] * k, Searches=r["searches"] * k, CouncilSearches=r["council_n"] * k,
                         ActiveMatters=float(stk.loc[m, "matters_active"]) if "matters_active" in stk.columns else None,
                         CashBalance=float(stk.loc[m, "cash"])))
    write("monthly_extra", rows, list(rows[0]), out)


# ----------------------------------------------------------------------------------------------- decision tables ---
def export_decision_tables(M, out):
    pa = X.practice_area_table(M).reset_index()
    write("where_to_hire", pa.to_dict("records"), list(pa.columns), out)
    dt = X.department_table(M)
    dt["order"] = range(1, len(dt) + 1)
    write("departments", dt.to_dict("records"), list(dt.columns), out)
    mk = X.marketing_table(M)
    fpm = mk.attrs["fee_per_matter"]
    mk = mk.reset_index()
    mk["fee_per_matter_firm"] = fpm
    write("marketing", mk.to_dict("records"), list(mk.columns), out)
    return pa, dt, mk


def _money(v):
    a = abs(v)
    if a >= 1_000_000:
        return f"${a / 1_000_000:.2f}M"
    if a >= 10_000:
        return f"${a / 1_000:.0f}K"
    if a >= 1_000:
        return f"${a / 1_000:.1f}K"
    return f"${a:,.0f}"


def _decisions(M, cur, top):
    """The Principal's open questions for a period, each with today's evidence and where to look in the report."""
    a, b = X.fin_sum(M, cur), X.plan_sum(M, cur)
    gap = a["op_profit"] - b["op_profit"]
    pa = X.practice_area_table(M)
    dt = X.department_table(M)
    over = dt[dt["status"] == "Over-staffed"].sort_values("gap", ascending=False)
    mk = X.marketing_table(M)
    best, worst = mk["cost_per_matter"].idxmin(), mk["cost_per_matter"].idxmax()
    items = [
        ("$", "#b91c1c" if gap < 0 else "#047857", "", f"Profit {_money(gap)} {'behind' if gap < 0 else 'ahead of'} budget",
         f"{cur.label}: rates, utilisation, pay or overheads? Test each in the Simulator."),
        ("H", "#0a8496", "", f"Hire next in {pa.index[0]}",
         f"Lawyers at {pa.iloc[0]['util']:.0%}, new matters {pa.iloc[0]['matters_growth']:+.0%}. People → Hiring & departments."),
    ]
    if len(over):
        o = over.iloc[0]
        items.append(("P", "#b45309", "", f"{o['branch']} {o['department'].lower()}: {o['headcount']} staff, {o['needed']:.1f} needed",
                      f"{_money(o['cost_of_gap'])} a year over the workload. People → Hiring & departments."))
    items.append(("M", "#1d4ed8", "", f"Marketing: {best} beats {worst}",
                  f"{_money(mk.loc[best, 'cost_per_matter'])} vs {_money(mk.loc[worst, 'cost_per_matter'])} per new matter. Clients → Marketing."))
    return items[:4]


def export_decisions(M, out, top):
    rows = []
    for p in periods():
        for i, (ic, fg, bg, t, d) in enumerate(_decisions(M, p["cur"], top)):
            rows.append(dict(Period=p["cur"].label, Order=i + 1, Icon=ic, Colour=fg, Title=t, Detail=d))
    write("decisions", rows, list(rows[0]), out)


def export_period_tables(M, out):
    """Tables whose rules depend on a point in time (receivables, clients, branches) for every period."""
    crow, arow, brow = [], [], []
    labels = ["Not yet due", "1–30 days", "31–60 days", "61–90 days", "90+ days"]
    for p in periods():
        cur, cmp = p["cur"], p["cmp"]
        ct = X.client_table(M, cur, cmp)
        for r in ct.to_dict("records"):
            crow.append(dict(Period=cur.label, **r))
        _, ag = X.ar_ageing(M, cur.end)
        for i, b in enumerate(labels):
            arow.append(dict(Period=cur.label, Bucket=b, Order=i + 1, Amount=float(ag[b])))
        bt = X.branch_table(M, cur).reset_index()
        for r in bt.to_dict("records"):
            brow.append(dict(Period=cur.label, **r))
    write("clients", crow, list(crow[0]), out)
    write("ar_ageing", arow, list(arow[0]), out)
    write("branches", brow, list(brow[0]), out)


def export_cash_and_outlook(M, out):
    cf = X.cash_forecast(M)
    cf["week"] = range(1, len(cf) + 1)
    cf["min_cash"] = MIN_CASH
    write("cash_forecast", cf.to_dict("records"), list(cf.columns), out)
    o = X.fy_outlook(M)
    path = o["path"]
    path["MonthKey"] = path["month"].map(mkey)
    write("fy_outlook", path.to_dict("records"), list(path.columns), out)
    summ = dict(budget_rev=o["budget_rev"], budget_cost=o["budget_cost"], budget_op=o["budget_op"], fc_rev=o["fc_rev"], fc_cost=o["fc_cost"],
                fc_op=o["fc_op"], r_rev=o["r_rev"], r_cost=o["r_cost"], ytd_rev=o["ytd_actual"]["revenue"], ytd_budget_rev=o["ytd_budget"]["revenue"],
                ytd_op=o["ytd_actual"]["op_profit"], ytd_budget_op=o["ytd_budget"]["op_profit"])
    write("fy_summary", [summ], list(summ), out)


def export_detail_tables(M, out):
    dl = M["deadlines"].copy()
    dl["days_from_as_of"] = (dl["date"] - AS_OF).dt.days
    write("deadlines", dl.to_dict("records"), list(dl.columns), out)
    for k in ("cards", "rapidpay", "commissions"):
        df = M[k]
        write(k, df.to_dict("records"), list(df.columns), out)


# ------------------------------------------------------------------------------------------------------ platforms ---
def export_platforms(M, out):
    inp = P.base_inputs(M)
    rk = P.ranking(inp).set_index("name")
    base_score = P.weighted_score(P.BASELINE)
    rows, cfr, sc, rr, gt, grid = [], [], [], [], [], []
    bvals, vmults = [0.25, 0.5, 0.75, 1.0], [0.8, 1.0, 1.2]
    for n in P.NAMES:
        ev, df = P.evaluate(n, inp)
        v, kind = P.verdict(n, ev, P.weighted_score(n), base_score)
        pl = P.PLATFORMS[n]
        rows.append(dict(Platform=n, Short=pl["short"], Colour=pl["color"], Tagline=pl["tagline"], Score=rk.loc[n, "score"], NPV=ev["npv"],
                         Payback=ev["payback"], IRR=ev["irr"], RunRate=ev["run_rate"], RunRateDelta=ev["run_rate_delta"], TCO3y=ev["tco_alt"],
                         TCODelta=ev["tco_delta"], OneOff=ev["one_off"], Benefit3y=ev["benefit_3y"], Year1Net=ev["year1_net"], GoLive=ev["go_live"],
                         CostPerFeeEarner=ev["cost_per_fee_earner"], CostPerSearch=ev["cost_per_search"], Decision=rk.loc[n, "decision"],
                         Rank=rk.loc[n, "rank"], Verdict=v, Subscription=pl["sub"], SearchFee=pl["fee"], Migration=pl["migration"],
                         ImplWeeks=pl["impl_weeks"], Uplift=pl["uplift"], IsCurrent=n == P.BASELINE))
        for r in df.to_dict("records"):
            cfr.append(dict(Platform=n, Month=int(r["t"]) + 1, Current=r["cur"], Alternative=r["alt"], OneOff=r["one_off"], Benefit=r["benefit"],
                            Net=r["net"], Cumulative=r["cum"], PV=r["pv"]))
        for c in P.CRITERIA:
            sc.append(dict(Platform=n, Criterion=c, Score=pl["scores"][c], Weight=P.DEFAULT_WEIGHTS[c]))
        for r in P.risk_register(n).to_dict("records"):
            rr.append(dict(Platform=n, **r))
        for i, (ph, s, e) in enumerate(P.gantt(n)):
            gt.append(dict(Platform=n, Order=i + 1, Phase=ph, StartWeek=s, EndWeek=e, Weeks=e - s))
        z = P.npv_grid(n, inp, bvals, vmults)
        for i, vm in enumerate(vmults):
            for j, b in enumerate(bvals):
                grid.append(dict(Platform=n, Volume=f"{vm:.0%} of today's searches", VolumeOrder=i + 1, Realisation=f"{b:.0%}", RealisationOrder=j + 1, NPV=z[i, j]))
    write("platforms", rows, list(rows[0]), out)
    write("platform_cashflow", cfr, list(cfr[0]), out)
    write("platform_scores", sc, list(sc[0]), out)
    write("platform_risks", rr, list(rr[0]), out)
    write("platform_gantt", gt, list(gt[0]), out)
    write("platform_npv_grid", grid, list(grid[0]), out)
    return rk.sort_values("rank").iloc[0]


# ------------------------------------------------------------------------------------------- Simulator check values ---
CHECK_METRICS = ["op1", "rev1", "cost1", "one_off", "margin1", "util1", "low1"]


def sim_expected(M):
    """What core.simulate says for each preset: the Check page compares the DAX measures with these numbers."""
    p, f = S.base_actuals(M)
    ctx = S.context(M)
    bt = S.budget_targets(M)
    low0 = float(X.cash_forecast(M)["closing"].min())
    rows = []
    for name in ["Custom"] + list(S.PRESETS):
        s = S.DEFAULTS if name == "Custom" else S.preset_state(name)
        r = S.project(f, s, ctx=ctx)
        vals = dict(op1=r["op1"], rev1=r["rev1"], cost1=r["cost1"], one_off=r["one_off"], margin1=S.margin(r), util1=r["util1"], low1=low0 + r["cash_effect"])
        for m in CHECK_METRICS:
            rows.append(dict(Preset=name, Metric=m, Expected=vals[m]))
        dr = S.delivery_range(f, s, ctx=ctx)
        rows.append(dict(Preset=name, Metric="op1_half_delivered", Expected=float(dr["op"].iloc[2])))
        gs = S.goal_seek(f, s, target_op=bt["op"], ctx=ctx).set_index("lever")
        for lv in ("sim_rate", "sim_util", "sim_infl"):
            row = gs.loc[lv]
            if row["required"] is None or pd.isna(row["required"]):
                continue
            step = S.BOUNDS[lv][2]
            x = float(row["required"])
            rounded = float(np.floor(x / step + 1e-9) * step) if lv == "sim_infl" else float(np.ceil(x / step - 1e-9) * step)
            rows.append(dict(Preset=name, Metric=f"goal_{lv[4:]}", Expected=rounded))
        if s["sim_pay_fe"] or s["sim_pay_support"]:
            rows.append(dict(Preset=name, Metric="rate_to_fund", Expected=S.rate_to_fund(f, s, ctx)))
        if s["sim_branch"]:
            rows.append(dict(Preset=name, Metric="branch_payback", Expected=r["branch_payback"]))
        if s["sim_new_area"]:
            rows.append(dict(Preset=name, Metric="area_payback", Expected=r["area_payback"]))
    for test, v in S.lever_ranking(f, ctx=ctx):
        rows.append(dict(Preset="Custom", Metric="rank: " + test, Expected=v))
    return rows


def answers(M):
    """The Principal's six questions, each answered from the engine (Overview page). Nothing here is typed in by hand."""
    from core import platforms as PL
    from core.ref import NEW_AREAS
    p, f = S.base_actuals(M)
    ctx = S.context(M)
    base = S.project(f, S.DEFAULTS, ctx=ctx)
    low0 = float(X.cash_forecast(M)["closing"].min())
    run = lambda **kw: S.project(f, {**S.DEFAULTS, **kw}, ctx=ctx)
    k = lambda v: _money(v)
    out = []
    # 1 software
    inp = PL.base_inputs(M)
    rk = PL.ranking(inp).sort_values("rank")
    top = rk.iloc[0]
    out.append(("Should we switch software?", f"Yes: {top['name']}",
                f"NPV +{k(top['npv'])} over 3 years, payback {int(top['payback'])} months. Today: {k(PL.run_rate(PL.BASELINE, inp))} a year on LEAP + InfoTrack.",
                "Platform"))
    # 2 branch
    r = r_branch = run(**S.PRESETS["Open a branch"])
    low = low0 + r["cash_effect"]
    verdict = "Not yet: fund it first" if low < MIN_CASH else ("Yes" if r["branch_net_full"] > 0 else "No")
    out.append(("Should we open a branch?", verdict,
                f"{k(r['branch_net_full'])} a year at full speed, fit-out back in {r['branch_payback']} months, but cash dips to {k(low)} (minimum {k(MIN_CASH)}).",
                "Simulator"))
    # 3 hiring
    pa = X.practice_area_table(M)
    hire = S.PRESETS["Hire an associate"]                         # one associate, 60% productive in year one
    gain = lambda a: run(**hire, sim_hire_area=a)["op1"] - base["op1"]
    a_top = pa.index[0]
    a_low = min(pa.index, key=gain)
    out.append(("Where should we hire lawyers?", f"{a_top} first",
                f"Lawyers at {pa.iloc[0]['util']:.0%} utilisation. One associate adds {k(gain(a_top))} in year one, against {k(gain(a_low))} in {a_low}.",
                "People"))
    # 4 support teams
    dt = X.department_table(M)
    over = dt[dt["status"] == "Over-staffed"].sort_values("gap", ascending=False).iloc[0]
    cut = run(**S.PRESETS["Cut 2 support roles"])
    out.append(("Are support teams the right size?", f"{over['branch']} {over['department'].split()[0].lower()}: overstaffed",
                f"{over['headcount']} {over['department'].lower()} staff for {over['needed']:.1f} roles of work. Cutting 2 saves {k(cut['support_saving'])} a year, {k(cut['one_off'])} once (NES).",
                "People"))
    # 5 pay
    pay = run(**S.PRESETS["Pay rise 3%"])
    rtf = S.rate_to_fund(f, {**S.DEFAULTS, **S.PRESETS["Pay rise 3%"]}, ctx)
    out.append(("Should pay go up?", f"3% is affordable with +{rtf:.1f}% rates",
                f"A 3% rise costs {k(pay['pay_cost'])} a year. Market wage growth is {MARKET_WAGE_GROWTH:.1%} (ABS WPI), so less risks losing people.",
                "Simulator"))
    # 6 marketing and new services
    mk = X.marketing_table(M)
    best, worst = mk["cost_per_matter"].idxmin(), mk["cost_per_matter"].idxmax()
    nas = {n: run(sim_new_area=True, sim_new_area_type=n) for n in NEW_AREAS}
    na = max(nas, key=lambda n: nas[n]["area_net_full"])
    out.append(("Where should growth come from?", f"{best}, {na}",
                f"{k(mk.loc[best, 'cost_per_matter'])} per new matter vs {k(mk.loc[worst, 'cost_per_matter'])} on {worst}. {na}: {k(nas[na]['area_net_full'])} a year at full speed.",
                "Clients"))
    rows = [dict(Order=i + 1, Question=q, Answer=a, Evidence=e, Page=pg) for i, (q, a, e, pg) in enumerate(out)]
    # the small chart in each tile (Overview): what proves the answer
    ch = []
    add = lambda o, item, v, hi, unit="$": ch.append(dict(Order=o, Item=item, ItemOrder=len(ch) + 1, Value=float(v), Highlight=int(hi), Unit=unit))
    for _, r in rk.sort_values("npv", ascending=False).iterrows():
        add(1, PL.PLATFORMS[r["name"]]["short"], r["npv"], r["name"] == top["name"])
    add(2, "Profit, year one", r_branch["branch_net"], False)
    add(2, "Profit at full speed", r_branch["branch_net_full"], False)
    add(2, "Cash low point after", low, True)
    add(2, "Minimum cash balance", MIN_CASH, False)
    for a in sorted(pa.index, key=gain, reverse=True):
        add(3, a, gain(a), a == a_top)
    for _, d in dt.sort_values("gap", ascending=False).iterrows():
        add(4, f"{d['branch']} {d['department'].split()[0].lower()}", d["gap"], d is not None and d["branch"] == over["branch"] and d["department"] == over["department"], "roles")
    for pct in (1, 2, 3, 4, 5):
        add(5, f"Pay +{pct}%", run(sim_pay_fe=float(pct), sim_pay_support=float(pct))["pay_cost"], pct == 3)
    for c in mk.sort_values("cost_per_matter").index:
        add(6, c, mk.loc[c, "cost_per_matter"], c == best)
    return rows, ch


def export_all(out=OUT):
    M = build_model()
    export_periods(M, out)
    export_monthly_extra(M, out)
    export_decision_tables(M, out)
    export_period_tables(M, out)
    export_cash_and_outlook(M, out)
    export_detail_tables(M, out)
    top = export_platforms(M, out)
    export_decisions(M, out, top)
    ans, chart = answers(M)
    write("answers", ans, list(ans[0]), out)
    write("answer_chart", chart, list(chart[0]), out)
    rows = sim_expected(M)
    write("sim_expected", rows, ["Preset", "Metric", "Expected"], out)
    write("about", [dict(AsOf=AS_OF, MarketWageGrowth=MARKET_WAGE_GROWTH, MinCash=MIN_CASH)], ["AsOf", "MarketWageGrowth", "MinCash"], out)
    return M


if __name__ == "__main__":
    export_all()
    print(f"wrote {len(list(OUT.glob('*.csv')))} tables to {OUT}")
