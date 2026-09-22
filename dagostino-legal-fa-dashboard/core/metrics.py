"""KPI and analysis functions computed from the model for any reporting period."""
import numpy as np
import pandas as pd

from .ref import AS_OF, START, AREAS, ATTORNEYS, BRANCHES, CLIENTS
from .period import Period, month_weights, flow, stock_at, has_data, months_in, delta
from .model import COST_LINES, OVERHEAD_LINES, GST

ATT_SHORT = [a["short"] for a in ATTORNEYS]


# ------------------------------------------------------------------ flows -----
def fin_sum(M, p):
    return flow(M["fin"], p, list(M["fin"].columns)) if has_data(p) else None


def plan_sum(M, p):
    return flow(M["plan"], p, list(M["plan"].columns)) if has_data(p) else None


def ratios(f):
    """Efficiency ratios from a period flow series."""
    if f is None:
        return {}
    return dict(util=f["hours"] / f["capacity"] if f["capacity"] else np.nan,
                realisation=f["fees"] / f["value_std"] if f["value_std"] else np.nan,
                eff_rate=f["fees"] / f["hours"] if f["hours"] else np.nan,
                margin=f["op_profit"] / f["revenue"] if f["revenue"] else np.nan,
                gross_margin=(f["revenue"] - f["payroll_fee"] - f["disb_cost"]) / f["revenue"] if f["revenue"] else np.nan,
                disb_recovery=f["disb_billed"] / f["disb_cost"] if f["disb_cost"] else np.nan)


def monthly(M, col, end, n=12, source="fin"):
    """Trailing n months (full-month equivalents) ending at the month containing `end`."""
    df = M[source]
    m1 = pd.Timestamp(end).replace(day=1)
    s = df[col].loc[m1 - pd.DateOffset(months=n - 1):m1]
    return s[~s.isna()]


def spark(M, col, end, n=12, source="fin"):
    s = monthly(M, col, end, n, source)
    return s.values.tolist() if len(s) > 1 else [0, 0]


# ---------------------------------------------------------------- people ------
def att_table(M, p):
    w = month_weights(p, M["months"])
    idx = M["months"].get_indexer(w.index)
    wv = w.values
    H = (M["H"][:, :, idx] * wv).sum(2)
    V = (M["V_ak"][:, :, idx] * wv).sum(2)
    F = (M["fees_ak"][:, :, idx] * wv).sum(2)
    act = M["active"][:, idx]
    cap = (act * wv).sum(1) * 190
    cost = (act * M["wi"][idx] * wv).sum(1) * np.array([a["pay_rate"] for a in ATTORNEYS]) * 190
    df = pd.DataFrame({"attorney": [a["name"] for a in ATTORNEYS], "role": [a["role"] for a in ATTORNEYS],
                       "branch": [a["branch"] for a in ATTORNEYS], "hours": H.sum(1), "capacity": cap,
                       "value": V.sum(1), "fees": F.sum(1), "cost": cost}, index=ATT_SHORT)
    df["util"] = df["hours"] / df["capacity"].replace(0, np.nan)
    df["realisation"] = df["fees"] / df["value"].replace(0, np.nan)
    df["eff_rate"] = df["fees"] / df["hours"].replace(0, np.nan)
    df["contribution"] = df["fees"] - df["cost"]
    df["breakeven_hours"] = df["cost"] / (df["eff_rate"].replace(0, np.nan))
    for ki, k in enumerate(AREAS):
        df[f"h_{k}"] = H[:, ki]
        df[f"f_{k}"] = F[:, ki]
    return df


def att_monthly(M, end, n=12, what="hours"):
    m1 = pd.Timestamp(end).replace(day=1)
    months = pd.date_range(m1 - pd.DateOffset(months=n - 1), m1, freq="MS")
    idx = M["months"].get_indexer(months)
    src = {"hours": M["H"], "fees": M["fees_ak"]}[what]
    return pd.DataFrame(src[:, :, idx].sum(1).T, index=months, columns=ATT_SHORT)


def area_table(M, p):
    f = fin_sum(M, p)
    return pd.DataFrame({"hours": [f[f"hours_{k}"] for k in AREAS], "fees": [f[f"fees_{k}"] for k in AREAS]}, index=AREAS)


