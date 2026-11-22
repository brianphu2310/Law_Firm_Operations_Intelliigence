"""Builds the Power BI semantic model (TMDL): tables from the CSVs on GitHub, relationships, and every DAX measure.

Descriptive measures aggregate the warehouse facts for the reporting period picked on the Period slicer
(the same periods and day weights as the Python model). Simulator measures are generated from powerbi/sim_spec.py.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from core import simulate as S
from . import sim_spec as SP
from .tmdl import Column, Measure, Table, relationship, q

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE_URL = "https://raw.githubusercontent.com/brianphu2310/law-firm-decision-support/main/"
DEFAULT_PERIOD = "FY26 Q1 QTD"

WAREHOUSE = [("Date", "dim_date"), ("Branch", "dim_branch"), ("Attorney", "dim_attorney"), ("Client", "dim_client"),
             ("Department", "dim_department"), ("Channel", "dim_marketing_channel"), ("Matter", "dim_matter"),
             ("Practice Area", "dim_practice_area"), ("Scenario", "dim_scenario"), ("Attorney Month", "fact_attorney_month"),
             ("Invoice", "fact_invoice"), ("Matter Position", "fact_matter_position"), ("Funnel", "fact_monthly_funnel"),
             ("PnL", "fact_monthly_pnl"), ("Snapshot", "fact_monthly_snapshot"), ("Staffing", "fact_staffing"),
             ("Supplier Order", "fact_supplier_order"), ("Time by Area", "fact_time_by_area"), ("Trust Balance", "fact_trust_balance"),
             ("Trust Txn", "fact_trust_txn")]
ANALYSIS = [("Period", "period"), ("Period Month", "period_month"), ("Period Balance", "period_balance"), ("Monthly Extra", "monthly_extra"),
            ("Where to Hire", "where_to_hire"), ("Dept Workload", "departments"), ("Marketing", "marketing"), ("Decisions", "decisions"),
            ("Client Period", "clients"), ("AR Ageing", "ar_ageing"), ("Branch Period", "branches"), ("Cash Forecast", "cash_forecast"),
            ("FY Outlook", "fy_outlook"), ("FY Summary", "fy_summary"), ("Deadlines", "deadlines"), ("Cards", "cards"), ("RapidPay", "rapidpay"),
            ("Commissions", "commissions"), ("Platforms", "platforms"), ("Platform Cashflow", "platform_cashflow"),
            ("Platform Scores", "platform_scores"), ("Platform Risks", "platform_risks"), ("Platform Gantt", "platform_gantt"),
            ("Platform NPV Grid", "platform_npv_grid"), ("Sim Expected", "sim_expected")]
DATE_COLS = {"full_date", "month_start_date", "Start", "End", "PriorStart", "PriorEnd", "week_start", "month", "date"}
INT_SUFFIX = ("_key", "Key", "Order", "order")
HIDE = {"Period Month", "Period Balance", "Sim Expected"}

RELATIONSHIPS = [
    ("PnL", "month_start_date_key", "Date", "date_key"), ("PnL", "scenario_key", "Scenario", "scenario_key"),
    ("Attorney Month", "attorney_key", "Attorney", "attorney_key"), ("Attorney Month", "month_start_date_key", "Date", "date_key"),
    ("Time by Area", "attorney_key", "Attorney", "attorney_key"), ("Time by Area", "practice_area_key", "Practice Area", "practice_area_key"),
    ("Time by Area", "month_start_date_key", "Date", "date_key"),
    ("Invoice", "client_key", "Client", "client_key"), ("Invoice", "practice_area_key", "Practice Area", "practice_area_key"),
    ("Invoice", "attorney_key", "Attorney", "attorney_key"), ("Invoice", "branch_key", "Branch", "branch_key"),
    ("Invoice", "issue_date_key", "Date", "date_key"),
    ("Matter", "client_key", "Client", "client_key"), ("Matter", "practice_area_key", "Practice Area", "practice_area_key"),
    ("Matter", "attorney_key", "Attorney", "attorney_key"), ("Matter", "branch_key", "Branch", "branch_key"),
    ("Matter Position", "matter_key", "Matter", "matter_key"),
    ("Funnel", "month_start_date_key", "Date", "date_key"), ("Snapshot", "month_start_date_key", "Date", "date_key"),
    ("Monthly Extra", "MonthKey", "Date", "date_key"),
    ("Staffing", "branch_key", "Branch", "branch_key"), ("Staffing", "department_key", "Department", "department_key"),
    ("Supplier Order", "branch_key", "Branch", "branch_key"), ("Supplier Order", "order_date_key", "Date", "date_key"),
    ("Trust Balance", "client_key", "Client", "client_key"), ("Trust Balance", "month_start_date_key", "Date", "date_key"),
    ("Trust Txn", "client_key", "Client", "client_key"), ("Trust Txn", "txn_date_key", "Date", "date_key"),
    ("Client Period", "Period", "Period", "Period"), ("AR Ageing", "Period", "Period", "Period"), ("Branch Period", "Period", "Period", "Period"),
    ("Decisions", "Period", "Period", "Period"),
    ("Platform Cashflow", "Platform", "Platforms", "Platform"), ("Platform Scores", "Platform", "Platforms", "Platform"),
    ("Platform Risks", "Platform", "Platforms", "Platform"), ("Platform Gantt", "Platform", "Platforms", "Platform"),
    ("Platform NPV Grid", "Platform", "Platforms", "Platform"),
]

MONEY = '\\$#,0;-\\$#,0;\\$0'
MONEY_K = '\\$#,0,"K";-\\$#,0,"K";\\$0'
PCT = "0.0%;-0.0%;0.0%"
PCT0 = "0%;-0%;0%"
NUM = "#,0"
NUM1 = "#,0.0"


# --------------------------------------------------------------------------------------------------- import tables ---
def _infer(path: Path):
    df = pd.read_csv(path)
    cols = []
    for c in df.columns:
        s = df[c]
        if c in DATE_COLS:
            t = "dateTime"
        elif pd.api.types.is_numeric_dtype(s):
            t = "int64" if (c.endswith(INT_SUFFIX) or c in ("Month", "week", "rank", "Rank", "since", "Days", "IsDefault", "IsCurrent", "GoLive")) else "double"
        else:
            t = "string"
        cols.append((c, t))
    return cols


def _m_source(rel_path, cols):
    types = {"int64": "Int64.Type", "double": "type number", "string": "type text", "dateTime": "type date"}
    nonstr = [c for c, t in cols if t != "string"]
    typed = ", ".join(f'{{"{c}", {types[t]}}}' for c, t in cols)
    lines = [
        "let",
        f'    Source = Csv.Document(Web.Contents(BaseUrl, [RelativePath = "{rel_path}"]), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),',
        "    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),",
    ]
    if nonstr:
        lst = ", ".join(f'"{c}"' for c in nonstr)
        lines.append(f'    Blanks = Table.ReplaceValue(Promoted, "", null, Replacer.ReplaceValue, {{{lst}}}),')
        lines.append(f'    Typed = Table.TransformColumnTypes(Blanks, {{{typed}}}, "en-US")')
    else:
        lines.append(f'    Typed = Table.TransformColumnTypes(Promoted, {{{typed}}}, "en-US")')
    lines += ["in", "    Typed"]
    return "\n".join(lines)


def import_table(name, folder, file):
    path = ROOT / "data" / folder / f"{file}.csv"
    cols = _infer(path)
    keys = {r[1] for r in RELATIONSHIPS if r[0] == name} | {r[3] for r in RELATIONSHIPS if r[2] == name and r[3].endswith("_key")}
    tcols = []
    for c, t in cols:
        fmt = None
        if t == "dateTime":
            fmt = "dd mmm yyyy"
        elif t == "double":
            lc = c.lower()
            if any(x in lc for x in ("util", "margin", "share", "realisation", "conversion", "growth", "irr", "weight", "fraction", "r_rev", "r_cost")):
                fmt = PCT
            elif any(x in lc for x in ("hours", "inquiries", "matters", "volume", "needed", "gap", "score", "priority", "days", "dso", "lockup",
                                       "probability", "impact", "week", "payback", "decision", "searches", "count", "ramp", "fte", "uplift")):
                fmt = NUM1 if any(x in lc for x in ("needed", "gap", "days", "dso", "lockup", "score", "priority", "decision")) else NUM
            else:
                fmt = MONEY
        elif t == "int64":
            fmt = "0"
        hidden = c in keys and c.endswith(("_key", "Key")) and name != "Date"
        tcols.append(Column(c, t, fmt=fmt, hidden=hidden))
    t = Table(name, tcols, "m", _m_source(f"data/{folder}/{file}.csv", cols), hidden=name in HIDE)
    if name == "Date":
        t.data_category = "Time"
        for c in tcols:
            if c.name == "full_date":
                c.is_key = True
            if c.name == "month_name":
                c.sort_by = "month"
        for c in tcols:
            if c.name == "month_start_date":
                c.fmt = "mmm yy"
    if name == "Period":
        for c in tcols:
            if c.name == "Period":
                c.sort_by = "Order"
    sort_by = {"AR Ageing": ("Bucket", "Order"), "Platform Gantt": ("Phase", "Order"), "Platform NPV Grid": ("Volume", "VolumeOrder")}
    if name in sort_by:
        a, b = sort_by[name]
        for c in tcols:
            if c.name == a:
                c.sort_by = b
    if name == "Platform NPV Grid":
        for c in tcols:
            if c.name == "Realisation":
                c.sort_by = "RealisationOrder"
    if name == "Matter Position":
        tcols.append(Column("Age bucket", "string", expression='SWITCH( TRUE(), [days_open] <= 90, "0–90 days", [days_open] <= 180, "91–180 days", '
                                                                 '[days_open] <= 365, "181–365 days", "Over a year" )'))
    return t


# --------------------------------------------------------------------------------------------------- DAX helpers -----
def psum(expr, role="Current"):
    """Day-weighted sum of a monthly fact expression over the selected reporting period (or its prior period)."""
    return (f"VAR p = [Period Sel]\n"
            f"RETURN\n"
            f"    SUMX(\n"
            f"        FILTER( ALL( 'Period Month' ), 'Period Month'[Period] = p && 'Period Month'[Role] = \"{role}\" ),\n"
            f"        'Period Month'[Weight] * CALCULATE( {expr}, TREATAS( {{ 'Period Month'[MonthKey] }}, 'Date'[date_key] ) )\n"
            f"    )")


def bal(col, role="Current"):
    return (f"VAR p = [Period Sel]\n"
            f"RETURN CALCULATE( MAX( 'Period Balance'[{col}] ), REMOVEFILTERS( 'Period Balance' ), 'Period Balance'[Period] = p, 'Period Balance'[Role] = \"{role}\" )")


def trend(expr, frac_expr="CALCULATE( MAX( 'Monthly Extra'[Fraction] ) )"):
    """Full-month-equivalent value of a month on a chart axis, shown only for the 12 months up to the period end."""
    return (f"VAR e = [Period End Month]\n"
            f"VAR m = MAX( 'Date'[month_start_date] )\n"
            f"VAR v = {expr}\n"
            f"VAR fr = {frac_expr}\n"
            f"RETURN IF( m > EDATE( e, -12 ) && m <= e && NOT ISBLANK( v ), DIVIDE( v, IF( ISBLANK( fr ), 1, fr ) ) )")


def delta_text(cur, prior, kind="pct"):
    if kind == "pp":
        fmt = 'FORMAT( d * 100, "▲ +0.0 ""pp"";▼ -0.0 ""pp"";0.0 ""pp""" )'
        dline = f"VAR d = {cur} - {prior}"
    else:
        fmt = 'FORMAT( d, "▲ +0.0%;▼ -0.0%;0.0%" )'
        dline = f"VAR d = DIVIDE( {cur} - {prior}, ABS( {prior} ) )"
    return (f"VAR c = {cur}\nVAR pr = {prior}\n{dline}\n"
            f"RETURN IF( ISBLANK( pr ) || pr = 0, \"no comparison\", {fmt} & \" vs prior period\" )")


