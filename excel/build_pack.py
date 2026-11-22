"""Excel "Principal's Decision Pack": the SQL answers to the Principal's questions in one workbook, with a formula-driven summary.

    python -m excel.build_pack        # -> excel/Principal_Decision_Pack.xlsx

Data sheets hold the results of sql/analysis/ queries 07, 09, 11, 12 and 13 as Excel tables. In day-to-day use they are
refreshed by Power Query (excel/powerquery/*.pq, steps on the "Power Query" sheet) straight from the CSV files in this
repository; this script builds the same workbook locally so it can be versioned and tested.
The Summary sheet is formulas only (SUMIFS, INDEX/MATCH, MIN, COUNTIF), so every number traces back to a data sheet.
All data is SIMULATED.
"""
from __future__ import annotations

import sys
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "sql"))
import run_queries as RQ  # noqa: E402
from warehouse.build import build_warehouse  # noqa: E402

OUT = ROOT / "excel" / "Principal_Decision_Pack.xlsx"
F = "Arial"
MONEY, PCT = '$#,##0;($#,##0);-', '0.0"%"'
HEAD_FILL, HEAD_FONT = PatternFill("solid", fgColor="0A8496"), Font(name=F, bold=True, color="FFFFFF")
BODY, BOLD, TITLE = Font(name=F, size=10), Font(name=F, size=10, bold=True), Font(name=F, size=14, bold=True)
INPUT_FILL = PatternFill("solid", fgColor="FFF2CC")
SHEETS = [  # sheet, query, table name, money columns, percent columns
    ("PnL", "09_pnl_actual_vs_budget", "tblPnL", {"actual_revenue", "budget_revenue", "actual_profit", "budget_profit", "actual_profit_fy_ytd",
                                                  "budget_profit_fy_ytd", "profit_ytd_variance"}, {"revenue_var_pct", "profit_var_pct", "actual_margin_pct", "revenue_mom_pct"}),
    ("Where_to_hire", "11_where_to_hire", "tblHire", {"effective_rate", "fees_12m"}, {"matters_growth_pct", "lawyer_utilisation_pct", "margin_pct"}),
    ("Staffing", "12_support_staffing", "tblStaffing", {"gap_cost_a_year"}, {"pct_of_support_staff"}),
    ("Marketing", "13_marketing_channels", "tblMarketing", {"spend_12m", "cost_per_inquiry", "cost_per_new_matter", "fees_from_new_matters"}, {"conversion_pct"}),
    ("Receivables", "07_receivables_ageing_by_client", "tblAgeing", {"ar_incl_gst", "not_yet_due", "days_1_30", "days_31_60", "days_61_90", "days_90_plus"},
     {"pct_overdue", "pct_of_firm_ar"}),
]


def _data_sheet(wb, con, name, query, table, money, pct):
    ws = wb.create_sheet(name)
    cols, rows = RQ.run_query(con, RQ.QUERY_DIR / f"{query}.sql")
    ws.append(cols)
    for r in rows:
        ws.append(list(r))
    for c in ws[1]:
        c.font, c.fill, c.alignment = HEAD_FONT, HEAD_FILL, Alignment(wrap_text=True, vertical="center")
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.font = BODY
            col = cols[c.column - 1]
            if col in money:
                c.number_format = MONEY
            elif col in pct:
                c.number_format = PCT
    t = Table(displayName=table, ref=f"A1:{get_column_letter(len(cols))}{len(rows) + 1}")
    t.tableStyleInfo = TableStyleInfo(name="TableStyleMedium2", showRowStripes=True)
    ws.add_table(t)
    for i, col in enumerate(cols, 1):
        ws.column_dimensions[get_column_letter(i)].width = max(11, min(28, len(col) + 3))
    ws.freeze_panes = "A2"
    return {col: (get_column_letter(i), len(rows) + 1) for i, col in enumerate(cols, 1)}


