"""Single source of truth. Everything the dashboards show is derived from this deterministic model:

    hours × rates  →  value (WIP inflow)  →  fees billed  →  invoice ledger  →  collections  →  cash
    fees + disbursements  →  revenue  →  P&L (actual vs budget)  →  drawings / GST  →  bank balance

Monthly figures are stored as "full-month equivalents" (the month in progress is scaled up by days elapsed) and every
period query weights months by the days it overlaps – so MTD / QTD / custom ranges reconcile exactly.
"""
import numpy as np
import pandas as pd

from .ref import (AS_OF, START, PLAN_END, AREAS, ATTORNEYS, BRANCHES, CLIENTS, NAMED_MATTERS, NAMED_DEADLINES,
                  TRUST_TARGET, OFFICE_CASH_AT_AS_OF, SEARCH_TYPES, CARD_CATEGORIES, COMMISSIONS)

SEED = 20250917
LEAP_SUB, LEAP_SEATS, INFOTRACK_FEE = 189, 8, 38           # current platform: $/seat/mo, seats, $/search
S_RAW = {1: .86, 2: .97, 3: 1.04, 4: .98, 5: 1.03, 6: 1.07, 7: 1.0, 8: 1.02, 9: 1.03, 10: 1.05, 11: 1.06, 12: .89}
S_MEAN = float(np.mean(list(S_RAW.values())))
RATE_IDX = {2023: 0.9246, 2024: 0.9615, 2025: 1.0}          # annual rate review (+4%) keyed by FY start year
WAGE_IDX = {2023: 0.9335, 2024: 0.9662, 2025: 1.0}          # annual wage / cost inflation (+3.5%)
GST = 0.10
COST_LINES = ["payroll_fee", "disb_cost", "payroll_support", "rent", "software", "insurance", "marketing", "prof_fees",
              "cards", "merchant", "commission", "bank_fees", "other"]
OVERHEAD_LINES = COST_LINES[2:]


def fy_start_year(ts):
    return ts.year if ts.month >= 7 else ts.year - 1


def _month_end_dates(months, t_act):
    out = []
    for i, m in enumerate(months):
        e = m + pd.offsets.MonthEnd(0)
        out.append(AS_OF if i == t_act - 1 else e)
    return pd.DatetimeIndex(out)


def _chain(H, rate, kw, wo):
    """hours (A,K,T) → value → WIP roll-forward → fees billed. Returns a dict of arrays."""
    V_ak = H * rate[:, None, :]
    V = V_ak.sum((0, 1))
    wip_end = kw * V
    wip_open = np.r_[wip_end[0] * 0.97, wip_end[:-1]]
    writeoff = V * wo
    fees = wip_open + V - wip_end - writeoff
    return dict(V_ak=V_ak, V=V, wip_end=wip_end, wip_open=wip_open, writeoff=writeoff, fees=fees)


