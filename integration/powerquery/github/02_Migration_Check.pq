// Query name: Migration_Check
// LEAP active matters vs the triConvey migration dry run. Expected: 140 Migrated, 1 Not migrated, 1 Duplicated.
let
    Base     = "https://raw.githubusercontent.com/brianphu2310/Law_Firm_Operations_Intelliigence/main/integration/data/",
    Get      = (path as text) => Json.Document(Web.Contents(Base, [RelativePath = path])),
    Leap     = Table.FromRecords(Get("leap/matters.json"), {"matterNumber", "matterDescription", "clientName", "practiceArea", "status"}, MissingField.UseNull),
    Active   = Table.SelectRows(Leap, each List.Contains({"Open", "On Hold"}, [status])),
    Tc       = Table.FromRecords(Get("triconvey/matters.json"), {"number"}, MissingField.UseNull),
    TcCopies = Table.Group(Tc, {"number"}, {{"Copies", each Table.RowCount(_), Int64.Type}}),
    Joined   = Table.NestedJoin(Active, {"matterNumber"}, TcCopies, {"number"}, "TC", JoinKind.FullOuter),
    Expanded = Table.ExpandTableColumn(Joined, "TC", {"number", "Copies"}, {"triConvey Number", "triConvey Copies"}),
    Outcome  = Table.AddColumn(Expanded, "Outcome", each
                   if [matterNumber] = null then "Unexpected in triConvey"
                   else if [triConvey Copies] = null then "Not migrated"
                   else if [triConvey Copies] > 1 then "Duplicated"
                   else "Migrated", type text),
    Sorted   = Table.Sort(Outcome, {{"Outcome", Order.Descending}, {"matterNumber", Order.Ascending}})
in
    Sorted
