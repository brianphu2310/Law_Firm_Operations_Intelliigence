"""Decision Simulator engine: annual what-if on the last 12 months, goal-seek, delivery-risk range and lever ranking.

Pure functions (no Streamlit) so every number can be unit-tested. Levers are stored in the units the analyst sees:
percentage points (pp), percent, number of hires, days.
"""
import numpy as np
import pandas as pd

from .ref import DEPT_PAY, FIRST_YEAR_BILLING, MARKETING_CHANNELS as MKT, MARKETING_EFFICIENCY, NEW_AREAS, PARALEGAL_LEVERAGE_HOURS

from .metrics import fin_sum, fy_outlook
from .model import GST
from .period import Period
from .ref import AS_OF

ROLES = {"Associate": dict(bill=380, pay=120), "Senior Associate": dict(bill=520, pay=170), "Partner": dict(bill=650, pay=210)}
CURRENT_PLATFORM = "LEAP + InfoTrack (current)"
DEFAULTS = dict(sim_util=0.0, sim_rate=0.0, sim_real=0.0, sim_recov=0.0, sim_infl=0.0, sim_hires=0, sim_role="Associate", sim_ramp=75, sim_dso=0,
                # people: fee earners and support staff leaving (redundancy)
                sim_cut_fe=0, sim_cut_role="Associate", sim_keep_work=30, sim_cut_support=0, sim_cut_years=3,
                # a new branch
                sim_branch=False, sim_branch_fe=2, sim_branch_support=2, sim_branch_rent=8000, sim_branch_fitout=120000, sim_branch_ramp=12,
                # practice-management platform
                sim_platform=CURRENT_PLATFORM,
                # where a new fee earner works, support staff by department, pay review
                sim_hire_area="Firm mix", sim_support_dept="Reception & admin", sim_add_support=0, sim_pay_fe=0.0, sim_pay_support=0.0,
                # marketing and a new matter type
                sim_mkt_channel="Website & SEO", sim_mkt_extra=0, sim_new_area=False, sim_new_area_type="Wills & Estates")
HIRE_OVERHEAD = 9000        # desk, software, insurance and recruitment per new fee earner per year (assumption)
SUPPORT_PAY_MONTH = 5400    # all-in monthly cost of one support-staff member (same figure the model uses for support payroll)
BRANCH_RUNNING = 24000      # utilities, IT, cleaning and insurance of an extra office per year (assumption)
SMALL_BUSINESS = 15         # NES: employers with fewer than 15 employees are generally exempt from redundancy pay
# NES redundancy pay (weeks) by completed years of continuous service; Fair Work Act 2009 s 119
NES_REDUNDANCY_WEEKS = [(1, 4), (2, 6), (3, 7), (4, 8), (5, 10), (6, 11), (7, 13), (8, 14), (9, 16), (10, 12)]
# NES minimum notice (weeks); s 117. Over-45s with 2+ years get one more week (not modelled)
NES_NOTICE_WEEKS = [(1, 1), (3, 2), (5, 3)]
LTM_DAYS = 352              # length of the "last 12 months" window (1 Oct 24 – 17 Sep 25) in days
HOURS_PER_MONTH = 190

# slider ranges (min, max, step) used by the page; goal-seek reports whether a required change fits inside them
BOUNDS = dict(sim_util=(-10.0, 10.0, 0.5), sim_rate=(0.0, 10.0, 0.5), sim_real=(-5.0, 5.0, 0.5), sim_recov=(-10.0, 10.0, 1.0),
              sim_infl=(-10.0, 10.0, 0.5), sim_hires=(0, 3, 1), sim_ramp=(40, 100, 5), sim_dso=(-15, 15, 1),
              sim_cut_fe=(0, 2, 1), sim_keep_work=(0, 80, 10), sim_cut_support=(0, 4, 1), sim_cut_years=(0, 15, 1),
              sim_branch_fe=(1, 3, 1), sim_branch_support=(1, 4, 1), sim_branch_rent=(4000, 15000, 500), sim_branch_fitout=(40000, 250000, 10000),
              sim_branch_ramp=(3, 24, 3), sim_add_support=(0, 3, 1), sim_pay_fe=(-5.0, 10.0, 0.5), sim_pay_support=(-5.0, 10.0, 0.5),
              sim_mkt_extra=(0, 10000, 500))