def build_model():
    rng = np.random.default_rng(SEED)
    months = pd.date_range(START, PLAN_END, freq="MS")
    T = len(months)
    T_act = int((months <= AS_OF).sum())
    dim = np.array(months.days_in_month)
    frac = np.ones(T)
    frac[T_act - 1] = AS_OF.day / dim[T_act - 1]
    tt = np.arange(T)
    is_act = tt < T_act
    S = np.array([S_RAW[m.month] / S_MEAN for m in months])
    G = 0.90 + 0.10 * tt / 26.0
    ri = np.array([RATE_IDX[fy_start_year(m)] for m in months])
    wi = np.array([WAGE_IDX[fy_start_year(m)] for m in months])
    A, K = len(ATTORNEYS), len(AREAS)

    # ---------------- hours ----------------
    H_exp = np.zeros((A, K, T)); H = np.zeros((A, K, T)); active = np.zeros((A, T))
    for ai, a in enumerate(ATTORNEYS):
        st = pd.Timestamp(a["start"])
        si = 0 if st <= START else int(months.get_indexer([st])[0])
        for t in range(T):
            if t < si:
                f = 0.0
            elif st <= START:
                f = 1.0
            else:
                age = t - si
                f = [0.6, 0.85][age] if age < 2 else 1.0
            active[ai, t] = 1.0 if t >= si else 0.0
            for ki, k in enumerate(AREAS):
                e = a["base"][k] * S[t] * G[t] * f
                H_exp[ai, ki, t] = e
                H[ai, ki, t] = e * np.clip(rng.normal(1, 0.04), 0.88, 1.12) if is_act[t] else e
    rate = np.array([a["bill_rate"] for a in ATTORNEYS])[:, None] * ri[None, :]
    kw_act = np.where(is_act, np.clip(rng.normal(0.86, 0.035, T), 0.78, 0.94), 0.86)
    wo_act = np.where(is_act, np.clip(rng.normal(0.085, 0.010, T), 0.06, 0.11), 0.085)
    act = _chain(H, rate, kw_act, wo_act)
    pln = _chain(H_exp, rate, np.full(T, 0.86), np.full(T, 0.085))
    rf = np.array([a["real_factor"] for a in ATTORNEYS])

    def alloc(ch):
        w = ch["V_ak"] * rf[:, None, None]
        return w / w.sum((0, 1)) * ch["fees"]
    fees_ak, fees_ak_p = alloc(act), alloc(pln)

    # ---------------- disbursements ----------------
    def disb(noisy):
        n = lambda s: np.clip(rng.normal(1, s, T), 0.85, 1.2) if noisy else np.ones(T)
        searches = 210 * S * (0.95 + 0.10 * tt / 26) * n(0.05)
        council_n = 42 * S * n(0.06)
        filing = 11500 * S * wi * n(0.08)
        rec = np.clip(rng.normal(0.86, 0.02, T), 0.80, 0.92) if noisy else np.full(T, 0.90)
        cost = searches * INFOTRACK_FEE + council_n * 105 + filing
        return dict(searches=searches, council_n=council_n, filing=filing, cost=cost, billed=rec * cost, rec=rec)
    d_a, d_p = disb(True), disb(False)

    # ---------------- invoice ledger → collections ----------------
    fees_k = fees_ak.sum(0)
    inv = _gen_invoices(rng, months, T_act, dim, frac, fees_k, d_a["billed"])
    paid = inv[inv["paid"].notna()]
    coll_incl = np.zeros(T)
    for t in range(T_act):
        mask = (paid["paid"] >= months[t]) & (paid["paid"] <= months[t] + pd.offsets.MonthEnd(0))
        coll_incl[t] = paid.loc[mask, "total"].sum() / frac[t]

    # ---------------- P&L (actual & plan share one cost function) ----------------
    supp_hc = np.array([14 if m < pd.Timestamp("2024-01-01") else 15 if m < pd.Timestamp("2024-08-01")
                        else 16 if m < pd.Timestamp("2025-03-01") else 17 for m in months])

    def costs(ch, d, coll, noisy):
        nz = lambda lo, hi: rng.uniform(lo, hi, T) if noisy else np.ones(T)
        fees, disb_b = ch["fees"], d["billed"]
        rev = fees + disb_b
        c = dict(
            payroll_fee=(active * np.array([a["pay_rate"] for a in ATTORNEYS])[:, None]).sum(0) * wi * 190,
            disb_cost=d["cost"], payroll_support=supp_hc * 5400 * wi,
            rent=sum(b["rent"] for b in BRANCHES) * wi, software=(LEAP_SUB * LEAP_SEATS + 450 + 3200) * wi,
            insurance=4200 * wi, marketing=10000 * wi * nz(0.7, 1.4), prof_fees=7000 * wi * (rng.lognormal(0, 0.3, T) if noisy else 1),
            cards=5200 * wi * nz(0.85, 1.2),
            merchant=(0.0175 * np.clip(rng.normal(0.28, 0.01, T), 0.25, 0.31) * coll) if noisy else 0.0175 * 0.28 * 1.1 * rev,
            commission=0.013 * fees * nz(0.85, 1.15), bank_fees=900 * nz(0.9, 1.2), other=12000 * wi * nz(0.9, 1.15))
        c["total_costs"] = sum(c[k] for k in COST_LINES)
        c["revenue"] = rev
        c["op_profit"] = rev - c["total_costs"]
        c["gst_credits"] = GST * (c["disb_cost"] + c["rent"] + c["software"] + c["marketing"] + c["prof_fees"] + 0.5 * c["other"] + 0.6 * c["cards"])
        return c
    ca = costs(act, d_a, coll_incl, True)
    cp = costs(pln, d_p, None, False)

    # ---------------- cash: collections in, costs + GST credits + BAS + drawings out ----------------
    gst_net = GST * ca["revenue"] - ca["gst_credits"]
    bas = np.zeros(T)
    for t in range(T_act):
        if months[t].month in (10, 1, 4, 7):
            bas[t] = gst_net[max(0, t - 3):t].sum() if t >= 3 else 3 * gst_net[0]
    base_net = coll_incl - (ca["total_costs"] + ca["gst_credits"] + bas)
    prev_profit = np.r_[ca["op_profit"][0], ca["op_profit"][:-1]]
    fl = frac[T_act - 1]
    c0 = 200_000.0                                       # opening bank balance, raised until the low point stays healthy
    for _ in range(8):
        s_base = base_net[:T_act - 1].sum() + fl * base_net[T_act - 1]
        s_prof = prev_profit[:T_act - 1].sum() + fl * prev_profit[T_act - 1]
        rho = (c0 + s_base - OFFICE_CASH_AT_AS_OF) / s_prof   # partner drawings as a share of last month's operating profit
        drawings = rho * prev_profit
        net_cash = base_net - drawings
        cum = np.cumsum(np.where(is_act, net_cash, 0))
        cash_end = c0 + cum
        cash_end[T_act - 1] = OFFICE_CASH_AT_AS_OF
        low = cash_end[:T_act].min()
        if low >= 60_000:
            break
        c0 += 60_000 - low
    cash_out = ca["total_costs"] + ca["gst_credits"] + bas + drawings
    draw_ratio = rho

    # ---------------- assemble monthly frame (full-month equivalents) ----------------
    def frame(ch, fak, d, c, use_actual):
        df = pd.DataFrame(index=months)
        df["hours"] = (H if use_actual else H_exp).sum((0, 1))
        df["value_std"] = ch["V"]; df["writeoff"] = ch["writeoff"]; df["fees"] = ch["fees"]
        for ki, k in enumerate(AREAS):
            df[f"fees_{k}"] = fak[:, ki, :].sum(0)
            df[f"hours_{k}"] = (H if use_actual else H_exp)[:, ki, :].sum(0)
        df["disb_billed"] = d["billed"]; df["searches"] = d["searches"]; df["council_n"] = d["council_n"]
        for k in COST_LINES + ["total_costs", "revenue", "op_profit", "gst_credits"]:
            df[k] = c[k]
        return df
    fin = frame(act, fees_ak, d_a, ca, True)
    plan = frame(pln, fees_ak_p, d_p, cp, False)
    fin.loc[months > AS_OF.replace(day=1), :] = np.nan       # no actuals after the as-of month
    fin["capacity"] = np.array([a["target"] for a in ATTORNEYS]) @ active
    fin.loc[months > AS_OF.replace(day=1), "capacity"] = np.nan
    plan["capacity"] = fin["capacity"].copy(); plan["capacity"] = np.array([a["target"] for a in ATTORNEYS]) @ active
    fin["collections"] = coll_incl; fin["collections_ex"] = coll_incl / (1 + GST)
    fin["gst_net"] = gst_net; fin["bas_paid"] = bas; fin["drawings"] = drawings
    fin["cash_in"] = coll_incl; fin["cash_out"] = cash_out; fin["net_cash"] = net_cash
    for c_ in ["collections", "collections_ex", "gst_net", "bas_paid", "drawings", "cash_in", "cash_out", "net_cash"]:
        fin.loc[months > AS_OF.replace(day=1), c_] = np.nan

    mend = _month_end_dates(months, T_act)
    stock = pd.DataFrame(index=months)
    stock["date"] = mend
    stock["wip"] = act["wip_end"]
    stock.loc[stock.index[T_act - 1], "wip"] = act["wip_end"][T_act - 2] + frac[T_act - 1] * (act["wip_end"][T_act - 1] - act["wip_end"][T_act - 2])
    stock["cash"] = cash_end
    stock["ar"] = [_ar_at(inv, d) if i < T_act else np.nan for i, d in enumerate(mend)]
    stock["ar_ex"] = stock["ar"] / (1 + GST)
    stock.loc[months > AS_OF.replace(day=1), ["wip", "cash", "ar", "ar_ex"]] = np.nan

    M = dict(wi=wi, ri=ri, draw_ratio=draw_ratio, open_cash=c0, months=months, T=T, T_act=T_act, dim=dim, frac=frac, fin=fin, plan=plan, stock=stock, inv=inv,
             H=H, H_exp=H_exp, active=active, fees_ak=fees_ak, V_ak=act["V_ak"], rate=rate, S=S)
    _gen_trust(rng, M)
    _gen_matters(rng, M)
    _gen_detail_tables(rng, M)
    return M