ACTUAL = "'PnL'[scenario_key] = 1"
BUDGET = "'PnL'[scenario_key] = 2"
PNL_LINES = [  # (label, column, is_cost, section, order)
    ("Fees", "fees", False, "Revenue", 1), ("Disbursements billed", "disbursements_billed", False, "Revenue", 2),
    ("Total revenue", "revenue", False, "Revenue", 3),
    ("Fee-earner payroll", "payroll_fee_earners", True, "Costs", 4), ("Disbursement costs", "disbursement_cost", True, "Costs", 5),
    ("Support payroll", "payroll_support", True, "Costs", 6), ("Rent", "rent", True, "Costs", 7), ("Software", "software", True, "Costs", 8),
    ("Insurance", "insurance", True, "Costs", 9), ("Marketing", "marketing", True, "Costs", 10), ("Professional fees", "professional_fees", True, "Costs", 11),
    ("Card expenses", "cards", True, "Costs", 12), ("Merchant fees", "merchant_fees", True, "Costs", 13), ("Referral commission", "commission", True, "Costs", 14),
    ("Bank fees", "bank_fees", True, "Costs", 15), ("Other", "other_costs", True, "Costs", 16), ("Total costs", "total_costs", True, "Costs", 17),
    ("Operating profit", "operating_profit", False, "Result", 18),
]


