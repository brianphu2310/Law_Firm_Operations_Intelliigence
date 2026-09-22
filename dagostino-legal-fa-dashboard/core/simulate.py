"""Decision Simulator engine: annual what-if on the last 12 months, goal-seek, delivery-risk range and lever ranking.

Pure functions (no Streamlit) so every number can be unit-tested. Levers are stored in the units the analyst sees:
percentage points (pp), percent, number of hires, days.
"""
import numpy as np
import pandas as pd

from .metrics import fin_sum, fy_outlook
from .model import GST
from .period import Period
from .ref import AS_OF

ROLES = {"Associate": dict(bill=380, pay=120), "Senior Associate": dict(bill=520, pay=170), "Partner": dict(bill=650, pay=210)}
DEFAULTS = dict(sim_util=0.0, sim_rate=0.0, sim_real=0.0, sim_recov=0.0, sim_infl=0.0, sim_hires=0, sim_role="Associate", sim_ramp=75, sim_dso=0)
HIRE_OVERHEAD = 9000        # desk, software, insurance and recruitment per new fee earner per year (assumption)
LTM_DAYS = 352              # length of the "last 12 months" window (1 Oct 24 – 17 Sep 25) in days
HOURS_PER_MONTH = 190

# slider ranges (min, max, step) used by the page; goal-seek reports whether a required change fits inside them
BOUNDS = dict(sim_util=(-10.0, 10.0, 0.5), sim_rate=(0.0, 10.0, 0.5), sim_real=(-5.0, 5.0, 0.5), sim_recov=(-10.0, 10.0, 1.0),
              sim_infl=(-10.0, 10.0, 0.5), sim_hires=(0, 3, 1), sim_ramp=(40, 100, 5), sim_dso=(-15, 15, 1))
LEVER_LABEL = dict(sim_util="Utilisation (pp)", sim_rate="Rate increase (%)", sim_real="Realisation (pp)", sim_recov="Disbursement recovery (pp)",
                   sim_infl="Overhead change (%)", sim_hires="New fee earners", sim_ramp="Year-one productivity of a new hire", sim_dso="Days to collect")

PRESETS = {
    "Hire an associate": dict(sim_hires=1, sim_role="Associate", sim_ramp=60),
    "Raise rates 5%": dict(sim_rate=5.0),
    "Lift utilisation +3 pp": dict(sim_util=3.0),
    "Collect 7 days faster": dict(sim_dso=-7),
    "Cut overheads 5%": dict(sim_infl=-5.0),
    "Downturn": dict(sim_util=-5.0, sim_infl=3.0),
}
PRESET_HELP = {"Hire an associate": "One associate, 60% as busy as the firm average in year one", "Raise rates 5%": "5% across the board", "Lift utilisation +3 pp": "Three more points of billable time",
               "Collect 7 days faster": "DSO down by a week (one-off cash release)", "Cut overheads 5%": "5% off non-payroll, non-disbursement costs",
               "Downturn": "Utilisation −5 pp and overheads +3%"}


def preset_state(name):
    """Full lever state for a named preset (everything else back to its default)."""
    return {**DEFAULTS, **PRESETS[name]}


def base_period():
    return Period(AS_OF.replace(day=1) - pd.DateOffset(months=11), AS_OF, "Last 12 months")


def base_actuals(M):
    p = base_period()
    return p, fin_sum(M, p)


def budget_targets(M):
    """Annual FY budget operating profit, revenue and margin (the yardstick for 'close the gap')."""
    o = fy_outlook(M)
    return dict(op=float(o["budget_op"]), rev=float(o["budget_rev"]), margin=float(o["budget_op"] / o["budget_rev"]))


def haircut(s, delivery):
    """Deliver only `delivery` (0–1) of the *improvements*: better utilisation, rates, realisation, recovery, overhead cuts and the productivity of new hires.
    Setbacks and fixed costs (a hire's pay) are never softened."""
    if delivery >= 1.0:
        return dict(s)
    t = dict(s)
    for k in ("sim_util", "sim_rate", "sim_real", "sim_recov"):
        if t[k] > 0:
            t[k] = t[k] * delivery
    if t["sim_infl"] < 0:
        t["sim_infl"] = t["sim_infl"] * delivery
    if int(t["sim_hires"]) > 0:                                  # a new hire's ramp-up is the uncertain part; their pay is not
        t["sim_ramp"] = t["sim_ramp"] * delivery
    return t