LEVER_LABEL = dict(sim_util="Utilisation (pp)", sim_rate="Rate increase (%)", sim_real="Realisation (pp)", sim_recov="Disbursement recovery (pp)",
                   sim_infl="Overhead change (%)", sim_hires="New fee earners", sim_ramp="Year-one productivity of a new hire", sim_dso="Days to collect",
                   sim_cut_fe="Fee earners leaving", sim_keep_work="Work kept by the team (%)", sim_cut_support="Support roles cut", sim_cut_years="Years of service",
                   sim_branch="New branch", sim_branch_fe="Branch fee earners", sim_branch_support="Branch support staff", sim_branch_rent="Branch rent / month",
                   sim_branch_fitout="Branch fit-out", sim_branch_ramp="Months to full productivity", sim_platform="Platform",
                   sim_hire_area="Hire for", sim_support_dept="Department", sim_add_support="Support staff added", sim_pay_fe="Fee-earner pay change (%)",
                   sim_pay_support="Support pay change (%)", sim_mkt_channel="Marketing channel", sim_mkt_extra="Extra marketing a month",
                   sim_new_area="New matter type", sim_new_area_type="Matter type")

PRESETS = {
    "Hire an associate": dict(sim_hires=1, sim_role="Associate", sim_ramp=60),
    "Raise rates 5%": dict(sim_rate=5.0),
    "Lift utilisation +3 pp": dict(sim_util=3.0),
    "Collect 7 days faster": dict(sim_dso=-7),
    "Cut overheads 5%": dict(sim_infl=-5.0),
    "Pay rise 3%": dict(sim_pay_fe=3.0, sim_pay_support=3.0),
    "Cut 2 support roles": dict(sim_cut_support=2, sim_cut_years=3, sim_support_dept="Reception & admin"),
    "More marketing": dict(sim_mkt_channel="Website & SEO", sim_mkt_extra=3000),
    "Open a new matter type": dict(sim_new_area=True, sim_new_area_type="Wills & Estates"),
    "Open a branch": dict(sim_branch=True),
    "Switch platform": dict(sim_platform="Smokeball + GlobalX"),
    "Downturn": dict(sim_util=-5.0, sim_infl=3.0),
}
PRESET_SHORT = {"Hire an associate": "Hire 1", "Raise rates 5%": "Rates +5%", "Lift utilisation +3 pp": "Util +3 pp", "Collect 7 days faster": "Collect faster",
                "Cut overheads 5%": "Costs −5%", "Cut 2 support roles": "Cut 2 support", "Open a branch": "New branch", "Switch platform": "Switch system", "Downturn": "Downturn",
                "Pay rise 3%": "Pay +3%", "More marketing": "Mktg +$3K", "Open a new matter type": "New service"}
PRESET_HELP = {"Hire an associate": "One associate, 60% as busy as the firm average in year one", "Raise rates 5%": "5% across the board", "Lift utilisation +3 pp": "Three more points of billable time",
               "Collect 7 days faster": "DSO down by a week (one-off cash release)", "Cut overheads 5%": "5% off non-payroll, non-disbursement costs",
               "Cut 2 support roles": "Two reception/admin roles made redundant after 3 years' service: NES redundancy and notice pay are paid once",
               "Pay rise 3%": "3% for fee earners and support staff, just under market wage growth",
               "More marketing": "An extra $3,000 a month on Website & SEO, the cheapest channel per new matter",
               "Open a new matter type": "Wills & Estates: one associate, $25K launch campaign, full speed after 12 months",
               "Open a branch": "Two associates and two support staff, $8,000 a month rent, $120K fit-out, full productivity after 12 months",
               "Switch platform": "Move from LEAP + InfoTrack to Smokeball + GlobalX, the top-ranked platform on the evaluation pages",
               "Downturn": "Utilisation −5 pp and overheads +3%"}


def _weeks(table, years):
    """Look up an NES table: the last row whose service threshold the employee has reached (0 if none)."""
    out = 0
    for threshold, weeks in table:
        if years >= threshold:
            out = weeks
    return out


def redundancy_weeks(years, headcount):
    """NES redundancy pay in weeks; none for a small-business employer (fewer than 15 employees) or under one year of service."""
    return 0 if headcount < SMALL_BUSINESS else _weeks(NES_REDUNDANCY_WEEKS, years)