def branch_table(M, p):
    f = fin_sum(M, p)
    at = att_table(M, p)
    rows = []
    fee_tot = at["fees"].sum()
    hc_supp = np.array([b["support"] for b in BRANCHES], float)
    for bi, b in enumerate(BRANCHES):
        a = at[at["branch"] == b["name"]]
        share = a["fees"].sum() / fee_tot if fee_tot else 0
        rev = a["fees"].sum() + f["disb_billed"] * share
        w = month_weights(p, M["months"])
        rent = b["rent"] * float((M["wi"][M["months"].get_indexer(w.index)] * w.values).sum())
        supp = f["payroll_support"] * hc_supp[bi] / hc_supp.sum()
        other = sum(f[k] for k in OVERHEAD_LINES if k not in ("payroll_support", "rent")) * share
        cost = a["cost"].sum() + f["disb_cost"] * share + supp + rent + other
        rows.append(dict(branch=b["name"], council=b["council"], fee_earners=int((a["capacity"] > 0).sum()), support=b["support"],
                         headcount=int((a["capacity"] > 0).sum()) + b["support"], hours=a["hours"].sum(), util=a["hours"].sum() / a["capacity"].sum() if a["capacity"].sum() else np.nan,
                         revenue=rev, cost=cost, op_profit=rev - cost, margin=(rev - cost) / rev if rev else np.nan))
    df = pd.DataFrame(rows).set_index("branch")
    mt = M["matters"]
    d = pd.Timestamp(p.end)
    act = mt[(mt["opened"] <= d) & (mt["closed"].isna() | (mt["closed"] > d))]
    df["active_matters"] = act.groupby("branch").size().reindex(df.index).fillna(0).astype(int)
    return df


# --------------------------------------------------------------- receivables --
def open_invoices(M, date):
    inv = M["inv"]
    return inv[(inv["issue"] <= date) & (inv["paid"].isna() | (inv["paid"] > date))].copy()


def ar_ageing(M, date):
    o = open_invoices(M, date)
    o["past_due"] = (pd.Timestamp(date) - o["due"]).dt.days
    bins = [-10**6, 0, 30, 60, 90, 10**6]
    labels = ["Not yet due", "1–30 days", "31–60 days", "61–90 days", "90+ days"]
    o["bucket"] = pd.cut(o["past_due"], bins=bins, labels=labels)
    return o, o.groupby("bucket", observed=False)["total"].sum().reindex(labels).fillna(0)


def ar_total(M, date):
    return float(open_invoices(M, date)["total"].sum())


def dso(M, date):
    inv = M["inv"]
    d = pd.Timestamp(date)
    billed = inv[(inv["issue"] > d - pd.Timedelta(days=90)) & (inv["issue"] <= d)]["total"].sum()
    return ar_total(M, d) / (billed / 90) if billed else np.nan


def lockup_days(M, date):
    d = pd.Timestamp(date)
    inv = M["inv"]
    rev90 = inv[(inv["issue"] > d - pd.Timedelta(days=90)) & (inv["issue"] <= d)]["ex_gst"].sum()
    return (stock_at(M["stock"], "wip", d) + ar_total(M, d) / (1 + GST)) / (rev90 / 90) if rev90 else np.nan


def client_table(M, p, cmp=None):
    inv = M["inv"]
    cur = inv[(inv["issue"] >= p.start) & (inv["issue"] <= p.end)]
    df = pd.DataFrame(CLIENTS).set_index("name")[["practice", "attorney", "since", "country"]]
    df["revenue"] = cur.groupby("client")["ex_gst"].sum().reindex(df.index).fillna(0)
    if cmp is not None and has_data(cmp):
        prev = inv[(inv["issue"] >= cmp.start) & (inv["issue"] <= cmp.end)]
        df["prev"] = prev.groupby("client")["ex_gst"].sum().reindex(df.index).fillna(0)
    else:
        df["prev"] = np.nan
    o, _ = ar_ageing(M, p.end)
    df["ar"] = o.groupby("client")["total"].sum().reindex(df.index).fillna(0)
    df["overdue"] = o[o["past_due"] > 0].groupby("client")["total"].sum().reindex(df.index).fillna(0)
    paid = inv[inv["paid"].notna() & (inv["issue"] >= AS_OF - pd.Timedelta(days=365))]
    df["days_to_pay"] = ((paid["paid"] - paid["issue"]).dt.days).groupby(paid["client"]).mean().reindex(df.index)
    mt = M["matters"]; d = pd.Timestamp(p.end)
    act = mt[(mt["opened"] <= d) & (mt["closed"].isna() | (mt["closed"] > d))]
    df["active_matters"] = act.groupby("client").size().reindex(df.index).fillna(0).astype(int)
    df["since_start"] = inv.groupby("client")["ex_gst"].sum().reindex(df.index).fillna(0)
    df["share"] = df["revenue"] / df["revenue"].sum() if df["revenue"].sum() else 0
    df.index.name = "client"
    return df.reset_index()


