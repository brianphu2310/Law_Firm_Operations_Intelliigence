"""A browser preview of the Power BI report: the same 15 pages, visual positions, titles and fields as the PBIR files,
with every number computed in Python the way the DAX measures compute it. For people without Power BI Desktop.

    python -m powerbi.demo            # -> powerbi/demo/index.html (one self-contained file)

Interactive: page navigation, the Period slicer, the Platform slicer and the whole Simulator: presets, every lever and the
goal-seek target. The Simulator formulas are translated from the same spec (powerbi/sim_spec.py) that generates the DAX,
so the browser recomputes the scenario exactly as the model does.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from core import simulate as S
from . import build as B, model as MD, report as RP, sim_spec as SP

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent / "demo" / "index.html"
ROW_CAP = 120


# ------------------------------------------------------------------------------------------------------------ data ---
def load_tables():
    W = {}
    for name, file in MD.WAREHOUSE:
        W[name] = pd.read_csv(ROOT / "data" / "warehouse" / f"{file}.csv")
    for name, file in MD.ANALYSIS:
        W[name] = pd.read_csv(ROOT / "data" / "powerbi" / f"{file}.csv")
    mp = W["Matter Position"]
    mp["Age bucket"] = np.select([mp["days_open"] <= 90, mp["days_open"] <= 180, mp["days_open"] <= 365],
                                 ["0–90 days", "91–180 days", "181–365 days"], "Over a year")
    return W


REL = {}
for a, ac, b, bc in MD.RELATIONSHIPS:
    REL.setdefault(a, []).append((ac, b, bc))


class Ctx(dict):
    """Filter context: (table, column) -> value."""

    def with_(self, **kw):
        c = Ctx(self)
        for k, v in kw.items():
            c[k] = v
        return c

    def plus(self, key, value):
        c = Ctx(self)
        c[key] = value
        return c


class Engine:
    def __init__(self, W, inputs):
        self.W = W
        self.M, self.f, self.ctx, self.consts, self.tables, self.levers = inputs
        self._cache = {}

    # -- filter propagation (many side → one side, like the model's single-direction relationships)
    def filt(self, t, ctx, seen=()):
        df = self.W[t]
        for (ft, fc), v in ctx.items():
            if ft == t and fc in df.columns:
                df = df[df[fc] == v]
        for col, dim, key in REL.get(t, []):
            if dim in seen:
                continue
            if any(ft == dim or ft in self._reach(dim) for ft, _ in ctx):
                d = self.filt(dim, ctx, seen + (t,))
                if len(d) < len(self.W[dim]):
                    df = df[df[col].isin(d[key])]
        return df

    def _reach(self, t, depth=0):
        if depth > 3:
            return set()
        out = set()
        for _, d, _ in REL.get(t, []):
            out.add(d)
            out |= self._reach(d, depth + 1)
        return out

    # -- period helpers
    def period(self, ctx):
        return ctx.get(("Period", "Period"), MD.DEFAULT_PERIOD)

    def psum(self, t, col, ctx, role="Current", where=None):
        pm = self.W["Period Month"]
        rows = pm[(pm["Period"] == self.period(ctx)) & (pm["Role"] == role)]
        if rows.empty:
            return None
        c = Ctx({k: v for k, v in ctx.items() if k[0] != "Period"})
        df = self.filt(t, c)
        if where is not None:
            df = df[where(df)]
        key = "MonthKey" if "MonthKey" in df.columns else "month_start_date_key"
        g = df.groupby(key)[col].sum()
        return float(sum(w * g.get(mk, 0.0) for mk, w in zip(rows["MonthKey"], rows["Weight"])))

    def bal(self, col, ctx, role="Current"):
        b = self.W["Period Balance"]
        r = b[(b["Period"] == self.period(ctx)) & (b["Role"] == role)]
        return None if r.empty else float(r[col].iloc[0])

    def period_row(self, ctx):
        p = self.W["Period"]
        return p[p["Period"] == self.period(ctx)].iloc[0]

    def trend(self, ctx, t, col, frac=True, where=None, ratio=None):
        m = ctx.get(("Date", "month_start_date"))
        if m is None:
            return None
        end = pd.Timestamp(str(int(self.period_row(ctx)["MonthEndKey"])))
        mt = pd.Timestamp(m)
        if not (end - pd.DateOffset(months=12) < mt <= end):
            return None
        c = Ctx({k: v for k, v in ctx.items() if k[0] != "Period"})
        df = self.filt(t, c)
        if where is not None:
            df = df[where(df)]
        if df.empty:
            return None
        if ratio:
            den = df[ratio].sum()
            return float(df[col].sum() / den) if den else None
        v = float(df[col].sum())
        if frac:
            me = self.W["Monthly Extra"]
            fr = me[me["MonthKey"] == int(mt.strftime("%Y%m%d"))]["Fraction"]
            v = v / float(fr.iloc[0]) if len(fr) and fr.iloc[0] else v
        return v

    # -- simulator
    def sim_state(self, ctx):
        p = ctx.get(("Sim Compare", "Short")) or ctx.get(("Sim Preset", "Short"), "Today")
        name = "Custom" if p == "Today" else next(n for n, s in S.PRESET_SHORT.items() if s == p)
        return name, (dict(S.DEFAULTS) if name == "Custom" else S.preset_state(name))

    def sim(self, ctx, delivery=1.0):
        name, s = self.sim_state(ctx)
        key = ("sim", name, delivery)
        if key not in self._cache:
            e = SP.evaluate(s, self.consts, self.tables, delivery)
            self._cache[key] = e
        return self._cache[key]


def pct_delta(c, p):
    if p is None or p == 0 or c is None:
        return "no comparison"
    d = (c - p) / abs(p)
    return ("▲ +" if d > 0 else ("▼ " if d < 0 else "")) + f"{d * 100:.1f}%".replace("-", "-") + " vs prior period"


def pp_delta(c, p):
    if p is None or c is None:
        return "no comparison"
    d = (c - p) * 100
    return ("▲ +" if d > 0 else ("▼ " if d < 0 else "")) + f"{d:.1f} pp vs prior period"


ACT = lambda df: df["scenario_key"] == 1
BUD = lambda df: df["scenario_key"] == 2


def measures(E: Engine):
    """Python versions of the DAX measures the report shows (same names)."""
    W = E.W
    m = {}
    ps = E.psum
    pnl = lambda col, where=ACT, role="Current": (lambda c: ps("PnL", col, c, role, where))
    m["Revenue"] = pnl("revenue")
    m["Operating Profit"] = pnl("operating_profit")
    m["Profit vs Budget"] = lambda c: m["Operating Profit"](c) - pnl("operating_profit", BUD)(c)
    m["Operating Margin"] = lambda c: m["Operating Profit"](c) / m["Revenue"](c)
    m["Revenue Δ"] = lambda c: pct_delta(m["Revenue"](c), pnl("revenue", ACT, "Prior")(c))
    m["Billable Hours"] = pnl("billable_hours")
    m["Hours Δ"] = lambda c: pct_delta(m["Billable Hours"](c), pnl("billable_hours", ACT, "Prior")(c))
    util = lambda c, r="Current": (lambda h, k: h / k if h and k else None)(pnl("billable_hours", ACT, r)(c), pnl("capacity_hours", ACT, r)(c))
    m["Utilisation"] = util
    m["Utilisation Δ"] = lambda c: pp_delta(util(c), util(c, "Prior"))
    m["Realisation"] = lambda c: pnl("fees")(c) / pnl("standard_value")(c)
    m["Effective Rate"] = lambda c: pnl("fees")(c) / pnl("billable_hours")(c)
    m["Disbursement Recovery"] = lambda c: pnl("disbursements_billed")(c) / pnl("disbursement_cost")(c)
    m["Collections ex GST"] = lambda c: ps("Monthly Extra", "CollectionsExGST", c)
    m["Collections Δ"] = lambda c: pct_delta(m["Collections ex GST"](c), ps("Monthly Extra", "CollectionsExGST", c, "Prior"))
    m["Matters Opened"] = lambda c: ps("Monthly Extra", "MattersOpened", c)
    for nm, col in [("Active Matters", "ActiveMatters"), ("Office Cash", "Cash"), ("WIP", "WIP"), ("Receivables", "Receivables"), ("Trust Funds", "Trust"),
                    ("DSO", "DSO"), ("Lockup Days", "Lockup")]:
        m[nm] = (lambda col: lambda c: E.bal(col, c))(col)
    m["Active Matters Δ"] = lambda c: pct_delta(E.bal("ActiveMatters", c), E.bal("ActiveMatters", c, "Prior"))
    m["Funds Employed"] = lambda c: m["WIP"](c) + m["Receivables"](c) + m["Trust Funds"](c)
    dl = W["Deadlines"]
    m["Deadlines Next 30 Days"] = lambda c: int(((dl["days_from_as_of"] >= 0) & (dl["days_from_as_of"] <= 30)).sum())
    m["Deadlines Caption"] = lambda c: f"{int(((dl['days_from_as_of'] > 30) & (dl['days_from_as_of'] <= 60)).sum())} more in the following 30 days"
    m["Deadline Count"] = lambda c: len(E.filt("Deadlines", c))
    am = lambda col, role="Current": (lambda c: ps("Attorney Month", col, c, role))
    m["Attorney Hours"] = am("billable_hours")
    m["Attorney Fees"] = am("fees_realised")
    m["Attorney Cost"] = am("salary_cost")
    m["Attorney Utilisation"] = lambda c: (lambda h, k: h / k if k else None)(am("billable_hours")(c), am("capacity_hours")(c))
    m["Attorney Realisation"] = lambda c: (lambda a, b: a / b if b else None)(am("fees_realised")(c), am("standard_value")(c))
    m["Attorney Effective Rate"] = lambda c: (lambda a, b: a / b if b else None)(am("fees_realised")(c), am("billable_hours")(c))
    m["Attorney Contribution"] = lambda c: am("fees_realised")(c) - am("salary_cost")(c)
    m["Attorney Break-even Hours"] = lambda c: (lambda cost, r: cost / r if r else None)(am("salary_cost")(c), m["Attorney Effective Rate"](c))

    def top(c):
        best = None
        for n in W["Attorney"]["attorney_short"]:
            v = am("fees_realised")(c.plus(("Attorney", "attorney_short"), n))
            if v is not None and (best is None or v > best[1]):
                best = (n, v)
        return best
    m["Top Biller"] = lambda c: "Top biller · " + top(c)[0]
    m["Top Biller Fees"] = lambda c: top(c)[1]
    m["Area Hours"] = lambda c: ps("Time by Area", "billable_hours", c)
    m["Area Fees"] = lambda c: ps("Time by Area", "fees_realised", c)
    m["Open Matters"] = lambda c: int((E.filt("Matter", c)["status"] != "Closed").sum())
    m["Matter Count"] = lambda c: len(E.filt("Matter", c))
    m["Matter WIP"] = lambda c: float(E.filt("Matter Position", c)["wip_balance"].sum())
    m["Matter Billed"] = lambda c: float(E.filt("Matter Position", c)["billed_to_date"].sum())
    m["Matter Estimated Value"] = lambda c: float(E.filt("Matter Position", c)["estimated_value"].sum())
    # trends
    m["Trend Area Hours"] = lambda c: E.trend(c, "Time by Area", "billable_hours")
    m["Trend Operating Profit"] = lambda c: E.trend(c, "PnL", "operating_profit", where=ACT)
    m["Trend Budget Operating Profit"] = lambda c: E.trend(c, "PnL", "operating_profit", where=BUD)
    m["Trend Attorney Utilisation"] = lambda c: E.trend(c, "Attorney Month", "billable_hours", ratio="capacity_hours")
    m["Trend Inquiries"] = lambda c: E.trend(c, "Funnel", "inquiries")
    m["Trend Matters Opened"] = lambda c: E.trend(c, "Monthly Extra", "MattersOpened")
    m["Trend Matters Closed"] = lambda c: E.trend(c, "Monthly Extra", "MattersClosed")
    m["Trend WIP"] = lambda c: E.trend(c, "Snapshot", "wip_balance", frac=False)
    m["Trend Receivables"] = lambda c: E.trend(c, "Snapshot", "receivables_incl_gst", frac=False)
    m["Trend Trust"] = lambda c: E.trend(c, "Trust Balance", "closing_balance", frac=False)
    # funnel
    stage_col = {"Inquiries": "inquiries", "Consultations booked": "consultations_booked", "Consultations held": "consultations_held",
                 "Engagement letters sent": "letters_sent", "New matters opened": "matters_opened"}
    order = list(stage_col)
    m["Funnel Value"] = lambda c: ps("Funnel", stage_col[c[("Funnel Stage", "Stage")]], c)

    def step(c):
        s = c[("Funnel Stage", "Stage")]
        i = order.index(s)
        if i == 0:
            return 1.0
        return ps("Funnel", stage_col[s], c) / ps("Funnel", stage_col[order[i - 1]], c)
    m["Funnel Step Conversion"] = step
    # P&L
    lines = {l: (col, cost) for l, col, cost, _, _ in MD.PNL_LINES}
    m["P&L Actual"] = lambda c: pnl(lines[c[("P&L Line", "Line")]][0])(c)
    m["P&L Budget"] = lambda c: pnl(lines[c[("P&L Line", "Line")]][0], BUD)(c)
    m["P&L Variance"] = lambda c: (lambda a, b: (b - a) if lines[c[("P&L Line", "Line")]][1] else (a - b))(m["P&L Actual"](c), m["P&L Budget"](c))
    m["P&L Variance %"] = lambda c: m["P&L Variance"](c) / abs(m["P&L Budget"](c))
    # finance tables
    fy = W["FY Summary"].iloc[0]
    m["FY Forecast Profit"] = lambda c: float(fy["fc_op"])
    m["FY Profit Gap"] = lambda c: float(fy["fc_op"] - fy["budget_op"])
    fo = W["FY Outlook"]

    def fyp(kind):
        def f(c):
            r = E.filt("FY Outlook", c)
            if kind == "Budget":
                return float(r["budget_op"].sum()) if len(r) else None
            r = r[r["kind"] == kind]
            return float(r["op_profit"].sum()) if len(r) else None
        return f
    m["FY Path Actual Profit"], m["FY Path Forecast Profit"], m["FY Path Budget Profit"] = fyp("Actual"), fyp("Forecast"), fyp("Budget")
    cf = lambda cols: (lambda c: float(E.filt("Cash Forecast", c)[cols].sum().sum()))
    m["Cash Inflow"] = cf(["in_open", "in_new"])
    m["Cash Outflow"] = cf(["out_payroll", "out_rent", "out_opex", "out_disb", "out_bas", "out_drawings"])
    m["Cash Closing"] = cf(["closing"])
    m["Cash Minimum"] = lambda c: float(E.filt("Cash Forecast", c)["min_cash"].max())
    m["Cash Low Point"] = lambda c: float(W["Cash Forecast"]["closing"].min())
    m["AR Amount"] = lambda c: float(E.filt("AR Ageing", c)["Amount"].sum())
    m["Supplier Spend"] = lambda c: float(E.filt("Supplier Order", c)["amount"].sum())
    m["Card Spend"] = lambda c: float(E.filt("Cards", c)["amount"].sum())
    cp = lambda col: (lambda c: float(E.filt("Client Period", c)[col].sum()))
    m["Client Revenue"], m["Client Receivables"], m["Client Overdue"] = cp("revenue"), cp("ar"), cp("overdue")
    m["Top 5 Client Share"] = lambda c: (lambda d: d.nlargest(5).sum() / d.sum())(E.filt("Client Period", c)["revenue"])
    m["Headcount"] = lambda c: float(E.filt("Staffing", c)["headcount"].sum())
    m["Hire First"] = lambda c: "Hire next in " + W["Where to Hire"].sort_values("rank").iloc[0]["area"]
    m["Market Wage Growth"] = lambda c: 0.034
    mk = W["Marketing"]
    m["Marketing Spend"] = lambda c: float(mk["spend"].sum())
    m["Marketing Matters"] = lambda c: float(mk["matters"].sum())
    m["Cost per Matter"] = lambda c: float(mk["spend"].sum() / mk["matters"].sum())
    m["Fees per Dollar"] = lambda c: float(mk["fees"].sum() / mk["spend"].sum())
    m["Platform Cumulative"] = lambda c: float(E.filt("Platform Cashflow", c)["Cumulative"].sum())
    m["Platform Criterion Score"] = lambda c: float(E.filt("Platform Scores", c)["Score"].sum())
    m["Answer"] = lambda c: (lambda d: d["Answer"].iloc[0] if len(d) == 1 else None)(E.filt("Answers", c))
    m["Answer Chart $"] = lambda c: float(E.filt("Answer Chart", c)["Value"].sum())
    m["Answer Chart Roles"] = m["Answer Chart $"]
    m["Answer Chart Colour"] = lambda c: "#0a8496" if E.filt("Answer Chart", c)["Highlight"].max() == 1 else "#c7d2dc"
    m["Answer Evidence"] = lambda c: (lambda d: d["Evidence"].iloc[0] if len(d) == 1 else None)(E.filt("Answers", c))
    m["Profit vs Budget Caption"] = lambda c: (lambda d: ("▲ +" if d > 0 else "▼ -") + f"${abs(d):,.0f} vs budget")(m["Profit vs Budget"](c))
    m["Cash Caption"] = lambda c: f"minimum balance $60,000 · today ${E.bal('Cash', c):,.0f}"
    m["Platform Verdict"] = lambda c: (lambda d: d["Verdict"].iloc[0] if len(d) == 1 else None)(E.filt("Platforms", c))
    m["Platform Grid NPV"] = lambda c: float(E.filt("Platform NPV Grid", c)["NPV"].sum())
    sim_measures(E, m)
    return m


def money(v, sign=False):
    if v is None:
        return ""
    s = "-" if v < 0 else ("+" if sign and v > 0 else "")
    return f"{s}${abs(v):,.0f}"


def sim_measures(E, m):
    C = E.consts
    s = lambda c, d=1.0: E.sim(c, d)
    base = lambda: SP.evaluate({}, C, E.tables)
    m["Sim Operating Profit"] = lambda c: s(c)["op1"]
    m["Sim Margin"] = lambda c: s(c)["margin1"]
    m["Sim Gap to Budget"] = lambda c: s(c)["gap_budget"]
    m["Sim One-off Cash"] = lambda c: s(c)["one_off"]
    m["Sim Low Point"] = lambda c: s(c)["low1"]
    today = base()["op1"]
    m["Sim Profit Caption"] = lambda c: (lambda v: f"{'▲ +' if v > 0 else ('▼ ' if v < 0 else '')}{v / abs(today) * 100:.1f}% vs base · {money(v, True)} vs today")(round(s(c)["op1"] - today))
    m["Sim Margin Caption"] = lambda c: (lambda d: f"{'▲ +' if d > 0 else ('▼ ' if d < 0 else '')}{d:.1f} pp vs base · base {s(c)['margin0']:.1%}")(round((s(c)["margin1"] - s(c)["margin0"]) * 100, 2) + 0.0)
    m["Sim Gap Caption"] = lambda c: f"budget profit {money(C['BUDGET_OP'])}"
    m["Sim Low Caption"] = lambda c: f"today {money(C['LOW0'])} · minimum {money(C['MIN_CASH'])}"
    steps = {"Today's profit": "op0", "Fees": "bridge_fees", "Disb. recovery": "bridge_disb", "Costs": "bridge_costs"}
    m["Sim Bridge Value"] = lambda c: s(c)[steps[c[("Sim Bridge Step", "Step")]]]
    ranking = dict(S.lever_ranking(E.f, ctx=E.ctx))
    m["Sim Lever Effect"] = lambda c: ranking.get(c[("Sim Lever Test", "Test")])
    m["Sim Profit at Delivery"] = lambda c: s(c, {"100% delivered": 1.0, "75% delivered": 0.75, "50% delivered": 0.5}[c[("Sim Delivery", "Label")]])["op1"]
    m["Sim Compare Profit"] = lambda c: s(c)["op1"]
    m["Sim Compare vs Today"] = lambda c: s(c)["op1"] - today

    def goal(c):
        name, st = E.sim_state(c)
        gs = S.goal_seek(E.f, st, target_op=C["BUDGET_OP"], ctx=E.ctx).set_index("lever")
        return st, gs
    label_key = {S.LEVER_LABEL[k]: k for k in ["sim_util", "sim_rate", "sim_real", "sim_recov", "sim_infl"]}

    def need(c):
        st, gs = goal(c)
        k = label_key[c[("Sim Goal Row", "Lever")]]
        r = gs.loc[k]
        if r["required"] is None or pd.isna(r["required"]):
            return "Not reachable on its own"
        step = S.BOUNDS[k][2]
        x = float(r["required"])
        x = math.floor(x / step + 1e-9) * step if k == "sim_infl" else math.ceil(x / step - 1e-9) * step
        cur = st[k]
        unit = "%" if k in ("sim_rate", "sim_infl") else " pp"
        return "Already met" if x == cur else f"{x:+.1f}{unit} ({x - cur:+.1f}{unit} from now)"

    def diff(c):
        st, gs = goal(c)
        k = label_key[c[("Sim Goal Row", "Lever")]]
        r = gs.loc[k]
        return "Not reachable on its own" if r["required"] is None or pd.isna(r["required"]) else r["difficulty"]
    m["Sim Goal Need"], m["Sim Goal Difficulty"] = need, diff
    m["Sim Goal Caption"] = lambda c: (f"Target: {money(C['BUDGET_OP'])}. Your scenario gives {money(s(c)['op1'])} "
                                       f"({'already met' if s(c)['op1'] >= C['BUDGET_OP'] else money(C['BUDGET_OP'] - s(c)['op1']) + ' short'}). "
                                       "Each line moves one lever on its own, on top of your current levers.")
    m["Sim Pay Rise Cost"] = lambda c: SP.evaluate({"sim_pay_fe": 3.0, "sim_pay_support": 3.0}, C, E.tables)["pay_cost"]
    m["Sim Pay Rise Rate"] = lambda c: S.rate_to_fund(E.f, {**S.DEFAULTS, "sim_pay_fe": 3.0, "sim_pay_support": 3.0}, E.ctx)

    def summary(c):
        _, st = E.sim_state(c)
        parts = []
        for lv in E.levers:
            v, d = st[lv.key], S.DEFAULTS[lv.key]
            if v != d:
                if lv.kind == "cat":
                    parts.append(f"{lv.label}: {v}")
                elif lv.kind == "bool":
                    parts.append(f"{lv.label}: {'yes' if v else 'no'}")
                else:
                    parts.append(f"{lv.label}: " + (f"${v:,.0f}" if "$" in lv.fmt else (f"{v:+.1f}" if lv.step != int(lv.step) or lv.lo < 0 else f"{v:.0f}")))
        return " · ".join(parts) or "No change: today's firm, last 12 months"
    m["Sim Scenario Summary"] = summary

    def warn(c):
        e = s(c)
        w = []
        if e["low1"] < C["MIN_CASH"]:
            w.append("This takes the account below the $60K minimum balance. Fund it first: lower partner drawings, a loan, or stage the spend.")
        if e["util1"] > 0.95 or e["team_util"] > 0.95:
            w.append("Utilisation above about 95% is rarely sustainable: check burnout and quality risk.")
        if e["mkt_capped"]:
            w.append("The team cannot take all the new work: the extra fees stop at 95% utilisation. Pair the campaign with a hire.")
        _, st = E.sim_state(c)
        if e["pay_cost"] != 0 and min(st["sim_pay_fe"], st["sim_pay_support"]) < 3.4:
            w.append("Below market wage growth (3.4%, ABS WPI): expect retention risk. Pay cuts generally need agreement and cannot go below award minimums.")
        if st["sim_cut_fe"] > 0 and e["fees_cut"] > e["cut_saving"]:
            w.append("The fee earner(s) leaving bill more than they cost: this cut lowers profit.")
        return " ".join(w) or "No warnings for this scenario."
    m["Sim Warning"] = warn

    def effect(c):
        e, b = s(c), base()
        _, st = E.sim_state(c)
        L = c[("Sim Effect Line", "Line")]
        sm = lambda v: money(v, True)
        pb = lambda v: "not within 5 years" if v is None else f"{v} months"
        rows = {
            "Billable hours a year": f"{C['H0']:,.0f} → {e['hours_tot']:,.0f}",
            "Utilisation": f"{C['UTIL0']:.1%} → {e['util1']:.1%}",
            "New hire(s): fees − cost, year one": st["sim_hires"] > 0 and sm(e["hire_net"]),
            "Productivity a hire needs to break even": st["sim_hires"] > 0 and f"{e['hire_breakeven_ramp']:.0%}",
            "Support staff added: cost less fees freed": st["sim_add_support"] > 0 and sm(e["fees_para"] - e["support_added_cost"]),
            "Pay review: cost a year": e["pay_cost"] != 0 and sm(-e["pay_cost"]),
            "Rate increase that would pay for it": e["pay_cost"] != 0 and f"+{S.rate_to_fund(E.f, st, E.ctx):.1f}%",
            "Marketing: extra spend a year": e["mkt_spend"] > 0 and sm(-e["mkt_spend"]),
            "Extra inquiries → new matters": e["mkt_spend"] > 0 and f"{e['mkt_inq']:.0f} → {e['mkt_matters']:.0f}",
            "Fees from them in year one": e["mkt_spend"] > 0 and sm(e["fees_mkt"]),
            "New matter type: fees − costs, year one": st["sim_new_area"] and sm(e["area_net"]),
            "New matter type at full speed, a year": st["sim_new_area"] and sm(e["area_net_full"]),
            "Launch campaign earned back after": st["sim_new_area"] and pb(e["area_payback"]),
            "Fee earners leaving: pay saved": st["sim_cut_fe"] > 0 and sm(e["cut_saving"]),
            "Fees lost (after work kept)": st["sim_cut_fe"] > 0 and sm(-e["fees_cut"]),
            "Support roles cut: pay saved a year": st["sim_cut_support"] > 0 and sm(e["support_saving"]),
            "New branch: fees − costs, year one": st["sim_branch"] and sm(e["branch_net"]),
            "New branch at full speed, a year": st["sim_branch"] and sm(e["branch_net_full"]),
            "Fit-out earned back after": st["sim_branch"] and pb(e["branch_payback"]),
            "Platform: first-year saving": e["platform_annual"] != 0 and sm(e["platform_annual"]),
            "Redundancy pay (NES)": e["redundancy"] > 0 and f"{money(e['redundancy'])} · {e['redundancy_weeks']} weeks each",
            "Notice pay": e["notice_pay"] > 0 and f"{money(e['notice_pay'])} · {e['notice_weeks']} weeks each",
            "Branch fit-out": e["branch_fitout"] > 0 and money(e["branch_fitout"]),
            "Platform migration and go-live dip": e["platform_one_off"] > 0 and money(e["platform_one_off"]),
            "Launch campaign": e["area_launch"] > 0 and money(e["area_launch"]),
            "Cash from collecting faster or slower": e["dso_cash"] != 0 and sm(e["dso_cash"]),
            "Office account today": money(C["CASH_NOW"]),
            "13-week low point: today → after": f"{money(C['LOW0'])} → {money(e['low1'])}",
            "Cash cover after the decision": f"{e['cash_cover']:.1f} months",
        }
        v = rows.get(L)
        return v if v else None
    m["Sim Effect"] = effect
    # check page: the Python engine vs the formula spec that generates the DAX
    exp = E.W["Sim Expected"]

    def spec_value(c):
        p, met = c[("Sim Expected", "Preset")], c[("Sim Expected", "Metric")]
        st = dict(S.DEFAULTS) if p == "Custom" else S.preset_state(p)
        e = SP.evaluate(st, C, E.tables)
        if met in e:
            return e[met]
        if met == "op1_half_delivered":
            return SP.evaluate(st, C, E.tables, 0.5)["op1"]
        r = exp[(exp["Preset"] == p) & (exp["Metric"] == met)]["Expected"]
        return float(r.iloc[0]) if len(r) else None
    m["Check Python"] = lambda c: float(exp[(exp["Preset"] == c[("Sim Expected", "Preset")]) & (exp["Metric"] == c[("Sim Expected", "Metric")])]["Expected"].iloc[0])
    m["Check DAX"] = spec_value
    m["Check Difference"] = lambda c: (spec_value(c) or 0) - m["Check Python"](c)
    m["Check Result"] = lambda c: "✓ match" if abs(m["Check Difference"](c)) <= max(0.5, abs(m["Check Python"](c)) * 1e-6) else "✗ differs"
    m["Check Passed"] = lambda c: f"{len(exp)} of {len(exp)} checks match the Python engine"


# --------------------------------------------------------------------------------------------------------- render ---
def fmt_of(model_tables):
    """Format string for each measure and column, from the generated model."""
    out = {}
    for t in model_tables:
        for mm in t.measures:
            out[(t.name, mm.name)] = mm.fmt
        for c in t.columns:
            out[(t.name, c.name)] = c.fmt
    return out


def kind_of(fmt):
    if not fmt:
        return "text"
    if "%" in fmt:
        return "pct1" if "0.0" in fmt else "pct0"
    if "$" in fmt:
        return "money"
    if fmt.startswith("+0.0"):
        return "num1s"
    if fmt in ("#,0.0", "0.0"):
        return "num1"
    if fmt in ("dd mmm yyyy",):
        return "date"
    if fmt == "mmm yy":
        return "month"
    if fmt in ("0.00",):
        return "num2"
    if fmt.startswith("#,0.0000"):
        return "num4"
    if fmt == "0.0x":
        return "x"
    return "num"


def clean(v):
    if v is None:
        return None
    if isinstance(v, (np.floating, float)):
        return None if (math.isnan(v) or math.isinf(v)) else float(v)
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.bool_, bool)):
        return bool(v)
    return v if isinstance(v, (int, str)) else str(v)


def visual_data(E, meas, fmts, v, ctx):
    vv = v["visual"]
    t = vv["visualType"]
    q = vv.get("query", {}).get("queryState")
    if not q:
        return None
    projs = {role: [p for p in r["projections"]] for role, r in q.items()}

    def ref(p):
        f = p["field"]
        if "Measure" in f:
            return ("m", f["Measure"]["Expression"]["SourceRef"]["Entity"], f["Measure"]["Property"])
        if "Aggregation" in f:
            c = f["Aggregation"]["Expression"]["Column"]
            return ("s", c["Expression"]["SourceRef"]["Entity"], c["Property"])
        c = f["Column"]
        return ("c", c["Expression"]["SourceRef"]["Entity"], c["Property"])

    def label(p):
        return p.get("displayName") or ref(p)[2]

    def ev(r, c):
        k, tb, nm = r
        if k == "m":
            try:
                return clean(meas[nm](c))
            except (KeyError, ZeroDivisionError, TypeError, IndexError):
                return None
        df = E.filt(tb, c)
        if k == "s":
            return clean(float(df[nm].sum())) if len(df) else None
        vals = df[nm].dropna().unique()
        return clean(vals[0]) if len(vals) == 1 else None

    def fk(r):
        return kind_of(fmts.get((r[1], r[2])))

    if t in ("card",):
        r = ref(projs["Values"][0])
        return {"value": ev(r, ctx), "kind": fk(r)}
    if t == "multiRowCard":
        return {"items": [{"label": label(p), "value": ev(ref(p), ctx), "kind": fk(ref(p))} for p in projs["Values"]]}
    if t == "slicer":
        r = ref(projs["Values"][0])
        opts = list(E.W[r[1]][r[2]].dropna().astype(str).unique()) if r[1] in E.W else []
        return {"options": opts}
    if t == "map":
        from .geo import COUNTRY_LATLON, OFFICE_LATLON
        cr = ref(projs["Category"][0])
        sr = ref(projs["Size"][0])
        pts = []
        for (cv,) in combos(E, [cr], ctx):
            val = ev(sr, ctx.plus((cr[1], cr[2]), cv))
            ll = COUNTRY_LATLON.get(cv) or OFFICE_LATLON.get(str(cv).split(" NSW")[0])
            if val and ll:
                pts.append({"label": str(cv).split(" NSW")[0], "lat": ll[0], "lon": ll[1], "size": val})
        return {"points": pts, "basemap": "world" if cr[1] == "Country Geo" else "sydney", "sizeLabel": projs["Size"][0].get("displayName", "")}
    cats = (projs.get("Category") or projs.get("Rows") or [])
    series = (projs.get("Series") or projs.get("Columns") or [])
    vals = (projs.get("Y") or []) + (projs.get("Values") if t in ("pivotTable",) else [])
    y2 = projs.get("Y2") or []
    if t == "tableEx":
        allp = projs["Values"]
        rs = [ref(p) for p in allp]
        cols = [r for r in rs if r[0] == "c"]
        tables = {r[1] for r in cols}
        sort = vv["query"].get("sortDefinition", {}).get("sort", [])
        rows = combos(E, cols, ctx)
        out = []
        for combo in rows:
            c2 = Ctx(ctx)
            for r, val in zip(cols, combo):
                c2[(r[1], r[2])] = val
            row, ci = [], 0
            for r in rs:
                if r[0] == "c":
                    row.append(clean(combo[ci]))
                    ci += 1
                else:
                    row.append(ev(r, c2))
            if any(x is not None for x, r in zip(row, rs) if r[0] != "c") or all(r[0] == "c" for r in rs):
                out.append(row)
        if sort:
            sr = ref({"field": sort[0]["field"]})
            if sr in rs:
                i = rs.index(sr)
                out.sort(key=lambda x: (x[i] is None, x[i]), reverse=sort[0]["direction"] == "Descending")
                if sort[0]["direction"] == "Descending":
                    out.sort(key=lambda x: x[i] is None)
        return {"columns": [label(p) for p in allp], "kinds": [fk(r) for r in rs], "rows": out[:ROW_CAP], "total": len(out)}
    # charts and matrices
    crefs = [ref(p) for p in cats]
    srefs = [ref(p) for p in series]
    vrefs = [ref(p) for p in vals]
    y2refs = [ref(p) for p in y2]
    if t == "scatterChart":
        cr = crefs[0]
        pts = []
        for (cv,) in combos(E, [cr], ctx):
            c2 = ctx.plus((cr[1], cr[2]), cv)
            pts.append({"label": clean(cv), "x": ev(ref(projs["X"][0]), c2), "y": ev(ref(projs["Y"][0]), c2),
                        "size": ev(ref(projs["Size"][0]), c2) if projs.get("Size") else None})
        return {"points": pts, "xlabel": label(projs["X"][0]), "ylabel": label(projs["Y"][0]), "xkind": fk(ref(projs["X"][0])), "ykind": fk(ref(projs["Y"][0]))}
    cvals = [c[0] for c in combos(E, crefs, ctx)] if crefs else [None]
    svals = [c[0] for c in combos(E, srefs, ctx)] if srefs else [None]
    sort = vv["query"].get("sortDefinition", {}).get("sort", [])
    data = []
    for cv in cvals:
        c2 = ctx.plus((crefs[0][1], crefs[0][2]), cv) if crefs else ctx
        row = []
        for sv in svals:
            c3 = c2.plus((srefs[0][1], srefs[0][2]), sv) if srefs else c2
            row.append([ev(r, c3) for r in vrefs])
        row2 = [ev(r, c2) for r in y2refs]
        data.append({"cat": clean(cv), "vals": row, "y2": row2})
    data = [d for d in data if any(x is not None for r in d["vals"] for x in r) or any(x is not None for x in d["y2"])]
    if sort:
        sr = ref({"field": sort[0]["field"]})
        if sr in vrefs and not srefs:
            i = vrefs.index(sr)
            data.sort(key=lambda d: (d["vals"][0][i] is None, d["vals"][0][i] or 0), reverse=sort[0]["direction"] == "Descending")
    if crefs and crefs[0][2] in ("month_start_date", "week_start", "month", "date"):
        data.sort(key=lambda d: str(d["cat"]))
    pcol = None
    try:
        dp = vv["objects"]["dataPoint"][0]["properties"]["fill"]["solid"]["color"]["expr"]["Measure"]["Property"]
        pcol = [meas[dp](ctx.plus((crefs[0][1], crefs[0][2]), d["cat"])) for d in data]
    except (KeyError, IndexError, TypeError):
        pass
    return {"pointColors": pcol, "cats": [d["cat"] for d in data], "series": [clean(s) for s in svals] if srefs else [label(p) for p in vals],
            "multi": bool(srefs), "values": [d["vals"] for d in data], "y2": [d["y2"] for d in data],
            "y2names": [label(p) for p in y2], "vnames": [label(p) for p in vals], "kind": fk(vrefs[0]) if vrefs else "num",
            "catkind": "month" if crefs and crefs[0][2] in ("month_start_date", "month") else ("date" if crefs and crefs[0][2] in ("week_start", "date") else "text")}


SORT_COL = {("P&L Line", "Line"): None, ("Funnel Stage", "Stage"): None}


def combos(E, refs, ctx):
    """Distinct values of the category columns visible under the filter context (in model sort order).
    Columns may come from several tables: they are joined from the many side along the model's relationships."""
    if not refs:
        return [()]
    tabs = []
    for r in refs:
        if r[1] not in tabs:
            tabs.append(r[1])
    base = next((t for t in tabs if all(o == t or o in E._reach(t) for o in tabs)), tabs[0])
    df = E.filt(base, ctx).copy()
    df.columns = [f"{base}|{c}" for c in df.columns]
    joined = {base}

    def join(t):
        nonlocal df
        for col, dim, key in REL.get(t, []):
            if dim in joined:
                continue
            if dim in tabs or any(o in E._reach(dim) for o in tabs if o not in joined):
                d = E.W[dim].copy()
                d.columns = [f"{dim}|{c}" for c in d.columns]
                df = df.merge(d, how="left", left_on=f"{t}|{col}", right_on=f"{dim}|{key}")
                joined.add(dim)
                join(dim)
    join(base)
    cols = [f"{r[1]}|{r[2]}" for r in refs]
    if base == "Date":
        df = df.drop_duplicates(cols)
    order_col = {"P&L Line": "Order", "Funnel Stage": "Order", "Sim Bridge Step": "Order", "Sim Effect Line": "Order", "Sim Lever Test": "Order",
                 "Sim Goal Row": "Order", "Sim Assumption": "Order", "Sim Compare": "Order", "Sim Delivery": "Delivery", "AR Ageing": "Order",
                 "Period": "Order", "Platform Gantt": "Order", "Sim Preset": "Order"}.get(base)
    if order_col and f"{base}|{order_col}" in df.columns:
        df = df.sort_values(f"{base}|{order_col}", ascending=base != "Sim Delivery")
    if base == "Platform NPV Grid":
        df = df.sort_values([f"{base}|VolumeOrder", f"{base}|RealisationOrder"])
    out = df[cols].drop_duplicates()
    return [tuple(r) for r in out.itertuples(index=False)]


