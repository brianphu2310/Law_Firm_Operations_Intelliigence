"""The Decision Simulator written once as a formula spec, then turned into DAX (for Power BI) and evaluated in Python (to test it).

Why: Power BI cannot run the Python engine (core/simulate.py). Rewriting ~100 formulas in DAX by hand would be easy to get wrong
and impossible to test without Power BI. Instead every formula below is a small Python expression. `evaluate()` runs them in
Python and tests/test_powerbi.py checks the result against core.simulate.project for every preset and hundreds of random lever
mixes. `to_dax()` translates the same expressions to one DAX measure (a chain of VARs, each formula computed once).

Expression language (a safe subset of Python syntax, parsed with `ast`):
  numbers, names of levers / constants / earlier formulas, + - * /, comparisons, `and` / `or`, string literals and
  iff(cond, a, b)       if-then-else                     min(a, b) / max(a, b)
  lk('Table', 'Col', lever)   value of Col in a lookup table, on the row the categorical lever selects
  ramp_sum(m, R)        sum over i = 1..m of min(1, i / R): productivity that rises in a straight line to 100% at month R
  payback(L, F, R, C)   first month (1-60) at which -L + sum of (F x ramp(i) - C) turns positive; blank if never
  nes_redundancy(y)     NES redundancy weeks for y completed years of service (Fair Work Act s 119)
  blank()               no value (DAX BLANK, Python None)
"""
from __future__ import annotations

import ast
import math
from dataclasses import dataclass, field

from core import simulate as S
from core.ref import DEPT_PAY, FIRST_YEAR_BILLING, MARKETING_EFFICIENCY, NEW_AREAS, PARALEGAL_LEVERAGE_HOURS
from core.model import GST


# ----------------------------------------------------------------------------------------------------------- levers ----
@dataclass
class Lever:
    key: str               # name in core.simulate (sim_rate ...)
    label: str             # slicer header in the report
    kind: str              # num | bool | cat
    table: str             # slicer table in the model
    lo: float = 0
    hi: float = 0
    step: float = 1
    options: list = field(default_factory=list)
    fmt: str = "0.0"

    @property
    def default(self):
        return S.DEFAULTS[self.key]

    @property
    def var(self):
        return "L_" + self.key[4:]


def _num(key, table, fmt="0.0"):
    lo, hi, step = S.BOUNDS[key]
    return Lever(key, S.LEVER_LABEL[key], "num", table, lo, hi, step, fmt=fmt)


def build_levers(ctx):
    areas = ["Firm mix"] + list(ctx["areas"])
    return [
        _num("sim_util", "L Utilisation"), _num("sim_rate", "L Rates"), _num("sim_real", "L Realisation"),
        _num("sim_recov", "L Recovery", "0"), _num("sim_infl", "L Overheads"), _num("sim_dso", "L Days to collect", "0"),
        _num("sim_hires", "L Hires", "0"), Lever("sim_role", "Role of the hire", "cat", "L Hire role", options=list(S.ROLES)),
        _num("sim_ramp", "L Hire productivity", "0"), Lever("sim_hire_area", "Hire for", "cat", "L Hire area", options=areas),
        _num("sim_cut_fe", "L Fee earners leaving", "0"), Lever("sim_cut_role", "Role leaving", "cat", "L Leaving role", options=list(S.ROLES)),
        _num("sim_keep_work", "L Work kept", "0"), _num("sim_cut_support", "L Support cut", "0"), _num("sim_cut_years", "L Years of service", "0"),
        Lever("sim_support_dept", "Department", "cat", "L Department", options=list(DEPT_PAY)),
        _num("sim_add_support", "L Support added", "0"), _num("sim_pay_fe", "L Fee-earner pay"), _num("sim_pay_support", "L Support pay"),
        Lever("sim_mkt_channel", "Marketing channel", "cat", "L Channel", options=list(ctx["marketing"])), _num("sim_mkt_extra", "L Extra marketing", "$#,0"),
        Lever("sim_new_area", "New matter type", "bool", "L New matter type on"), Lever("sim_new_area_type", "Matter type", "cat", "L Matter type", options=list(NEW_AREAS)),
        Lever("sim_branch", "New branch", "bool", "L New branch on"), _num("sim_branch_fe", "L Branch fee earners", "0"),
        _num("sim_branch_support", "L Branch support", "0"), _num("sim_branch_rent", "L Branch rent", "$#,0"),
        _num("sim_branch_fitout", "L Branch fit-out", "$#,0"), _num("sim_branch_ramp", "L Branch ramp-up", "0"),
        Lever("sim_platform", "Platform", "cat", "L Platform", options=list(ctx["platforms"])),
    ]


