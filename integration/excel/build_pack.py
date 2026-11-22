"""Excel "Debtors & Revenue Pack" built from the warehouse marts.

    python -m integration.excel.build_pack      # -> integration/excel/Debtors_Revenue_Pack.xlsx

The Data_* tabs are Excel tables (tblAged, tblRevenue, tblCollections). In day-to-day use they are refreshed by Power Query
(integration/powerquery/*.pq, steps on the "Power Query" tab); this script produces the same workbook from the local marts so it
can be versioned and tested. The Summary tab is formulas only (SUMIFS, COUNTIFS, INDEX/MATCH) plus a reconciliation cell.
"""
from __future__ import annotations

from pathlib import Path

import duckdb
from openpyxl import Workbook
from openpyxl.formatting.rule import DataBarRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo

HERE = Path(__file__).resolve().parent
DB = HERE.parent / "law_firm.duckdb"
OUT = HERE / "Debtors_Revenue_Pack.xlsx"
BUCKETS = ["Not yet due", "1–30 days", "31–60 days", "61–90 days", "90+ days"]
F, MONEY = "Arial", '$#,##0;($#,##0);-'
H_FILL, H_FONT = PatternFill("solid", fgColor="0A8496"), Font(name="Arial", bold=True, color="FFFFFF")
BODY, BOLD = Font(name=F, size=10), Font(name=F, size=10, bold=True)
THIN = Side(style="thin", color="BFBFBF")


def _header(ws, row, labels):
    for i, h in enumerate(labels, 1):
        c = ws.cell(row, i, h)
        c.font, c.fill, c.alignment = H_FONT, H_FILL, Alignment(wrap_text=True, vertical="center")


def _data_sheet(wb, con, name, sql, table, fmts):
    ws = wb.create_sheet(name)
    cur = con.execute(sql)
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    ws.append(cols)
    for r in rows:
        ws.append([float(v) if hasattr(v, "as_tuple") else v for v in r])
    _header(ws, 1, cols)
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.font = BODY
            if cols[c.column - 1] in fmts:
                c.number_format = fmts[cols[c.column - 1]]
    t = Table(displayName=table, ref=f"A1:{get_column_letter(len(cols))}{len(rows) + 1}")
    t.tableStyleInfo = TableStyleInfo(name="TableStyleMedium2", showRowStripes=True)
    ws.add_table(t)
    for i, col in enumerate(cols, 1):
        ws.column_dimensions[get_column_letter(i)].width = max(12, len(col) + 4)
    ws.freeze_panes = "A2"