def _ar_at(inv, date):
    m = (inv["issue"] <= date) & (inv["paid"].isna() | (inv["paid"] > date))
    return float(inv.loc[m, "total"].sum())


def _gen_invoices(rng, months, T_act, dim, frac, fees_k, disb_billed):
    cl = pd.DataFrame(CLIENTS)
    rows = []
    for t in range(-3, T_act):                       # t < 0 → opening receivables issued before the data window
        ti = max(t, 0)
        m = months[0] + pd.DateOffset(months=t) if t < 0 else months[t]
        last_day = int(m.days_in_month) if t < T_act - 1 else AS_OF.day
        fr = 1.0 if t < 0 else frac[t]
        tot_fee_t = fees_k[:, ti].sum()
        for ki, k in enumerate(AREAS):
            cands = cl[(cl.practice == k) & (cl.since <= m.year)]
            if cands.empty:
                cands = cl[cl.practice == k]
            pick = rng.random(len(cands)) < cands["freq"].values
            if not pick.any():
                pick[rng.integers(len(cands))] = True
            sel = cands[pick]
            w = sel["w"].values * rng.lognormal(0, 0.25, len(sel)); w = w / w.sum()
            fee_amt = fees_k[ki, ti] * fr * w
            for (_, c), fa in zip(sel.iterrows(), fee_amt):
                da = disb_billed[ti] * fr * fa / (tot_fee_t * fr)
                p = 0.5 + np.arange(1, last_day + 1) / last_day
                day = int(rng.choice(np.arange(1, last_day + 1), p=p / p.sum()))
                issue = m + pd.Timedelta(days=day - 1)
                while issue.weekday() >= 5:
                    issue -= pd.Timedelta(days=1)
                if issue < m:
                    issue = m + pd.Timedelta(days=(7 - m.weekday()) % 7)
                issue = min(issue, AS_OF)
                delay = float(np.clip(rng.normal(c["delay"], c["delay"] * 0.30), 5, 180)) + (90 if rng.random() < 0.012 else 0)
                pay = issue + pd.Timedelta(days=int(round(delay)))
                ex = fa + da
                rows.append(dict(client=c["name"], area=k, attorney=c["attorney"], issue=issue, due=issue + pd.Timedelta(days=30),
                                 paid=pay if pay <= AS_OF else pd.NaT, ex_gst=ex, gst=GST * ex, total=(1 + GST) * ex))
    inv = pd.DataFrame(rows).sort_values("issue", kind="stable").reset_index(drop=True)
    n = len(inv)
    inv["invoice"] = [f"INV-{1057 - n + 1 + i:04d}" for i in range(n)]
    inv["branch"] = inv["attorney"].map({a["short"]: a["branch"] for a in ATTORNEYS})
    return inv


