// Query name: Staffing_From_Warehouse  (consolidation in Power Query, without SQL)
// Rebuilds support headcount and monthly payroll by office and department by merging three warehouse tables:
// fact_staffing (headcount) + dim_branch (office name) + dim_department (department and pay). Expected: 10 rows (teams with at least one person), 17 staff.
let
    Staffing    = Table.TransformColumnTypes(fnQueryResult("data/warehouse", "fact_staffing"),
                      {{"branch_key", Int64.Type}, {"department_key", Int64.Type}, {"headcount", Int64.Type}}),
    Branches    = Table.TransformColumnTypes(Table.SelectColumns(fnQueryResult("data/warehouse", "dim_branch"), {"branch_key", "branch_name"}),
                      {{"branch_key", Int64.Type}}),
    Departments = Table.TransformColumnTypes(Table.SelectColumns(fnQueryResult("data/warehouse", "dim_department"), {"department_key", "department", "monthly_pay"}),
                      {{"department_key", Int64.Type}, {"monthly_pay", Currency.Type}}, "en-AU"),
    WithOffice  = Table.ExpandTableColumn(Table.NestedJoin(Staffing, {"branch_key"}, Branches, {"branch_key"}, "B", JoinKind.LeftOuter), "B", {"branch_name"}, {"Office"}),
    WithDept    = Table.ExpandTableColumn(Table.NestedJoin(WithOffice, {"department_key"}, Departments, {"department_key"}, "D", JoinKind.LeftOuter),
                      "D", {"department", "monthly_pay"}, {"Department", "Monthly pay"}),
    Staffed     = Table.SelectRows(WithDept, each [headcount] > 0),
    Payroll     = Table.AddColumn(Staffed, "Monthly payroll", each [headcount] * [Monthly pay], Currency.Type),
    Result      = Table.Sort(Table.SelectColumns(Payroll, {"Office", "Department", "headcount", "Monthly pay", "Monthly payroll"}),
                      {{"Office", Order.Ascending}, {"Department", Order.Ascending}})
in
    Result