def descriptive_measures():
    M = []
    add = lambda name, expr, fmt=None, folder=None, hidden=False, desc=None: M.append(Measure(name, expr, fmt, folder, hidden, desc))
    # period helpers
    add("Period Sel", f'SELECTEDVALUE( \'Period\'[Period], "{DEFAULT_PERIOD}" )', folder="Period", desc="The reporting period picked on the Period slicer (FY26 Q1 QTD when none).")
    add("Period End", "VAR p = [Period Sel]\nRETURN CALCULATE( MAX( 'Period'[End] ), REMOVEFILTERS( 'Period' ), 'Period'[Period] = p )", "dd mmm yyyy", "Period")
    add("Period End Month", "VAR p = [Period Sel]\nVAR k = CALCULATE( MAX( 'Period'[MonthEndKey] ), REMOVEFILTERS( 'Period' ), 'Period'[Period] = p )\n"
                    "RETURN DATE( INT( k / 10000 ), MOD( INT( k / 100 ), 100 ), 1 )", "dd mmm yyyy", "Period", True)
    add("Period Caption", 'VAR p = [Period Sel]\nVAR s = CALCULATE( MAX( \'Period\'[Start] ), REMOVEFILTERS( \'Period\' ), \'Period\'[Period] = p )\n'
        'VAR e = [Period End]\nRETURN p & " · " & FORMAT( s, "d mmm yy" ) & " – " & FORMAT( e, "d mmm yy" ) & " · vs prior period · data as of 17 Sep 2025"',
        folder="Period")
    # P&L lines, actual / budget / prior
    for label, col, is_cost, sec, order in PNL_LINES:
        add(f"Actual {label}", psum(f"SUM( 'PnL'[{col}] ), {ACTUAL}"), MONEY, "P&L\\Actual", hidden=True)
        add(f"Budget {label}", psum(f"SUM( 'PnL'[{col}] ), {BUDGET}"), MONEY, "P&L\\Budget", hidden=True)
    sw = lambda kind: "SWITCH( SELECTEDVALUE( 'P&L Line'[Line] ),\n" + ",\n".join(f'    "{l}", [{kind} {l}]' for l, *_ in PNL_LINES) + "\n)"
    add("P&L Actual", sw("Actual"), MONEY, "P&L")
    add("P&L Budget", sw("Budget"), MONEY, "P&L")
    add("P&L Variance", "VAR a = [P&L Actual]\nVAR b = [P&L Budget]\nVAR cost = SELECTEDVALUE( 'P&L Line'[IsCost] )\nRETURN IF( cost = 1, b - a, a - b )", MONEY, "P&L",
        desc="Favourable is positive: more revenue or profit, or less cost, than budget.")
    add("P&L Variance %", "DIVIDE( [P&L Variance], ABS( [P&L Budget] ) )", PCT, "P&L")
    # headline KPIs
    add("Revenue", "[Actual Total revenue]", MONEY, "KPIs")
    add("Revenue (prior)", psum(f"SUM( 'PnL'[revenue] ), {ACTUAL}", "Prior"), MONEY, "KPIs", True)
    add("Operating Profit", "[Actual Operating profit]", MONEY, "KPIs")
    add("Budget Operating Profit", "[Budget Operating profit]", MONEY, "KPIs")
    add("Profit vs Budget", "[Operating Profit] - [Budget Operating Profit]", MONEY, "KPIs")
    add("Operating Margin", "DIVIDE( [Operating Profit], [Revenue] )", PCT, "KPIs")
    add("Fees", "[Actual Fees]", MONEY, "KPIs")
    add("Billable Hours", psum(f"SUM( 'PnL'[billable_hours] ), {ACTUAL}"), NUM, "KPIs")
    add("Billable Hours (prior)", psum(f"SUM( 'PnL'[billable_hours] ), {ACTUAL}", "Prior"), NUM, "KPIs", True)
    add("Capacity Hours", psum(f"SUM( 'PnL'[capacity_hours] ), {ACTUAL}"), NUM, "KPIs")
    add("Capacity Hours (prior)", psum(f"SUM( 'PnL'[capacity_hours] ), {ACTUAL}", "Prior"), NUM, "KPIs", True)
    add("Standard Value", psum(f"SUM( 'PnL'[standard_value] ), {ACTUAL}"), MONEY, "KPIs")
    add("Utilisation", "DIVIDE( [Billable Hours], [Capacity Hours] )", PCT, "KPIs")
    add("Utilisation (prior)", "DIVIDE( [Billable Hours (prior)], [Capacity Hours (prior)] )", PCT, "KPIs", True)
    add("Realisation", "DIVIDE( [Fees], [Standard Value] )", PCT, "KPIs")
    add("Effective Rate", "DIVIDE( [Fees], [Billable Hours] )", MONEY, "KPIs")
    add("Disbursement Recovery", "DIVIDE( [Actual Disbursements billed], [Actual Disbursement costs] )", PCT, "KPIs")
    add("Collections ex GST", psum("SUM( 'Monthly Extra'[CollectionsExGST] )"), MONEY, "KPIs")
    add("Collections ex GST (prior)", psum("SUM( 'Monthly Extra'[CollectionsExGST] )", "Prior"), MONEY, "KPIs", True)
    add("Matters Opened", psum("SUM( 'Monthly Extra'[MattersOpened] )"), NUM, "KPIs")
    add("Active Matters", bal("ActiveMatters"), NUM, "Balances")
    add("Active Matters (prior)", bal("ActiveMatters", "Prior"), NUM, "Balances", True)
    add("Office Cash", bal("Cash"), MONEY, "Balances")
    add("WIP", bal("WIP"), MONEY, "Balances")
    add("Receivables", bal("Receivables"), MONEY, "Balances")
    add("Trust Funds", bal("Trust"), MONEY, "Balances")
    add("DSO", bal("DSO"), NUM1, "Balances", desc="Days sales outstanding: receivables over the last 90 days of billing.")
    add("Lockup Days", bal("Lockup"), NUM1, "Balances", desc="WIP plus receivables, in days of billing.")
    add("Funds Employed", "[WIP] + [Receivables] + [Trust Funds]", MONEY, "Balances")
    add("Deadlines Next 30 Days", "COUNTROWS( FILTER( 'Deadlines', 'Deadlines'[days_from_as_of] >= 0 && 'Deadlines'[days_from_as_of] <= 30 ) ) + 0", NUM, "KPIs")
    add("Deadlines Following 30 Days", "COUNTROWS( FILTER( 'Deadlines', 'Deadlines'[days_from_as_of] > 30 && 'Deadlines'[days_from_as_of] <= 60 ) ) + 0", NUM, "KPIs")
    add("Deadlines Caption", 'FORMAT( [Deadlines Following 30 Days], "0" ) & " more in the following 30 days"', None, "KPIs")
    for nm, cur, pr, kind in [("Hours Δ", "[Billable Hours]", "[Billable Hours (prior)]", "pct"), ("Collections Δ", "[Collections ex GST]", "[Collections ex GST (prior)]", "pct"),
                              ("Utilisation Δ", "[Utilisation]", "[Utilisation (prior)]", "pp"), ("Active Matters Δ", "[Active Matters]", "[Active Matters (prior)]", "pct"),
                              ("Revenue Δ", "[Revenue]", "[Revenue (prior)]", "pct")]:
        add(nm, delta_text(cur, pr, kind), None, "KPIs\\Change")
    # attorneys
    add("Attorney Hours", psum("SUM( 'Attorney Month'[billable_hours] )"), NUM, "People")
    add("Attorney Capacity", psum("SUM( 'Attorney Month'[capacity_hours] )"), NUM, "People")
    add("Attorney Fees", psum("SUM( 'Attorney Month'[fees_realised] )"), MONEY, "People")
    add("Attorney Fees (prior)", psum("SUM( 'Attorney Month'[fees_realised] )", "Prior"), MONEY, "People", True)
    add("Attorney Standard Value", psum("SUM( 'Attorney Month'[standard_value] )"), MONEY, "People")
    add("Attorney Cost", psum("SUM( 'Attorney Month'[salary_cost] )"), MONEY, "People")
    add("Attorney Utilisation", "DIVIDE( [Attorney Hours], [Attorney Capacity] )", PCT, "People")
    add("Attorney Realisation", "DIVIDE( [Attorney Fees], [Attorney Standard Value] )", PCT, "People")
    add("Attorney Effective Rate", "DIVIDE( [Attorney Fees], [Attorney Hours] )", MONEY, "People")
    add("Attorney Contribution", "[Attorney Fees] - [Attorney Cost]", MONEY, "People")
    add("Attorney Break-even Hours", "DIVIDE( [Attorney Cost], [Attorney Effective Rate] )", NUM, "People")
    add("Top Biller", "VAR t = TOPN( 1, ALL( 'Attorney'[attorney_short] ), [Attorney Fees], DESC )\nRETURN \"Top biller · \" & MAXX( t, 'Attorney'[attorney_short] )", None, "People")
    add("Top Biller Fees", "MAXX( ALL( 'Attorney'[attorney_short] ), [Attorney Fees] )", MONEY, "People")
    add("Top Biller Δ", "VAR t = TOPN( 1, ALL( 'Attorney'[attorney_short] ), [Attorney Fees], DESC )\nVAR n = MAXX( t, 'Attorney'[attorney_short] )\n"
        "VAR c = CALCULATE( [Attorney Fees], 'Attorney'[attorney_short] = n )\nVAR pr = CALCULATE( [Attorney Fees (prior)], 'Attorney'[attorney_short] = n )\n"
        "VAR d = DIVIDE( c - pr, ABS( pr ) )\nRETURN IF( ISBLANK( pr ) || pr = 0, \"no comparison\", FORMAT( d, \"▲ +0.0%;▼ -0.0%;0.0%\" ) & \" vs prior period\" )",
        None, "People")
    add("Area Hours", psum("SUM( 'Time by Area'[billable_hours] )"), NUM, "People")
    add("Area Fees", psum("SUM( 'Time by Area'[fees_realised] )"), MONEY, "People")
    # monthly trends (12 months to the period end, full-month equivalents)
    add("Trend Billable Hours", trend(f"CALCULATE( SUM( 'PnL'[billable_hours] ), {ACTUAL} )"), NUM, "Trends")
    add("Trend Revenue", trend(f"CALCULATE( SUM( 'PnL'[revenue] ), {ACTUAL} )"), MONEY, "Trends")
    add("Trend Budget Revenue", trend(f"CALCULATE( SUM( 'PnL'[revenue] ), {BUDGET} )"), MONEY, "Trends")
    add("Trend Operating Profit", trend(f"CALCULATE( SUM( 'PnL'[operating_profit] ), {ACTUAL} )"), MONEY, "Trends")
    add("Trend Budget Operating Profit", trend(f"CALCULATE( SUM( 'PnL'[operating_profit] ), {BUDGET} )"), MONEY, "Trends")
    add("Trend Utilisation", trend(f"DIVIDE( CALCULATE( SUM( 'PnL'[billable_hours] ), {ACTUAL} ), CALCULATE( SUM( 'PnL'[capacity_hours] ), {ACTUAL} ) )", "1"), PCT, "Trends")
    add("Trend Area Hours", trend("SUM( 'Time by Area'[billable_hours] )"), NUM, "Trends")
    add("Trend Attorney Hours", trend("SUM( 'Attorney Month'[billable_hours] )"), NUM, "Trends")
    add("Trend Attorney Utilisation", trend("DIVIDE( SUM( 'Attorney Month'[billable_hours] ), SUM( 'Attorney Month'[capacity_hours] ) )", "1"), PCT, "Trends")
    add("Trend Collections", trend("SUM( 'Monthly Extra'[CollectionsExGST] )"), MONEY, "Trends")
    add("Trend Matters Opened", trend("SUM( 'Monthly Extra'[MattersOpened] )"), NUM, "Trends")
    add("Trend Matters Closed", trend("SUM( 'Monthly Extra'[MattersClosed] )"), NUM, "Trends")
    add("Trend Active Matters", trend("SUM( 'Monthly Extra'[ActiveMatters] )", "1"), NUM, "Trends")
    add("Trend Inquiries", trend("SUM( 'Funnel'[inquiries] )"), NUM1, "Trends")
    add("Trend Cash Balance", trend("SUM( 'Monthly Extra'[CashBalance] )", "1"), MONEY, "Trends")
    add("Trend WIP", trend("SUM( 'Snapshot'[wip_balance] )", "1"), MONEY, "Trends")
    add("Trend Receivables", trend("SUM( 'Snapshot'[receivables_incl_gst] )", "1"), MONEY, "Trends")
    add("Trend Trust", trend("SUM( 'Trust Balance'[closing_balance] )", "1"), MONEY, "Trends")
    add("Trend Realisation", trend(f"DIVIDE( CALCULATE( SUM( 'PnL'[fees] ), {ACTUAL} ), CALCULATE( SUM( 'PnL'[standard_value] ), {ACTUAL} ) )", "1"), PCT, "Trends")
    # funnel
    stages = [("Inquiries", "inquiries"), ("Consultations booked", "consultations_booked"), ("Consultations held", "consultations_held"),
              ("Engagement letters sent", "letters_sent"), ("New matters opened", "matters_opened")]
    for lab, col in stages:
        add(f"Funnel {lab}", psum(f"SUM( 'Funnel'[{col}] )"), NUM, "Funnel", True)
    add("Funnel Value", "SWITCH( SELECTEDVALUE( 'Funnel Stage'[Stage] ),\n" + ",\n".join(f'    "{l}", [Funnel {l}]' for l, _ in stages) + "\n)", NUM, "Funnel")
    add("Funnel Conversion", f"DIVIDE( [Funnel New matters opened], [Funnel Inquiries] )", PCT0, "Funnel")
    add("Funnel Step Conversion", "VAR o = SELECTEDVALUE( 'Funnel Stage'[Order] )\nVAR prev = CALCULATE( [Funnel Value], REMOVEFILTERS( 'Funnel Stage' ), 'Funnel Stage'[Order] = o - 1 )\n"
        "RETURN IF( o = 1, 1, DIVIDE( [Funnel Value], prev ) )", PCT0, "Funnel")
    # balances by bucket / decision tables
    add("AR Amount", "SUM( 'AR Ageing'[Amount] )", MONEY, "Finance")
    add("Client Revenue", "SUM( 'Client Period'[revenue] )", MONEY, "Clients")
    add("Client Receivables", "SUM( 'Client Period'[ar] )", MONEY, "Clients")
    add("Client Overdue", "SUM( 'Client Period'[overdue] )", MONEY, "Clients")
    add("Top 5 Client Share", "VAR t = TOPN( 5, 'Client Period', 'Client Period'[revenue], DESC )\nRETURN DIVIDE( SUMX( t, 'Client Period'[revenue] ), SUM( 'Client Period'[revenue] ) )",
        PCT, "Clients")
    add("Supplier Spend", "SUM( 'Supplier Order'[amount] )", MONEY, "Finance")
    add("Card Spend", "SUM( 'Cards'[amount] )", MONEY, "Finance")
    add("Trust Txn Amount", "SUM( 'Trust Txn'[amount] )", MONEY, "Finance")
    add("Cash Inflow", "SUM( 'Cash Forecast'[in_open] ) + SUM( 'Cash Forecast'[in_new] )", MONEY, "Finance")
    add("Cash Outflow", "SUM( 'Cash Forecast'[out_payroll] ) + SUM( 'Cash Forecast'[out_rent] ) + SUM( 'Cash Forecast'[out_opex] ) + SUM( 'Cash Forecast'[out_disb] )"
        " + SUM( 'Cash Forecast'[out_bas] ) + SUM( 'Cash Forecast'[out_drawings] )", MONEY, "Finance")
    add("Cash Closing", "SUM( 'Cash Forecast'[closing] )", MONEY, "Finance")
    add("Cash Minimum", "MAX( 'Cash Forecast'[min_cash] )", MONEY, "Finance")
    add("Cash Low Point", "MINX( ALL( 'Cash Forecast' ), 'Cash Forecast'[closing] )", MONEY, "Finance")
    add("FY Forecast Profit", "MAX( 'FY Summary'[fc_op] )", MONEY, "Finance")
    add("FY Budget Profit", "MAX( 'FY Summary'[budget_op] )", MONEY, "Finance")
    add("FY Forecast Revenue", "MAX( 'FY Summary'[fc_rev] )", MONEY, "Finance")
    add("FY Budget Revenue", "MAX( 'FY Summary'[budget_rev] )", MONEY, "Finance")
    add("FY Profit Gap", "[FY Forecast Profit] - [FY Budget Profit]", MONEY, "Finance")
    add("FY Path Revenue", "SUM( 'FY Outlook'[revenue] )", MONEY, "Finance")
    add("FY Path Budget Revenue", "SUM( 'FY Outlook'[budget_rev] )", MONEY, "Finance")
    add("FY Path Profit", "SUM( 'FY Outlook'[op_profit] )", MONEY, "Finance")
    add("FY Path Budget Profit", "SUM( 'FY Outlook'[budget_op] )", MONEY, "Finance")
    add("FY Path Actual Profit", "CALCULATE( SUM( 'FY Outlook'[op_profit] ), 'FY Outlook'[kind] = \"Actual\" )", MONEY, "Finance")
    add("FY Path Forecast Profit", "CALCULATE( SUM( 'FY Outlook'[op_profit] ), 'FY Outlook'[kind] = \"Forecast\" )", MONEY, "Finance")
    # people & staffing
    add("Headcount", "SUM( 'Staffing'[headcount] )", NUM, "People")
    add("Support Needed", "SUM( 'Dept Workload'[needed] )", NUM1, "People")
    add("Support Headcount", "SUM( 'Dept Workload'[headcount] )", NUM, "People")
    add("Support Gap Cost", "SUM( 'Dept Workload'[cost_of_gap] )", MONEY, "People")
    add("Over-staffed Cost", "CALCULATE( SUM( 'Dept Workload'[cost_of_gap] ), 'Dept Workload'[status] = \"Over-staffed\" )", MONEY, "People")
    add("Hire Priority", "SUM( 'Where to Hire'[priority] )", NUM1, "People")
    add("Area Utilisation", "SUM( 'Where to Hire'[util] )", PCT, "People")
    add("Area New Matter Growth", "SUM( 'Where to Hire'[matters_growth] )", PCT, "People")
    add("Area Contribution", "SUM( 'Where to Hire'[contribution] )", MONEY, "People")
    add("Hire First", "\"Hire next in \" & MAXX( FILTER( ALL( 'Where to Hire' ), 'Where to Hire'[rank] = 1 ), 'Where to Hire'[area] )", None, "People")
    add("Market Wage Growth", "0.034", PCT, "People", desc="ABS Wage Price Index, private sector, year to the September quarter 2026.")
    # marketing
    add("Marketing Spend", "SUM( 'Marketing'[spend] )", MONEY, "Marketing")
    add("Marketing Matters", "SUM( 'Marketing'[matters] )", NUM1, "Marketing")
    add("Marketing Fees", "SUM( 'Marketing'[fees] )", MONEY, "Marketing")
    add("Cost per Matter", "DIVIDE( [Marketing Spend], [Marketing Matters] )", MONEY, "Marketing")
    add("Fees per Dollar", "DIVIDE( [Marketing Fees], [Marketing Spend] )", "0.0x", "Marketing")
    add("Cheapest Channel", "VAR t = TOPN( 1, VALUES( 'Marketing'[channel] ), [Cost per Matter], ASC )\nRETURN MAXX( t, 'Marketing'[channel] )", None, "Marketing")
    # matters
    add("Matter Count", "COUNTROWS( 'Matter' )", NUM, "Matters")
    add("Open Matters", "CALCULATE( COUNTROWS( 'Matter' ), 'Matter'[status] <> \"Closed\" )", NUM, "Matters")
    add("Matter WIP", "SUM( 'Matter Position'[wip_balance] )", MONEY, "Matters")
    add("Matter Billed", "SUM( 'Matter Position'[billed_to_date] )", MONEY, "Matters")
    add("Matter Estimated Value", "SUM( 'Matter Position'[estimated_value] )", MONEY, "Matters")
    add("Deadline Count", "COUNTROWS( 'Deadlines' ) + 0", NUM, "Calendar")
    # platform
    add("Platform NPV", "SUM( 'Platforms'[NPV] )", MONEY, "Platform")
    add("Platform Run Rate", "SUM( 'Platforms'[RunRate] )", MONEY, "Platform")
    add("Platform Score", "AVERAGE( 'Platforms'[Score] )", NUM1, "Platform")
    add("Platform Cumulative", "SUM( 'Platform Cashflow'[Cumulative] )", MONEY, "Platform")
    add("Platform Weighted Score", "DIVIDE( SUMX( 'Platform Scores', 'Platform Scores'[Score] * 'Platform Scores'[Weight] ), SUM( 'Platform Scores'[Weight] ) )", NUM1, "Platform")
    add("Platform Criterion Score", "SUM( 'Platform Scores'[Score] )", "0", "Platform")
    add("Platform Grid NPV", "SUM( 'Platform NPV Grid'[NPV] )", MONEY, "Platform")
    add("Best Platform", "VAR t = TOPN( 1, ALL( 'Platforms'[Platform] ), CALCULATE( MAX( 'Platforms'[Decision] ) ), DESC )\nRETURN MAXX( t, 'Platforms'[Platform] )", None, "Platform")
    add("Story", '"HOW THIS STARTED  The Principal asked which software saves the firm the most ("'
        ' & FORMAT( CALCULATE( MAX( \'Platforms\'[RunRate] ), \'Platforms\'[IsCurrent] = 1 ), "$#,0" ) & " a year on LEAP + InfoTrack today; best: " & [Best Platform]'
        ' & ", NPV " & FORMAT( CALCULATE( MAX( \'Platforms\'[NPV] ), \'Platforms\'[Platform] = [Best Platform] ), "+$#,0" ) & "). The same model now answers hiring, staffing, pay, marketing, new services and branches."',
        None, "Overview")
    return M


