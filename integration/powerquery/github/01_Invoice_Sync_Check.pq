// Query name: Invoice_Sync_Check
// LEAP invoices vs MYOB invoices, live from the simulated source JSON in the public GitHub repo.
// Excel: Data > Get Data > From Other Sources > Blank Query > Advanced Editor > paste > Done > rename > Close & Load.
// Refresh All re-downloads the sources. Expected: 472 rows, all "Matched".
let
    Base     = "https://raw.githubusercontent.com/brianphu2310/Law_Firm_Operations_Intelliigence/main/integration/data/",
    Get      = (path as text) => Json.Document(Web.Contents(Base, [RelativePath = path])),
    Leap     = Table.FromRecords(Get("leap/invoices.json"), {"invoiceNumber", "matterNumber", "clientName", "issueDate", "total"}, MissingField.UseNull),
    MyobAll  = Table.FromRecords(Get("invoices.json"), {"Number", "TotalAmount", "Status"}, MissingField.UseNull),
    Joined   = Table.NestedJoin(Leap, {"invoiceNumber"}, MyobAll, {"Number"}, "MYOB", JoinKind.FullOuter),
    Expanded = Table.ExpandTableColumn(Joined, "MYOB", {"Number", "TotalAmount", "Status"}, {"MYOB Number", "MYOB Total", "MYOB Status"}),
    Result   = Table.AddColumn(Expanded, "Result", each
                   if [MYOB Number] = null then "Missing in MYOB"
                   else if [invoiceNumber] = null then "Missing in LEAP"
                   else if Number.Round([total], 2) <> Number.Round([MYOB Total], 2) then "Amount differs"
                   else "Matched", type text),
    Renamed  = Table.RenameColumns(Result, {{"invoiceNumber", "Invoice"}, {"matterNumber", "Matter"}, {"clientName", "Client"},
                                            {"issueDate", "Issued"}, {"total", "LEAP Total"}}),
    Typed    = Table.TransformColumnTypes(Renamed, {{"Issued", type datetime}, {"LEAP Total", Currency.Type}, {"MYOB Total", Currency.Type}})
in
    Typed