def notice_weeks(years):
    return 1 if years <= 1 else (2 if years <= 3 else (3 if years <= 5 else 4))


def ramp_average(ramp_months, months=12):
    """Average productivity over the first `months` when productivity rises in a straight line to 100% at `ramp_months`."""
    return float(np.mean([min(1.0, m / ramp_months) for m in range(1, months + 1)]))


def context(M):
    """Firm facts the engine needs that are not in the 12-month P&L: headcount and the first-year effect of each platform."""
    from . import platforms as P
    from .ref import ATTORNEYS, BRANCHES
    inp = P.base_inputs(M)
    plat = {CURRENT_PLATFORM: dict(annual=0.0, one_off=0.0)}
    for n in P.NAMES:
        if n == P.BASELINE:
            continue
        cf, _ = P.cashflow(n, inp)
        y1 = cf[cf["t"] < 12]
        plat[n] = dict(annual=float((y1["benefit"] - y1["incr_cost"]).sum()), one_off=float(y1["one_off"].sum()))
    support = sum(b["support"] for b in BRANCHES)
    from . import metrics as X
    pa = X.practice_area_table(M)
    mk = X.marketing_table(M)
    firm_rate = float(pa["fees"].sum() / pa["hours"].sum())
    firm_util = float((pa["util"] * pa["hours"]).sum() / pa["hours"].sum())
    # a hire in an area earns that area's effective rate and is as busy as the lawyers already doing the work
    areas = {a: dict(realisation=float(r["realisation"]), util=float(r["util"]), growth=float(r["matters_growth"]), verdict=r["verdict"],
                     factor=(float(r["eff_rate"]) / firm_rate) * (float(r["util"]) / firm_util)) for a, r in pa.iterrows()}
    mkt = {c: dict(cost_per_inquiry=float(r["cost_per_inquiry"]), conversion=float(r["conversion"]), fee_per_matter=mk.attrs["fee_per_matter"] * MKT[c]["value"],
                   spend=float(r["spend"]))
           for c, r in mk.iterrows()}
    return dict(platforms=plat, headcount=len(ATTORNEYS) + support, support=support, areas=areas, marketing=mkt, top_area=pa.index[0])


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
    t["sim_keep_work"] = t.get("sim_keep_work", 0) * delivery    # work the team absorbs after someone leaves is not guaranteed
    t["_bdeliv"] = delivery                                      # a new branch's, matter type's or campaign's fees are; their costs are not
    return t