# ------------------------------------------------------------------------------------------------ helper tables -----
def datatable(name, cols, rows, hidden=False, sort=None, fmts=None):
    """A calculated table from DATATABLE. cols: [(name, DAX type)]."""
    tmap = {"STRING": "string", "DOUBLE": "double", "INTEGER": "int64", "BOOLEAN": "boolean"}

    def lit(v, t):
        if t == "STRING":
            return SP.dax_str(v)
        return SP.dax_num(v)
    body = ",\n".join("    { " + ", ".join(lit(v, t) for v, (_, t) in zip(r, cols)) + " }" for r in rows)
    src = "DATATABLE(\n    " + ", ".join(f'"{c}", {t}' for c, t in cols) + ",\n    {\n" + body + "\n    }\n)"
    tc = []
    for c, t in cols:
        tc.append(Column(c, tmap[t], calc_source=c, sort_by=(sort or {}).get(c), fmt=(fmts or {}).get(c),
                         summarize="none"))
    return Table(name, tc, "calculated", src, hidden=hidden)


def series_table(name, col, lo, hi, step, fmt):
    lo_s, hi_s, st = SP.dax_num(lo), SP.dax_num(hi), SP.dax_num(step)
    return Table(name, [Column(col, "double" if isinstance(step, float) and step != int(step) or isinstance(lo, float) else "int64", calc_source="Value", fmt=fmt)],
                 "calculated", f"GENERATESERIES( {lo_s}, {hi_s}, {st} )")


def helper_tables():
    t = []
    t.append(datatable("P&L Line", [("Line", "STRING"), ("Order", "INTEGER"), ("Section", "STRING"), ("IsCost", "INTEGER"), ("IsTotal", "INTEGER")],
                       [[l, o, s, int(c), int(l.startswith(("Total", "Operating")))] for l, _, c, s, o in PNL_LINES], sort={"Line": "Order"}))
    t.append(datatable("Funnel Stage", [("Stage", "STRING"), ("Order", "INTEGER")],
                       [["Inquiries", 1], ["Consultations booked", 2], ["Consultations held", 3], ["Engagement letters sent", 4], ["New matters opened", 5]],
                       sort={"Stage": "Order"}))
    meas = Table("Measures", [Column("Note", "string", calc_source="Note", hidden=True)], "calculated", 'ROW( "Note", "Measures live here" )')
    meas.measures = descriptive_measures()
    t.append(meas)
    return t


