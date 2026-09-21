"""Platform evaluation engine: 3-year cash flows, TCO, NPV, IRR, payback, weighted score, scenarios, sensitivity.

IMPORTANT: prices, scores and every "assumption" below are illustrative sample inputs (they come from the original
prototype and analyst judgement) – they are NOT vendor facts. Replace them with real quotes / demo findings before use.
"""
from dataclasses import dataclass, replace
import numpy as np
import pandas as pd

BASELINE = "LEAP + InfoTrack (current)"
CRITERIA = ["Speed", "Cost", "Reliability", "Support", "Integration"]
DEFAULT_WEIGHTS = {"Cost": 30, "Integration": 25, "Reliability": 20, "Support": 15, "Speed": 10}

PLATFORMS = {
    BASELINE: dict(short="LEAP", color="#22d3ee", sub=189, fee=38, seats=8, esc=0.04, migration=0, impl_weeks=0, uplift=0.0,
                   scores=dict(Speed=75, Cost=55, Reliability=90, Support=85, Integration=90), badges=[("LEAP", "#152b4e"), ("IT", "#0a8496")],
                   tagline="Incumbent — baseline for every comparison", risk_adj=dict(adoption=0, migration=0, integration=0, price=1, downtime=0, compliance=0)),
    "triConvey + triSearch": dict(short="triConvey", color="#34d399", sub=0, fee=34, seats=8, esc=0.03, migration=14000, impl_weeks=8, uplift=1.0,
                                  scores=dict(Speed=80, Cost=85, Reliability=82, Support=75, Integration=78), badges=[("tC", "#0a8496"), ("tS", "#3ba7b3")],
                                  tagline="Usage-priced model: no seat subscription, per-search fee only", risk_adj=dict(adoption=0, migration=1, integration=1, price=-1, downtime=0, compliance=1)),
    "Smokeball + GlobalX": dict(short="Smokeball", color="#fbbf24", sub=179, fee=36, seats=8, esc=0.04, migration=22000, impl_weeks=12, uplift=3.5,
                                scores=dict(Speed=85, Cost=65, Reliability=88, Support=80, Integration=82), badges=[("SB", "#f2b134"), ("GX", "#6b46c1")],
                                tagline="Assumed automatic time-capture upside on fee-earner hours", risk_adj=dict(adoption=0, migration=1, integration=0, price=0, downtime=0, compliance=0)),
    "Actionstep + GlobalX": dict(short="Actionstep", color="#fb7185", sub=165, fee=37, seats=8, esc=0.04, migration=26000, impl_weeks=14, uplift=2.5,
                                 scores=dict(Speed=78, Cost=68, Reliability=84, Support=78, Integration=80), badges=[("AS", "#e2665a"), ("GX", "#6b46c1")],
                                 tagline="Workflow-automation play: shorter matter cycle times", risk_adj=dict(adoption=1, migration=1, integration=0, price=0, downtime=1, compliance=0)),
    "PracticeEvolve + PEXA": dict(short="PracEvolve", color="#a78bfa", sub=172, fee=39, seats=8, esc=0.035, migration=24000, impl_weeks=10, uplift=1.5,
                                  scores=dict(Speed=72, Cost=60, Reliability=86, Support=82, Integration=85), badges=[("PE", "#1f7a4d"), ("PX", "#0a8496")],
                                  tagline="Settlement-centric: value depends on property-related work", risk_adj=dict(adoption=0, migration=0, integration=-1, price=0, downtime=0, compliance=0)),
    "Clio + GlobalX": dict(short="Clio", color="#60a5fa", sub=155, fee=36, seats=8, esc=0.04, migration=20000, impl_weeks=10, uplift=2.5,
                           scores=dict(Speed=88, Cost=72, Reliability=80, Support=88, Integration=75), badges=[("Cl", "#3182ce"), ("GX", "#6b46c1")],
                           tagline="Open-ecosystem play: broad third-party integrations", risk_adj=dict(adoption=-1, migration=0, integration=1, price=0, downtime=0, compliance=1)),
    "MyCase + SAI Global": dict(short="MyCase", color="#f472b6", sub=149, fee=40, seats=8, esc=0.03, migration=15000, impl_weeks=8, uplift=1.0,
                                scores=dict(Speed=82, Cost=78, Reliability=79, Support=76, Integration=70), badges=[("MC", "#d53f8c"), ("SAI", "#718096")],
                                tagline="Lowest seat price; check feature fit against must-haves", risk_adj=dict(adoption=0, migration=0, integration=1, price=0, downtime=0, compliance=1)),
}
NAMES = list(PLATFORMS)
SHORT = {k: v["short"] for k, v in PLATFORMS.items()}
SHORT_TO_FULL = {v: k for k, v in SHORT.items()}
COLORS = {k: v["color"] for k, v in PLATFORMS.items()}

SCENARIOS = {
    "Base": dict(benefit_realisation=0.50, migration_mult=1.00, vol_growth=0.05, esc_delta=0.0),
    "Downside": dict(benefit_realisation=0.25, migration_mult=1.40, vol_growth=0.00, esc_delta=0.02),
    "Upside": dict(benefit_realisation=0.75, migration_mult=0.85, vol_growth=0.10, esc_delta=-0.01),
}