# ------------------------------------------------------------------------------------------------- constants & tables --
def build_constants(f, ctx, bt, cash_now, low0, min_cash):
    k = 365.0 / S.LTM_DAYS
    return dict(
        K=k, H0=f["hours"] * k, F0=f["fees"] * k, V0=f["value_std"] * k, UTIL0=f["hours"] / f["capacity"], REAL0=f["fees"] / f["value_std"],
        STD0=f["value_std"] / f["hours"], CAP=f["capacity"], DISB_COST=f["disb_cost"], DISB_BILLED=f["disb_billed"], TOTAL=f["total_costs"],
        PAYF=f["payroll_fee"], PAYS=f["payroll_support"], FEES_RAW=f["fees"], HPM=S.HOURS_PER_MONTH, HIRE_OH=S.HIRE_OVERHEAD,
        SUP_PAY=S.SUPPORT_PAY_MONTH, BR_RUN=S.BRANCH_RUNNING, SMALL_BIZ=S.SMALL_BUSINESS, HEADCOUNT=ctx["headcount"],
        PARA_H=PARALEGAL_LEVERAGE_HOURS, PARA_PAY=DEPT_PAY["Paralegals & clerks"], MKT_EFF=MARKETING_EFFICIENCY, FYB=FIRST_YEAR_BILLING,
        GST=GST, ASSOC_BILL=S.ROLES["Associate"]["bill"], ASSOC_PAY=S.ROLES["Associate"]["pay"],
        BUDGET_OP=bt["op"], BUDGET_MARGIN=bt["margin"], CASH_NOW=cash_now, LOW0=low0, MIN_CASH=min_cash,
    )


def build_tables(ctx):
    """Lookup tables the formulas read with lk(). key column first."""
    t = {}
    t["Sim Role"] = dict(key="Role", cols=["Bill", "Pay"], rows=[[r, v["bill"], v["pay"]] for r, v in S.ROLES.items()])
    t["Sim Area"] = dict(key="Area", cols=["Factor"], rows=[["Firm mix", 1.0]] + [[a, v["factor"]] for a, v in ctx["areas"].items()])
    t["Sim Department"] = dict(key="Department", cols=["Pay"], rows=[[d, p] for d, p in DEPT_PAY.items()])
    t["Sim Channel"] = dict(key="Channel", cols=["Spend", "CostPerInquiry", "Conversion", "FeePerMatter"],
                            rows=[[c, v["spend"], v["cost_per_inquiry"], v["conversion"], v["fee_per_matter"]] for c, v in ctx["marketing"].items()])
    t["Sim Platform"] = dict(key="Platform", cols=["Annual", "OneOff"], rows=[[p, v["annual"], v["one_off"]] for p, v in ctx["platforms"].items()])
    t["Sim New Area"] = dict(key="MatterType", cols=["Fee", "Mature", "Ramp", "Support", "Monthly", "Launch", "Bill", "Pay"],
                             rows=[[n, v["fee"], v["mature"], v["ramp"], v["support"], v["monthly"], v["launch"], S.ROLES[v["role"]]["bill"],
                                    S.ROLES[v["role"]]["pay"]] for n, v in NEW_AREAS.items()])
    return t