# ----------------------------------------------------------------------------------------------------- simulator ----
def simulator_tables(consts, tables, levers, ctx):
    out = []
    # lever slicer tables
    for lv in levers:
        if lv.kind == "num":
            dt = "DOUBLE" if lv.step != int(lv.step) or lv.lo != int(lv.lo) else "INTEGER"
            n = int(round((lv.hi - lv.lo) / lv.step))
            vals = [lv.lo + i * lv.step for i in range(n + 1)]
            out.append(datatable(lv.table, [(lv.label, dt)], [[round(v, 6) if dt == "DOUBLE" else int(round(v))] for v in vals],
                                 fmts={lv.label: lv.fmt}))
        elif lv.kind == "bool":
            out.append(datatable(lv.table, [(lv.label, "STRING"), ("Value", "INTEGER")], [["No", 0], ["Yes", 1]]))
        else:
            out.append(datatable(lv.table, [(lv.label, "STRING"), ("Order", "INTEGER")], [[o, i + 1] for i, o in enumerate(lv.options)],
                                 sort={lv.label: "Order"}))
    # presets: one row per preset with every lever's value
    cols = [("Preset", "STRING"), ("Short", "STRING"), ("Help", "STRING"), ("Order", "INTEGER")]
    for lv in levers:
        cols.append((lv.key, "STRING" if lv.kind == "cat" else "DOUBLE"))
    rows = []
    names = ["Custom"] + list(S.PRESETS)
    for i, nme in enumerate(names):
        s = S.DEFAULTS if nme == "Custom" else S.preset_state(nme)
        r = [nme, "Today" if nme == "Custom" else S.PRESET_SHORT[nme], "Today's firm: last 12 months, no change" if nme == "Custom" else S.PRESET_HELP[nme], i]
        for lv in levers:
            v = s[lv.key]
            r.append(v if lv.kind == "cat" else float(v))
        rows.append(r)
    out.append(datatable("Sim Preset", cols, rows, sort={"Preset": "Order", "Short": "Order"}))
    out.append(datatable("Sim Compare", [("Compare preset", "STRING"), ("Short", "STRING"), ("Order", "INTEGER")],
                         [[n, "Today" if n == "Custom" else S.PRESET_SHORT[n], i] for i, n in enumerate(names)], sort={"Compare preset": "Order", "Short": "Order"}))
    out.append(datatable("Sim Delivery", [("Delivery", "DOUBLE"), ("Label", "STRING")],
                         [[1.0, "100% delivered"], [0.75, "75% delivered"], [0.5, "50% delivered"]], sort={"Label": "Delivery"}, fmts={"Delivery": PCT0}))
    out.append(datatable("Sim Goal Lever", [("Lever", "STRING")], [["sim_util"], ["sim_rate"], ["sim_real"], ["sim_recov"], ["sim_infl"], ["sim_pay_both"]], hidden=True))
    out.append(series_table("Sim Goal Step", "Hundredths", -6000, 3000, 1, "0"))
    out[-1].hidden = True
    out.append(datatable("Sim Goal Target", [("Target", "STRING"), ("Order", "INTEGER")],
                         [["FY26 budget profit", 1], ["FY26 budget margin", 2], ["Today's profit plus extra", 3]], sort={"Target": "Order"}))
    out.append(datatable("Sim Goal Uplift", [("Extra profit a year", "INTEGER")], [[v] for v in range(0, 2_000_001, 25_000)], fmts={"Extra profit a year": MONEY}))
    # lookup tables
    for tname, tb in tables.items():
        cols = [(tb["key"], "STRING")] + [(c, "DOUBLE") for c in tb["cols"]]
        out.append(datatable(tname, cols, [[r[0]] + [float(x) for x in r[1:]] for r in tb["rows"]], hidden=True))
    # lever tests (what moves profit most) and bridge / effect lines
    out.append(datatable("Sim Lever Test", [("Test", "STRING"), ("Order", "INTEGER")], [[n, i] for i, n in enumerate(t for t, v in S.LEVER_TESTS.items() if v)],
                         sort={"Test": "Order"}))
    out.append(datatable("Sim Bridge Step", [("Step", "STRING"), ("Order", "INTEGER")],
                         [["Today's profit", 1], ["Fees", 2], ["Disb. recovery", 3], ["Costs", 4]], sort={"Step": "Order"}))
    out.append(datatable("Sim Effect Line", [("Line", "STRING"), ("Group", "STRING"), ("Order", "INTEGER")],
                         [[l, g, i] for i, (l, g, _) in enumerate(EFFECT_LINES)], sort={"Line": "Order"}))
    out.append(datatable("Sim Goal Row", [("Lever", "STRING"), ("Key", "STRING"), ("Order", "INTEGER")],
                         [[S.LEVER_LABEL[k], k, i] for i, k in enumerate(["sim_util", "sim_rate", "sim_real", "sim_recov", "sim_infl"])], sort={"Lever": "Order"}))
    out.append(datatable("Sim Assumption", [("Assumption", "STRING"), ("Value", "STRING"), ("Order", "INTEGER")],
                         [[a, v, i] for i, (a, v) in enumerate(assumption_rows(consts))], sort={"Assumption": "Order"}))
    return out


def assumption_rows(C):
    return [
        ("Base period", "Last 12 months to 17 Sep 2025, scaled to a full year"),
        ("Billable hours a year (base)", f"{C['H0']:,.0f}"), ("Utilisation (base)", f"{C['UTIL0']:.1%}"), ("Realisation (base)", f"{C['REAL0']:.1%}"),
        ("Standard rate per hour (base)", f"${C['STD0']:,.0f}"), ("New fee earner overhead", f"${C['HIRE_OH']:,.0f} a year"),
        ("Support staff (branch)", f"${C['SUP_PAY']:,.0f} a month"), ("Branch running costs", f"${C['BR_RUN']:,.0f} a year"),
        ("Employees (NES small-business test)", f"{C['HEADCOUNT']}"), ("Paralegal frees", f"{C['PARA_H']:.0f} billable hours a year"),
        ("Marketing efficiency", f"{C['MKT_EFF']:.0%} of the channel's current cost per inquiry, with diminishing returns"),
        ("New matters billed in year one", f"{C['FYB']:.0%} of a typical matter"), ("FY26 budget profit", f"${C['BUDGET_OP']:,.0f}"),
        ("Office account today", f"${C['CASH_NOW']:,.0f}"), ("13-week low point today", f"${C['LOW0']:,.0f}"), ("Minimum balance", f"${C['MIN_CASH']:,.0f}"),
        ("Market wage growth", "3.4% (ABS WPI, private sector, Sep qtr 2026)"),
    ]


# lines of the "Effects & cash" table: (label, group, DAX value expression using sim measures; BLANK when not relevant)
EFFECT_LINES = [
    ("Billable hours a year", "Profit effects (a year)", 'FORMAT( [Sim Base Hours], "#,0" ) & " → " & FORMAT( [Sim Hours], "#,0" )'),
    ("Utilisation", "Profit effects (a year)", 'FORMAT( [Sim Base Utilisation], "0.0%" ) & " → " & FORMAT( [Sim Utilisation], "0.0%" )'),
    ("New hire(s): fees − cost, year one", "Profit effects (a year)", 'IF( [Sim Lever Hires] > 0, FORMAT( [Sim Hire Net], "+$#,0;-$#,0" ) )'),
    ("Productivity a hire needs to break even", "Profit effects (a year)", 'IF( [Sim Lever Hires] > 0, FORMAT( [Sim Hire Breakeven], "0%" ) )'),
    ("Support staff added: cost less fees freed", "Profit effects (a year)", 'IF( [Sim Lever Support Added] > 0, FORMAT( [Sim Paralegal Fees] - [Sim Support Added Cost], "+$#,0;-$#,0" ) )'),
    ("Pay review: cost a year", "Profit effects (a year)", 'IF( [Sim Pay Cost] <> 0, FORMAT( -[Sim Pay Cost], "+$#,0;-$#,0" ) )'),
    ("Rate increase that would pay for it", "Profit effects (a year)", 'IF( [Sim Pay Cost] <> 0, IF( ISBLANK( [Sim Rate To Fund] ), "not reachable", FORMAT( [Sim Rate To Fund], "+0.0" ) & "%" ) )'),
    ("Marketing: extra spend a year", "Profit effects (a year)", 'IF( [Sim Marketing Spend] > 0, FORMAT( -[Sim Marketing Spend], "+$#,0;-$#,0" ) )'),
    ("Extra inquiries → new matters", "Profit effects (a year)", 'IF( [Sim Marketing Spend] > 0, FORMAT( [Sim Marketing Inquiries], "0" ) & " → " & FORMAT( [Sim Marketing Matters], "0" ) )'),
    ("Fees from them in year one", "Profit effects (a year)", 'IF( [Sim Marketing Spend] > 0, FORMAT( [Sim Marketing Fees], "+$#,0;-$#,0" ) )'),
    ("New matter type: fees − costs, year one", "Profit effects (a year)", 'IF( [Sim Lever New Area] > 0, FORMAT( [Sim Area Net], "+$#,0;-$#,0" ) )'),
    ("New matter type at full speed, a year", "Profit effects (a year)", 'IF( [Sim Lever New Area] > 0, FORMAT( [Sim Area Net Full], "+$#,0;-$#,0" ) )'),
    ("Launch campaign earned back after", "Profit effects (a year)", 'IF( [Sim Lever New Area] > 0, IF( ISBLANK( [Sim Area Payback] ), "not within 5 years", [Sim Area Payback] & " months" ) )'),
    ("Fee earners leaving: pay saved", "Profit effects (a year)", 'IF( [Sim Lever Fee Earners Leaving] > 0, FORMAT( [Sim Cut Saving], "+$#,0;-$#,0" ) )'),
    ("Fees lost (after work kept)", "Profit effects (a year)", 'IF( [Sim Lever Fee Earners Leaving] > 0, FORMAT( -[Sim Fees Lost], "+$#,0;-$#,0" ) )'),
    ("Support roles cut: pay saved a year", "Profit effects (a year)", 'IF( [Sim Lever Support Cut] > 0, FORMAT( [Sim Support Saving], "+$#,0;-$#,0" ) )'),
    ("New branch: fees − costs, year one", "Profit effects (a year)", 'IF( [Sim Lever Branch] > 0, FORMAT( [Sim Branch Net], "+$#,0;-$#,0" ) )'),
    ("New branch at full speed, a year", "Profit effects (a year)", 'IF( [Sim Lever Branch] > 0, FORMAT( [Sim Branch Net Full], "+$#,0;-$#,0" ) )'),
    ("Fit-out earned back after", "Profit effects (a year)", 'IF( [Sim Lever Branch] > 0, IF( ISBLANK( [Sim Branch Payback] ), "not within 5 years", [Sim Branch Payback] & " months" ) )'),
    ("Platform: first-year saving", "Profit effects (a year)", 'IF( [Sim Platform Annual] <> 0, FORMAT( [Sim Platform Annual], "+$#,0;-$#,0" ) )'),
    ("Redundancy pay (NES)", "Cash", 'IF( [Sim Redundancy] > 0, FORMAT( [Sim Redundancy], "$#,0" ) & " · " & [Sim Redundancy Weeks] & " weeks each" )'),
    ("Notice pay", "Cash", 'IF( [Sim Notice Pay] > 0, FORMAT( [Sim Notice Pay], "$#,0" ) & " · " & [Sim Notice Weeks] & " weeks each" )'),
    ("Branch fit-out", "Cash", 'IF( [Sim Branch Fitout] > 0, FORMAT( [Sim Branch Fitout], "$#,0" ) )'),
    ("Platform migration and go-live dip", "Cash", 'IF( [Sim Platform One-off] > 0, FORMAT( [Sim Platform One-off], "$#,0" ) )'),
    ("Launch campaign", "Cash", 'IF( [Sim Area Launch] > 0, FORMAT( [Sim Area Launch], "$#,0" ) )'),
    ("Cash from collecting faster or slower", "Cash", 'IF( [Sim DSO Cash] <> 0, FORMAT( [Sim DSO Cash], "+$#,0;-$#,0" ) )'),
    ("Office account today", "Cash", 'FORMAT( [Sim Cash Now], "$#,0" )'),
    ("13-week low point: today → after", "Cash", 'FORMAT( [Sim Low Point Today], "$#,0" ) & " → " & FORMAT( [Sim Low Point], "$#,0" )'),
    ("Cash cover after the decision", "Cash", 'FORMAT( [Sim Cash Cover], "0.0" ) & " months"'),
]


