// Query name: Marketing  ->  load to the "Marketing" sheet as table tblMarketing
// Spend, inquiries, new matters and cost per matter by channel (sql/analysis/13_marketing_channels.sql).
let
    Source = fnQueryResult("docs/query_results", "13_marketing_channels"),
    Typed  = Table.TransformColumnTypes(Source, {
                 {"channel", type text}, {"spend_12m", Currency.Type}, {"inquiries_12m", type number}, {"new_matters_12m", type number},
                 {"conversion_pct", type number}, {"cost_per_inquiry", Currency.Type}, {"cost_per_new_matter", Currency.Type},
                 {"fees_from_new_matters", Currency.Type}, {"cost_rank", Int64.Type}, {"action", type text}}, "en-AU")
in
    Typed