# ----------------------------------------------------------------------------------------------------------- formulas --
# (name, expression). Order matters: a formula may only use levers, constants and formulas above it.
# Mirrors core/simulate.py project() line by line; see that file for the reasoning behind each assumption.
FORMULAS = [
    # delivery: only the uncertain improvements are cut back (core.simulate.haircut)
    ("e_util", "iff(L_util > 0, L_util * D, L_util)"),
    ("e_rate", "iff(L_rate > 0, L_rate * D, L_rate)"),
    ("e_real", "iff(L_real > 0, L_real * D, L_real)"),
    ("e_recov", "iff(L_recov > 0, L_recov * D, L_recov)"),
    ("e_infl", "iff(L_infl < 0, L_infl * D, L_infl)"),
    ("e_ramp", "iff(L_hires > 0, L_ramp * D, L_ramp)"),
    ("e_keep", "L_keep_work * D"),
    # existing team
    ("util1", "UTIL0 + e_util / 100"),
    ("real1", "REAL0 + e_real / 100"),
    ("rate_up", "1 + e_rate / 100"),
    ("hours1", "H0 * util1 / UTIL0"),
    ("fees_core", "hours1 * STD0 * rate_up * real1"),
    # hires
    ("role_bill", "lk('Sim Role', 'Bill', L_role)"),
    ("role_pay", "lk('Sim Role', 'Pay', L_role)"),
    ("area_factor", "lk('Sim Area', 'Factor', L_hire_area)"),
    ("hire_hours", "L_hires * HPM * 12 * util1 * e_ramp / 100"),
    ("fees_hire", "hire_hours * role_bill * rate_up * real1 * area_factor"),
    # people leaving
    ("cut_bill", "lk('Sim Role', 'Bill', L_cut_role)"),
    ("cut_pay", "lk('Sim Role', 'Pay', L_cut_role)"),
    ("cut_hours", "L_cut_fe * HPM * 12 * util1"),
    ("kept_hours", "cut_hours * e_keep / 100"),
    ("fees_cut", "cut_hours * cut_bill * rate_up * real1 - kept_hours * STD0 * rate_up * real1"),
    # new branch
    ("br_fe", "iff(L_branch > 0, L_branch_fe, 0)"),
    ("br_sup", "iff(L_branch > 0, L_branch_support, 0)"),
    ("br_prod", "ramp_sum(12, L_branch_ramp) / 12 * D"),
    ("br_hours", "br_fe * HPM * 12 * util1 * br_prod"),
    ("fees_branch", "br_hours * ASSOC_BILL * rate_up * real1"),
    # support staff added
    ("dept_pay", "lk('Sim Department', 'Pay', L_support_dept)"),
    ("para_hours", "iff(L_support_dept == 'Paralegals & clerks', L_add_support * PARA_H * D, 0)"),
    ("fees_para", "para_hours * STD0 * rate_up * real1"),
    # marketing
    ("ch_spend", "lk('Sim Channel', 'Spend', L_mkt_channel)"),
    ("ch_cpi", "lk('Sim Channel', 'CostPerInquiry', L_mkt_channel)"),
    ("ch_conv", "lk('Sim Channel', 'Conversion', L_mkt_channel)"),
    ("ch_fpm", "lk('Sim Channel', 'FeePerMatter', L_mkt_channel)"),
    ("mkt_spend", "L_mkt_extra * 12"),
    ("mkt_inq", "iff(mkt_spend > 0, mkt_spend * MKT_EFF / (1 + mkt_spend / ch_spend) / ch_cpi, 0)"),
    ("mkt_matters", "mkt_inq * ch_conv"),
    ("fees_mkt_raw", "mkt_matters * ch_fpm * FYB * D"),
    ("mkt_hours_raw", "fees_mkt_raw / (STD0 * rate_up * real1)"),
    ("spare", "max(0, 0.95 * CAP * K - (hours1 + kept_hours + para_hours))"),
    ("mkt_capped", "iff(mkt_hours_raw > spare, 1, 0)"),
    ("fees_mkt", "iff(mkt_capped > 0, fees_mkt_raw * spare / mkt_hours_raw, fees_mkt_raw)"),
    ("mkt_hours", "iff(mkt_capped > 0, spare, mkt_hours_raw)"),
    # new matter type
    ("na_on", "iff(L_new_area > 0, 1, 0)"),
    ("na_fee", "lk('Sim New Area', 'Fee', L_new_area_type)"),
    ("na_mature", "lk('Sim New Area', 'Mature', L_new_area_type)"),
    ("na_ramp", "lk('Sim New Area', 'Ramp', L_new_area_type)"),
    ("na_support", "lk('Sim New Area', 'Support', L_new_area_type)"),
    ("na_monthly", "lk('Sim New Area', 'Monthly', L_new_area_type)"),
    ("na_launch_cost", "lk('Sim New Area', 'Launch', L_new_area_type)"),
    ("na_bill", "lk('Sim New Area', 'Bill', L_new_area_type)"),
    ("na_pay", "lk('Sim New Area', 'Pay', L_new_area_type)"),
    ("fees_na", "na_on * ramp_sum(12, na_ramp) * na_mature * na_fee * D"),
    ("na_cost", "na_on * (na_pay * HPM * 12 + HIRE_OH + na_support * PARA_PAY * 12 + na_monthly * 12)"),
    ("na_hours", "fees_na / (na_bill * real1)"),
    ("area_net_full", "na_on * na_mature * na_fee * 12 - na_cost"),
    ("area_payback", "iff(na_on > 0, payback(na_launch_cost, na_mature * na_fee * D, na_ramp, na_cost / 12), blank())"),
    ("area_launch", "na_on * na_launch_cost"),
    # totals: fees, hours, disbursements, revenue
    ("fees1", "fees_core + fees_hire + fees_branch - fees_cut + fees_para + fees_mkt + fees_na"),
    ("hours_tot", "hours1 + hire_hours + br_hours - cut_hours + kept_hours + para_hours + mkt_hours + na_hours"),
    ("disb_cost1", "DISB_COST * K * hours_tot / H0"),
    ("disb_bill1", "disb_cost1 * (DISB_BILLED / DISB_COST + e_recov / 100)"),
    ("rev0", "(FEES_RAW + DISB_BILLED) * K"),
    ("rev1", "fees1 + disb_bill1"),
    ("over0", "(TOTAL - PAYF - DISB_COST) * K"),
    ("cost0", "TOTAL * K"),
    # costs of the decisions
    ("hire_cost", "L_hires * (role_pay * HPM * 12 + HIRE_OH)"),
    ("cut_saving", "L_cut_fe * (cut_pay * HPM * 12 + HIRE_OH)"),
    ("support_saving", "L_cut_support * dept_pay * 12"),
    ("support_added_cost", "L_add_support * (dept_pay * 12 + 3000)"),
    ("wk_fe", "cut_pay * HPM * 12 / 52"),
    ("wk_sup", "dept_pay * 12 / 52"),
    ("redundancy_weeks", "iff(HEADCOUNT < SMALL_BIZ, 0, nes_redundancy(L_cut_years))"),
    ("notice_weeks", "iff(L_cut_years <= 1, 1, iff(L_cut_years <= 3, 2, iff(L_cut_years <= 5, 3, 4)))"),
    ("redundancy", "(L_cut_fe * wk_fe + L_cut_support * wk_sup) * redundancy_weeks"),
    ("notice_pay", "(L_cut_fe * wk_fe + L_cut_support * wk_sup) * notice_weeks"),
    ("branch_cost", "iff(L_branch > 0, br_fe * (ASSOC_PAY * HPM * 12 + HIRE_OH) + br_sup * SUP_PAY * 12 + L_branch_rent * 12 + BR_RUN, 0)"),
    ("branch_fitout", "iff(L_branch > 0, L_branch_fitout, 0)"),
    ("platform_annual", "lk('Sim Platform', 'Annual', L_platform)"),
    ("platform_one_off", "lk('Sim Platform', 'OneOff', L_platform)"),
    ("pay_cost", "PAYF * K * L_pay_fe / 100 + PAYS * K * L_pay_support / 100"),
    ("cost1", "PAYF * K + L_hires * role_pay * HPM * 12 + disb_cost1 + over0 * (1 + e_infl / 100) + L_hires * HIRE_OH - cut_saving"
              " - support_saving + support_added_cost + branch_cost - platform_annual + pay_cost + mkt_spend + na_cost"),
    # results
    ("op0", "rev0 - cost0"),
    ("op1", "rev1 - cost1"),
    ("margin0", "op0 / rev0"),
    ("margin1", "op1 / rev1"),
    ("eff1", "fees1 / hours_tot"),
    ("hire_net", "fees_hire - hire_cost"),
    ("hire_breakeven_ramp", "iff(L_hires > 0, hire_cost / L_hires / (HPM * 12 * util1 * role_bill * rate_up * real1), blank())"),
    ("branch_net", "fees_branch - branch_cost"),
    ("br_full_month", "br_fe * HPM * util1 * ASSOC_BILL * rate_up * real1 * D"),
    ("branch_net_full", "iff(L_branch > 0, (br_full_month - branch_cost / 12) * 12, 0)"),
    ("branch_payback", "iff(L_branch > 0, payback(branch_fitout, br_full_month, L_branch_ramp, branch_cost / 12), blank())"),
    ("area_net", "fees_na - na_cost"),
    ("team_util", "(hours1 + kept_hours + para_hours + mkt_hours) / (CAP * K - L_cut_fe * HPM * 12)"),
    ("dso_cash", "0 - L_dso * rev1 * (1 + GST) / 365"),
    ("one_off", "redundancy + notice_pay + branch_fitout + platform_one_off + area_launch"),
    ("cash_effect", "dso_cash - one_off"),
    ("low1", "LOW0 + cash_effect"),
    ("cash_cover", "(CASH_NOW + cash_effect) / (cost1 / 12)"),
    ("gap_budget", "op1 - BUDGET_OP"),
    ("bridge_fees", "fees1 - F0"),
    ("bridge_disb", "(rev1 - fees1) - (rev0 - F0)"),
    ("bridge_costs", "0 - (cost1 - cost0)"),
]
NAMES = [n for n, _ in FORMULAS]
# outputs that core.simulate.project returns under the same name (checked in tests)
PROJECT_KEYS = {"rev0": "rev0", "rev1": "rev1", "cost0": "cost0", "cost1": "cost1", "op0": "op0", "op1": "op1", "fees1": "fees1",
                "hours_tot": "hours1", "util1": "util1", "real1": "real1", "eff1": "eff1", "hire_net": "hire_net",
                "hire_breakeven_ramp": "hire_breakeven_ramp", "fees_cut": "cut_fees_lost", "cut_saving": "cut_saving",
                "support_saving": "support_saving", "redundancy": "redundancy", "notice_pay": "notice_pay",
                "redundancy_weeks": "redundancy_weeks", "notice_weeks": "notice_weeks", "fees_branch": "branch_fees",
                "branch_cost": "branch_cost", "branch_net": "branch_net", "branch_fitout": "branch_fitout", "branch_payback": "branch_payback",
                "branch_net_full": "branch_net_full", "platform_annual": "platform_annual", "platform_one_off": "platform_one_off",
                "support_added_cost": "support_added_cost", "fees_para": "paralegal_fees", "pay_cost": "pay_cost", "mkt_spend": "mkt_spend",
                "mkt_inq": "mkt_inquiries", "mkt_matters": "mkt_matters", "fees_mkt": "mkt_fees", "mkt_capped": "mkt_capped",
                "area_factor": "hire_area_factor", "fees_na": "area_fees", "na_cost": "area_cost", "area_net": "area_net",
                "area_net_full": "area_net_full", "area_payback": "area_payback", "area_launch": "area_launch", "team_util": "team_util",
                "dso_cash": "dso_cash", "one_off": "one_off", "cash_effect": "cash_effect", "fees_hire": "hire_fees", "hire_cost": "hire_cost"}