# =====================================================================================
# Trust ledger — monthly history per client that lands exactly on the reference balances
# =====================================================================================
def _gen_trust(rng, M):
    """Per-client trust ledger. Each client's balance follows a mean-reverting path around its reference level and ends
    exactly on the reference balance at AS_OF; receipts and payments are derived from that path (never negative)."""
    months, T_act = M["months"], M["T_act"]
    rows, bal = [], {}
    for client, target in TRUST_TARGET.items():
        x = rng.normal(0, 0.12)
        path = []
        for t in range(T_act + 1):                       # index 0 = opening balance, 1..T_act = month-ends
            x = 0.82 * x + rng.normal(0, 0.10)
            path.append(target * float(np.clip(1 + x, 0.45, 1.6)))
        path[-1] = float(target)
        for t in range(1, T_act + 1):
            prev, now = path[t - 1], path[t]
            f = rng.uniform(0.05, 0.25) if rng.random() < 0.7 else 0.0
            dep = now / (1 - f) - prev if f < 1 else 0.0
            if dep < 0:                                   # balance fell more than a normal payment would explain: payments only
                f, dep = max(0.0, 1 - now / prev), 0.0
            m = months[t - 1]
            last = (m + pd.offsets.MonthEnd(0)).day if t < T_act else AS_OF.day
            if dep > 1:
                rows.append(dict(date=m + pd.Timedelta(days=int(rng.integers(0, last))), client=client, type="Deposit", amount=round(float(dep), 2)))
            d_amt = (prev + dep) * f
            if d_amt > 1:
                rows.append(dict(date=m + pd.Timedelta(days=int(rng.integers(0, last))), client=client, type="Disbursement", amount=-round(float(d_amt), 2)))
        bal[client] = path[1:]
    M["trust"] = pd.DataFrame(bal, index=months[:T_act])
    M["trust_txns"] = pd.DataFrame(rows).sort_values("date", ascending=False).reset_index(drop=True)
    M["stock"].loc[months[:T_act], "trust"] = M["trust"].sum(1).values


