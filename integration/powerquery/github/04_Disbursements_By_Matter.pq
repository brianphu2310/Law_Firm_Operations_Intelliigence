// Query name: Disbursements_By_Matter
// InfoTrack search fees + PEXA workspace fees per LEAP matter (ex GST). Expected: 439 matters, about $214,203 in total.
let
    Base     = "https://raw.githubusercontent.com/brianphu2310/Law_Firm_Operations_Intelliigence/main/integration/data/",
    Get      = (path as text) => Json.Document(Web.Contents(Base, [RelativePath = path])),
    Matters  = Table.FromRecords(Get("leap/matters.json"), {"matterNumber", "clientName", "practiceArea", "status"}, MissingField.UseNull),
    Orders   = Table.FromRecords(Get("infotrack/orders.json"), {"clientReference", "totalFeeExGst"}, MissingField.UseNull),
    Searches = Table.Group(Orders, {"clientReference"}, {{"Searches", each Table.RowCount(_), Int64.Type},
                                                        {"InfoTrack Fees", each List.Sum([totalFeeExGst]), Currency.Type}}),
    Pexa     = Table.FromRecords(Get("pexa/workspaces.json"), {"subscriberReference", "pexaFee"}, MissingField.UseNull),
    Settle   = Table.Group(Pexa, {"subscriberReference"}, {{"PEXA Workspaces", each Table.RowCount(_), Int64.Type},
                                                         {"PEXA Fees", each List.Sum([pexaFee]), Currency.Type}}),
    J1       = Table.NestedJoin(Matters, {"matterNumber"}, Searches, {"clientReference"}, "IT", JoinKind.LeftOuter),
    E1       = Table.ExpandTableColumn(J1, "IT", {"Searches", "InfoTrack Fees"}),
    J2       = Table.NestedJoin(E1, {"matterNumber"}, Settle, {"subscriberReference"}, "PX", JoinKind.LeftOuter),
    E2       = Table.ExpandTableColumn(J2, "PX", {"PEXA Workspaces", "PEXA Fees"}),
    WithAny  = Table.SelectRows(E2, each [Searches] <> null or [PEXA Workspaces] <> null),
    Zeroed   = Table.ReplaceValue(WithAny, null, 0, Replacer.ReplaceValue, {"Searches", "InfoTrack Fees", "PEXA Workspaces", "PEXA Fees"}),
    Total    = Table.AddColumn(Zeroed, "Total Disbursements", each [InfoTrack Fees] + [PEXA Fees], Currency.Type),
    Sorted   = Table.Sort(Total, {{"Total Disbursements", Order.Descending}})
in
    Sorted