def project(f, s, delivery=1.0, ctx=None):
    """Annualised P&L under the scenario. f = last-12-month actuals (fin_sum Series); s = lever values; ctx = context(M) for
    headcount and platform effects (without it a platform switch has no effect and redundancy pay assumes a 25-person firm)."""
    s = {**DEFAULTS, **s}
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
    # fee earners leaving: their hours go, except the share of their work the rest of the team picks up (billed at the firm's mix)
    cut_n, cut_role, keep = int(s["sim_cut_fe"]), ROLES[s["sim_cut_role"]], s["sim_keep_work"] / 100.0
    cut_hours = cut_n * HOURS_PER_MONTH * 12 * util1
    kept_hours = cut_hours * keep
    fees_cut = cut_hours * cut_role["bill"] * rate_up * real1 - kept_hours * std_rate0 * rate_up * real1
    # a new branch: associates ramping up to the firm's utilisation
    br = bool(s["sim_branch"])
    br_fe, br_sup = (int(s["sim_branch_fe"]), int(s["sim_branch_support"])) if br else (0, 0)
    br_prod = ramp_average(s["sim_branch_ramp"]) * s.get("_bdeliv", 1.0)
    br_role = ROLES["Associate"]
    br_hours = br_fe * HOURS_PER_MONTH * 12 * util1 * br_prod
    fees_branch = br_hours * br_role["bill"] * rate_up * real1
    fees_core = hours1 * std_rate0 * rate_up * real1
    areas = (ctx or {}).get("areas") or {}
    area_factor = areas[s["sim_hire_area"]]["factor"] if s["sim_hire_area"] in areas else 1.0
    real_hire = real1
    fees_hire = hire_hours * role["bill"] * rate_up * real1 * area_factor
    deliv = s.get("_bdeliv", 1.0)
    # support staff added: a paralegal frees fee-earner time that can be billed (others add capacity, not fees)
    add_n, dept = int(s["sim_add_support"]), s["sim_support_dept"]
    para_hours = add_n * PARALEGAL_LEVERAGE_HOURS * deliv if dept == "Paralegals & clerks" else 0.0
    fees_para = para_hours * std_rate0 * rate_up * real1
    # extra marketing: inquiries at the channel's cost, with diminishing returns; matters arrive through the year (half billed in year one)
    mk = ((ctx or {}).get("marketing") or {}).get(s["sim_mkt_channel"])
    mkt_spend = float(s["sim_mkt_extra"]) * 12
    if mk and mkt_spend:
        saturation = 1.0 / (1.0 + mkt_spend / mk["spend"])          # each extra dollar works less hard as spend grows past today's level
        mkt_inq = mkt_spend * MARKETING_EFFICIENCY * saturation / mk["cost_per_inquiry"]
        mkt_matters = mkt_inq * mk["conversion"]
        fees_mkt = mkt_matters * mk["fee_per_matter"] * FIRST_YEAR_BILLING * deliv
    else:
        mkt_inq = mkt_matters = fees_mkt = 0.0
    mkt_hours = fees_mkt / (std_rate0 * rate_up * real1)
    # the existing team can only take the new work up to 95% utilisation; beyond that it needs a hire
    spare = max(0.0, 0.95 * f["capacity"] * k - (hours1 + kept_hours + para_hours))
    mkt_capped = mkt_hours > spare
    if mkt_capped:
        fees_mkt *= spare / mkt_hours
        mkt_hours = spare
    # a new matter type: matters ramp up in a straight line to the mature rate
    na = NEW_AREAS[s["sim_new_area_type"]] if s["sim_new_area"] else None
    if na:
        na_role = ROLES[na["role"]]
        fees_na = sum(min(1.0, m / na["ramp"]) for m in range(1, 13)) * na["mature"] * na["fee"] * deliv
        na_cost = na_role["pay"] * HOURS_PER_MONTH * 12 + HIRE_OVERHEAD + na["support"] * DEPT_PAY["Paralegals & clerks"] * 12 + na["monthly"] * 12
        na_hours = fees_na / (na_role["bill"] * real1)
        na_full = na["mature"] * na["fee"] * 12 - na_cost
        na_payback, cum = None, -float(na["launch"])
        for m in range(1, 61):
            cum += na["mature"] * na["fee"] * min(1.0, m / na["ramp"]) * deliv - na_cost / 12
            if cum >= 0:
                na_payback = m
                break
    else:
        fees_na = na_cost = na_hours = na_full = 0.0
        na_payback = None
    fees1 = fees_core + fees_hire + fees_branch - fees_cut + fees_para + fees_mkt + fees_na
    hrs_ratio = (hours1 + hire_hours + br_hours - cut_hours + kept_hours + para_hours + mkt_hours + na_hours) / hours0
    disb_cost1 = f["disb_cost"] * k * hrs_ratio
    disb_bill1 = disb_cost1 * (f["disb_billed"] / f["disb_cost"] + s["sim_recov"] / 100.0)
    rev0, rev1 = (f["fees"] + f["disb_billed"]) * k, fees1 + disb_bill1
    over0 = (f["total_costs"] - f["payroll_fee"] - f["disb_cost"]) * k
    cost0 = f["total_costs"] * k
    hire_cost = hires * (role["pay"] * HOURS_PER_MONTH * 12 + HIRE_OVERHEAD)
    # people leaving: pay saved every year; NES redundancy and notice pay once
    headcount = (ctx or {}).get("headcount", 25)
    years = s["sim_cut_years"]
    cut_fe_saving = cut_n * (cut_role["pay"] * HOURS_PER_MONTH * 12 + HIRE_OVERHEAD)
    sup_n = int(s["sim_cut_support"])
    dept_pay = DEPT_PAY.get(dept, SUPPORT_PAY_MONTH)
    sup_saving = sup_n * dept_pay * 12
    add_cost = add_n * (dept_pay * 12 + 3000)                       # pay plus a desk, phone and software
    wk_fe, wk_sup = cut_role["pay"] * HOURS_PER_MONTH * 12 / 52, dept_pay * 12 / 52
    red_weeks, notice = redundancy_weeks(years, headcount), notice_weeks(years)
    redundancy = (cut_n * wk_fe + sup_n * wk_sup) * red_weeks
    notice_pay = (cut_n * wk_fe + sup_n * wk_sup) * notice
    # new branch costs (fit-out is capital: cash, not operating profit)
    br_cost = (br_fe * (br_role["pay"] * HOURS_PER_MONTH * 12 + HIRE_OVERHEAD) + br_sup * SUPPORT_PAY_MONTH * 12 + s["sim_branch_rent"] * 12 + BRANCH_RUNNING) if br else 0.0
    br_fitout = float(s["sim_branch_fitout"]) if br else 0.0
    # platform: first-year benefit less extra running cost, and the one-off migration
    pl = ((ctx or {}).get("platforms") or {}).get(s["sim_platform"], dict(annual=0.0, one_off=0.0))
    # pay review on the existing team (people leaving or joining are priced at today's rates)
    pay_fe = (f["payroll_fee"] * k) * s["sim_pay_fe"] / 100.0
    pay_sup = (f["payroll_support"] * k) * s["sim_pay_support"] / 100.0
    cost1 = (f["payroll_fee"] * k + hires * role["pay"] * HOURS_PER_MONTH * 12 + disb_cost1 + over0 * (1 + s["sim_infl"] / 100.0) + hires * HIRE_OVERHEAD
             - cut_fe_saving - sup_saving + add_cost + br_cost - pl["annual"] + pay_fe + pay_sup + mkt_spend + na_cost)
    hire_full_fees = HOURS_PER_MONTH * 12 * util1 * role["bill"] * rate_up * real1          # one hire at 100% of firm utilisation
    br_month_cost = br_cost / 12
    br_full_month = br_fe * HOURS_PER_MONTH * util1 * br_role["bill"] * rate_up * real1 * s.get("_bdeliv", 1.0)
    br_payback = None
    if br:                                                         # months until the branch has earned back its fit-out
        cum = -br_fitout
        for m in range(1, 61):
            cum += br_full_month * min(1.0, m / s["sim_branch_ramp"]) - br_month_cost
            if cum >= 0:
                br_payback = m
                break
    dso_cash = -s["sim_dso"] * rev1 * (1 + GST) / 365.0                                     # slower payment (+days) ties up cash → negative
    na_launch = float(na["launch"]) if na else 0.0
    one_off = redundancy + notice_pay + br_fitout + pl["one_off"] + na_launch
    hours_tot = hours1 + hire_hours + br_hours - cut_hours + kept_hours + para_hours + mkt_hours + na_hours
    return dict(rev0=rev0, rev1=rev1, cost0=cost0, cost1=cost1, op0=rev0 - cost0, op1=rev1 - cost1, fees0=fees0, fees1=fees1,
                hours0=hours0, hours1=hours_tot, util0=util0, util1=util1, eff0=fees0 / hours0, eff1=fees1 / hours_tot,
                real0=real0, real1=real1, over0=over0, hire_fees=fees_hire, hire_cost=hire_cost, hire_net=fees_hire - hire_cost,
                hire_breakeven_ramp=(hire_cost / hires) / hire_full_fees if hires else None,
                cut_fees_lost=fees_cut, cut_saving=cut_fe_saving, support_saving=sup_saving, redundancy=redundancy, notice_pay=notice_pay,
                redundancy_weeks=red_weeks, notice_weeks=notice, small_business=headcount < SMALL_BUSINESS, headcount=headcount,
                branch_fees=fees_branch, branch_cost=br_cost, branch_net=fees_branch - br_cost, branch_fitout=br_fitout, branch_payback=br_payback,
                branch_net_full=(br_full_month - br_month_cost) * 12 if br else 0.0,
                platform_annual=pl["annual"], platform_one_off=pl["one_off"],
                hire_realisation=real_hire, support_added_cost=add_cost, paralegal_fees=fees_para, pay_cost=pay_fe + pay_sup,
                mkt_spend=mkt_spend, mkt_inquiries=mkt_inq, mkt_matters=mkt_matters, mkt_fees=fees_mkt, mkt_capped=mkt_capped, hire_area_factor=area_factor,
                area_fees=fees_na, area_cost=na_cost, area_net=fees_na - na_cost, area_net_full=na_full, area_payback=na_payback, area_launch=na_launch,
                team_util=(hours1 + kept_hours + para_hours + mkt_hours) / (f["capacity"] * k - cut_n * HOURS_PER_MONTH * 12),
                dso_cash=dso_cash, one_off=one_off, cash_effect=dso_cash - one_off)


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