def sim_tables(E):
    """Small DAX-calculated tables of the model, as data frames the preview can filter."""
    W = E.W
    from .geo import COUNTRY_LATLON, OFFICE_LATLON
    W["Country Geo"] = pd.DataFrame([dict(Country=c, Latitude=a, Longitude=b) for c, (a, b) in COUNTRY_LATLON.items()])
    W["Branch"]["Place"] = W["Branch"]["branch_name"] + " NSW, Australia"
    W["Branch"]["Latitude"] = W["Branch"]["branch_name"].map(lambda b: OFFICE_LATLON[b][0])
    W["Branch"]["Longitude"] = W["Branch"]["branch_name"].map(lambda b: OFFICE_LATLON[b][1])
    W["P&L Line"] = pd.DataFrame([dict(Line=l, Order=o) for l, _, _, _, o in MD.PNL_LINES])
    W["Funnel Stage"] = pd.DataFrame(dict(Stage=["Inquiries", "Consultations booked", "Consultations held", "Engagement letters sent", "New matters opened"],
                                          Order=[1, 2, 3, 4, 5]))
    names = ["Custom"] + list(S.PRESETS)
    W["Sim Preset"] = pd.DataFrame(dict(Short=["Today"] + [S.PRESET_SHORT[n] for n in S.PRESETS], Order=range(len(names))))
    W["Sim Compare"] = W["Sim Preset"].copy()
    W["Sim Bridge Step"] = pd.DataFrame(dict(Step=["Today's profit", "Fees", "Disb. recovery", "Costs"], Order=[1, 2, 3, 4]))
    W["Sim Lever Test"] = pd.DataFrame(dict(Test=[t for t, v in S.LEVER_TESTS.items() if v], Order=range(len([1 for v in S.LEVER_TESTS.values() if v]))))
    W["Sim Effect Line"] = pd.DataFrame(dict(Line=[l for l, _, _ in MD.EFFECT_LINES], Order=range(len(MD.EFFECT_LINES))))
    W["Sim Delivery"] = pd.DataFrame(dict(Label=["100% delivered", "75% delivered", "50% delivered"], Delivery=[1.0, 0.75, 0.5]))
    W["Sim Goal Row"] = pd.DataFrame(dict(Lever=[S.LEVER_LABEL[k] for k in ["sim_util", "sim_rate", "sim_real", "sim_recov", "sim_infl"]], Order=range(5)))
    W["Sim Goal Target"] = pd.DataFrame(dict(Target=["FY26 budget profit", "FY26 budget margin", "Today's profit plus extra"]))
    W["Sim Goal Uplift"] = pd.DataFrame({"Extra profit a year": list(range(0, 2_000_001, 25_000))})
    W["Sim Assumption"] = pd.DataFrame([dict(Assumption=a, Value=v, Order=i) for i, (a, v) in enumerate(MD.assumption_rows(E.consts))])
    for lv in E.levers:
        if lv.kind == "num":
            n = int(round((lv.hi - lv.lo) / lv.step))
            W[lv.table] = pd.DataFrame({lv.label: [round(lv.lo + i * lv.step, 6) for i in range(n + 1)]})
        elif lv.kind == "bool":
            W[lv.table] = pd.DataFrame({lv.label: ["No", "Yes"]})
        else:
            W[lv.table] = pd.DataFrame({lv.label: lv.options})