def lever_dax(levers):
    """DAX expression for each lever's current value: goal-seek override, else compare-preset row, else slicer, else preset."""
    out = {}
    for lv in levers:
        pcol = f"CALCULATE( SELECTEDVALUE( 'Sim Preset'[{lv.key}] ), REMOVEFILTERS( 'Sim Preset' ), 'Sim Preset'[Preset] = v_preset )"
        if lv.kind == "num":
            sel = f"'{lv.table}'[{lv.label}]"
        elif lv.kind == "bool":
            sel = f"'{lv.table}'[Value]"
        else:
            sel = f"'{lv.table}'[{lv.label}]"
        filt = f"'{lv.table}'[{lv.label}]"
        normal = f"IF( NOT v_cmp && ISFILTERED( {filt} ) && HASONEVALUE( {sel} ), VALUES( {sel} ), {pcol} )"
        goal = None
        if lv.key in ("sim_util", "sim_rate", "sim_real", "sim_recov", "sim_infl"):
            goal = f'"{lv.key}"'
        if lv.key in ("sim_pay_fe", "sim_pay_support"):
            goal = '"sim_pay_both"'
        if goal:
            out[lv.var] = f"IF( v_goal = {goal}, v_goalval, {normal} )"
        else:
            out[lv.var] = normal
    out["D"] = "IF( ISFILTERED( 'Sim Delivery'[Delivery] ) && HASONEVALUE( 'Sim Delivery'[Delivery] ), VALUES( 'Sim Delivery'[Delivery] ), 1 )"
    return out


COMMON_VARS = """VAR v_cmp = ISFILTERED( 'Sim Compare'[Compare preset] )
VAR v_preset = IF( v_cmp, SELECTEDVALUE( 'Sim Compare'[Compare preset], "Custom" ), SELECTEDVALUE( 'Sim Preset'[Preset], "Custom" ) )
VAR v_goal = SELECTEDVALUE( 'Sim Goal Lever'[Lever], "" )
VAR v_goalval = SELECTEDVALUE( 'Sim Goal Step'[Hundredths], 0 ) / 100"""

# (measure name, formula, format) for every simulator output exposed in the report
SIM_OUTPUTS = [
    ("Sim Operating Profit", "op1", MONEY), ("Sim Base Operating Profit", "op0", MONEY), ("Sim Revenue", "rev1", MONEY), ("Sim Base Revenue", "rev0", MONEY),
    ("Sim Costs", "cost1", MONEY), ("Sim Base Costs", "cost0", MONEY), ("Sim Margin", "margin1", PCT), ("Sim Base Margin", "margin0", PCT),
    ("Sim Fees", "fees1", MONEY), ("Sim Hours", "hours_tot", NUM), ("Sim Base Hours", None, NUM),
    ("Sim Utilisation", "util1", PCT), ("Sim Team Utilisation", "team_util", PCT), ("Sim Hire Net", "hire_net", MONEY), ("Sim Hire Breakeven", "hire_breakeven_ramp", PCT0),
    ("Sim Paralegal Fees", "fees_para", MONEY), ("Sim Support Added Cost", "support_added_cost", MONEY), ("Sim Pay Cost", "pay_cost", MONEY),
    ("Sim Marketing Spend", "mkt_spend", MONEY), ("Sim Marketing Inquiries", "mkt_inq", NUM), ("Sim Marketing Matters", "mkt_matters", NUM1),
    ("Sim Marketing Fees", "fees_mkt", MONEY), ("Sim Marketing Capped", "mkt_capped", "0"), ("Sim Area Net", "area_net", MONEY),
    ("Sim Area Net Full", "area_net_full", MONEY), ("Sim Area Payback", "area_payback", "0"), ("Sim Area Launch", "area_launch", MONEY),
    ("Sim Cut Saving", "cut_saving", MONEY), ("Sim Fees Lost", "fees_cut", MONEY), ("Sim Support Saving", "support_saving", MONEY),
    ("Sim Branch Net", "branch_net", MONEY), ("Sim Branch Net Full", "branch_net_full", MONEY), ("Sim Branch Payback", "branch_payback", "0"),
    ("Sim Branch Fitout", "branch_fitout", MONEY), ("Sim Platform Annual", "platform_annual", MONEY), ("Sim Platform One-off", "platform_one_off", MONEY),
    ("Sim Redundancy", "redundancy", MONEY), ("Sim Redundancy Weeks", "redundancy_weeks", "0"), ("Sim Notice Pay", "notice_pay", MONEY),
    ("Sim Notice Weeks", "notice_weeks", "0"), ("Sim DSO Cash", "dso_cash", MONEY), ("Sim One-off Cash", "one_off", MONEY),
    ("Sim Cash Effect", "cash_effect", MONEY), ("Sim Low Point", "low1", MONEY), ("Sim Cash Cover", "cash_cover", NUM1),
    ("Sim Gap to Budget", "gap_budget", MONEY), ("Sim Bridge Fees", "bridge_fees", MONEY), ("Sim Bridge Disbursements", "bridge_disb", MONEY),
    ("Sim Bridge Costs", "bridge_costs", MONEY), ("Sim Effective Rate", "eff1", MONEY),
]
LEVER_MEASURES = [("Sim Lever Hires", "L_hires"), ("Sim Lever Support Added", "L_add_support"), ("Sim Lever New Area", "L_new_area"),
                  ("Sim Lever Fee Earners Leaving", "L_cut_fe"), ("Sim Lever Support Cut", "L_cut_support"), ("Sim Lever Branch", "L_branch"),
                  ("Sim Lever Rate", "L_rate"), ("Sim Lever Utilisation", "L_util"), ("Sim Lever Realisation", "L_real"),
                  ("Sim Lever Recovery", "L_recov"), ("Sim Lever Overheads", "L_infl"), ("Sim Lever Pay FE", "L_pay_fe"), ("Sim Lever Pay Support", "L_pay_support")]
ALL_SIM_TABLES = None   # filled by simulator_measures (every lever / preset / goal table, for REMOVEFILTERS)