def goal_seek(f, s, target_op=None, target_margin=None, ctx=None):
    """For each single lever: how far must it move (on top of the current scenario) to reach a target operating profit or margin?

    Returns a DataFrame with the exact requirement, the requirement rounded up to the slider step, whether it fits the slider
    range and a plain-English difficulty label.
    """
    assert (target_op is None) != (target_margin is None), "give exactly one target"
    r0 = project(f, s, ctx=ctx)
    util0, real0 = r0["util0"], r0["real0"]
    caps = dict(sim_util=(s["sim_util"], (1.0 - util0) * 100.0), sim_rate=(s["sim_rate"], 30.0), sim_real=(s["sim_real"], (1.0 - real0) * 100.0),
                sim_recov=(s["sim_recov"], 30.0))
    if target_op is not None:
        metric = lambda t: project(f, t, ctx=ctx)["op1"]; goal = target_op
    else:
        metric = lambda t: margin(project(f, t, ctx=ctx)); goal = target_margin
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
def delivery_range(f, s, levels=(1.0, 0.75, 0.5), ctx=None):
    """Operating profit if only part of the planned improvement is delivered (setbacks are not softened)."""
    base = project(f, DEFAULTS, ctx=ctx)
    rows = []
    for d in levels:
        r = project(f, s, delivery=d, ctx=ctx)
        rows.append(dict(delivery=d, op=r["op1"], margin=margin(r), vs_base=r["op1"] - base["op0"]))
    return pd.DataFrame(rows)