# ------------------------------------------------------------ headline KPIs ---
def headline(M, cur, cmp):
    """Overview KPIs for the period and their comparison, plus 12-month sparklines."""
    fc, fp = fin_sum(M, cur), fin_sum(M, cmp) if cmp else None
    at_c, at_p = att_table(M, cur), (att_table(M, cmp) if cmp and has_data(cmp) else None)
    rc, rp = ratios(fc), ratios(fp)
    stk = M["stock"]
    act_c = stock_at(stk, "matters_active", cur.end)
    act_p = stock_at(stk, "matters_active", cmp.end) if cmp and has_data(cmp) else None
    top = at_c["fees"].idxmax()
    dl = M["deadlines"]
    nxt = dl[(dl["date"] >= AS_OF) & (dl["date"] <= AS_OF + pd.Timedelta(days=30))]
    prev30 = dl[(dl["date"] > AS_OF + pd.Timedelta(days=30)) & (dl["date"] <= AS_OF + pd.Timedelta(days=60))]
    return dict(fc=fc, fp=fp, rc=rc, rp=rp, at=at_c, atp=at_p, active=act_c, active_p=act_p, top=top,
                top_fees=at_c.loc[top, "fees"], top_fees_p=(at_p.loc[top, "fees"] if at_p is not None else None),
                deadlines=len(nxt), deadlines_next=len(prev30))


# ------------------------------------------------------- budget & outlook -----
def fy_bounds(date):
    y = date.year if date.month >= 7 else date.year - 1
    return pd.Timestamp(year=y, month=7, day=1), pd.Timestamp(year=y + 1, month=6, day=30)


def fy_outlook(M, date=AS_OF):
    """Year-to-date actual + rest-of-year forecast (budget × YTD performance ratio) vs full-year budget."""
    s, e = fy_bounds(date)
    ytd = Period(s, date, "YTD")
    rest_months = pd.date_range(date.replace(day=1) + pd.DateOffset(months=1), e, freq="MS")
    a, b = fin_sum(M, ytd), plan_sum(M, ytd)
    plan = M["plan"]
    budget_year = plan.loc[pd.date_range(s, e, freq="MS")]
    # remaining days of the current month + all later months, at budget × YTD ratio
    left_cur = 1 - (date.day / date.days_in_month)
    rest = plan.loc[rest_months].sum() + plan.loc[date.replace(day=1)] * left_cur
    r_rev = a["revenue"] / b["revenue"] if b["revenue"] else 1.0
    r_cost = a["total_costs"] / b["total_costs"] if b["total_costs"] else 1.0
    fc_rev, fc_cost = a["revenue"] + rest["revenue"] * r_rev, a["total_costs"] + rest["total_costs"] * r_cost
    out = dict(ytd_actual=a, ytd_budget=b, budget_rev=budget_year["revenue"].sum(), budget_cost=budget_year["total_costs"].sum(),
               budget_op=budget_year["op_profit"].sum(), fc_rev=fc_rev, fc_cost=fc_cost, fc_op=fc_rev - fc_cost, r_rev=r_rev, r_cost=r_cost)
    path = []
    fin = M["fin"]
    for m in pd.date_range(s, e, freq="MS"):
        if m <= date.replace(day=1):
            path.append(dict(month=m, revenue=fin.loc[m, "revenue"], op_profit=fin.loc[m, "op_profit"], budget_rev=plan.loc[m, "revenue"], budget_op=plan.loc[m, "op_profit"], kind="Actual"))
        else:
            rv, cs = plan.loc[m, "revenue"] * r_rev, plan.loc[m, "total_costs"] * r_cost
            path.append(dict(month=m, revenue=rv, op_profit=rv - cs, budget_rev=plan.loc[m, "revenue"], budget_op=plan.loc[m, "op_profit"], kind="Forecast"))
    out["path"] = pd.DataFrame(path)
    return out


