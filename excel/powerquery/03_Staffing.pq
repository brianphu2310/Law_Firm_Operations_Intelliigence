// Query name: Staffing  ->  load to the "Staffing" sheet as table tblStaffing
// Support staff against workload by office and department (sql/analysis/12_support_staffing.sql).
let
    Source = fnQueryResult("docs/query_results", "12_support_staffing"),
    Typed  = Table.TransformColumnTypes(Source, {
                 {"office", type text}, {"department", type text}, {"headcount", Int64.Type}, {"workload_12m", type number}, {"roles_needed", type number},
                 {"gap", type number}, {"status", type text}, {"gap_cost_a_year", Currency.Type}, {"pct_of_support_staff", type number}}, "en-AU")
in
    Typed