@dataclass(frozen=True)
class Inputs:
    discount: float = 0.10            # annual discount rate for NPV
    horizon: int = 36                 # months evaluated
    benefit_realisation: float = 0.50 # share of the assumed productivity uplift that is actually captured
    ramp_months: int = 6              # months to reach full benefit after go-live
    vol_growth: float = 0.05          # annual growth in search volume
    migration_mult: float = 1.0
    dip_pct: float = 0.10             # productivity dip at cut-over (share of monthly fee-earner value)
    dip_weeks: float = 2.0
    esc_delta: float = 0.0            # added to each vendor's annual price escalator
    fee_earners: int = 8
    eff_rate: float = 450.0           # effective $/hour actually billed
    monthly_value: float = 690000.0   # fee-earner value at standard rates per month
    searches_pm: float = 210.0
    seats: int = 8


def base_inputs(M):
    """Anchor the evaluation to the last 12 months of actual data."""
    from .ref import AS_OF
    fin = M["fin"]; m1 = AS_OF.replace(day=1)
    ltm = fin.loc[m1 - pd.DateOffset(months=11):m1]
    return Inputs(eff_rate=float(ltm["fees"].sum() / ltm["hours"].sum()), monthly_value=float(ltm["value_std"].mean()),
                  searches_pm=float(ltm["searches"].mean()), fee_earners=int((M["active"][:, M["T_act"] - 1] > 0).sum()), seats=int((M["active"][:, M["T_act"] - 1] > 0).sum()))


def with_scenario(inp, name):
    return replace(inp, **SCENARIOS[name])


# ---------------------------------------------------------------- cash flows ---
def monthly_cost(name, inp, t, esc_delta=None):
    p = PLATFORMS[name]
    esc = p["esc"] + (inp.esc_delta if esc_delta is None else esc_delta)
    yr = t // 12
    vol = inp.searches_pm * (1 + inp.vol_growth) ** (t / 12)
    sub = p["sub"] * inp.seats * (1 + esc) ** yr
    srch = p["fee"] * vol * (1 + esc) ** yr
    return sub, srch, vol


def run_rate(name, inp):
    """Annual cost at today's prices and volumes (no escalation)."""
    p = PLATFORMS[name]
    return 12 * (p["sub"] * inp.seats + p["fee"] * inp.searches_pm)