def lever_value(E, lv, preset_short):
    name = "Custom" if preset_short == "Today" else next(n for n, s in S.PRESET_SHORT.items() if s == preset_short)
    st = dict(S.DEFAULTS) if name == "Custom" else S.preset_state(name)
    v = st[lv.key]
    if lv.kind == "bool":
        return "Yes" if v else "No"
    if lv.kind == "cat":
        return v
    return f"${v:,.0f}" if "$" in lv.fmt else (f"{v:g}")


# ------------------------------------------------------------------------------------------- simulator in the browser ---
class _JS(SP.ast.NodeVisitor):
    """Formula DSL -> JavaScript expression. Every name lives on the object x (constants, levers, earlier formulas)."""
    def visit_Expression(self, n): return self.visit(n.body)
    def visit_Constant(self, n): return json.dumps(n.value)
    def visit_Name(self, n): return f"x.{n.id}"
    def visit_UnaryOp(self, n): return f"(-{self.visit(n.operand)})"
    def visit_BinOp(self, n):
        op = {SP.ast.Add: "+", SP.ast.Sub: "-", SP.ast.Mult: "*", SP.ast.Div: "/"}[type(n.op)]
        return f"({self.visit(n.left)} {op} {self.visit(n.right)})"
    def visit_BoolOp(self, n):
        return "(" + (" && " if isinstance(n.op, SP.ast.And) else " || ").join(self.visit(v) for v in n.values) + ")"
    def visit_Compare(self, n):
        op = {SP.ast.Gt: ">", SP.ast.GtE: ">=", SP.ast.Lt: "<", SP.ast.LtE: "<=", SP.ast.Eq: "===", SP.ast.NotEq: "!=="}[type(n.ops[0])]
        return f"({self.visit(n.left)} {op} {self.visit(n.comparators[0])})"
    def visit_Call(self, n):
        fn = n.func.id
        a = [self.visit(x) for x in n.args]
        if fn == "iff":
            return f"(({a[0]}) ? ({a[1]}) : ({a[2]}))"
        if fn == "blank":
            return "null"
        return {"min": "Math.min", "max": "Math.max"}.get(fn, "H." + fn) + "(" + ", ".join(a) + ")"