def simulator_measures(consts, levers):
    ldax = lever_dax(levers)
    out = []
    folder = "Simulator"

    def chain(target, extra_formulas=None):
        body = SP.to_dax(target, consts, ldax, SP.FORMULAS + (extra_formulas or []))
        return COMMON_VARS + "\n" + body

    for name, target, fmt in SIM_OUTPUTS:
        if name == "Sim Base Hours":
            out.append(Measure(name, SP.dax_num(consts["H0"]), fmt, folder))
            continue
        out.append(Measure(name, chain(target), fmt, folder))
    for name, var in LEVER_MEASURES:
        out.append(Measure(name, COMMON_VARS + f"\nVAR x = {ldax[var]}\nRETURN x", "0.0", folder + "\\Levers", hidden=True))
    out.append(Measure("Sim Base Utilisation", SP.dax_num(consts["UTIL0"]), PCT, folder))
    out.append(Measure("Sim Cash Now", SP.dax_num(consts["CASH_NOW"]), MONEY, folder))
    out.append(Measure("Sim Low Point Today", SP.dax_num(consts["LOW0"]), MONEY, folder))
    out.append(Measure("Sim Minimum Cash", SP.dax_num(consts["MIN_CASH"]), MONEY, folder))
    out.append(Measure("Sim Budget Profit", SP.dax_num(consts["BUDGET_OP"]), MONEY, folder))
    out.append(Measure("Sim Budget Margin", SP.dax_num(consts["BUDGET_MARGIN"]), PCT, folder))

    lever_by_key0 = {lv.key: lv for lv in levers}
    tables = [lv.table for lv in levers] + ["Sim Preset", "Sim Compare", "Sim Delivery", "Sim Goal Lever", "Sim Goal Step"]
    rm_all = ", ".join(f"REMOVEFILTERS( '{t}' )" for t in tables)
    # today (no change) and the comparison to it
    out.append(Measure("Sim Today Profit", f"CALCULATE( [Sim Operating Profit], {rm_all} )", MONEY, folder))
    out.append(Measure("Sim vs Today", "[Sim Operating Profit] - [Sim Today Profit]", MONEY, folder))
    out.append(Measure("Sim vs Today %", "DIVIDE( [Sim Operating Profit] - [Sim Today Profit], ABS( [Sim Today Profit] ) )", PCT, folder))
    # KPI captions
    out.append(Measure("Sim Profit Caption", 'FORMAT( [Sim vs Today %], "▲ +0.0%;▼ -0.0%;0.0%" ) & " vs base · " & FORMAT( [Sim vs Today], "+$#,0;-$#,0;$0" ) & " vs today"', None, folder))
    out.append(Measure("Sim Margin Caption", 'FORMAT( ( [Sim Margin] - [Sim Base Margin] ) * 100, "▲ +0.0 ""pp"";▼ -0.0 ""pp"";0.0 ""pp""" ) & " vs base · base " & FORMAT( [Sim Base Margin], "0.0%" )', None, folder))
    out.append(Measure("Sim Gap Caption", '"budget profit " & FORMAT( [Sim Budget Profit], "$#,0" )', None, folder))
    out.append(Measure("Sim Low Caption", '"today " & FORMAT( [Sim Low Point Today], "$#,0" ) & " · minimum " & FORMAT( [Sim Minimum Cash], "$#,0" )', None, folder))
    out.append(Measure("Sim Gap Colour", 'IF( [Sim Gap to Budget] >= 0, "#047857", "#b91c1c" )', None, folder + "\\Format", hidden=True))
    out.append(Measure("Sim Low Colour", 'IF( [Sim Low Point] < [Sim Minimum Cash], "#b91c1c", "#0f172a" )', None, folder + "\\Format", hidden=True))
    out.append(Measure("Sim Warning", (
        'VAR w1 = IF( [Sim Low Point] < [Sim Minimum Cash], "This takes the account below the $60K minimum balance. Fund it first: lower partner drawings, a loan, or stage the spend. ", "" )\n'
        'VAR w2 = IF( [Sim Utilisation] > 0.95 || [Sim Team Utilisation] > 0.95, "Utilisation above about 95% is rarely sustainable: check burnout and quality risk. ", "" )\n'
        'VAR w3 = IF( [Sim Marketing Capped] = 1, "The team cannot take all the new work: the extra fees stop at 95% utilisation. Pair the campaign with a hire. ", "" )\n'
        'VAR w4 = IF( [Sim Pay Cost] <> 0 && MIN( [Sim Lever Pay FE], [Sim Lever Pay Support] ) < 3.4, "Below market wage growth (3.4%, ABS WPI): expect retention risk. Pay cuts generally need agreement and cannot go below award minimums. ", "" )\n'
        'VAR w5 = IF( [Sim Lever Fee Earners Leaving] > 0 && [Sim Fees Lost] > [Sim Cut Saving], "The fee earner(s) leaving bill more than they cost: this cut lowers profit. ", "" )\n'
        'VAR txt = w1 & w2 & w3 & w4 & w5\n'
        'RETURN IF( txt = "", "No warnings for this scenario.", txt )'), None, folder))
    pay3 = f"TREATAS( {{ 3 }}, '{lever_by_key0['sim_pay_fe'].table}'[{lever_by_key0['sim_pay_fe'].label}] ), TREATAS( {{ 3 }}, '{lever_by_key0['sim_pay_support'].table}'[{lever_by_key0['sim_pay_support'].label}] )"
    out.append(Measure("Sim Pay Rise Cost", f"CALCULATE( [Sim Pay Cost], {rm_all}, {pay3} )", MONEY, folder))
    out.append(Measure("Sim Pay Rise Rate", f"CALCULATE( [Sim Rate To Fund], {rm_all}, {pay3} )", "0.0", folder))
    # what is switched on (the slicers start empty, so this shows the preset's levers too)
    parts, vars_ = [], []
    for lv in levers:
        vars_.append(f"VAR v_{lv.var} = {ldax[lv.var]}")
        d = S.DEFAULTS[lv.key]
        if lv.kind == "cat":
            parts.append(f'IF( v_{lv.var} <> {SP.dax_str(d)}, "{lv.label}: " & v_{lv.var} & " · " )')
        elif lv.kind == "bool":
            parts.append(f'IF( v_{lv.var} <> {SP.dax_num(d)}, "{lv.label}: " & IF( v_{lv.var} > 0, "yes", "no" ) & " · " )')
        else:
            fmt = "$#,0" if "$" in lv.fmt else ("+0.0;-0.0;0" if lv.step != int(lv.step) or lv.lo < 0 else "0")
            parts.append(f'IF( v_{lv.var} <> {SP.dax_num(d)}, "{lv.label}: " & FORMAT( v_{lv.var}, "{fmt}" ) & " · " )')
    summ = COMMON_VARS + "\n" + "\n".join(vars_) + "\nVAR txt = " + "\n    & ".join(parts) + \
        '\nRETURN IF( txt = "", "No change: today\'s firm, last 12 months", LEFT( txt, LEN( txt ) - 3 ) )'
    out.append(Measure("Sim Scenario Summary", summ, None, folder))
    # bridge
    out.append(Measure("Sim Bridge Value", "SWITCH( SELECTEDVALUE( 'Sim Bridge Step'[Step] ),\n    \"Today's profit\", [Sim Base Operating Profit],\n"
                       "    \"Fees\", [Sim Bridge Fees],\n    \"Disb. recovery\", [Sim Bridge Disbursements],\n    \"Costs\", [Sim Bridge Costs]\n)", MONEY, folder))
    # effect lines
    sw = "SWITCH( SELECTEDVALUE( 'Sim Effect Line'[Line] ),\n" + ",\n".join(f'    "{l}", {e}' for l, _, e in EFFECT_LINES) + "\n)"
    out.append(Measure("Sim Effect", sw, None, folder))
    # what moves profit most (one unit of each lever, from today's base)
    tests = [(n, v) for n, v in S.LEVER_TESTS.items() if v]
    lever_by_key = {lv.key: lv for lv in levers}
    branches = []
    for n, t in tests:
        filt = []
        for k, v in t.items():
            lv = lever_by_key[k]
            col = f"'{lv.table}'[{lv.label}]"
            filt.append(f"TREATAS( {{ {SP.dax_str(v) if lv.kind == 'cat' else SP.dax_num(v)} }}, {col} )")
        branches.append(f'    "{n}", CALCULATE( [Sim Operating Profit], {rm_all}, {", ".join(filt)} ) - base')
    out.append(Measure("Sim Lever Effect", "VAR base = [Sim Today Profit]\nRETURN SWITCH( SELECTEDVALUE( 'Sim Lever Test'[Test] ),\n" + ",\n".join(branches) + "\n)", MONEY, folder))
    # delivery
    out.append(Measure("Sim Profit at Delivery", "[Sim Operating Profit]", MONEY, folder, description="Use with 'Sim Delivery'[Label] on the axis."))
    # goal seek
    out.append(Measure("Sim Goal Kind", "SELECTEDVALUE( 'Sim Goal Target'[Target], \"FY26 budget profit\" )", None, folder + "\\Goal", hidden=True))
    out.append(Measure("Sim Goal Metric", 'IF( [Sim Goal Kind] = "FY26 budget margin", [Sim Margin], [Sim Operating Profit] )', None, folder + "\\Goal", hidden=True))
    out.append(Measure("Sim Goal Value", ('VAR k = [Sim Goal Kind]\nRETURN SWITCH( k, "FY26 budget margin", [Sim Budget Margin],\n'
                                          '    "Today\'s profit plus extra", [Sim Today Profit] + SELECTEDVALUE( \'Sim Goal Uplift\'[Extra profit a year], 0 ),\n'
                                          '    [Sim Budget Profit] )'), None, folder + "\\Goal"))
    out.append(Measure("Sim Goal Caption", ('VAR k = [Sim Goal Kind]\nVAR t = [Sim Goal Value]\nVAR c = [Sim Goal Metric]\n'
                                            'VAR tt = IF( k = "FY26 budget margin", FORMAT( t, "0.0%" ), FORMAT( t, "$#,0" ) )\n'
                                            'VAR cc = IF( k = "FY26 budget margin", FORMAT( c, "0.0%" ), FORMAT( c, "$#,0" ) )\n'
                                            'VAR gap = IF( c >= t, "already met", IF( k = "FY26 budget margin", FORMAT( ( t - c ) * 100, "0.0" ) & " pp short", FORMAT( t - c, "$#,0" ) & " short" ) )\n'
                                            'RETURN "Target: " & tt & ". Your scenario gives " & cc & " (" & gap & "). Each line moves one lever on its own, on top of your current levers."'),
                       None, folder + "\\Goal"))
    caps = dict(sim_util=(1 - consts["UTIL0"]) * 100, sim_rate=30.0, sim_real=(1 - consts["REAL0"]) * 100, sim_recov=30.0)
    seek = {}
    for k in ("sim_util", "sim_rate", "sim_real", "sim_recov", "sim_infl"):
        lv = lever_by_key[k]
        stepH = int(round(S.BOUNDS[k][2] * 100))
        cur = f"[{dict((v, n) for n, v in LEVER_MEASURES)[lv.var]}]"
        ev = (f"CALCULATE( [Sim Goal Metric], TREATAS( {{ \"{k}\" }}, 'Sim Goal Lever'[Lever] ), TREATAS( {{ [Value] }}, 'Sim Goal Step'[Hundredths] ) ) >= target")
        if k == "sim_infl":
            body = (f"VAR target = [Sim Goal Value]\nVAR curH = ROUND( {cur} * 100, 0 )\n"
                    f"VAR lo = -6000\n"
                    f"VAR x = MAXX( FILTER( GENERATESERIES( lo, curH, {stepH} ), {ev} ), [Value] )\n"
                    f"RETURN IF( ISBLANK( x ), BLANK(), x / 100 )")
        else:
            capH = int(-(-caps[k] * 100 // stepH) * stepH)   # cap rounded up to the slider step
            body = (f"VAR target = [Sim Goal Value]\nVAR curH = ROUND( {cur} * 100, 0 )\n"
                    f"VAR x = MINX( FILTER( GENERATESERIES( curH, MAX( curH, {capH} ), {stepH} ), {ev} ), [Value] )\n"
                    f"RETURN IF( ISBLANK( x ), BLANK(), x / 100 )")
        nm = f"Sim Goal {k[4:]}"
        seek[k] = (nm, cur)
        out.append(Measure(nm, body, "0.0", folder + "\\Goal", hidden=True))
    g_req = "SWITCH( SELECTEDVALUE( 'Sim Goal Row'[Key] ),\n" + ",\n".join(f'    "{k}", [{nm}]' for k, (nm, _) in seek.items()) + "\n)"
    g_cur = "SWITCH( SELECTEDVALUE( 'Sim Goal Row'[Key] ),\n" + ",\n".join(f'    "{k}", {cur}' for k, (_, cur) in seek.items()) + "\n)"
    out.append(Measure("Sim Goal Required", g_req, "0.0", folder + "\\Goal"))
    out.append(Measure("Sim Goal Current", g_cur, "0.0", folder + "\\Goal"))
    bounds = ",\n".join(f'    "{k}", {SP.dax_num(S.BOUNDS[k][0])}' for k in seek)
    bounds_hi = ",\n".join(f'    "{k}", {SP.dax_num(S.BOUNDS[k][1])}' for k in seek)
    out.append(Measure("Sim Goal Need", ('VAR k = SELECTEDVALUE( \'Sim Goal Row\'[Key] )\nVAR r = [Sim Goal Required]\nVAR c = [Sim Goal Current]\n'
                                         'VAR unit = IF( k = "sim_rate" || k = "sim_infl", "%", " pp" )\n'
                                         'RETURN IF( ISBLANK( r ), "Not reachable on its own", IF( r = c, "Already met", FORMAT( r, "+0.0;-0.0;0.0" ) & unit & " (" & FORMAT( r - c, "+0.0;-0.0" ) & unit & " from now)" ) )'),
                       None, folder + "\\Goal"))
    out.append(Measure("Sim Goal Difficulty", ('VAR k = SELECTEDVALUE( \'Sim Goal Row\'[Key] )\nVAR r = [Sim Goal Required]\nVAR c = [Sim Goal Current]\n'
                                               f'VAR lo = SWITCH( k,\n{bounds}\n)\nVAR hi = SWITCH( k,\n{bounds_hi}\n)\n'
                                               'VAR fits = r >= lo && r <= hi\n'
                                               'VAR span = IF( k = "sim_infl", c - lo, hi - MAX( c, 0 ) )\n'
                                               'VAR share = DIVIDE( ABS( r - c ), span, 9 )\n'
                                               'RETURN IF( ISBLANK( r ), "Not reachable on its own", IF( r = c, "Already met", IF( fits && share <= 0.5, "Comfortable", IF( fits, "Stretch", "Beyond a realistic range" ) ) ) )'),
                       None, folder + "\\Goal"))
    # rate that would fund the pay review (to 0.01%)
    out.append(Measure("Sim Rate To Fund", (
        "VAR target = CALCULATE( [Sim Operating Profit], TREATAS( { \"sim_pay_both\" }, 'Sim Goal Lever'[Lever] ), TREATAS( { 0 }, 'Sim Goal Step'[Hundredths] ) )\n"
        "VAR curH = ROUND( [Sim Lever Rate] * 100, 0 )\n"
        "VAR coarse = MINX( FILTER( GENERATESERIES( curH, 3000, 50 ), CALCULATE( [Sim Operating Profit], TREATAS( { \"sim_rate\" }, 'Sim Goal Lever'[Lever] ), TREATAS( { [Value] }, 'Sim Goal Step'[Hundredths] ) ) >= target ), [Value] )\n"
        "VAR fine = MINX( FILTER( GENERATESERIES( MAX( curH, coarse - 50 ), coarse, 1 ), CALCULATE( [Sim Operating Profit], TREATAS( { \"sim_rate\" }, 'Sim Goal Lever'[Lever] ), TREATAS( { [Value] }, 'Sim Goal Step'[Hundredths] ) ) >= target ), [Value] )\n"
        "RETURN IF( ISBLANK( coarse ), BLANK(), ( fine - curH ) / 100 )"), "0.00", folder))
    # compare presets
    out.append(Measure("Sim Compare Profit", "[Sim Operating Profit]", MONEY, folder + "\\Compare"))
    out.append(Measure("Sim Compare vs Today", "[Sim Operating Profit] - [Sim Today Profit]", MONEY, folder + "\\Compare"))
    # check page: DAX vs the Python engine
    metric_sw = ",\n".join([f'        "{m}", {e}' for m, e in [("op1", "[Sim Operating Profit]"), ("rev1", "[Sim Revenue]"), ("cost1", "[Sim Costs]"),
                                                            ("one_off", "[Sim One-off Cash]"), ("margin1", "[Sim Margin]"), ("util1", "[Sim Utilisation]"),
                                                            ("low1", "[Sim Low Point]"),
                                                            ("op1_half_delivered", "CALCULATE( [Sim Operating Profit], TREATAS( { 0.5 }, 'Sim Delivery'[Delivery] ) )"),
                                                            ("goal_rate", "[Sim Goal rate]"), ("goal_util", "[Sim Goal util]"), ("goal_infl", "[Sim Goal infl]"),
                                                            ("rate_to_fund", "[Sim Rate To Fund]"), ("branch_payback", "[Sim Branch Payback]"),
                                                            ("area_payback", "[Sim Area Payback]")]]
                         + [f'        "rank: {n}", CALCULATE( [Sim Lever Effect], TREATAS( {{ "{n}" }}, \'Sim Lever Test\'[Test] ) )' for n, _ in tests])
    out.append(Measure("Check DAX", ("VAR p = SELECTEDVALUE( 'Sim Expected'[Preset] )\nVAR m = SELECTEDVALUE( 'Sim Expected'[Metric] )\n"
                                     "RETURN CALCULATE(\n    SWITCH( m,\n" + metric_sw + "\n    ),\n    TREATAS( { p }, 'Sim Compare'[Compare preset] ),\n"
                                     "    REMOVEFILTERS( 'Sim Goal Target' ), REMOVEFILTERS( 'Sim Goal Uplift' )\n)"), "#,0.0000", "Check"))
    out.append(Measure("Check Python", "SUM( 'Sim Expected'[Expected] )", "#,0.0000", "Check"))
    out.append(Measure("Check Difference", "[Check DAX] - [Check Python]", "#,0.0000", "Check"))
    out.append(Measure("Check Result", ('VAR e = [Check Python]\nVAR d = ABS( [Check Difference] )\n'
                                        'VAR m = SELECTEDVALUE( \'Sim Expected\'[Metric] )\n'
                                        'VAR tol = IF( m = "rate_to_fund", 0.011, MAX( 0.5, ABS( e ) * 0.000001 ) )\n'
                                        'RETURN IF( ISBLANK( [Check DAX] ) && NOT ISBLANK( e ), "✗ missing", IF( d <= tol, "✓ match", "✗ differs" ) )'), None, "Check"))
    out.append(Measure("Check Passed", ("VAR t = ADDCOLUMNS( SUMMARIZE( 'Sim Expected', 'Sim Expected'[Preset], 'Sim Expected'[Metric] ), \"r\", [Check Result] )\n"
                                        "RETURN COUNTROWS( FILTER( t, [r] = \"✓ match\" ) ) & \" of \" & COUNTROWS( t ) & \" checks match the Python engine\""), None, "Check"))
    return out


def build_model(consts, tables, levers, ctx, base_url=DEFAULT_BASE_URL):
    """Returns (list of Table, list of relationship strings, expressions text)."""
    out = [import_table(n, "warehouse", f) for n, f in WAREHOUSE] + [import_table(n, "powerbi", f) for n, f in ANALYSIS]
    out += helper_tables()
    sim = simulator_tables(consts, tables, levers, ctx)
    sim_measures = Table("Simulator", [Column("Note", "string", calc_source="Note", hidden=True)], "calculated", 'ROW( "Note", "Simulator measures live here" )')
    sim_measures.measures = simulator_measures(consts, levers)
    out += sim + [sim_measures]
    rels = [relationship(*r) for r in RELATIONSHIPS]
    expr = f'expression BaseUrl = "{base_url}" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]\n'
    return out, rels, expr
