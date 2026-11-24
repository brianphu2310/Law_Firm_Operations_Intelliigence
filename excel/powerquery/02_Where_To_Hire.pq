// Query name: Where_to_hire  ->  load to the "Where_to_hire" sheet as table tblHire
// Demand, pressure and margin by practice area (sql/analysis/11_where_to_hire.sql).
let
    Source = fnQueryResult("docs/query_results", "11_where_to_hire"),
    Typed  = Table.TransformColumnTypes(Source, {
                 {"practice_area", type text}, {"matters_opened_12m", Int64.Type}, {"matters_growth_pct", type number}, {"billable_hours_12m", type number},
                 {"lawyers", Int64.Type}, {"lawyer_utilisation_pct", type number}, {"effective_rate", Currency.Type}, {"fees_12m", Currency.Type},
                 {"margin_pct", type number}, {"priority_score", type number}, {"priority_rank", Int64.Type}, {"verdict", type text}}, "en-AU"),
    Sorted = Table.Sort(Typed, {{"priority_rank", Order.Ascending}})
in
    Sorted