# =====================================================================================
# Matter ledger — 33 named key matters + generated matters; reconciles to 142 active at AS_OF
# =====================================================================================
_TEMPLATES = {
    "Corporate": ["Share Sale Agreement", "Shareholders' Agreement Review", "Lease Review", "Due Diligence", "Capital Raise", "Asset Purchase", "Joint Venture Agreement"],
    "Litigation": ["Contract Dispute", "Debt Recovery", "Defence of Statement of Claim", "Mediation", "Injunction Application", "Costs Assessment"],
    "IP Portfolio": ["Trademark Registration", "Patent Portfolio Review", "Licensing Agreement", "IP Assignment", "Infringement Notice", "Opposition Response"],
    "Employment": ["Unfair Dismissal Defence", "Award Compliance Review", "Employment Contracts", "Redundancy Advisory", "Workplace Investigation"],
    "Advisory": ["Governance Advisory", "Regulatory Advice", "Structuring Advice", "Compliance Review", "Board Advisory"],
}
_DUR = {"Corporate": 6, "Litigation": 12, "IP Portfolio": 9, "Employment": 5, "Advisory": 4}
_VAL = {"Corporate": 150e3, "Litigation": 200e3, "IP Portfolio": 90e3, "Employment": 45e3, "Advisory": 35e3}
TARGET_ACTIVE = 142
OPEN_RATE0, OPEN_SLOPE = 11.3, 0.06             # matters opened per month: intercept, monthly growth