def cashflow(name, inp):
    """Incremental cash flow of moving from the incumbent to `name` over the horizon (months 0..H-1)."""
    p = PLATFORMS[name]; H = inp.horizon
    go_live = int(np.ceil(p["impl_weeks"] / 4.345)) if name != BASELINE else 0
    rows = []
    one_off_fee = p["migration"] * inp.migration_mult
    dip_cost = inp.monthly_value * inp.dip_pct * inp.dip_weeks / 4.345 if name != BASELINE else 0.0
    for t in range(H):
        s_c, q_c, _ = monthly_cost(BASELINE, inp, t)
        s_a, q_a, vol = monthly_cost(name, inp, t)
        cur, alt = s_c + q_c, s_a + q_a
        overlap = cur if (name != BASELINE and t < go_live) else 0.0            # both systems run until go-live
        incr_cost = (alt + overlap) - cur if name != BASELINE else 0.0
        if name != BASELINE and t >= go_live:
            months_live = t - go_live + 1
            ramp = min(1.0, months_live / max(inp.ramp_months, 1))
            benefit = p["uplift"] * inp.fee_earners * inp.eff_rate * inp.benefit_realisation * ramp * (1.03 ** (t // 12))
        else:
            benefit = 0.0
        one_off = (one_off_fee if t == 0 else 0.0) + (dip_cost if (name != BASELINE and t == go_live) else 0.0)
        net = benefit - incr_cost - one_off
        rows.append(dict(t=t, cur=cur, alt=alt, sub=s_a, search=q_a, overlap=overlap, incr_cost=incr_cost, benefit=benefit, one_off=one_off, net=net, vol=vol))
    df = pd.DataFrame(rows)
    df["cum"] = df["net"].cumsum()
    rm = (1 + inp.discount) ** (1 / 12) - 1
    df["pv"] = df["net"] / (1 + rm) ** df["t"]
    return df, go_live


def _irr(flows):
    f = np.asarray(flows, float)
    if not (f.min() < 0 < f.max()):
        return None
    lo, hi = -0.99, 50.0
    npv = lambda r: float(np.sum(f / (1 + r) ** np.arange(len(f))))
    if npv(lo) * npv(hi) > 0:
        return None
    for _ in range(80):
        mid = (lo + hi) / 2
        if npv(lo) * npv(mid) <= 0:
            hi = mid
        else:
            lo = mid
    return (1 + (lo + hi) / 2) ** 12 - 1


def evaluate(name, inp):
    df, go_live = cashflow(name, inp)
    p = PLATFORMS[name]
    pos = df.index[df["cum"] >= 0]
    after_neg = df[(df["cum"] < 0)]
    payback = None
    if name != BASELINE:
        neg_idx = df.index[df["cum"] < 0]
        if len(neg_idx) == 0:
            payback = 0
        else:
            last_neg = neg_idx.max()
            payback = int(last_neg + 2) if last_neg < len(df) - 1 else None       # months from start (1-based) to turn cumulative positive
    tco_alt = float(df["alt"].sum() + df["overlap"].sum() + df["one_off"].sum())
    tco_cur = float(df["cur"].sum())
    out = dict(name=name, go_live=go_live, npv=float(df["pv"].sum()), payback=payback, irr=_irr(df["net"].values) if name != BASELINE else None,
               tco_alt=tco_alt, tco_cur=tco_cur, tco_delta=tco_alt - tco_cur, benefit_3y=float(df["benefit"].sum()),
               one_off=float(df["one_off"].sum()), run_rate=run_rate(name, inp), run_rate_delta=run_rate(name, inp) - run_rate(BASELINE, inp),
               cost_per_fee_earner=run_rate(name, inp) / inp.fee_earners, cost_per_search=(p["sub"] * inp.seats / max(inp.searches_pm, 1) + p["fee"]),
               year1_net=float(df.loc[:11, "net"].sum()))
    return out, df


# ------------------------------------------------------------------- scoring ---
def weighted_score(name, weights=None):
    w = weights or DEFAULT_WEIGHTS
    tot = sum(w.values()) or 1
    return sum(w[c] * PLATFORMS[name]["scores"][c] for c in CRITERIA) / tot


def ranking(inp, weights=None):
    rows = []
    for n in NAMES:
        ev, _ = evaluate(n, inp)
        rows.append(dict(name=n, short=SHORT[n], score=weighted_score(n, weights), npv=ev["npv"], payback=ev["payback"], run_rate=ev["run_rate"], tco_delta=ev["tco_delta"]))
    df = pd.DataFrame(rows)
    df["rank_score"] = df["score"].rank(ascending=False, method="min").astype(int)
    df["rank_npv"] = df["npv"].rank(ascending=False, method="min").astype(int)
    # combined decision index: 50% weighted score, 50% financial (NPV scaled into 0-100 around the sample range)
    lo, hi = df["npv"].min(), df["npv"].max()
    fin_idx = (df["npv"] - lo) / (hi - lo) * 100 if hi > lo else 50
    df["decision"] = 0.5 * df["score"] + 0.5 * fin_idx
    df["rank"] = df["decision"].rank(ascending=False, method="min").astype(int)
    return df


def verdict(name, ev, score, base_score):
    if name == BASELINE:
        return "Baseline", "info"
    if ev["npv"] > 50000 and score >= base_score - 3:
        return "Recommend", "good"
    if ev["npv"] > 0:
        return "Consider", "warn"
    return "Not recommended", "bad"


# --------------------------------------------------- sensitivity + risk + gantt ---
def npv_grid(name, inp, benefit_vals, vol_mults):
    z = np.zeros((len(vol_mults), len(benefit_vals)))
    for i, vm in enumerate(vol_mults):
        for j, b in enumerate(benefit_vals):
            ev, _ = evaluate(name, replace(inp, searches_pm=inp.searches_pm * vm, benefit_realisation=b))
            z[i, j] = ev["npv"]
    return z


_RISKS = [("Data migration errors", 3, 4, "adoption", "Trial migration + reconciliation of trust and WIP balances before cut-over"),
          ("Staff adoption / training gap", 3, 3, "adoption", "Champions per branch, phased training, 4-week hypercare"),
          ("Integration gaps (MYOB, banking, payments)", 3, 4, "integration", "Confirm feeds in a proof-of-concept before signing"),
          ("Vendor price escalation", 3, 2, "price", "Negotiate multi-year price cap in the contract"),
          ("Downtime during cut-over", 2, 4, "downtime", "Cut over on a weekend, keep the legacy system read-only for 90 days"),
          ("Trust-accounting compliance fit", 2, 5, "compliance", "Compliance sign-off and reconciliation test before go-live")]


def risk_register(name):
    adj = PLATFORMS[name]["risk_adj"]
    rows = []
    for r, p_, i_, key, mit in _RISKS:
        if name == BASELINE:
            p_ = 1 if key != "price" else 3
        else:
            p_ = int(np.clip(p_ + adj.get(key, 0), 1, 5))
        rows.append(dict(risk=r, probability=p_, impact=i_, score=p_ * i_, mitigation=mit))
    return pd.DataFrame(rows).sort_values("score", ascending=False).reset_index(drop=True)


PHASES = [("Planning & contract", 0.00, 0.14), ("Data migration", 0.10, 0.38), ("Configuration & integrations", 0.24, 0.62),
          ("Training", 0.55, 0.80), ("Parallel run", 0.72, 0.92), ("Cut-over & hypercare", 0.88, 1.00)]


def gantt(name):
    w = PLATFORMS[name]["impl_weeks"]
    return [(ph, s * w, e * w) for ph, s, e in PHASES]