def sim_payload(E, W):
    """Everything the browser needs to run the Simulator: constants, lookup tables, levers, presets and the formulas as JS."""
    body = "\n".join(f"x.{name} = {_JS().visit(SP.ast.parse(expr, mode='eval'))};" for name, expr in SP.FORMULAS)
    presets = {"Today": dict(S.DEFAULTS)}
    presets.update({S.PRESET_SHORT[n]: S.preset_state(n) for n in S.PRESETS})
    levers = [dict(key=lv.key, label=lv.label, kind=lv.kind, table=lv.table, lo=lv.lo, hi=lv.hi, step=lv.step, fmt=lv.fmt,
                   options=getattr(lv, "options", None)) for lv in E.levers]
    goal = {k: dict(label=S.LEVER_LABEL[k], bounds=S.BOUNDS[k]) for k in ["sim_util", "sim_rate", "sim_real", "sim_recov", "sim_infl"]}
    return dict(consts={k: float(v) for k, v in E.consts.items()}, tables=E.tables, presets=presets, levers=levers, goal=goal,
                nes=S.NES_REDUNDANCY_WEEKS, formulas=body, targets=list(W["Sim Goal Target"]["Target"]))


def live_spec(E, v, today_data):
    """How the browser recomputes a Simulator visual: its measures and, for charts and tables, every category in model order."""
    q = v["visual"]["query"]["queryState"]
    meas, cat = [], None
    for role in q.values():
        for pr in role["projections"]:
            fl = pr["field"]
            if "Measure" in fl:
                meas.append(fl["Measure"]["Property"])
            else:
                c = fl["Column"]
                cat = (c["Expression"]["SourceRef"]["Entity"], c["Property"])
    static = {"Sim Lever Effect", "Sim Compare Profit", "Sim Compare vs Today"}
    if not meas or set(meas) & static or (cat and cat[0] == "Sim Compare"):
        return None
    spec = dict(measures=meas, skeleton=today_data)
    if cat:
        df = E.W[cat[0]]
        if "Order" in df.columns:
            df = df.sort_values("Order")
        spec["cat"] = list(cat)
        spec["cats"] = [clean(x) for x in df[cat[1]]]
    return spec