def build(out: Path = OUT) -> Path:
    con = build_warehouse(":memory:")
    wb = Workbook()
    summary = wb.active
    summary.title = "Summary"
    refs = {name: _data_sheet(wb, con, name, q, t, m, p) for name, q, t, m, p in SHEETS}

    def rng(sheet, col):
        letter, last = refs[sheet][col]
        return f"{sheet}!${letter}$2:${letter}${last}"

    s = summary
    s["A1"], s["A1"].font = "Principal's Decision Pack (simulated data)", TITLE
    s["A2"], s["A2"].font = "Every number below is a formula on the data sheets, which Power Query refreshes from the repository.", BODY
    s["A4"], s["B4"] = "Financial year", "FY26"
    s["B4"].fill, s["B4"].font = INPUT_FILL, BOLD
    lines = [
        ("Is the firm on budget?", None, None),
        ("Operating profit, year to date", f'=SUMIFS({rng("PnL", "actual_profit")},{rng("PnL", "fy_label")},$B$4)', MONEY),
        ("Budget operating profit, year to date", f'=SUMIFS({rng("PnL", "budget_profit")},{rng("PnL", "fy_label")},$B$4)', MONEY),
        ("Variance (favourable +)", "=B7-B8", MONEY),
        ("Where should we hire?", None, None),
        ("Practice area to hire in first", f'=INDEX({rng("Where_to_hire", "practice_area")},MATCH(1,{rng("Where_to_hire", "priority_rank")},0))', None),
        ("Its lawyers' utilisation", f'=INDEX({rng("Where_to_hire", "lawyer_utilisation_pct")},MATCH(1,{rng("Where_to_hire", "priority_rank")},0))', PCT),
        ("Are support teams sized right?", None, None),
        ("Teams over-staffed", f'=COUNTIF({rng("Staffing", "status")},"Over-staffed")', "0"),
        ("Cost of over-staffing a year", f'=SUMIFS({rng("Staffing", "gap_cost_a_year")},{rng("Staffing", "status")},"Over-staffed")', MONEY),
        ("Where does marketing work?", None, None),
        ("Cheapest channel per new matter", f'=INDEX({rng("Marketing", "channel")},MATCH(MIN({rng("Marketing", "cost_per_new_matter")}),{rng("Marketing", "cost_per_new_matter")},0))', None),
        ("Its cost per new matter", f'=MIN({rng("Marketing", "cost_per_new_matter")})', MONEY),
        ("Dearest channel per new matter", f'=INDEX({rng("Marketing", "channel")},MATCH(MAX({rng("Marketing", "cost_per_new_matter")}),{rng("Marketing", "cost_per_new_matter")},0))', None),
        ("Who owes us money?", None, None),
        ("Receivables (incl. GST)", f'=SUM({rng("Receivables", "ar_incl_gst")})', MONEY),
        ("Overdue more than 60 days", f'=SUM({rng("Receivables", "days_61_90")})+SUM({rng("Receivables", "days_90_plus")})', MONEY),
        ("Clients to escalate", f'=COUNTIF({rng("Receivables", "collections_action")},"Escalate")', "0"),
    ]
    r = 6
    for label, formula, fmt in lines:
        a = s.cell(r, 1, label)
        if formula is None:
            a.font = Font(name=F, size=11, bold=True, color="0A8496")
        else:
            a.font = BODY
            b = s.cell(r, 2, formula)
            b.font = BOLD
            if fmt:
                b.number_format = fmt
        r += 1
    s.column_dimensions["A"].width, s.column_dimensions["B"].width = 42, 26

    pq = wb.create_sheet("Power Query")
    steps = ["How to refresh this workbook with Power Query (Excel for Windows or Mac, Microsoft 365)",
             "1. Data > Get Data > From Other Sources > Blank Query > Advanced Editor.",
             "2. Paste excel/powerquery/00_fnQueryResult.pq, Done, rename the query to fnQueryResult.",
             "3. Repeat for 01_PnL.pq … 05_Receivables.pq (one query each), then Close & Load To > Table on the matching sheet.",
             "4. 06_Staffing_From_Warehouse.pq rebuilds the staffing headcount by merging three warehouse tables (dim_branch, dim_department, fact_staffing).",
             "5. Data > Refresh All re-downloads every CSV from GitHub; the Summary formulas update by themselves.",
             "Source files: docs/query_results/*.csv (SQL answers) and data/warehouse/*.csv (warehouse tables) in this repository."]
    for i, t in enumerate(steps, 1):
        pq.cell(i, 1, t).font = BOLD if i == 1 else BODY
    pq.column_dimensions["A"].width = 130
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    return out


if __name__ == "__main__":
    print(f"wrote {build()}")