# ------------------------------------------------------------------------------------------------------ evaluation ---
def ramp_sum(m, R):
    n = min(m, math.floor(R))
    return n * (n + 1) / (2 * R) + (m - n)


def payback(L, F, R, C):
    for m in range(1, 61):
        if -L + F * ramp_sum(m, R) - C * m >= 0:
            return m
    return None


def nes_redundancy(y):
    return S._weeks(S.NES_REDUNDANCY_WEEKS, y)


class _Eval(ast.NodeVisitor):
    def __init__(self, env, tables):
        self.env, self.tables = env, tables

    def visit_Expression(self, n):
        return self.visit(n.body)

    def visit_Constant(self, n):
        return n.value

    def visit_Name(self, n):
        return self.env[n.id]

    def visit_UnaryOp(self, n):
        v = self.visit(n.operand)
        return -v if isinstance(n.op, ast.USub) else v

    def visit_BinOp(self, n):
        a, b = self.visit(n.left), self.visit(n.right)
        op = type(n.op)
        return {ast.Add: lambda: a + b, ast.Sub: lambda: a - b, ast.Mult: lambda: a * b, ast.Div: lambda: a / b}[op]()

    def visit_BoolOp(self, n):
        vals = [self.visit(v) for v in n.values]
        return all(vals) if isinstance(n.op, ast.And) else any(vals)

    def visit_Compare(self, n):
        a, b = self.visit(n.left), self.visit(n.comparators[0])
        op = type(n.ops[0])
        return {ast.Gt: a > b, ast.GtE: a >= b, ast.Lt: a < b, ast.LtE: a <= b, ast.Eq: a == b, ast.NotEq: a != b}[op]

    def visit_Call(self, n):
        fn = n.func.id
        if fn == "iff":                      # lazy, like DAX IF
            return self.visit(n.args[1]) if self.visit(n.args[0]) else self.visit(n.args[2])
        if fn == "blank":
            return None
        if fn == "lk":
            t, col = n.args[0].value, n.args[1].value
            key = self.visit(n.args[2])
            tb = self.tables[t]
            row = next(r for r in tb["rows"] if r[0] == key)
            return row[1 + tb["cols"].index(col)]
        args = [self.visit(a) for a in n.args]
        return dict(min=min, max=max, ramp_sum=ramp_sum, payback=payback, nes_redundancy=nes_redundancy)[fn](*args)