LEVER_TESTS = {"+1 pp utilisation": dict(sim_util=1.0), "+1% rates": dict(sim_rate=1.0), "+1 pp realisation": dict(sim_real=1.0),
               "+1% pay, everyone": dict(sim_pay_fe=1.0, sim_pay_support=1.0),
               "+5 pp disbursement recovery": dict(sim_recov=5.0), "−1% overheads": dict(sim_infl=-1.0),
               "+1 Associate hire (50% productive)": dict(sim_hires=1, sim_role="Associate", sim_ramp=50), "−1 support role": dict(sim_cut_support=1),
               "−1 day to collect (cash, one-off)": None}


def lever_ranking(f, s=None, ctx=None):
    """Annual operating-profit effect of one unit of each lever, measured from the base (not the current scenario)."""
    base_op = project(f, DEFAULTS, ctx=ctx)["op1"]
    out = []
    for name, t in LEVER_TESTS.items():
        if t is None:
            continue
        out.append((name, project(f, {**DEFAULTS, **t}, ctx=ctx)["op1"] - base_op))
    return sorted(out, key=lambda x: x[1])


DETAIL_KEYS = ("sim_role", "sim_ramp", "sim_cut_role", "sim_keep_work", "sim_cut_years", "sim_branch_fe", "sim_branch_support", "sim_branch_rent",
               "sim_branch_fitout", "sim_branch_ramp", "sim_hire_area", "sim_support_dept", "sim_mkt_channel", "sim_new_area_type")


def rate_to_fund(f, s, ctx=None):
    """Rate increase (percentage points on top of the current one) that keeps operating profit where it would be without the pay review."""
    target = project(f, {**s, "sim_pay_fe": 0.0, "sim_pay_support": 0.0}, ctx=ctx)["op1"]
    x = _solve(lambda v: project(f, {**s, "sim_rate": v}, ctx=ctx)["op1"], s["sim_rate"], 30.0, target)
    return None if x is None else x - s["sim_rate"]


def scenario_summary(name, r, s):
    changed = ", ".join(f"{LEVER_LABEL.get(k, k)}={v}" for k, v in s.items() if k in DEFAULTS and v != DEFAULTS[k] and k not in DETAIL_KEYS)
    if int(s["sim_hires"]):
        changed += f" ({s['sim_role']}, {s['sim_ramp']}% productive)"
    return dict(Scenario=name, Revenue=r["rev1"], Costs=r["cost1"], OperatingProfit=r["op1"], Margin=margin(r), Utilisation=r["util1"],
                OneOff=r["one_off"], Levers=changed or "none")