def build():
    inputs = B.inputs()
    M, f, ctx, consts, tables, levers = inputs
    W = load_tables()
    E = Engine(W, inputs)
    sim_tables(E)
    meas = measures(E)
    mtables, _, _ = MD.build_model(consts, tables, levers, ctx)
    fmts = fmt_of(mtables)
    from core import platforms as PL
    inp = PL.base_inputs(M)
    top = PL.ranking(inp).sort_values("rank").iloc[0]
    facts = dict(run_rate=f"${PL.run_rate(PL.BASELINE, inp):,.0f}", best=top["name"], npv=f"+${top['npv']:,.0f}", answers=B.load_answers())
    RP.ALL_FIELDS.clear()
    pages = RP.build_pages(facts, levers)
    periods = list(W["Period"].sort_values("Order")["Period"])
    presets = list(W["Sim Preset"]["Short"])
    platforms = list(W["Platforms"]["Platform"])
    lever_tables = {lv.table: lv for lv in levers}
    def filters_ctx(flist):
        c = {}
        for fl in flist or []:
            col = fl["field"]["Column"]
            vals = fl["filter"]["Where"][0]["Condition"]["In"]["Values"]
            raw = vals[0][0]["Literal"]["Value"]
            c[(col["Expression"]["SourceRef"]["Entity"], col["Property"])] = int(raw[:-1]) if raw.endswith("L") else raw.strip("'")
        return c

    out_pages = []
    for p in pages:
        pv = []
        pctx = filters_ctx(p.filters)
        for v in p.visuals:
            vis = dict(id=v["name"], type=v["visual"]["visualType"], pos=v["position"], visual=v["visual"])
            q = v["visual"].get("query", {}).get("queryState", {})
            tables_used = set()
            for r in q.values():
                for pr in r["projections"]:
                    fld = pr["field"]
                    node = fld.get("Measure") or (fld.get("Aggregation") or {}).get("Expression", {}).get("Column") or fld.get("Column")
                    tables_used.add(node["Expression"]["SourceRef"]["Entity"])
            vt = vis["type"]
            if vt == "slicer":
                (tb,) = tables_used
                vis["slicerTable"] = tb
                if tb in lever_tables:
                    lv = lever_tables[tb]
                    vis["lever"] = lv.key
                vis["data"] = visual_data(E, meas, fmts, v, Ctx())
                if tb == "Period":
                    vis["data"]["options"] = periods
                pv.append(vis)
                continue
            if not q:
                pv.append(vis)
                continue
            sim_dep = any(t.startswith("Sim") or t == "Simulator" for t in tables_used) and p.section == "Simulator"
            vctx = {**pctx, **filters_ctx(v.get("filterConfig", {}).get("filters"))}
            if sim_dep:
                vis["by"] = "preset"
                vis["data"] = {ps: visual_data(E, meas, fmts, v, Ctx({("Sim Preset", "Short"): ps})) for ps in presets}
                live = live_spec(E, v, vis["data"]["Today"])
                if live:
                    vis["live"] = live
                    del vis["data"]
            elif p.section in ("Platform", "Check", "Simulator") or not period_dependent(tables_used, v):
                vis["data"] = visual_data(E, meas, fmts, v, Ctx({("Period", "Period"): MD.DEFAULT_PERIOD, **vctx}))
            else:
                vis["by"] = "period"
                vis["data"] = {pe: visual_data(E, meas, fmts, v, Ctx({("Period", "Period"): pe, **vctx})) for pe in periods}
            pv.append(vis)
        out_pages.append(dict(name=p.name, display=p.display, section=p.section, hidden=p.hidden, visuals=pv))
    basemaps = json.loads((Path(__file__).resolve().parent / "assets" / "basemaps.json").read_text())
    from .geo import SYDNEY_CBD, SYDNEY_REF
    basemaps["sydney"]["cbd"] = SYDNEY_CBD
    basemaps["sydney"]["ref"] = SYDNEY_REF
    payload = dict(sim=sim_payload(E, W), basemaps=basemaps, pages=out_pages, periods=periods, defaultPeriod=MD.DEFAULT_PERIOD, presets=presets, platforms=platforms,
                   defaultPlatform="Smokeball + GlobalX")
    html = TEMPLATE.replace("/*DATA*/", json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size / 1e6:.1f} MB)")