def project(f, s, delivery=1.0):
    """Annualised P&L under the scenario. f = last-12-month actuals (fin_sum Series); s = lever values."""
    s = haircut(s, delivery)
    k = 365.0 / LTM_DAYS
    hours0, fees0, val0 = f["hours"] * k, f["fees"] * k, f["value_std"] * k
    util0, real0 = f["hours"] / f["capacity"], f["fees"] / f["value_std"]
    std_rate0 = val0 / hours0
    hires, role, ramp = int(s["sim_hires"]), ROLES[s["sim_role"]], s["sim_ramp"] / 100.0
    util1 = util0 + s["sim_util"] / 100.0
    real1 = real0 + s["sim_real"] / 100.0
    rate_up = 1 + s["sim_rate"] / 100.0
    hours1 = hours0 * util1 / util0                                 # existing team: hours scale with utilisation
    hire_hours = hires * HOURS_PER_MONTH * 12 * util1 * ramp        # new hires bill at the firm's utilisation × year-one productivity
    fees_core = hours1 * std_rate0 * rate_up * real1
    fees_hire = hire_hours * role["bill"] * rate_up * real1
    fees1 = fees_core + fees_hire
    hrs_ratio = (hours1 + hire_hours) / hours0
    disb_cost1 = f["disb_cost"] * k * hrs_ratio
    disb_bill1 = disb_cost1 * (f["disb_billed"] / f["disb_cost"] + s["sim_recov"] / 100.0)
    rev0, rev1 = (f["fees"] + f["disb_billed"]) * k, fees1 + disb_bill1
    over0 = (f["total_costs"] - f["payroll_fee"] - f["disb_cost"]) * k
    cost0 = f["total_costs"] * k
    hire_cost = hires * (role["pay"] * HOURS_PER_MONTH * 12 + HIRE_OVERHEAD)
    cost1 = f["payroll_fee"] * k + hires * role["pay"] * HOURS_PER_MONTH * 12 + disb_cost1 + over0 * (1 + s["sim_infl"] / 100.0) + hires * HIRE_OVERHEAD
    hire_full_fees = HOURS_PER_MONTH * 12 * util1 * role["bill"] * rate_up * real1          # one hire at 100% of firm utilisation
    return dict(rev0=rev0, rev1=rev1, cost0=cost0, cost1=cost1, op0=rev0 - cost0, op1=rev1 - cost1, fees0=fees0, fees1=fees1,
                hours0=hours0, hours1=hours1 + hire_hours, util0=util0, util1=util1, eff0=fees0 / hours0, eff1=fees1 / (hours1 + hire_hours),
                real0=real0, real1=real1, over0=over0, hire_fees=fees_hire, hire_cost=hire_cost, hire_net=fees_hire - hire_cost,
                hire_breakeven_ramp=(hire_cost / hires) / hire_full_fees if hires else None,
                dso_cash=-s["sim_dso"] * rev1 * (1 + GST) / 365.0)                      # slower payment (+days) ties up cash → negative


def margin(r):
    return r["op1"] / r["rev1"]


# ------------------------------------------------------------------ goal seek ----
def _solve(fn, lo, hi, target, iters=60):
    """Smallest x in [lo, hi] with fn(x) >= target, for increasing fn; None if even fn(hi) < target."""
    if fn(lo) >= target:
        return lo
    if fn(hi) < target:
        return None
    for _ in range(iters):
        mid = (lo + hi) / 2
        if fn(mid) >= target:
            hi = mid
        else:
            lo = mid
    return hi


