// Query name: Trust_Migration_Check
// Trust balance per client, LEAP vs triConvey. Expected: one difference (Global Trust Bank, -5,799.21).
let
    Base     = "https://raw.githubusercontent.com/brianphu2310/Law_Firm_Operations_Intelliigence/main/integration/data/",
    Get      = (path as text) => Json.Document(Web.Contents(Base, [RelativePath = path])),
    Leap     = Table.FromRecords(Get("leap/trust_balances.json"), {"clientName", "balance"}, MissingField.UseNull),
    Tc       = Table.FromRecords(Get("triconvey/trust_balances.json"), {"contactName", "balance"}, MissingField.UseNull),
    Joined   = Table.NestedJoin(Leap, {"clientName"}, Tc, {"contactName"}, "TC", JoinKind.FullOuter),
    Expanded = Table.ExpandTableColumn(Joined, "TC", {"balance"}, {"triConvey Balance"}),
    Renamed  = Table.RenameColumns(Expanded, {{"clientName", "Client"}, {"balance", "LEAP Balance"}}),
    Diff     = Table.AddColumn(Renamed, "Difference", each (if [triConvey Balance] = null then 0 else [triConvey Balance]) -
                                                       (if [LEAP Balance] = null then 0 else [LEAP Balance]), Currency.Type),
    Result   = Table.AddColumn(Diff, "Result", each if Number.Abs([Difference]) < 0.005 then "Matched" else "Difference", type text),
    Typed    = Table.TransformColumnTypes(Result, {{"LEAP Balance", Currency.Type}, {"triConvey Balance", Currency.Type}})
in
    Typed