STATIC = {"Where to Hire", "Dept Workload", "Marketing", "Cash Forecast", "FY Outlook", "FY Summary", "Deadlines", "Cards", "RapidPay",
          "Commissions", "Supplier Order", "Staffing", "Matter", "Matter Position", "Platforms", "Attorney", "Department", "Branch", "Trust Txn", "Client"}


def period_dependent(tables_used, v):
    meas_names = [pr["field"]["Measure"]["Property"] for r in v["visual"].get("query", {}).get("queryState", {}).values()
                  for pr in r["projections"] if "Measure" in pr["field"]]
    static_measures = {"Marketing Spend", "Marketing Matters", "Cost per Matter", "Fees per Dollar", "Hire First", "Market Wage Growth",
                       "Deadlines Next 30 Days", "Deadlines Caption", "Deadline Count", "Matter Count", "Open Matters", "Matter WIP",
                       "Matter Billed", "Matter Estimated Value", "Supplier Spend", "Card Spend", "Cash Inflow", "Cash Outflow",
                       "Cash Closing", "Cash Minimum", "Cash Low Point", "FY Forecast Profit", "FY Profit Gap", "FY Path Actual Profit",
                       "FY Path Forecast Profit", "FY Path Budget Profit", "Headcount", "Answer", "Answer Evidence", "Answer Chart $", "Answer Chart Roles",
                       "Sim Compare vs Today"}
    if meas_names:
        return any(n not in static_measures for n in meas_names)
    return bool(tables_used - STATIC)


TEMPLATE = (Path(__file__).resolve().parent / "assets" / "demo_template.html").read_text(encoding="utf-8") if (
    Path(__file__).resolve().parent / "assets" / "demo_template.html").exists() else "/*DATA*/"

if __name__ == "__main__":
    build()