def goal_seek(f, s, target_op=None, target_margin=None):
    """For each single lever: how far must it move (on top of the current scenario) to reach a target operating profit or margin?

    Returns a DataFrame with the exact requirement, the requirement rounded up to the slider step, whether it fits the slider
    range and a plain-English difficulty label.
    """
    assert (target_op is None) != (target_margin is None), "give exactly one target"
    r0 = project(f, s)
    util0, real0 = r0["util0"], r0["real0"]
    caps = dict(sim_util=(s["sim_util"], (1.0 - util0) * 100.0), sim_rate=(s["sim_rate"], 30.0), sim_real=(s["sim_real"], (1.0 - real0) * 100.0),
                sim_recov=(s["sim_recov"], 30.0))
    if target_op is not None:
        metric = lambda t: project(f, t)["op1"]; goal = target_op
    else:
        metric = lambda t: margin(project(f, t)); goal = target_margin
    rows = []
    for lever, (lo, hi) in caps.items():
        x = _solve(lambda v: metric({**s, lever: v}), lo, hi, goal)
        rows.append(_goal_row(lever, x, s[lever]))
    # overhead is a "lower is better" lever: search downwards, i.e. maximise -x
    x = _solve(lambda v: metric({**s, "sim_infl": -v}), -s["sim_infl"], 60.0, goal)
    rows.append(_goal_row("sim_infl", None if x is None else -x, s["sim_infl"]))
    return pd.DataFrame(rows)


def _goal_row(lever, x, current):
    lo, hi, step = BOUNDS[lever]
    if x is None:
        return dict(lever=lever, label=LEVER_LABEL[lever], required=None, change=None, apply_value=None, fits_slider=False, difficulty="Not reachable on its own")
    change = x - current
    if abs(change) < 1e-9:
        return dict(lever=lever, label=LEVER_LABEL[lever], required=x, change=0.0, apply_value=current, fits_slider=True, difficulty="Already met")
    rounded = float(np.ceil(x / step - 1e-9) * step) if lever != "sim_infl" else float(np.floor(x / step + 1e-9) * step)
    fits = lo - 1e-9 <= rounded <= hi + 1e-9
    span = (hi - max(current, 0)) if lever != "sim_infl" else (current - lo)
    share = abs(change) / span if span > 0 else 9
    difficulty = "Comfortable" if fits and share <= 0.5 else ("Stretch" if fits else "Beyond a realistic range")
    return dict(lever=lever, label=LEVER_LABEL[lever], required=x, change=change, apply_value=rounded if fits else None, fits_slider=fits, difficulty=difficulty)


# ------------------------------------------------------------ risk and ranking ----
def delivery_range(f, s, levels=(1.0, 0.75, 0.5)):
    """Operating profit if only part of the planned improvement is delivered (setbacks are not softened)."""
    base = project(f, DEFAULTS)
    rows = []
    for d in levels:
        r = project(f, s, delivery=d)
        rows.append(dict(delivery=d, op=r["op1"], margin=margin(r), vs_base=r["op1"] - base["op0"]))
    return pd.DataFrame(rows)


LEVER_TESTS = {"+1 pp utilisation": dict(sim_util=1.0), "+1% rates": dict(sim_rate=1.0), "+1 pp realisation": dict(sim_real=1.0),
               "+5 pp disbursement recovery": dict(sim_recov=5.0), "−1% overheads": dict(sim_infl=-1.0),
               "+1 Associate hire (50% productive)": dict(sim_hires=1, sim_role="Associate", sim_ramp=50), "−1 day to collect (cash, one-off)": None}


def lever_ranking(f, s=None):
    """Annual operating-profit effect of one unit of each lever, measured from the base (not the current scenario)."""
    base_op = project(f, DEFAULTS)["op1"]
    out = []
    for name, t in LEVER_TESTS.items():
        if t is None:
            continue
        out.append((name, project(f, {**DEFAULTS, **t})["op1"] - base_op))
    return sorted(out, key=lambda x: x[1])


def scenario_summary(name, r, s):
    changed = ", ".join(f"{LEVER_LABEL.get(k, k)}={v}" for k, v in s.items() if v != DEFAULTS[k] and k not in ("sim_role", "sim_ramp"))
    if int(s["sim_hires"]):
        changed += f" ({s['sim_role']}, {s['sim_ramp']}% productive)"
    return dict(Scenario=name, Revenue=r["rev1"], Costs=r["cost1"], OperatingProfit=r["op1"], Margin=margin(r), Utilisation=r["util1"], Levers=changed or "none")