def evaluate(levers_state, consts, tables, delivery=1.0, formulas=FORMULAS):
    """Run every formula in Python. levers_state: dict sim_* -> value (missing keys take the defaults)."""
    s = {**S.DEFAULTS, **levers_state}
    env = dict(consts)
    env["D"] = delivery
    for k, v in s.items():
        if k.startswith("sim_"):
            env["L_" + k[4:]] = float(v) if isinstance(v, bool) else v
    out = {}
    for name, expr in formulas:
        v = _Eval(env, tables).visit(ast.parse(expr, mode="eval"))
        env[name] = v
        out[name] = v
    return out


# ------------------------------------------------------------------------------------------------------------- DAX ---
def dax_num(v):
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, int):
        return str(v)
    r = repr(float(v))
    return r[:-2] if r.endswith(".0") else r


def dax_str(s):
    return '"' + str(s).replace('"', '""') + '"'


class _Dax(ast.NodeVisitor):
    """Expression -> DAX text. Names become VAR references (v_name); constants are inlined as literals."""

    def __init__(self, consts):
        self.consts = consts

    def visit_Expression(self, n):
        return self.visit(n.body)

    def visit_Constant(self, n):
        return dax_str(n.value) if isinstance(n.value, str) else dax_num(n.value)

    def visit_Name(self, n):
        if n.id in self.consts:
            return dax_num(self.consts[n.id])
        return "v_" + n.id

    def visit_UnaryOp(self, n):
        return f"( -{self.visit(n.operand)} )"

    def visit_BinOp(self, n):
        a, b = self.visit(n.left), self.visit(n.right)
        if isinstance(n.op, ast.Div):
            if isinstance(n.right, ast.Constant):
                return f"( {a} / {b} )"
            return f"DIVIDE( {a}, {b} )"
        op = {ast.Add: "+", ast.Sub: "-", ast.Mult: "*"}[type(n.op)]
        return f"( {a} {op} {b} )"

    def visit_BoolOp(self, n):
        j = " && " if isinstance(n.op, ast.And) else " || "
        return "( " + j.join(self.visit(v) for v in n.values) + " )"

    def visit_Compare(self, n):
        op = {ast.Gt: ">", ast.GtE: ">=", ast.Lt: "<", ast.LtE: "<=", ast.Eq: "=", ast.NotEq: "<>"}[type(n.ops[0])]
        return f"( {self.visit(n.left)} {op} {self.visit(n.comparators[0])} )"

    def visit_Call(self, n):
        fn = n.func.id
        a = [self.visit(x) for x in n.args] if fn != "lk" else None
        if fn == "iff":
            return f"IF( {a[0]}, {a[1]}, {a[2]} )"
        if fn == "blank":
            return "BLANK()"
        if fn in ("min", "max"):
            return f"{fn.upper()}( {a[0]}, {a[1]} )"
        if fn == "lk":
            t, col = n.args[0].value, n.args[1].value
            key_col = TABLE_KEYS[t]
            return f"CALCULATE( MAX( '{t}'[{col}] ), REMOVEFILTERS( '{t}' ), '{t}'[{key_col}] = {self.visit(n.args[2])} )"
        if fn == "ramp_sum":
            return dax_ramp_sum(a[0], a[1])
        if fn == "payback":
            L, F, R, C = a
            return ("MINX( FILTER( GENERATESERIES( 1, 60, 1 ), "
                    f"( -{L} ) + {F} * {dax_ramp_sum('[Value]', R)} - {C} * [Value] >= 0 ), [Value] )")
        if fn == "nes_redundancy":
            parts = ", ".join(f"{a[0]} >= {y}, {w}" for y, w in sorted(S.NES_REDUNDANCY_WEEKS, reverse=True))
            return f"SWITCH( TRUE(), {parts}, 0 )"
        raise ValueError(fn)