# ----------------------------------------------------- 13-week cash forecast --
def cash_forecast(M, weeks=13):
    """Weekly cash forecast from open invoices (client payment behaviour), run-rate billing, payroll cycle, rent, BAS and drawings."""
    fin, plan = M["fin"], M["plan"]
    cur_m = AS_OF.replace(day=1)
    w0 = AS_OF + pd.Timedelta(days=1)
    edges = [w0 + pd.Timedelta(days=7 * i) for i in range(weeks + 1)]
    wk = pd.DataFrame({"week_start": edges[:-1]})
    def bucket(dates):
        out = np.zeros(weeks)
        for d, amt in dates:
            i = int((d - w0).days // 7)
            if 0 <= i < weeks:
                out[i] += amt
        return out
    # 1) collections on open invoices — expected date = issue + the client's typical days-to-pay (overdue items assumed within 3 weeks)
    o = open_invoices(M, AS_OF)
    delay = pd.DataFrame(CLIENTS).set_index("name")["delay"]
    exp = []
    for i, r in enumerate(o.itertuples()):
        d = r.issue + pd.Timedelta(days=int(delay[r.client]))
        if d <= AS_OF:
            d = AS_OF + pd.Timedelta(days=4 + (i * 5) % 18)
        exp.append((d, r.total))
    wk["in_open"] = bucket(exp)
    # 2) collections on invoices not yet issued (run-rate billing, paid 4–9 weeks later)
    weekly_bill = plan.loc[cur_m + pd.DateOffset(months=1), "revenue"] * (1 + GST) / 4.345
    lag = {4: 0.15, 5: 0.30, 6: 0.30, 7: 0.15, 9: 0.10}
    new = np.zeros(weeks)
    for i in range(weeks):
        for L, sh in lag.items():
            if i + L < weeks:
                new[i + L] += weekly_bill * sh
    wk["in_new"] = new
    # 3) outflows
    pr = plan.loc[cur_m + pd.DateOffset(months=1)]
    payroll_m = pr["payroll_fee"] + pr["payroll_support"]
    pay_dates = [pd.Timestamp("2025-09-26") + pd.Timedelta(days=14 * i) for i in range(8)]
    wk["out_payroll"] = -bucket([(d, payroll_m * 12 / 26) for d in pay_dates])
    rent_dates = [pd.Timestamp("2025-10-01"), pd.Timestamp("2025-11-03"), pd.Timestamp("2025-12-01")]
    wk["out_rent"] = -bucket([(d, pr["rent"]) for d in rent_dates])
    opex_w = (pr["software"] + pr["insurance"] + pr["marketing"] + pr["prof_fees"] + pr["cards"] + pr["merchant"] + pr["commission"] + pr["bank_fees"] + pr["other"]) / 4.345
    disb_w = (pr["disb_cost"] + pr["gst_credits"]) / 4.345
    wk["out_opex"] = -(np.full(weeks, opex_w))
    wk["out_disb"] = -(np.full(weeks, disb_w))
    q1 = fin.loc[pd.Timestamp("2025-07-01"):cur_m, "gst_net"].sum()
    wk["out_bas"] = -bucket([(pd.Timestamp("2025-10-28"), q1)])
    draw = []
    prev_profit = fin.loc[cur_m - pd.DateOffset(months=1), "op_profit"]
    for k, d in enumerate([pd.Timestamp("2025-09-25"), pd.Timestamp("2025-10-27"), pd.Timestamp("2025-11-25"), pd.Timestamp("2025-12-22")]):
        pp = prev_profit if k == 0 else plan.loc[(d - pd.DateOffset(months=1)).replace(day=1), "op_profit"]
        draw.append((d, M["draw_ratio"] * pp))
    wk["out_drawings"] = -bucket(draw)
    inflow = wk["in_open"] + wk["in_new"]
    outflow = wk[["out_payroll", "out_rent", "out_opex", "out_disb", "out_bas", "out_drawings"]].sum(axis=1)
    wk["net"] = inflow + outflow
    wk["closing"] = float(M["stock"]["cash"].iloc[M["T_act"] - 1]) + wk["net"].cumsum()
    wk["opening"] = wk["closing"] - wk["net"]
    return wk
