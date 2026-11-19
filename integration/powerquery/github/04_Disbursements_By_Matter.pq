// Query name: Disbursements_By_Matter
// Search fees from BOTH suppliers (InfoTrack, then TriSearch) + PEXA workspace fees per matter (ex GST). Expected: 439 matters, about $213,752 in total.
let
    Base     = "https://raw.githubusercontent.com/brianphu2310/Law_Firm_Operations_Intelliigence/main/integration/data/",
    Get      = (path as text) => Json.Document(Web.Contents(Base, [RelativePath = path])),
    Key      = (ref as nullable text) as text => Text.Upper(Text.Select(ref ?? "", {"A".."Z", "a".."z", "0".."9"})),     // 'm20250413' = 'M-2025-0413'
    Leap     = Table.FromRecords(Get("leap/matters.json"), {"matterNumber", "clientName", "practiceArea", "status"}, MissingField.UseNull),
    TcNew    = Table.SelectRows(Table.FromRecords(Get("triconvey/matters.json"), {"number", "clientName", "matterType", "origin"}, MissingField.UseNull),
                                each [origin] = "Created in triConvey"),
    TcRows   = Table.AddColumn(Table.RenameColumns(Table.SelectColumns(TcNew, {"number", "clientName", "matterType"}), {{"number", "matterNumber"}}),
                               "practiceArea", each [matterType][category], type text),
    Matters  = Table.Combine({Leap, TcRows}),
    InfoT    = Table.FromRecords(Get("infotrack/orders.json"), {"clientReference", "totalFeeExGst"}, MissingField.UseNull),
    TriS     = Table.RenameColumns(Table.FromRecords(Get("trisearch/orders.json"), {"reference", "feeExGst"}, MissingField.UseNull),
                                   {{"reference", "clientReference"}, {"feeExGst", "totalFeeExGst"}}),
    Orders   = Table.AddColumn(Table.Combine({InfoT, TriS}), "RefKey", each Key([clientReference]), type text),
    MatterK  = Table.AddColumn(Matters, "RefKey", each Key([matterNumber]), type text),
    Searches = Table.Group(Orders, {"RefKey"}, {{"Searches", each Table.RowCount(_), Int64.Type},
                                                        {"Search Fees", each List.Sum([totalFeeExGst]), Currency.Type}}),
    Pexa     = Table.FromRecords(Get("pexa/workspaces.json"), {"subscriberReference", "pexaFee"}, MissingField.UseNull),
    Settle   = Table.Group(Pexa, {"subscriberReference"}, {{"PEXA Workspaces", each Table.RowCount(_), Int64.Type},
                                                         {"PEXA Fees", each List.Sum([pexaFee]), Currency.Type}}),
    J1       = Table.NestedJoin(MatterK, {"RefKey"}, Searches, {"RefKey"}, "IT", JoinKind.LeftOuter),
    E1       = Table.ExpandTableColumn(J1, "IT", {"Searches", "Search Fees"}),
    J2       = Table.NestedJoin(E1, {"matterNumber"}, Settle, {"subscriberReference"}, "PX", JoinKind.LeftOuter),
    E2       = Table.ExpandTableColumn(J2, "PX", {"PEXA Workspaces", "PEXA Fees"}),
    WithAny  = Table.SelectRows(E2, each [Searches] <> null or [PEXA Workspaces] <> null),
    Zeroed   = Table.ReplaceValue(WithAny, null, 0, Replacer.ReplaceValue, {"Searches", "Search Fees", "PEXA Workspaces", "PEXA Fees"}),
    Total    = Table.AddColumn(Zeroed, "Total Disbursements", each [Search Fees] + [PEXA Fees], Currency.Type),
    Sorted   = Table.Sort(Total, {{"Total Disbursements", Order.Descending}})
in
    Sorted