def _gen_matters(rng, M):
    months, T_act = M["months"], M["T_act"]
    cl = pd.DataFrame(CLIENTS)
    att_branch = {a["short"]: a["branch"] for a in ATTORNEYS}
    rows = []
    for (name, client, area, att, status, opened, val, branch, country) in NAMED_MATTERS:
        o = pd.Timestamp(opened)
        closed = pd.NaT
        if status == "Closed":
            closed = min(o + pd.Timedelta(days=int(rng.uniform(120, 300))), AS_OF - pd.Timedelta(days=int(rng.integers(12, 60))))
        rows.append(dict(name=name, client=client, area=area, attorney=att, status=status, opened=o, closed=closed,
                         est_value=float(val), branch=branch, country=country, named=True))

    def make(opened, area=None):
        area = area or rng.choice(AREAS, p=[0.30, 0.22, 0.22, 0.10, 0.16])
        cands = cl[(cl.practice == area) & (cl.since <= opened.year)]
        cands = cands if len(cands) else cl[cl.practice == area]
        c = cands.iloc[rng.choice(len(cands), p=(cands["w"] / cands["w"].sum()).values)]
        if rng.random() < 0.7:
            att = c["attorney"]
        else:
            wts = np.array([a["base"][area] + 1 for a in ATTORNEYS], float)
            att = ATTORNEYS[rng.choice(len(ATTORNEYS), p=wts / wts.sum())]["short"]
        dur = float(rng.lognormal(np.log(_DUR[area]), 0.45)) * 30.4
        closed = opened + pd.Timedelta(days=int(dur))
        val = float(np.round(rng.lognormal(np.log(_VAL[area]), 0.55) / 500) * 500)
        short = c["name"].replace(" Ltd.", "").replace(" Ltd", "").replace(" Co.", "")
        st = "Closed" if closed <= AS_OF else ("On Hold" if rng.random() < 0.08 else "Open")
        return dict(name=f"{short} — {rng.choice(_TEMPLATES[area])}", client=c["name"], area=area, attorney=att, status=st, opened=opened,
                    closed=closed if st == "Closed" else pd.NaT, est_value=val, branch=att_branch[att], country=c["country"], named=False)

    t0 = pd.Timestamp("2022-07-01")
    n_months = int((AS_OF.year - t0.year) * 12 + AS_OF.month - t0.month) + 1
    for i in range(n_months):
        m = t0 + pd.DateOffset(months=i)
        last = (m + pd.offsets.MonthEnd(0)).day if m < AS_OF.replace(day=1) else AS_OF.day
        elapsed = 1.0 if m < AS_OF.replace(day=1) else AS_OF.day / m.days_in_month      # the month in progress is only partly elapsed
        n = rng.poisson((OPEN_RATE0 + OPEN_SLOPE * i) * elapsed)
        for _ in range(n):
            rows.append(make(m + pd.Timedelta(days=int(rng.integers(0, last)))))
    df = pd.DataFrame(rows)
    df = df[(df["closed"].isna()) | (df["closed"] >= START - pd.Timedelta(days=1))].reset_index(drop=True)

    def n_active(d): return int(d["status"].isin(["Open", "On Hold"]).sum())
    excess = n_active(df) - TARGET_ACTIVE
    if excess > 0:
        drop = rng.choice(df[(~df["named"]) & df["status"].isin(["Open", "On Hold"])].index, size=excess, replace=False)
        df = df.drop(index=drop).reset_index(drop=True)
    elif excess < 0:
        add = []
        while len(add) < -excess:
            r = make(AS_OF - pd.Timedelta(days=int(rng.integers(3, 240))))
            if r["status"] != "Closed":
                add.append(r)
        df = pd.concat([df, pd.DataFrame(add)], ignore_index=True)

    df = df.sort_values("opened", kind="stable").reset_index(drop=True)
    df["id"] = [f"M-{o.year}-{i + 1:04d}" for i, o in enumerate(df["opened"])]
    ref = df["closed"].fillna(AS_OF)
    dur_days = (rng.uniform(0.7, 1.4, len(df)) * df["area"].map(_DUR) * 30.4).clip(lower=45)
    progress = ((ref - df["opened"]).dt.days / dur_days).clip(0, 1)
    progress = np.where(df["status"] == "Closed", 1.0, np.minimum(progress, 0.95))
    df["progress"] = progress
    df["billed"] = np.round(df["est_value"] * progress * np.where(df["status"] == "Closed", rng.normal(0.97, 0.05, len(df)), rng.normal(0.85, 0.08, len(df))), 0)
    wip_raw = np.where(df["status"] == "Closed", 0.0, df["est_value"] * (0.02 + 0.10 * progress * rng.uniform(0.4, 1.3, len(df))))
    firm_wip = float(M["stock"]["wip"].iloc[T_act - 1])
    df["wip"] = np.round(wip_raw * firm_wip / wip_raw.sum(), 0)          # matter WIP reconciles to the firm WIP balance
    df["days_open"] = (ref - df["opened"]).dt.days
    M["matters"] = df[["id", "name", "client", "area", "attorney", "branch", "country", "status", "opened", "closed", "est_value", "billed", "wip", "progress", "days_open", "named"]]

    fin, stock = M["fin"], M["stock"]
    opened_m = np.full(M["T"], np.nan); closed_m = np.full(M["T"], np.nan)
    act_m = np.full(M["T"], np.nan)
    for t in range(T_act):
        m0 = months[t]; m1 = m0 + pd.offsets.MonthEnd(0)
        opened_m[t] = ((df["opened"] >= m0) & (df["opened"] <= m1)).sum() / M["frac"][t]
        closed_m[t] = ((df["closed"] >= m0) & (df["closed"] <= m1)).sum() / M["frac"][t]
        d = stock["date"].iloc[t]
        act_m[t] = ((df["opened"] <= d) & (df["closed"].isna() | (df["closed"] > d))).sum()
    fin["matters_opened"], fin["matters_closed"] = opened_m, closed_m
    stock["matters_active"] = act_m
    conv = dict(booked=0.80, held=0.85, letters=0.72, opened=0.68)
    n = lambda s: np.clip(rng.normal(1, s, M["T"]), 0.85, 1.15)
    letters = opened_m / (conv["opened"] * n(0.05)); held = letters / (conv["letters"] * n(0.05))
    booked = held / (conv["held"] * n(0.04)); inq = booked / (conv["booked"] * n(0.04))
    fin["inquiries"], fin["booked"], fin["held"], fin["letters"] = inq, booked, held, letters

    # ---- deadlines: 12 named + a milestone for ~45% of active matters ----
    rows = [dict(date=pd.Timestamp(d), title=t, court=c, attorney=a, type="Key date", matter_id=None) for d, t, c, a in NAMED_DEADLINES]
    kinds = {"Corporate": [("Completion", "—"), ("Due Diligence Deadline", "—"), ("Board Approval", "—")],
             "Litigation": [("Hearing", "Federal Court"), ("Filing Deadline", "District Court"), ("Mediation", "—"), ("Discovery Deadline", "Supreme Court NSW")],
             "IP Portfolio": [("Filing Deadline", "IP Australia"), ("Examination Response", "IP Australia"), ("Opposition Deadline", "Federal Court")],
             "Employment": [("Conciliation", "Fair Work Commission"), ("Hearing", "Fair Work Commission"), ("Response Due", "—")],
             "Advisory": [("Advice Delivery", "—"), ("Panel Hearing", "Land & Environment Court"), ("Review Meeting", "—")]}
    for _, r in df[df["status"].isin(["Open", "On Hold"]) & ~df["named"]].iterrows():
        if rng.random() < 0.70:
            d = AS_OF + pd.Timedelta(days=int(rng.integers(2, 130)))
            while d.weekday() >= 5:
                d += pd.Timedelta(days=1)
            k, court = kinds[r["area"]][rng.integers(len(kinds[r["area"]]))]
            rows.append(dict(date=d, title=f"{r['name'].split(' — ')[0]} {k}", court=court, attorney=r["attorney"], type=k, matter_id=r["id"]))
    M["deadlines"] = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)