TABLE_KEYS = {"Sim Role": "Role", "Sim Area": "Area", "Sim Department": "Department", "Sim Channel": "Channel",
              "Sim Platform": "Platform", "Sim New Area": "MatterType"}


def dax_ramp_sum(m, R):
    n = f"MIN( {m}, INT( {R} ) )"
    return f"( {n} * ( {n} + 1 ) / ( 2 * {R} ) + ( {m} - {n} ) )"


def dependencies(target, formulas=FORMULAS):
    """Formulas (in order) that `target` needs, and the levers they read."""
    exprs = dict(formulas)
    need, levers, stack = set(), set(), [target]
    while stack:
        n = stack.pop()
        if n in need:
            continue
        need.add(n)
        for node in ast.walk(ast.parse(exprs[n], mode="eval")):
            if isinstance(node, ast.Name):
                if node.id in exprs:
                    stack.append(node.id)
                elif node.id.startswith("L_") or node.id == "D":
                    levers.add(node.id)
    return [n for n, _ in formulas if n in need], levers


def to_dax(target, consts, lever_dax, formulas=FORMULAS):
    """One DAX measure for `target`: VARs for the levers it reads, then every formula it needs, once each.

    lever_dax: dict L_x/D -> DAX expression giving the lever's current value."""
    order, levers = dependencies(target, formulas)
    exprs = dict(formulas)
    lines = []
    for lv in sorted(levers):
        lines.append(f"VAR v_{lv} = {lever_dax[lv]}")
    tr = _Dax(consts)
    for n in order:
        lines.append(f"VAR v_{n} = {tr.visit(ast.parse(exprs[n], mode='eval'))}")
    lines.append(f"RETURN v_{target}")
    return "\n".join(lines)
