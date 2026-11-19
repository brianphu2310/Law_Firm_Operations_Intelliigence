// Query name: Invoice_Sync_Check
// Practice-management invoices (LEAP until the final collection, triConvey after go-live) vs MYOB invoices, from the simulated JSON.
// Excel: Data > Get Data > From Other Sources > Blank Query > Advanced Editor > paste > Done > rename > Close & Load.
// Refresh All re-downloads the sources. Expected: 472 rows (457 LEAP + 15 triConvey), all "Matched".
let
    Base     = "https://raw.githubusercontent.com/brianphu2310/Law_Firm_Operations_Intelliigence/main/integration/data/",
    Get      = (path as text) => Json.Document(Web.Contents(Base, [RelativePath = path])),
    Cols     = {"invoiceNumber", "matterNumber", "clientName", "issueDate", "total"},
    Leap     = Table.FromRecords(Get("leap/invoices.json"), Cols, MissingField.UseNull),
    TcAll    = Table.FromRecords(Get("triconvey/invoices.json"), Cols & {"origin"}, MissingField.UseNull),
    TcNew    = Table.RemoveColumns(Table.SelectRows(TcAll, each [origin] = "Created in triConvey"), {"origin"}),   // migrated ones are LEAP invoices already
    Pms      = Table.Combine({Leap, TcNew}),
    MyobAll  = Table.FromRecords(Get("invoices.json"), {"Number", "TotalAmount", "Status"}, MissingField.UseNull),
    Joined   = Table.NestedJoin(Pms, {"invoiceNumber"}, MyobAll, {"Number"}, "MYOB", JoinKind.FullOuter),
    Expanded = Table.ExpandTableColumn(Joined, "MYOB", {"Number", "TotalAmount", "Status"}, {"MYOB Number", "MYOB Total", "MYOB Status"}),
    Result   = Table.AddColumn(Expanded, "Result", each
                   if [MYOB Number] = null then "Missing in MYOB"
                   else if [invoiceNumber] = null then "Missing in practice management"
                   else if Number.Round([total], 2) <> Number.Round([MYOB Total], 2) then "Amount differs"
                   else "Matched", type text),
    Renamed  = Table.RenameColumns(Result, {{"invoiceNumber", "Invoice"}, {"matterNumber", "Matter"}, {"clientName", "Client"},
                                            {"issueDate", "Issued"}, {"total", "PMS Total"}}),
    Typed    = Table.TransformColumnTypes(Renamed, {{"Issued", type datetime}, {"PMS Total", Currency.Type}, {"MYOB Total", Currency.Type}})
in
    Typed