def build(db: Path = DB, out: Path = OUT) -> Path:
    con = duckdb.connect(str(db), read_only=True)
    wb = Workbook()
    date_fmt = "dd/mm/yyyy"
    _data_sheet(wb, con, "Data_Aged", "select * from marts.aged_receivables order by days_past_due desc, balance_due desc", "tblAged",
                {"as_at": date_fmt, "invoice_date": date_fmt, "due_date": date_fmt, "balance_due": MONEY})
    _data_sheet(wb, con, "Data_Revenue", "select * from marts.revenue_monthly order by month, practice_area", "tblRevenue",
                {"month": "mmm-yy", "revenue_ex_gst": MONEY})
    _data_sheet(wb, con, "Data_Collections", "select * from marts.collection_performance order by outstanding desc", "tblCollections",
                {"outstanding": MONEY, "avg_days_to_pay": "0.0", "pct_paid_on_time": "0.0"})
    areas = [r[0] for r in con.execute("select practice_area from marts.collection_performance order by outstanding desc").fetchall()]
    as_at = con.execute("select max(as_at) from marts.aged_receivables").fetchone()[0]

    ws = wb.active
    ws.title = "Summary"
    ws.sheet_view.showGridLines = False
    ws["A1"] = "Example Legal: Debtors & Revenue Pack"
    ws["A1"].font = Font(name=F, bold=True, size=14)
    ws["A2"] = f"Simulated data. Source: MYOB API -> Snowflake marts via Power Query. Receivables as at {as_at:%d %b %Y}. Refresh: Data > Refresh All."
    ws["A2"].font = Font(name=F, italic=True, size=9, color="666666")

    ws["A4"] = "Receivables by age (incl. GST)"; ws["A4"].font = Font(name=F, bold=True, size=12)
    _header(ws, 5, ["Days past due", "Invoices", "Balance due", "% of total"])
    for r, b in enumerate(BUCKETS, 6):
        ws.cell(r, 1, b).font = BODY
        ws.cell(r, 2, f"=COUNTIFS(tblAged[ageing_bucket],A{r})").font = BODY
        c = ws.cell(r, 3, f"=SUMIFS(tblAged[balance_due],tblAged[ageing_bucket],A{r})"); c.number_format, c.font = MONEY, BODY
        c = ws.cell(r, 4, f"=IFERROR(C{r}/$C$11,0)"); c.number_format, c.font = "0.0%", BODY
    ws["A11"], ws["B11"], ws["C11"], ws["D11"] = "Total", "=SUM(B6:B10)", "=SUM(C6:C10)", "=SUM(D6:D10)"
    ws["C11"].number_format, ws["D11"].number_format = MONEY, "0.0%"
    for c in ws[11][:4]:
        c.font, c.border = BOLD, Border(top=THIN)
    ws.conditional_formatting.add("C6:C10", DataBarRule(start_type="num", start_value=0, end_type="max", color="4FB6C4"))

    ws["F5"] = "Reconciliation"; ws["F5"].font = BOLD
    ws["F6"], ws["G6"] = "Total on Data_Aged", "=SUM(tblAged[balance_due])"
    ws["F7"], ws["G7"] = "Difference (must be 0)", "=ROUND(C11-G6,2)"
    ws["F8"], ws["G8"] = "Status", '=IF(G7=0,"OK","CHECK")'
    ws["F9"], ws["G9"] = "Dashboard receivables", 1053551.51
    ws["G9"].font = Font(name=F, size=10, color="0000FF")
    ws["F10"], ws["G10"] = "Ties to dashboard", '=IF(ROUND(G6-G9,2)=0,"OK","CHECK")'
    for cell in ("G6", "G7", "G9"):
        ws[cell].number_format = MONEY
    for cell in ("F6", "F7", "F8", "F9", "F10", "G6", "G7", "G8", "G10"):
        ws[cell].font = BODY
    ws["F11"] = "Input from docs/PIPELINE_QUALITY.md (receivables incl. GST at the report date)."
    ws["F11"].font = Font(name=F, italic=True, size=8, color="666666")

    ws["A14"] = "By practice area"; ws["A14"].font = Font(name=F, bold=True, size=12)
    _header(ws, 15, ["Practice area", "Revenue ex GST (all months)", "Avg days to pay", "% paid on time", "Outstanding", "Outstanding % of revenue"])
    for r, a in enumerate(areas, 16):
        ws.cell(r, 1, a).font = BODY
        cells = [(2, f"=SUMIFS(tblRevenue[revenue_ex_gst],tblRevenue[practice_area],A{r})", MONEY),
                 (3, f"=INDEX(tblCollections[avg_days_to_pay],MATCH(A{r},tblCollections[practice_area],0))", "0.0"),
                 (4, f"=INDEX(tblCollections[pct_paid_on_time],MATCH(A{r},tblCollections[practice_area],0))/100", "0.0%"),
                 (5, f"=INDEX(tblCollections[outstanding],MATCH(A{r},tblCollections[practice_area],0))", MONEY),
                 (6, f"=IFERROR(E{r}/B{r},0)", "0.0%")]
        for col, f, fmt in cells:
            c = ws.cell(r, col, f); c.number_format, c.font = fmt, BODY
    last = 15 + len(areas); tr = last + 1
    ws.cell(tr, 1, "Total")
    for col in (2, 5):
        L = get_column_letter(col)
        ws.cell(tr, col, f"=SUM({L}16:{L}{last})").number_format = MONEY
    ws.cell(tr, 6, f"=IFERROR(E{tr}/B{tr},0)").number_format = "0.0%"
    for c in ws[tr][:6]:
        c.font, c.border = BOLD, Border(top=THIN)

    top = tr + 2
    ws.cell(top, 1, "Open invoices, most overdue first (chase list)").font = Font(name=F, bold=True, size=12)
    _header(ws, top + 1, ["Client", "Invoice", "Attorney", "Due date", "Days past due", "Balance due"])
    for k in range(1, 11):                                   # Data_Aged is sorted by days past due, largest first
        r = top + 1 + k
        for col, field, fmt in [(1, "customer_name", None), (2, "invoice_number", None), (3, "attorney", None),
                                (4, "due_date", date_fmt), (5, "days_past_due", "0"), (6, "balance_due", MONEY)]:
            c = ws.cell(r, col, f'=IFERROR(INDEX(tblAged[{field}],{k}),"")')
            c.font = BODY
            if fmt:
                c.number_format = fmt
    for i, w in enumerate([30, 20, 16, 14, 16, 18, 22], 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.row_dimensions[15].height = 30

    pq = wb.create_sheet("Power Query", 1)
    pq.sheet_view.showGridLines = False
    steps = ["Power Query: cross-system checks that refresh from the source systems",
             "Paste each script from integration/powerquery/github/ as its own query (4 queries, about 5 minutes, steps below):",
             "     01_Invoice_Sync_Check.pq      LEAP invoices vs MYOB invoices (expect 472 Matched)",
             "     02_Migration_Check.pq         LEAP active matters vs triConvey dry run (expect 140 Migrated, 1 Not migrated, 1 Duplicated)",
             "     03_Trust_Migration_Check.pq   trust balances LEAP vs triConvey (expect 1 difference: Global Trust Bank -5,799.21)",
             "     04_Disbursements_By_Matter.pq InfoTrack + PEXA fees per LEAP matter (expect 439 matters)",
             "They read the simulated MYOB / LEAP / triConvey / InfoTrack / PEXA JSON from the public GitHub repo, so Refresh All works anywhere.",
             "",
             "How the Data_* tabs refresh with Power Query",
             "1. Data > Get Data > From Other Sources > Blank Query, then Home > Advanced Editor.",
             "2. Paste one script from integration/powerquery/:",
             "     01_marts_from_json_api.pq   reads a mart from the Marts JSON API (uvicorn integration.marts_api:app --port 8001)",
             "     02_myob_api_direct.pq        calls the MYOB API itself: OAuth token, headers, NextPageLink paging, nested records",
             "     03_marts_from_snowflake.pq   reads LAW_FIRM.MARTS views straight from Snowflake",
             "3. Close & Load To... > Existing table: load over the matching Data_* table (keep the table names tblAged, tblRevenue, tblCollections).",
             "4. Data > Refresh All. The Summary tab is formulas only, so it updates by itself and G8/G10 must read OK.",
             "Never store client secrets or passwords in the workbook: use Data > Get Data > Data Source Settings for credentials."]
    for i, s in enumerate(steps, 1):
        pq.cell(i, 1, s).font = Font(name=F, bold=(i == 1), size=12 if i == 1 else 10)
    pq.column_dimensions["A"].width = 130
    for sheet in (ws, pq):
        sheet.page_setup.orientation = "landscape"
        sheet.page_setup.fitToWidth, sheet.page_setup.fitToHeight = 1, 0
        sheet.sheet_properties.pageSetUpPr.fitToPage = True
    wb.save(out)
    return out


if __name__ == "__main__":
    print(build())