# =====================================================================================
# Detail tables that tie to monthly totals: searches, council searches, cards, RapidPay
# =====================================================================================
def _gen_detail_tables(rng, M):
    months, T_act, frac, fin = M["months"], M["T_act"], M["frac"], M["fin"]
    mt = M["matters"]
    types = list(SEARCH_TYPES); shares = np.array([SEARCH_TYPES[k][1] for k in types]); shares = shares / shares.sum()
    wts = np.array([SEARCH_TYPES[k][0] for k in types]); scale = INFOTRACK_FEE / float((wts * shares).sum())
    info, council, cards, rapid = [], [], [], []
    council_types = {"Rates Certificate": 95, "Section 10.7 Planning Certificate": 120, "Drainage Diagram": 60, "Zoning Certificate": 75}
    branch_w = np.array([b["support"] + sum(1 for a in ATTORNEYS if a["branch"] == b["name"]) for b in BRANCHES], float); branch_w /= branch_w.sum()
    inv = M["inv"]
    for t in range(T_act):
        m0 = months[t]; last = (m0 + pd.offsets.MonthEnd(0)).day if t < T_act - 1 else AS_OF.day
        pool = mt[(mt["opened"] <= m0 + pd.offsets.MonthEnd(0)) & (mt["closed"].isna() | (mt["closed"] >= m0))]
        pool = pool if len(pool) else mt
        # InfoTrack
        n = max(1, int(round(fin["searches"].iloc[t] * frac[t])))
        tp = rng.choice(len(types), size=n, p=shares)
        cost = wts[tp] * scale; cost = cost * (fin["searches"].iloc[t] * frac[t] * INFOTRACK_FEE / cost.sum())
        for i in range(n):
            mm = pool.iloc[rng.integers(len(pool))]
            d = m0 + pd.Timedelta(days=int(rng.integers(0, last)))
            info.append(dict(date=d, matter=mm["name"], matter_id=mm["id"], search_type=types[tp[i]], cost=round(float(cost[i]), 2), branch=mm["branch"],
                             status="Pending" if (AS_OF - d).days <= 2 and rng.random() < 0.5 else "Complete"))
        # council
        n = max(1, int(round(fin["council_n"].iloc[t] * frac[t])))
        names = list(council_types); base = np.array([council_types[k] for k in names], float)
        tp = rng.choice(len(names), size=n, p=[0.5, 0.25, 0.1, 0.15]); cost = base[tp] * (fin["council_n"].iloc[t] * frac[t] * 105 / base[tp].sum())
        for i in range(n):
            mm = pool.iloc[rng.integers(len(pool))]
            d = m0 + pd.Timedelta(days=int(rng.integers(0, last)))
            council.append(dict(date=d, matter=mm["name"], branch=mm["branch"], council=[b["council"] for b in BRANCHES if b["name"] == mm["branch"]][0],
                                search_type=names[tp[i]], cost=round(float(cost[i]), 2), status="Pending" if (AS_OF - d).days <= 3 and rng.random() < 0.5 else "Complete"))
        # cards
        total = fin["cards"].iloc[t] * frac[t]; n = int(rng.integers(30, 44))
        cats = list(CARD_CATEGORIES); cp = np.array([CARD_CATEGORIES[c][0] for c in cats]); cp /= cp.sum()
        ci = rng.choice(len(cats), size=n, p=cp); amt = rng.lognormal(0, 0.7, n) * np.array([1.6 if cats[i] in ("Travel", "Equipment") else 1 for i in ci])
        amt = amt / amt.sum() * total
        for i in range(n):
            cat = cats[ci[i]]; d = m0 + pd.Timedelta(days=int(rng.integers(0, last)))
            cards.append(dict(date=d, card="Amex" if rng.random() < 0.5 else "Visa", merchant=str(rng.choice(CARD_CATEGORIES[cat][1])), category=cat,
                              amount=round(float(amt[i]), 2), branch=str(rng.choice(BRANCH_NAMES_LOCAL, p=branch_w)), country="Australia"))
        # RapidPay
        vol = fin["merchant"].iloc[t] / 0.0175 * frac[t]
        pay_pool = inv[(inv["paid"] >= m0) & (inv["paid"] <= m0 + pd.offsets.MonthEnd(0))]
        n = max(1, int(vol / 5200)); a = rng.lognormal(0, 0.6, n); a = a / a.sum() * vol
        for i in range(n):
            row = pay_pool.iloc[rng.integers(len(pay_pool))] if len(pay_pool) else inv.iloc[0]
            d = row["paid"] if pd.notna(row["paid"]) else m0
            rapid.append(dict(date=d, client=row["client"], amount=round(float(a[i]), 2), fee=round(float(a[i]) * 0.0175, 2),
                              method=str(rng.choice(["Visa", "Mastercard", "Amex", "Apple/Google Pay"], p=[0.42, 0.33, 0.15, 0.10]))))
    M["infotrack"] = pd.DataFrame(info).sort_values("date", ascending=False).reset_index(drop=True)
    M["council"] = pd.DataFrame(council).sort_values("date", ascending=False).reset_index(drop=True)
    M["cards"] = pd.DataFrame(cards).sort_values("date", ascending=False).reset_index(drop=True)
    M["rapidpay"] = pd.DataFrame(rapid).sort_values("date", ascending=False).reset_index(drop=True)
    M["commissions"] = pd.DataFrame(COMMISSIONS, columns=["matter", "referrer", "rate_pct", "amount", "status"])
    M["commbiz"] = [dict(account="Office Account", matched=142, unmatched=3, last_sync="2025-09-17 07:12 AM"),
                    dict(account="Trust Account", matched=58, unmatched=0, last_sync="2025-09-17 07:12 AM")]


BRANCH_NAMES_LOCAL = [b["name"] for b in BRANCHES]
